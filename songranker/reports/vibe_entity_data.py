"""Compact, scoped Vibe Map cards using the dashboard's existing measures."""
from flask import render_template
from songranker.modes.vibe_map import VibeError
from songranker.modes.vibe_similarity import positions
from songranker.reports.vibe_stats_data import consistency, density, colour_points
from songranker.storage.vibe_state import MAPS
from songranker.vibe_maps import map_definitions, song_profiles


def build_entity_vibe(conn, kind, entity_id):
    tables = {'album': ('albums', 'title'), 'artist': ('artists', 'name'), 'tag': ('genres', 'name')}
    if kind not in tables:
        raise VibeError('Choose album, artist or tag.')
    if type(entity_id) is not int or not 0 < entity_id < 2**63:
        raise VibeError('A positive entity ID is required.')
    table, name_column = tables[kind]
    entity = conn.execute(f'SELECT id,{name_column} AS name FROM {table} WHERE id=?', (entity_id,)).fetchone()
    if entity is None:
        raise VibeError('This collection no longer exists.', 'missing_entity', 404)
    if kind == 'album':
        where = 's.album_id=?'
    else:
        link, column = ('song_artists', 'artist_id') if kind == 'artist' else ('song_genres', 'genre_id')
        where = f'EXISTS(SELECT 1 FROM {link} link WHERE link.song_id=s.id AND link.{column}=?)'
    songs = {r['id']: dict(r) for r in conn.execute(
        f'SELECT s.id,s.title FROM songs s WHERE {where} ORDER BY s.id', (entity_id,))}
    profiles = song_profiles(conn, songs)
    vectors = {sid: positions({'vibe_maps': profile}) for sid, profile in profiles.items()}
    full = [v for v in vectors.values() if len(v) == len(MAPS)]
    selected = sum(any(p['status'] != 'unmapped' for p in profile.values()) for profile in profiles.values())
    score = consistency(full)
    summary = dict(total=len(songs), full=len(full), partial=selected-len(full),
                   consistency=round(score, 1) if score is not None else None)
    maps = map_definitions(conn)
    for definition in maps:
        key = definition['id']
        points = [dict(song_id=sid, title=songs[sid]['title'], x=v[key][0], y=v[key][1])
                  for sid, v in vectors.items() if key in v]
        definition.update(points=points, count=len(points), max_nearby=density(points))
    maximum = max((m['max_nearby'] for m in maps), default=0)
    for definition in maps:
        colour_points(definition['points'], maximum)
    data = dict(profile_ready=len(full)>=2, kind=kind, entity=dict(entity), summary=summary, maps=maps)
    return dict(data, html=render_template('vibe_entity_stats_panel.html', **data))
