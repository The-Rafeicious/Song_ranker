"""V5.1 subjective-mode HTTP contracts used by gameplay and statistics pages."""
import secrets
import sqlite3

from flask import jsonify, request, session
from songranker.services import app, admin_required, get_db_connection
from songranker.modes.judgements import (MODES, JudgementError, get_offer, save_answer, mode_key)
from songranker.modes.vibe_map import MAPS, MAX_THEMES


@app.after_request
def judgement_response_headers(response):
    if request.endpoint in ('mode_updates_config','judgement_offer_api','judgement_answer_api','judgement_stats_api','judgement_selection_api'):
        response.headers['Cache-Control']='no-store'
    return response


def browser_owner(create=False):
    if create and not session.get('judgement_owner'):
        session['judgement_owner'] = secrets.token_urlsafe(32)
    return session.get('judgement_owner')


@app.route('/api/mode-updates')
def mode_updates_config():
    conn = get_db_connection()
    try:
        tags = [dict(r) for r in conn.execute('SELECT id,name,description FROM genres ORDER BY name COLLATE NOCASE,id')]
        paths={'spotlight':'shared_spotlight','vibe':'vibe_map'}
        return jsonify(rules_version=1,backend_only=False,modes=[dict(key=k,name=m.NAME,color=m.COLOR,
            songs=m.SONGS,rules_version=m.RULES_VERSION,subjective=True,play_url='/'+paths[k],stats_url='/'+paths[k]+'_stats') for k,m in MODES.items()],
            spotlight=dict(rules_version=2,points_per_song=12,max_round_points=24,coordinate_min=0,coordinate_max=100),
            vibe=dict(maps=MAPS,coordinate_min=0,coordinate_max=4,max_themes=MAX_THEMES,tags=tags),
            overall=dict(spotlight='Adaptive preference-family contribution',vibe='Descriptive coverage; no quality weight'))
    finally: conn.close()


@app.route('/api/<mode>/round', methods=['POST'])
def judgement_offer_api(mode):
    conn = None
    try:
        key = mode_key(mode)
        payload = request.get_json(silent=True)
        if not isinstance(payload,dict) or payload:
            raise JudgementError('Send an empty JSON object to request or resume a round.')
        conn = get_db_connection()
        return jsonify(get_offer(conn,browser_owner(True),key))
    except JudgementError as error:return jsonify(message=str(error)),error.status
    except sqlite3.OperationalError as error:
        if 'locked' not in str(error).lower():raise
        return jsonify(message='Database is busy. Retry the same request.'),503
    finally:
        if conn:conn.close()


@app.route('/api/<mode>/answer', methods=['POST'])
def judgement_answer_api(mode):
    conn = None
    try:
        key=mode_key(mode);conn=get_db_connection()
        return jsonify(save_answer(conn,browser_owner(),key,request.get_json(silent=True)))
    except JudgementError as error:return jsonify(message=str(error)),error.status
    except sqlite3.OperationalError as error:
        if 'locked' not in str(error).lower():raise
        return jsonify(message='Database is busy. Retry the same answer token.'),503
    finally:
        if conn:conn.close()


@app.route('/api/<mode>/stats')
def judgement_stats_api(mode):
    conn = None
    try:
        key=mode_key(mode)
        try:page=int(request.args.get('page','1'));size=int(request.args.get('page_size','20'))
        except ValueError:raise JudgementError('Use whole-number page parameters.') from None
        from songranker.reports.judgement_stats_data import build_judgement_stats
        conn=get_db_connection();conn.execute('BEGIN')
        try: response=jsonify(build_judgement_stats(conn,key,page=page,page_size=size))
        except ValueError as error:raise JudgementError(str(error)) from error
        response.headers['Cache-Control']='no-store';return response
    except JudgementError as error:return jsonify(message=str(error)),error.status
    finally:
        if conn:conn.close()


@app.route('/api/dev/mode-updates/selection/<mode>')
@admin_required
def judgement_selection_api(mode):
    conn=None
    try:
        from songranker.modes.judgement_selection import diagnostics
        key=mode_key(mode);conn=get_db_connection();conn.execute('BEGIN')
        return jsonify(diagnostics(conn,key))
    except JudgementError as error:return jsonify(message=str(error)),error.status
    finally:
        if conn:conn.close()
