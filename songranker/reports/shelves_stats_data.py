"""Read-only Shelves reporting. Saved shelf slots/numbers remain scoring facts."""
from songranker.reports.stats_activity import attach_reports
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import ceil, isclose

from songranker.catalog import proper_album
from songranker.modes.special_modes import (grade_shelf, shelf_pool)

PAGE_SIZE = 10


def percentage(right, total):
    return round(100*right/total, 1) if total else None


def saved_date(value):
    try:
        stamp = float(value)
        return dict(seconds=stamp, iso=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def integer(value, low=1, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def can_grade(items, rules):
    if rules != 1 or not 1 <= len(items) <= 10:
        return False
    slots = {i['album_slot'] for i in items}
    if not all(integer(i['item_slot'], high=10) and integer(i['album_slot'], high=3)
               and integer(i['track_number']) and i['answer_slot'] in slots
               and integer(i['answer_slot'], high=3) and integer(i['answer_position'], high=10) for i in items):
        return False
    def unique(keys):
        return len({tuple(i[k] for k in keys) for i in items}) == len(items)
    living_ids = [i['song_id'] for i in items if i['song_id'] is not None]
    return (unique(('item_slot',)) and unique(('album_slot','track_number'))
            and unique(('answer_slot','answer_position')) and len(set(living_ids)) == len(living_ids))


def empty_counts():
    return dict(graded_tracks=0, album_correct=0, order_right=0, order_pairs=0,
                points=0.0, available=0.0, fully_correct=0, wrong_album=0, order_affected=0)


def add_counts(target, source):
    for key in empty_counts():
        target[key] += source[key]


def item_counts(item):
    full = isclose(item['points'], item['available'], rel_tol=0, abs_tol=1e-8)
    return dict(graded_tracks=1, album_correct=item['album_correct'],
                order_right=item['order_right'], order_pairs=item['order_pairs'],
                points=item['points'], available=item['available'], fully_correct=int(full),
                wrong_album=int(not item['album_correct']), order_affected=int(item['album_correct'] and not full))


def finish_counts(row):
    row.update(order_accuracy=percentage(row['order_right'], row['order_pairs']),
               album_accuracy=percentage(row['album_correct'], row['graded_tracks']),
               order_wrong=row['order_pairs']-row['order_right'])
    return row


def window_totals(rows):
    rows = list(rows)
    result = empty_counts()
    known = [r for r in rows if r['graded']]
    for row in known:
        add_counts(result, row)
    result.update(rounds=len(rows), tracks=sum(r['tracks'] for r in rows), scored_rounds=len(known), unknown=len(rows)-len(known),
                  perfect=sum(r['outcome']=='perfect' for r in known),
                  average_points=sum(r['points'] for r in known)/len(known) if known else None)
    return finish_counts(result)


def page_number(value, pages):
    try:
        return max(1, min(int(value), pages))
    except (TypeError, ValueError, OverflowError):
        return 1


def build_shelves_stats(conn, now=None, history_page=1, album_page=1, selected=None):
    """Aggregate all completed rounds in the caller's snapshot; page only lists."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r['id']: dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums = {r['id']: dict(r) for r in conn.execute('SELECT * FROM albums')}
    tags = {r['id']: dict(r) for r in conn.execute('SELECT * FROM genres')}
    artist_links, tag_links = defaultdict(set), defaultdict(set)
    for r in conn.execute('SELECT song_id,artist_id FROM song_artists'):
        if r['artist_id'] in artists:
            artist_links[r['song_id']].add(r['artist_id'])
    for r in conn.execute('SELECT song_id,genre_id FROM song_genres'):
        if r['genre_id'] in tags:
            tag_links[r['song_id']].add(r['genre_id'])
    songs = {}
    album_artists = defaultdict(set)
    for raw in conn.execute('SELECT * FROM songs'):
        song = dict(raw)
        album = albums.get(song.get('album_id'), {})
        song.update(cover_url=album.get('cover_url') or '',
                    artist_links=sorted((artists[a] for a in artist_links[song['id']]),
                                        key=lambda a: (a['name'].casefold(), a['id'])),
                    album_link=album if proper_album(album) else None, attempts=0, **empty_counts())
        songs[song['id']] = song
        album_artists[song.get('album_id')].update(artist_links[song['id']])

    def album_identity(aid, slot=None):
        album = albums.get(aid)
        return dict(id=aid if album else None, title=album['title'] if album else 'Album unavailable',
                    cover_url=(album.get('cover_url') or '') if album else '',
                    linked=bool(album and proper_album(album)), album_link=None,
                    artist_links=sorted((artists[a] for a in album_artists.get(aid, ())),
                                        key=lambda a: (a['name'].casefold(), a['id'])) if album else [], slot=slot)

    rounds = {r['id']: dict(r, items=[], groups=[], **empty_counts()) for r in conn.execute(
        'SELECT id,completed_at,rules_version FROM album_shelf_rounds WHERE completed_at IS NOT NULL')}
    for raw in conn.execute('''SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r
                               ON r.id=i.round_id WHERE r.completed_at IS NOT NULL ORDER BY i.round_id,i.item_slot'''):
        rounds[raw['round_id']]['items'].append(dict(raw))
    album_totals = {}
    missing_album_slots = legacy_sizes = 0
    for row in rounds.values():
        items = row['items']
        row.update(date=saved_date(row['completed_at']), tracks=len(items),
                   album_count=len({i['album_slot'] for i in items}), graded=can_grade(items, row['rules_version']))
        legacy_sizes += len(items) != 10
        saved_groups = defaultdict(list)
        for item in items:
            saved_groups[item['album_slot']].append(item)
            aid = item['album_id']
            if aid in albums:
                target = album_totals.setdefault(aid, dict(album_identity(aid), name=albums[aid]['title'],
                                                          attempts=0, rounds_set=set(), songs_set=set(), **empty_counts()))
                target['attempts'] += 1
                target['rounds_set'].add(row['id'])
                if item['song_id'] in songs:
                    target['songs_set'].add(item['song_id'])
        if row['graded']:
            grade = grade_shelf(items)
            by_slot = {i['item_slot']: i for i in grade['items']}
            for item in items:
                graded = by_slot[item['item_slot']]
                item.update(graded)
                counts = item_counts(graded)
                add_counts(row, counts)
                if item['song_id'] in songs:
                    song = songs[item['song_id']]
                    song['attempts'] += 1
                    add_counts(song, counts)
                if item['album_id'] in album_totals:
                    add_counts(album_totals[item['album_id']], counts)
                item['outcome'] = 'correct' if counts['fully_correct'] else 'wrong_album' if counts['wrong_album'] else 'order_affected'
            row['outcome'] = 'perfect' if isclose(row['points'], row['available'], rel_tol=0, abs_tol=1e-8) else 'partial' if row['points'] else 'zero'
        else:
            row['outcome'] = 'unknown'
            for item in items:
                item.update(points=None, available=None, outcome='unknown', album_correct=None, order_right=None, order_pairs=None)
        finish_counts(row)
        slot_identities = {}
        for slot, saved in sorted(saved_groups.items(), key=lambda entry: str(entry[0])):
            ids = {i['album_id'] for i in saved if i['album_id'] is not None}
            identity = album_identity(next(iter(ids)) if len(ids)==1 else None, slot)
            slot_identities[slot] = identity
            missing_album_slots += identity['id'] is None
            group_counts = empty_counts()
            if row['graded']:
                for item in saved:
                    add_counts(group_counts, item_counts(item))
            group = dict(identity, items=sorted(saved, key=lambda i: (i['track_number'] if integer(i['track_number']) else float('inf'), str(i['item_slot']))),
                         graded=row['graded'], tracks=len(saved), **finish_counts(group_counts))
            row['groups'].append(group)
        for item in items:
            item.update(song=songs.get(item['song_id']),
                        answer_album=slot_identities.get(item['answer_slot']) or album_identity(None, item['answer_slot']),
                        saved_track=item['track_number'] if integer(item['track_number']) else None)

    ordered = sorted(rounds.values(), key=lambda r: ((r['date'] or {}).get('seconds', float('-inf')), r['id']))
    streak = best = 0
    for row in ordered:
        if row['date']:
            streak = streak+1 if row['outcome']=='perfect' else 0
            best = max(best, streak)
    summary = window_totals(ordered)
    summary.update(tracks=sum(r['tracks'] for r in ordered), albums_played=len(album_totals),
                   current_streak=streak if all(r['date'] for r in ordered) and
                   (not ordered or ordered[-1]['graded']) else None, best_streak=best,
                   active_days=len({r['date']['iso'][:10] for r in ordered if r['date'] and r['date']['seconds']<=now}),
                   undated=sum(r['date'] is None for r in ordered), legacy_sizes=legacy_sizes,
                   missing_album_slots=missing_album_slots)
    scored = [r for r in ordered if r['graded']]
    best_round = max(scored, key=lambda r: (r['points'], r['points']/r['available'], (r['date'] or {}).get('seconds', float('-inf')), r['id']), default=None)
    latest = list(reversed(ordered))
    windows = [dict(title='Latest 10 rounds', **window_totals(latest[:10]))]
    for days in (7, 30):
        windows.append(dict(title='Last '+str(days)+' days', **window_totals(r for r in ordered if r['date'] and now-days*86400<=r['date']['seconds']<=now)))
    outcomes = [dict(key=key, label=label, count=sum(r['outcome']==key for r in ordered),
                     share=percentage(sum(r['outcome']==key for r in ordered), len(ordered)))
                for key, label in (('perfect','Perfect rounds'),('partial','Partial credit'),('zero','No points'),('unknown','Unavailable'))
                if key!='unknown' or summary['unknown']]
    formats = [dict(key=size, label=label, **window_totals(r for r in ordered if (r['album_count']==size if size in (2,3) else r['album_count'] not in (2,3))))
               for size, label in ((2,'Two-album rounds'),(3,'Three-album rounds'),('other','Other saved formats'))
               if size!='other' or any(r['album_count'] not in (2,3) for r in ordered)]

    pool = shelf_pool(conn)
    playable = {aid for aid, tracks in pool.items() if any(
        len(pool)>=n and len(tracks)+sum(sorted((len(rows) for key, rows in pool.items() if key!=aid), reverse=True)[:n-1])>=10 for n in (2,3))}
    eligible_tracks = {s['id'] for aid in playable for s in pool[aid]}
    tested_tracks = {s['id'] for s in songs.values() if s['attempts']}
    tested_albums = {aid for aid, row in album_totals.items() if row['graded_tracks']}
    coverage = dict(albums=len(playable), albums_tested=len(playable & tested_albums),
                    albums_untested=len(playable-tested_albums), album_share=percentage(len(playable & tested_albums),len(playable)),
                    tracks=len(eligible_tracks), tracks_tested=len(eligible_tracks & tested_tracks),
                    tracks_untested=len(eligible_tracks-tested_tracks), track_share=percentage(len(eligible_tracks & tested_tracks),len(eligible_tracks)),
                    other_albums=len(tested_albums-playable), other_tracks=len(tested_tracks-eligible_tracks))
    tested = [finish_counts(s) for s in songs.values() if s['order_pairs']]
    def records(rows):
        rows = list(rows)
        return dict(best=sorted((r for r in rows if r['order_pairs']), key=lambda r: (-r['order_right']/r['order_pairs'], -r['order_pairs'], r['name'].casefold(),r['id']))[:5],
                    missed=sorted((r for r in rows if r['order_wrong']), key=lambda r: (-r['order_wrong'], -r['order_pairs'], r['name'].casefold(),r['id']))[:5])
    for album in album_totals.values():
        album.update(rounds=len(album.pop('rounds_set')), tested=len(album.pop('songs_set')))
        finish_counts(album)
    album_rows = sorted(album_totals.values(), key=lambda r: (-r['rounds'], -r['attempts'], r['name'].casefold(),r['id']))
    album_pages = max(1,ceil(len(album_rows)/PAGE_SIZE))
    album_page = page_number(album_page,album_pages)
    album_records = dict(records(r for r in album_rows if r['linked']), rows=album_rows[(album_page-1)*PAGE_SIZE:album_page*PAGE_SIZE],
                         page=album_page,pages=album_pages,total=len(album_rows))
    categories=[]
    for kind, title, identities, links in (('artist','Artist records',artists,artist_links),('tag','Tag records',tags,tag_links)):
        groups={}
        for song in tested:
            for identity in links[song['id']]:
                group=groups.setdefault(identity,dict(identities[identity],name=identities[identity]['name'],tested=0,attempts=0,**empty_counts()))
                group['tested']+=1;group['attempts']+=song['attempts'];add_counts(group,song)
        rows=[finish_counts(r) for r in groups.values()]
        categories.append(dict(kind=kind,title=title,**records(rows)))
    history_pages=max(1,ceil(len(latest)/PAGE_SIZE))
    history_page=page_number(history_page,history_pages)
    selected_row=next((r for r in latest if r['id']==selected),None)
    if selected_row:
        history_page=latest.index(selected_row)//PAGE_SIZE+1
    start=(history_page-1)*PAGE_SIZE
    return attach_reports(conn, dict(summary=summary,outcomes=outcomes,best_round=best_round,windows=windows,formats=formats,coverage=coverage,
                top_tracks=sorted(tested,key=lambda s:(-s['order_right']/s['order_pairs'],-s['order_pairs'],s['title'].casefold(),s['id']))[:10],
                practice_tracks=sorted((s for s in tested if s['order_wrong']),key=lambda s:(s['order_right']/s['order_pairs'],-s['order_pairs'],s['title'].casefold(),s['id']))[:10],
                album_records=album_records,categories=categories,history=latest[start:start+PAGE_SIZE],
                history_page=history_page,history_pages=history_pages,history_start=start+1 if latest else 0,
                history_end=min(start+PAGE_SIZE,len(latest)),selected_round=selected_row['id'] if selected_row else None,
                selection_missing=selected is not None and selected_row is None), 'shelves', now=now)
