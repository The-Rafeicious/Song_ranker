"""Presentation projections only: no schema, saved ratings or judgement changes."""
from collections import defaultdict
import math

from songranker.catalog import proper_album
from songranker.reports.judgement_stats_data import build_judgement_stats
from songranker.reports.tournament_stats_data import saved_time


def song_catalogue(conn):
    artists = defaultdict(list)
    for row in conn.execute('''SELECT sa.song_id,a.id,a.name FROM song_artists sa
                              JOIN artists a ON a.id=sa.artist_id ORDER BY a.name COLLATE NOCASE,a.id'''):
        artists[row['song_id']].append(dict(id=row['id'], name=row['name']))
    songs = {}
    for raw in conn.execute('''SELECT s.id,s.title,a.id album_id,a.title album,a.cover_url
                              FROM songs s LEFT JOIN albums a ON a.id=s.album_id'''):
        row = dict(raw)
        row.update(artist_links=artists[row['id']], album_link=(dict(id=row['album_id'],
            title=row['album']) if proper_album({'title': row['album']}) else None))
        songs[row['id']] = row
    return songs


def build_judgement_page(conn, mode, *, history_page=1, track_page=1, map_key='mood', query=''):
    data = build_judgement_stats(conn, mode, page=history_page, page_size=10)
    songs = song_catalogue(conn)
    details = data['details']
    for row in data['history']:
        row['date'] = saved_time(row['closed_at'])
        for song in row['songs']:
            song.update(songs.get(song['id'], dict(artist_links=[], album_link=None)))

    if mode == 'spotlight':
        from songranker.reports.spotlight_dashboard_data import enrich_spotlight
        enrich_spotlight(conn, data, songs)
        counts = dict(conn.execute('''SELECT a.points,COUNT(*) FROM spotlight_allocations a
            JOIN judgement_rounds r ON r.id=a.round_id WHERE r.status='answered' GROUP BY a.points'''))
        peak = max(counts.values(), default=0)
        details['distribution'] = [dict(points=p, count=counts.get(p, 0),
            height=100*counts.get(p, 0)/peak if peak else 0) for p in range(13)]
    elif mode == 'vibe':
        for table in details['maps']:
            table['peak'] = max((max(r) for r in table['heatmap']), default=0)
            for row in table['songs']:
                row['song'] = songs[row['song_id']]
        selected = next((m for m in details['maps'] if m['key'] == map_key), details['maps'][0])
        rows = selected['songs']
        query = query.strip()
        if query:
            text = query.casefold()
            rows = [r for r in rows if text in (' '.join([r['song']['title']] +
                [a['name'] for a in r['song']['artist_links']] +
                [r['song']['album'] or ''])).casefold()]
        pages = max(1, math.ceil(len(rows)/20))
        track_page = min(track_page, pages)
        data.update(selected_map=selected, track_rows=rows[(track_page-1)*20:track_page*20],
            track_total=len(rows), track_page=track_page, track_pages=pages, query=query)
        details['placements'] = sum(m['placements'] for m in details['maps'])
        current_tags = dict(conn.execute('SELECT id,name FROM genres'))
        for row in details['themes']:
            row['current_name'] = current_tags.get(row['tag_id'])
    return data
