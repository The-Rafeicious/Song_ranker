"""Read-only library cards and collection consistency rankings; no pair matrix."""
from collections import defaultdict
from flask import render_template
from songranker.catalog import proper_album
from songranker.modes.vibe_similarity import positions
from songranker.reports.vibe_stats_data import consistency, density, colour_points, percentage
from songranker.storage.vibe_state import MAPS
from songranker.vibe_maps import map_definitions, song_profiles, pass_counts

CATEGORIES = {'albums': ('albums','title'), 'artists': ('artists','name'), 'tags': ('genres','name')}


def library_data(conn):
    songs = {r['id']: dict(r) for r in conn.execute('SELECT id,title,album_id FROM songs ORDER BY id')}
    profiles = song_profiles(conn, songs)
    vectors = {sid: positions({'vibe_maps': p}) for sid,p in profiles.items()}
    full = [v for v in vectors.values() if len(v)==len(MAPS)]
    selected = sum(any(p['status']!='unmapped' for p in profile.values()) for profile in profiles.values())
    score = consistency(full)
    summary = dict(total=len(songs),full=len(full),partial=selected-len(full),selected=selected,
        consistency=round(score,1) if score is not None else None,
        positions=sum(map(len,vectors.values())),passes=sum(pass_counts(conn,songs).values()),
        coverage=percentage(selected,len(songs)))
    rankings = {}
    for category,(table,name) in CATEGORIES.items():
        cover = ",cover_url" if category!='tags' else ",'' AS cover_url"
        entities = {r['id']:dict(r) for r in conn.execute(f'SELECT id,{name} AS name{cover} FROM {table} ORDER BY id')}
        members = defaultdict(set)
        if category=='albums':
            for sid,s in songs.items():members[s['album_id']].add(sid)
        else:
            link,col=('song_artists','artist_id') if category=='artists' else ('song_genres','genre_id')
            for r in conn.execute(f'SELECT song_id,{col} AS entity_id FROM {link}'):
                if r['song_id'] in songs:members[r['entity_id']].add(r['song_id'])
        rows=[]
        for eid,entity in entities.items():
            if category=='albums' and not proper_album(dict(title=entity['name'])):continue
            ids=members[eid];mapped=[vectors[sid] for sid in sorted(ids) if len(vectors[sid])==len(MAPS)]
            if len(mapped)<2:continue
            raw=consistency(mapped)
            if category=='albums':entity['title']=entity['name']
            rows.append(dict(entity,mapped=len(mapped),total=len(ids),song_count=len(ids),coverage=percentage(len(mapped),len(ids)),consistency=round(raw,1),_score=raw))
        rows.sort(key=lambda r:(-r['_score'],-r['mapped'],-r['coverage'],r['id']))
        for rank,row in enumerate(rows,1):row.pop('_score');row['rank']=rank
        rankings[category]=rows
    return summary,songs,vectors,rankings


def build_library_vibe(conn):
    summary,songs,vectors,rankings=library_data(conn)
    maps=map_definitions(conn)
    for m in maps:
        points=[dict(song_id=sid,title=songs[sid]['title'],x=v[m['id']][0],y=v[m['id']][1]) for sid,v in vectors.items() if m['id'] in v]
        m.update(points=points,count=len(points),max_nearby=density(points))
    maximum=max((m['max_nearby'] for m in maps),default=0)
    for m in maps:colour_points(m['points'],maximum)
    data=dict(summary=summary,maps=maps)
    leaders={category:rows[0] if rows else None for category,rows in rankings.items()}
    counts={category:len(rows) for category,rows in rankings.items()}
    return dict(profile_ready=summary['full']>=2,**data,
        html=render_template('vibe_entity_stats_panel.html',**data),
        global_html=render_template('vibe_global_stats_panel.html',**data,leaders=leaders,counts=counts),
        banner={category:rows[:20] for category,rows in rankings.items()},counts=counts)


def build_vibe_rankings(conn,category,view):
    from songranker.modes.vibe_map import VibeError
    if category not in CATEGORIES:raise VibeError('Choose albums, artists or tags.')
    if view not in ('top','bottom'):raise VibeError('Choose top or bottom.')
    _,_,_,rankings=library_data(conn)
    rows=rankings[category]
    return dict(entity=category,view=view,total=len(rows),limit=20,
                items=(rows if view=='top' else list(reversed(rows)))[:20])
