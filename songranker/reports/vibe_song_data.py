"""Read-only song inspector, reusable by dedicated song profile panels."""
from flask import render_template
from songranker.catalog import proper_album
from songranker.modes.vibe_map import profile, similar_songs
from songranker.modes.preferences import snapshot_song
from songranker.services import get_song_full


def build_song_vibe(conn, song_id, *, show_identity=True):
    saved = profile(conn, song_id)  # Validate first; missing songs return the mode's 404.
    comparison = similar_songs(conn, song_id, limit=2)
    song = snapshot_song(conn, get_song_full(song_id, conn))
    for item in [song] + [match['song'] for match in comparison['matches']]:
        item['album_link'] = (dict(title=item['album'], id=item['album_id'])
                              if proper_album(dict(title=item['album'])) else None)
    # Public profile coordinates are -5..5; readiness uses the radar's validated slots.
    profile_ready = all(spoke['radius'] is not None for spoke in saved['radar']['spokes'])
    data = dict(profile_ready=profile_ready, song=song, profile=saved, matches=comparison['matches'],
                total_comparable=comparison['total_comparable'], map_count=comparison['map_count'])
    return dict(data, html=render_template('vibe_song_stats_panel.html', show_identity=show_identity, **data))
