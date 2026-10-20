"""V5.1.1 game shells and read-only, progressively detailed mode dashboards."""
from flask import abort, render_template, request

from songranker.services import app, get_db_connection
from songranker.modes.judgements import MODES
from songranker.modes.vibe_map import MAPS, MAX_THEMES
from songranker.reports.judgement_page_data import build_judgement_page

PATHS = {'spotlight': '/shared_spotlight', 'vibe': '/vibe_map'}


@app.route('/shared_spotlight', defaults={'mode': 'spotlight'})
@app.route('/vibe_map', defaults={'mode': 'vibe'})
def judgement_play(mode):
    tags = []
    if mode == 'vibe':
        conn = get_db_connection()
        try:
            tags = [dict(r) for r in conn.execute(
                'SELECT id,name,description FROM genres ORDER BY name COLLATE NOCASE,id')]
        finally:
            conn.close()
    response = app.make_response(render_template('judgement_game.html', mode=mode,
        mode_name=MODES[mode].NAME, stats_url=PATHS[mode]+'_stats',
        game_config=dict(mode=mode, maps=MAPS, tags=tags, max_themes=MAX_THEMES)))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/shared_spotlight_stats', defaults={'mode': 'spotlight'})
@app.route('/vibe_map_stats', defaults={'mode': 'vibe'})
def judgement_stats_page(mode):
    try:
        history_page = int(request.args.get('history_page', '1'))
        track_page = int(request.args.get('track_page', '1'))
        if history_page < 1 or track_page < 1:
            raise ValueError
    except ValueError:
        abort(400, 'Use positive whole-number page values.')
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        data = build_judgement_page(conn, mode, history_page=history_page,
            track_page=track_page, map_key=request.args.get('map', 'mood'),
            query=request.args.get('q', '')[:200])
        response = app.make_response(render_template('judgement_stats.html', **data,
            mode=mode, mode_name=MODES[mode].NAME, play_url=PATHS[mode],
            stats_url=PATHS[mode]+'_stats'))
        response.headers['Cache-Control'] = 'no-store'
        return response
    finally:
        conn.close()
