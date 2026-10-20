"""Conservative, fill-only Apple metadata planning. No library import helpers.

Fill blank positions, album/song dates and schema-13 Apple source facts only.
Keep local artwork, names, placement, tags and previews. Release matching accepts
removed trailing Single/EP labels while retaining artist and exact-art checks.
"""
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import re
import json
from copy import deepcopy
import sqlite3
import time
import unicodedata

from songranker.apple_access import (apple_lookup, AppleRequestError)
from songranker.developer.track_numbers import (parse_track_number, check_track_position)
from songranker.developer.catalog_sources import (observation, current_sources, source_conflict, save_source, source_label)


class ScanStopped(Exception):
    pass


def normalized(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    text = text.translate(str.maketrans({'’': "'", '‘': "'", '–': '-', '—': '-'}))
    return ' '.join(text.split())



def release_key(value):
    """Only ignore Apple's format suffix, never Deluxe/Live/remaster editions."""
    return re.sub(r'\s*-\s*(?:single|ep)$', '', normalized(value)).strip()


def missing_source(source):
    if not source:return True
    keys=('track_id','collection_id','artist_id','storefront','title','artist','album',
          'track_url','album_url','release_date','duration_ms')
    return (any(blank(source.get(k)) for k in keys)
            or source.get('explicitness') not in ('explicit','cleaned','notExplicit')
            or any(blank(source.get('metadata',{}).get(k)) for k in
                   ('source_track_number','disc_number','disc_count')))


def merge_source(previous, fresh):
    """Append enriched observations; never replace an existing known source fact."""
    result=deepcopy(previous or {})
    for key,value in fresh.items():
        if key=='metadata':
            metadata=result.setdefault('metadata',{})
            for field,entry in value.items():
                if blank(metadata.get(field)) and not blank(entry):metadata[field]=entry
        elif key!='explicitness' and blank(result.get(key)) and not blank(value):result[key]=value
    flag=result.get('explicitness')
    if flag not in ('explicit','cleaned','notExplicit'):
        result['explicitness']=fresh['explicitness']
        result['explicitness_assumed']=fresh['explicitness']=='unknown'
    return result


def propose_song(plan,song,remote):
    if 'release_date' not in song:return  # Legacy helper databases have only the old fields.
    fresh=observation(remote,plan['country'])
    for key,remote_key in [('disc_number','discNumber'),('disc_count','discCount')]:
        fresh['metadata'][key]=remote.get(remote_key)
    if remote.get('discNumber')!=1 or remote.get('discCount')!=1:
        fresh['metadata']['track_number']=None
    previous=song.get('source')
    if previous and previous['track_id']!=fresh['track_id']:
        raise ValueError('The verified track differs from the saved Apple source; existing link kept.')
    if any(s['id']!=song['id'] and s.get('source',{}).get('track_id')==fresh['track_id']
           for s in plan['snapshot']['songs']):
        raise ValueError('This Apple track is already linked to another local song.')
    if any(r['id']!=song['id'] and r['source']['track_id']==fresh['track_id'] for r in plan['sources']):
        raise ValueError('More than one local song matches this Apple identity; review needed.')
    if blank(song['release_date']):
        try:value=release_date(remote.get('releaseDate'))
        except ValueError as error:
            plan['metadata_failures'].append(dict(id=song['id'],title=song['title'],reason=str(error)))
        else:plan['song_dates'].append(dict(id=song['id'],title=song['title'],value=value))
    merged=merge_source(previous,fresh)
    if merged!=previous:
        fields=[key for key in merged if not previous or merged[key]!=previous.get(key)]
        plan['sources'].append(dict(id=song['id'],title=song['title'],source=merged,fields=fields))


def artwork_key(url):
    """Require a full Apple artwork asset path; ignore CDN host and size only."""
    try:
        u = urlsplit(url or '')
        if u.scheme != 'https' or not (u.hostname or '').endswith('.mzstatic.com'):
            return None
        path = u.path
        if not re.search(r'/[0-9]+x[0-9]+[^/]*\.(?:jpg|png|webp)$', path, re.I):
            return None
        # /image/thumb/Music.../<unique asset>/SIZE.jpg -> same asset at all sizes.
        key = re.sub(r'/[0-9]+x[0-9]+[^/]*\.(?:jpg|png|webp)$', '', path, flags=re.I)
        return key if len(key) > 30 and '/Music' in key else None
    except (ValueError, TypeError):
        return None


def same_art(local, remote):
    key = artwork_key(local)
    return bool(key and key == artwork_key(remote))


def release_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T.*)?', value):
        raise ValueError('Missing or invalid Apple release date.')
    day = date.fromisoformat(value[:10])
    if not 1900 <= day.year <= date.today().year + 2:
        raise ValueError('Implausible Apple release date.')
    return day.isoformat()


def blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def snapshot(conn):
    """Only matching identity/targets: voting and trivia can continue during scans."""
    albums = [dict(r) for r in conn.execute('SELECT id,title,cover_url,release_date FROM albums ORDER BY id')]
    columns={r['name'] for r in conn.execute('PRAGMA table_info(songs)')}
    modern={'release_date','release_date_origin'}<=columns
    extra=',release_date,release_date_origin' if modern else ''
    songs = [dict(r) for r in conn.execute('SELECT id,title,album_id,audio_url,track_number'+extra+' FROM songs ORDER BY id')]
    sources=current_sources(conn) if modern else {}
    artists = {r['id']: r['name'] for r in conn.execute('SELECT id,name FROM artists')}
    links = [tuple(r) for r in conn.execute('SELECT song_id,artist_id FROM song_artists ORDER BY song_id,artist_id')]
    for song in songs:
        song['artists'] = [artists[a] for s,a in links if s == song['id'] and a in artists]
        if modern:song['source']=sources.get(song['id'],{}).get('source',{})
    return {'albums': albums, 'songs': songs}


def connection(filename, readonly=False):
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError('Database does not exist; no new database was created.')
    conn = sqlite3.connect(path.as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    required = {'songs': {'id','title','album_id','audio_url','track_number'},
                'albums': {'id','title','cover_url','release_date'}}
    for table, columns in required.items():
        if not columns <= {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}:
            conn.close()
            raise ValueError('Use the current relational Song Ranker database.')
    return conn


def paced_lookup(url, cancelled=lambda: False):
    while True:
        if cancelled():
            raise ScanStopped('Scan cancelled.')
        try:
            return apple_lookup(url)
        except AppleRequestError as error:
            # Local spacing/window limits are expected. Remote errors stop the
            # batch; do not repeatedly retry a refusal or Apple's HTTP 429.
            if error.state != 'throttled':
                raise ScanStopped(str(error)) from error
            until = time.monotonic() + max(1, error.retry_after)
            while time.monotonic() < until:
                if cancelled():
                    raise ScanStopped('Scan cancelled.')
                time.sleep(min(.25, max(0, until-time.monotonic())))


def plan_metadata(filename, country='gb', lookup=paced_lookup, progress=lambda *a: None,
                  cancelled=lambda: False):
    if not re.fullmatch('[a-zA-Z]{2}', country):
        raise ValueError('Country must be a two-letter store code.')
    conn = connection(filename, True)
    try:
        conn.execute('BEGIN')
        original = snapshot(conn)
    finally:
        conn.close()
    plan = {'snapshot': original, 'dates': [], 'tracks': [], 'track_failures': [],
            'country': country.lower(), 'stopped': '', 'applied': False, 'backup': None,
            'song_dates':[], 'sources':[], 'metadata_failures':[]}
    occupied = {(s['album_id'],s['track_number']) for s in original['songs'] if s['track_number'] is not None}
    stopped = ''
    for index, album in enumerate(original['albums']):
        local = [s for s in original['songs'] if s['album_id'] == album['id']]
        missing_tracks = [s for s in local if blank(s['track_number'])]
        need_date = blank(album['release_date'])
        missing_metadata=[s for s in local if 'release_date' in s and (blank(s['release_date']) or missing_source(s.get('source')))]
        single = normalized(album['title']).endswith(' - single')
        date_row = {'id': album['id'], 'title': album['title'], 'value': album['release_date'],
                    'status': 'kept', 'reason': 'Existing date preserved.'}
        plan['dates'].append(date_row)
        failures = {}
        proposals = []
        if single:
            for song in missing_tracks:
                if len(local) != 1 or (album['id'],1) in occupied:
                    failures[song['id']] = 'Single has multiple tracks or track 1 is occupied.'
                else:
                    proposals.append({'id': song['id'], 'title': song['title'], 'album_id':album['id'], 'value':1})
        try:
            if need_date or (missing_tracks and not single) or missing_metadata:
                if stopped or cancelled():
                    raise ScanStopped(stopped or 'Scan cancelled.')
                if not normalized(album['title']):
                    raise ValueError('Blank local album title; manual review needed.')
                if not local:
                    raise ValueError('No local tracks to verify this release.')
                if not artwork_key(album['cover_url']):
                    raise ValueError('Artwork cannot be verified as an Apple asset; manual review needed.')
                names = {normalized(n) for song in local for n in song['artists'] if normalized(n)}
                if not names:
                    raise ValueError('No local artist available for verification.')
                search_artist = next(n for song in local for n in song['artists'] if normalized(n))
                term = (local[0]['title'] if single else release_key(album['title'])) + ' ' + search_artist
                url = 'https://itunes.apple.com/search?' + urlencode({'term':term,'country':country.lower(),
                        'media':'music','entity':'song' if single else 'album','explicit':'Yes','limit':200})
                results = lookup(url).get('results', [])
                candidates = []
                for row in results:
                    if not isinstance(row, dict):
                        continue
                    title = row.get('trackName') if single else row.get('collectionName')
                    expected = local[0]['title'] if single else album['title']
                    if ((normalized(title) == normalized(expected) if single else release_key(title) == release_key(expected)) and normalized(row.get('artistName')) in names
                            and same_art(album['cover_url'], row.get('artworkUrl100'))
                            and isinstance(row.get('collectionId'), int) and not isinstance(row.get('collectionId'), bool) and row['collectionId'] > 0):
                        candidates.append(row)
                ids = {r['collectionId'] for r in candidates}
                if len(ids) != 1:
                    raise ValueError('No unique title / artist / artwork match; manual review needed.')
                collection_id = next(iter(ids))
                data = lookup('https://itunes.apple.com/lookup?' + urlencode({'id':collection_id,
                              'country':country.lower(),'entity':'song','limit':200})).get('results', [])
                data = [r for r in data if isinstance(r, dict)]
                releases = [r for r in data if r.get('wrapperType') == 'collection' and r.get('collectionId') == collection_id
                            and same_art(album['cover_url'], r.get('artworkUrl100'))
                            and normalized(r.get('artistName')) in names
                            and (single or release_key(r.get('collectionName')) == release_key(album['title']))]
                if len(releases) != 1:
                    raise ValueError('Album lookup identity is missing or ambiguous.')
                source = releases[0]
                remote_tracks = [r for r in data if r.get('wrapperType') == 'track' and r.get('kind') == 'song'
                                 and r.get('collectionId') == collection_id]
                def matches(song):
                    return [r for r in remote_tracks if normalized(song['title']) and normalized(r.get('trackName')) == normalized(song['title'])
                            and normalized(r.get('artistName')) in {normalized(n) for n in song['artists']}
                            and normalized(r.get('collectionName')) == normalized(source.get('collectionName'))
                            and same_art(album['cover_url'],r.get('artworkUrl100'))
                            and (not song.get('source') or str(r.get('trackId'))==song['source']['track_id'])]
                # The release date is from the verified collection wrapper,
                # never guessed from the first song's original release date.
                if not any(len(matches(s)) == 1 for s in local):
                    raise ValueError('No uniquely verified local track in the album lookup.')
                if need_date:
                    try:
                        date_row.update(value=release_date(source.get('releaseDate')),status='proposed',
                                        reason='Verified Apple collection ' + str(collection_id) + ': ' + str(source.get('collectionName')))
                    except ValueError as error:
                        date_row.update(value=None,status='failed',reason=str(error))
                for song in missing_metadata:
                    try:
                        matched=matches(song)
                        if len(matched)!=1:raise ValueError('Track title / artist / artwork / source match is missing or ambiguous.')
                        propose_song(plan,song,matched[0])
                    except ValueError as error:
                        plan['metadata_failures'].append(dict(id=song['id'],title=song['title'],reason=str(error)))
                if not single:
                    for song in missing_tracks:
                        matched = matches(song)
                        try:
                            if len(matched) != 1:
                                raise ValueError('Track title / artist / artwork match is missing or ambiguous.')
                            row = matched[0]
                            if type(row.get('discCount')) is not int or row['discCount'] != 1 or type(row.get('discNumber')) is not int or row['discNumber'] != 1:
                                raise ValueError('Multi-disc or missing disc metadata; no position guessed.')
                            number = parse_track_number(row.get('trackNumber'))
                            count = parse_track_number(row.get('trackCount'))
                            if number is None or count is None or number > count:
                                raise ValueError('Invalid or missing Apple track position / count.')
                            proposals.append({'id':song['id'],'title':song['title'],'album_id':album['id'],'value':number})
                        except ValueError as error:
                            failures[song['id']] = str(error)
        except (ValueError, ScanStopped) as error:
            if isinstance(error, ScanStopped):
                stopped = str(error)
                plan['stopped'] = stopped
            if need_date:
                date_row.update(value=None,status='failed',reason=str(error))
            for song in missing_metadata:
                plan['metadata_failures'].append(dict(id=song['id'],title=song['title'],reason=str(error)))
            if not single:
                for song in missing_tracks:
                    failures[song['id']] = str(error)
        counts = Counter(p['value'] for p in proposals)
        for proposal in proposals:
            if counts[proposal['value']] > 1 or (album['id'],proposal['value']) in occupied:
                failures[proposal['id']] = 'Track position is duplicated or already occupied locally.'
            else:
                plan['tracks'].append(proposal)
                occupied.add((album['id'],proposal['value']))
        for song in missing_tracks:
            if song['id'] in failures:
                plan['track_failures'].append({'id':song['id'],'title':song['title'],'album':album['title'],
                                               'reason':failures[song['id']]})
        progress(index+1, len(original['albums']), album['title'])
    for song in original['songs']:
        if song['album_id'] not in {a['id'] for a in original['albums']} and 'release_date' in song and (blank(song['release_date']) or missing_source(song.get('source'))):
            plan['metadata_failures'].append(dict(id=song['id'],title=song['title'],reason='No linked album to verify; local links kept.'))
        if song['album_id'] not in {a['id'] for a in original['albums']} and blank(song['track_number']):
            plan['track_failures'].append({'id':song['id'],'title':song['title'],'album':'No album',
                                           'reason':'Missing or unlinked album; track position cannot be verified.'})
    return plan


def apply_plan(filename, plan):
    """Recheck identity and blanks under a write lock. All updates are atomic."""
    if plan['applied']:
        raise ValueError('This scan has already been applied.')
    conn = connection(filename)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if snapshot(conn) != plan['snapshot']:
            raise ValueError('Library metadata changed since the scan. Scan again; nothing was written.')
        for track in plan['tracks']:
            number = parse_track_number(track['value'])
            if number is None:
                raise ValueError('A proposed track position is blank.')
            check_track_position(conn, track['album_id'], number, track['id'])
        for row in plan.get('sources',[]):
            conflict=source_conflict(conn,row['id'],row['source'])
            if conflict:raise ValueError('An Apple identity is already linked to another song. Scan again.')
        for track in plan['tracks']:
            conn.execute('UPDATE songs SET track_number=? WHERE id=? AND (track_number IS NULL OR TRIM(track_number)=\'\')',
                         (track['value'],track['id']))
        for row in plan['dates']:
            if row['status'] == 'proposed':
                value = release_date(row['value'])
                conn.execute("UPDATE albums SET release_date=? WHERE id=? AND (release_date IS NULL OR TRIM(release_date)='')",
                             (value,row['id']))
        for row in plan.get('song_dates',[]):
            value=release_date(row['value'])
            conn.execute("UPDATE songs SET release_date=?,release_date_origin='apple' WHERE id=? AND (release_date IS NULL OR TRIM(release_date)='')",(value,row['id']))
        for row in plan.get('sources',[]):
            save_source(conn,row['id'],dict(source=row['source'],observed_at=time.time()))
        conn.commit()
        plan['applied'] = True
        plan['backup'] = None  # Routine edits do not create backups.
        for row in plan['dates']:
            if row['status'] == 'proposed':
                row['status'] = 'filled'
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return plan


def text_report(plan):
    lines = ['SONG RANKER — METADATA FILL',
             'Applied' if plan['applied'] else 'Dry run — no metadata written',
             'Track numbers ' + ('filled: ' if plan['applied'] else 'proposed: ') + str(len(plan['tracks'])),
             'Track failures: ' + str(len(plan['track_failures']))]
    lines += ['Song release dates: '+str(len(plan.get('song_dates',[]))),
              'Apple source updates: '+str(len(plan.get('sources',[]))),
              'Song metadata failures: '+str(len(plan.get('metadata_failures',[])))]
    if plan['backup']:
        lines.append('Backup: '+plan['backup'])
    if plan['stopped']:
        lines.append('Search stopped: '+plan['stopped'])
    lines += ['', 'RELEASE DATES — every album']
    for row in plan['dates']:
        lines.append(f"[{row['status'].upper()}] Album #{row['id']} {row['title']} | {row['value'] or 'blank'} | {row['reason']}")
    lines += ['', 'TRACK NUMBER FAILURES ONLY']
    lines += [f"[FAILED] Song #{r['id']} {r['title']} | {r['album']} | {r['reason']}" for r in plan['track_failures']]
    if not plan['track_failures']:
        lines.append('None.')
    lines += ['', 'SONG RELEASE DATES']
    lines += [f"Song #{r['id']} {r['title']} | {r['value']} | Apple track date" for r in plan.get('song_dates',[])]
    lines += ['', 'APPLE SOURCE FACTS — local artwork, placement, tags and previews kept']
    lines += [f"Song #{r['id']} {r['title']} | Apple {r['source']['track_id']} | {source_label(r['source'])} | {', '.join(r['fields'])}" for r in plan.get('sources',[])]
    lines += ['', 'SONG METADATA FAILURES']
    lines += [f"Song #{r['id']} {r['title']} | {r['reason']}" for r in plan.get('metadata_failures',[])]
    return '\n'.join(lines)+'\n'

