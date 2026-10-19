"""Verified Apple observations and conservative catalogue matching; no lookup side effects."""
from datetime import date
import json
import hashlib
import math
import re
import secrets
import time
import unicodedata
from functools import lru_cache
from urllib.parse import urlsplit

from songranker.developer.track_numbers import parse_track_number
from songranker.storage.source_storage import pack_source,unpack_source

CONTENT_LABELS={'explicit':'Explicit','cleaned':'Cleaned','notExplicit':'Not explicit'}


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().split())


def identifier(value):
    text=str(value or '')
    return str(int(text)) if re.fullmatch(r'[0-9]{1,20}',text) and int(text)>0 else None


def store_code(value):
    if not isinstance(value,str) or not re.fullmatch('[a-zA-Z]{2}',value):
        raise ValueError('Choose a two-letter Apple store, such as gb or us.')
    return value.lower()


def store_link(value):
    if not isinstance(value,str):return ''
    try:
        parsed=urlsplit(value)
        if (parsed.scheme not in ('http','https') or parsed.hostname not in
            ('music.apple.com','www.music.apple.com','itunes.apple.com','www.itunes.apple.com')
            or parsed.username or parsed.password or parsed.port not in (None,80,443)):
            return ''
        return parsed._replace(scheme='https').geturl()
    except ValueError:return ''


def text(value):
    return value[:2000] if isinstance(value,str) else ''


def release_day(value):
    if not isinstance(value,str):return ''
    try:return date.fromisoformat(value[:10]).isoformat()
    except ValueError:return ''


def apple_metadata(track):
    """Keep advisory flags distinct from censored titles and radio-edit title hints."""
    try:
        discs=int(track.get('discCount') or 1);disc=int(track.get('discNumber') or 1)
        position=parse_track_number(track.get('trackNumber')) if discs==disc==1 else None
    except (ValueError,TypeError,OverflowError):position=None
    return dict(title=text(track.get('trackName')) or 'Unknown',artist=text(track.get('artistName')) or 'Unknown',
        album=text(track.get('collectionName')),cover_url=text(track.get('artworkUrl100')).replace('100x100bb','300x300bb'),
        audio_url=text(track.get('previewUrl')),track_number=position,release_date=release_day(track.get('releaseDate')),
        genres=text(track.get('primaryGenreName')),source_track_number=track.get('trackNumber'),
        disc_number=track.get('discNumber') or 1,disc_count=track.get('discCount') or 1)


def observation(track,country):
    track_id=identifier(track.get('trackId'))
    if not track_id:raise ValueError('Apple did not return a valid track identity. Use an exact song link.')
    duration=track.get('trackTimeMillis')
    duration=duration if type(duration) in (int,float) and math.isfinite(duration) and duration>0 else None
    explicitness=track.get('trackExplicitness')
    return dict(track_id=track_id,collection_id=identifier(track.get('collectionId')),artist_id=identifier(track.get('artistId')),
        storefront=store_code(country),title=text(track.get('trackName')),artist=text(track.get('artistName')),
        album=text(track.get('collectionName')),track_url=store_link(track.get('trackViewUrl')),
        album_url=store_link(track.get('collectionViewUrl')),explicitness=explicitness if isinstance(explicitness,str) and explicitness in CONTENT_LABELS else 'unknown',
        collection_explicitness=text(track.get('collectionExplicitness')),
        censored_title=text(track.get('trackCensoredName')),release_date=release_day(track.get('releaseDate')),
        duration_ms=duration,metadata=apple_metadata(track))


def source_label(source):
    return CONTENT_LABELS.get(source.get('explicitness'),'Not explicit')


def public_source(source):
    # Fill-only observations omit blank optional values; reads must accept them.
    return dict(track_id=source.get('track_id'),collection_id=source.get('collection_id'),storefront=source.get('storefront') or '',
        track_url=source.get('track_url') or '',album_url=source.get('album_url') or '',explicitness=source.get('explicitness') or 'unknown',
        content_label=source_label(source),content_assumed=source.get('explicitness') not in CONTENT_LABELS,release_date=source.get('release_date') or '',duration_ms=source.get('duration_ms'),
        radio_hint=bool(re.search(r'\bradio\s+(?:edit|version|mix)\b',source.get('title') or '',re.I)),
        original_album=source.get('album') or '')


def owner():
    from flask import session
    if not session.get('catalog_owner'):session['catalog_owner']=secrets.token_urlsafe(24)
    return session['catalog_owner']


def serializer():
    from itsdangerous import URLSafeTimedSerializer
    from songranker.services import app
    return URLSafeTimedSerializer(app.secret_key,salt='apple-source-offer-v1')


def offer(track,country):
    source=observation(track,country)
    token=serializer().dumps(dict(owner=owner(),source=source,observed_at=time.time()))
    return dict(source['metadata'],source=public_source(source),source_token=token)


def unpack(token):
    from itsdangerous import BadData
    if not isinstance(token,str) or len(token)>20000:raise ValueError('Choose an Apple search result.')
    try:data=serializer().loads(token,max_age=86400)
    except BadData as error:raise ValueError('This Apple result expired or changed. Search again.') from error
    if data.get('owner')!=owner():raise ValueError('Search Apple in this browser before saving a source.')
    return data


def current_sources(conn):
    return {r['song_id']:dict(r,source=unpack_source(r['snapshot'])) for r in conn.execute('''
        SELECT * FROM song_sources WHERE id IN (SELECT MAX(id) FROM song_sources GROUP BY song_id)''')}


def current_source(conn,song_id):
    row=conn.execute('SELECT * FROM song_sources WHERE song_id=? ORDER BY id DESC LIMIT 1',(song_id,)).fetchone()
    return dict(row,source=unpack_source(row['snapshot'])) if row else None


def artist_names(conn,value,known=None):
    """Prefer an existing whole name; split only a unique composition of known names."""
    known=[r[0] for r in conn.execute('SELECT name FROM artists ORDER BY id')] if known is None else known
    names={}
    for name in known:
        if normalized(name):names.setdefault(normalized(name),name)
    full=normalized(value)
    if full in names:return [names[full]]
    if not full:return []
    candidates=sorted(names,key=len,reverse=True)
    @lru_cache(maxsize=None)
    def split(start):
        answers=[]
        for name in candidates:
            if not full.startswith(name,start):continue
            end=start+len(name)
            if end==len(full):answers.append((names[name],))
            else:
                separator=re.match(r'(?:,\s*|\s*&\s*|\s+and\s+|\s+feat\.?\s+|\s+ft\.?\s+)',full[end:])
                if separator:
                    for tail in split(end+separator.end()):answers.append((names[name],)+tail)
            if len(answers)>1:return tuple(answers[:2])
        return tuple(answers)
    choices=split(0)
    return list(choices[0]) if len(choices)==1 else [value]


def source_conflict(conn,song_id,source,replacing=()):
    excluded=tuple(replacing)
    exclusion=(' AND s.song_id NOT IN ('+','.join('?' for _ in excluded)+')') if excluded else ''
    return conn.execute('''SELECT s.song_id FROM song_sources s
        WHERE s.provider='apple' AND s.external_id=? AND s.id=(SELECT MAX(t.id) FROM song_sources t WHERE t.song_id=s.song_id)
        AND (? IS NULL OR s.song_id!=?)'''+exclusion+' LIMIT 1',(source['track_id'],song_id,song_id,*excluded)).fetchone()


def save_source(conn,song_id,verified,*,replacing=()):
    source=verified['source'];conflict=source_conflict(conn,song_id,source,replacing)
    if conflict:raise ValueError(f"This Apple track is already linked to song #{conflict['song_id']}.")
    snapshot=pack_source(source)
    previous=current_source(conn,song_id)
    if previous and previous['source']==source:return previous['id']
    if previous:
        conn.execute('''UPDATE song_sources SET external_id=?,storefront=?,collection_id=?,snapshot=?,observed_at=? WHERE id=?''',
            (source['track_id'],source['storefront'],source.get('collection_id'),snapshot,verified['observed_at'],previous['id']))
        return previous['id']
    cursor=conn.execute('''INSERT INTO song_sources(song_id,external_id,storefront,collection_id,snapshot,observed_at)
        VALUES(?,?,?,?,?,?)''',(song_id,source['track_id'],source['storefront'],source.get('collection_id'),snapshot,verified['observed_at']))
    return cursor.lastrowid


def catalogue_matches(conn,results):
    """A matching title/artist is a review candidate, never a verified Apple identity."""
    songs=[dict(r) for r in conn.execute('SELECT s.id,s.title,a.title album FROM songs s LEFT JOIN albums a ON a.id=s.album_id')]
    names={s['id']:[] for s in songs}
    for row in conn.execute('SELECT sa.song_id,a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id ORDER BY a.id'):
        names[row['song_id']].append(row['name'])
    saved=current_sources(conn);by_title={};by_source={}
    all_names=[r[0] for r in conn.execute('SELECT name FROM artists ORDER BY id')]
    resolved={result['artist']:{normalized(n) for n in artist_names(conn,result['artist'],all_names)} for result in results}
    for song in songs:
        by_title.setdefault(normalized(song['title']),[]).append(song)
        source=saved.get(song['id'],{}).get('source',{})
        if source.get('track_id'):by_source.setdefault(source['track_id'],[]).append(song)
    for result in results:
        source=result['source'];matches={}
        for song in by_title.get(normalized(result['title']),[]):
            artist=normalized(result['artist'])
            if (artist in {normalized(n) for n in names[song['id']]}|{normalized(', '.join(names[song['id']]))}
                or resolved[result['artist']]=={normalized(n) for n in names[song['id']]}):
                matches[song['id']]=dict(song_id=song['id'],title=song['title'],album=song['album'],kind='title_artist')
        for song in by_source.get(source['track_id'],[]):
            matches[song['id']]=dict(song_id=song['id'],title=song['title'],album=song['album'],kind='source_id')
        result['library_matches']=list(matches.values())
    return results


def source_summaries(conn):
    sources=current_sources(conn);result={}
    for song in conn.execute('SELECT id,audio_url FROM songs'):
        saved=sources.get(song['id'])
        result[song['id']]=dict(status='linked' if saved else 'needs_link',
            source_id=saved['id'] if saved else None,content_label=source_label(saved['source']) if saved else 'Not explicit',
            source=public_source(saved['source']) if saved else None,
            preview_matches=bool(saved and (saved['source'].get('metadata') or {}).get('audio_url')
                                 and saved['source']['metadata']['audio_url']==song['audio_url']))
    return result


def review_fingerprint(conn,song_id):
    row=conn.execute('''SELECT s.id,s.title,s.album_id,s.audio_url,s.track_number,s.release_date,s.release_date_origin,
        a.title album,a.cover_url,a.release_date album_release_date FROM songs s LEFT JOIN albums a ON a.id=s.album_id
        WHERE s.id=?''',(song_id,)).fetchone()
    if not row:return None
    source=current_source(conn,song_id)
    facts=dict(row,source_id=source['id'] if source else None,source_revision=source['snapshot'] if source else None,
        artists=[list(r) for r in conn.execute('SELECT a.id,a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=? ORDER BY a.id',(song_id,))],
        tags=[list(r) for r in conn.execute('SELECT g.id,g.name FROM song_genres sg JOIN genres g ON g.id=sg.genre_id WHERE sg.song_id=? ORDER BY g.id',(song_id,))])
    return hashlib.sha256(json.dumps(facts,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
