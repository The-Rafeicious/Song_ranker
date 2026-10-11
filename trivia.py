"""Field-by-field trivia: one persisted round, with summaries derived by a view."""
import time
import uuid
import random
from urllib.parse import quote
from flask import request, session, jsonify, render_template
from services import app, get_db_connection, get_song_full, is_close_match
from catalog import proper_album
from selection import exposure_weight

FIELDS = ('title', 'artist', 'album')
WEIGHTS = {'title': .5, 'artist': .2, 'album': .3}


def elapsed(row, now=None):
    if row['started_at'] is None:
        return 0
    end = row['paused_at'] or (time.time() if now is None else now)
    return max(0, min(30, end - row['started_at'] - row['paused_seconds']))


def round_points(row):
    denominator = 1 if row['album_available'] else .7
    return round(sum(WEIGHTS[f] / denominator * (.75 + .25 * (1 - min(30, max(0, row[f+'_seconds'] or 0))/30))
                     for f in FIELDS if row[f+'_correct'] == 1), 4)


def score_state(conn):
    keys = dict(conn.execute("SELECT key,value FROM global_stats WHERE key IN ('trivia_high_score','trivia_high_streak','trivia_legacy_high_score')"))
    if session.get('trivia_scoring_version') != 2:
        session.update(trivia_score=0, trivia_streak=0, trivia_scoring_version=2)
    return {'score': session.get('trivia_score', 0), 'streak': session.get('trivia_streak', 0),
            'high_score': keys.get('trivia_high_score', 0), 'high_streak': keys.get('trivia_high_streak', 0)}


def current(conn, token):
    if token != session.get('trivia_round_token'):
        return None
    return conn.execute('SELECT * FROM trivia_rounds WHERE token=?', (token,)).fetchone()


def actual_answers(conn, song):
    artists = [r['name'] for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?', (song['id'],))]
    return {'title': song['title'], 'artist': song['artist'] or '', 'album': song['album'] or ''}, artists


def grade(conn, row, field, guess, song, seconds):
    if row[field+'_correct'] is not None or field == 'album' and not row['album_available']:
        return
    answers, artists = actual_answers(conn, song)
    correct = is_close_match(str(guess or ''), answers[field])
    if field == 'artist':
        correct = correct or any(is_close_match(str(guess or ''), artist) for artist in artists)
    conn.execute(f'UPDATE trivia_rounds SET {field}_correct=?,{field}_seconds=? WHERE id=?',
                 (int(correct), min(30, max(0, seconds)), row['id']))


def payload(conn, row, reveal=False):
    song = get_song_full(row['song_id'], conn)
    state = score_state(conn)
    result = {**state, 'token': row['token'], 'song_id': row['song_id'], 'audio_url': song['audio_url'],
              'album_available': bool(row['album_available']), 'started': row['started_at'] is not None,
              'paused': row['paused_at'] is not None, 'elapsed': elapsed(row),
              'completed': row['completed_at'] is not None, 'round_points': round_points(row),
              'fields': {f: {'correct': None if row[f+'_correct'] is None else bool(row[f+'_correct']),
                            'actual': song[f] if row[f+'_correct'] is not None or reveal else None}
                         for f in FIELDS if f != 'album' or row['album_available']}}
    for field, answer in result['fields'].items():
        if answer['actual'] is None:
            answer['links']=[]
        elif field=='title':
            answer['links']=[{'name':song['title'],'url':f"/song/{song['id']}"}]
        elif field=='album':
            answer['links']=[{'name':song['album'],'url':'/album/'+quote(song['album'],safe='')}]
        else:
            answer['links']=[{'name':r['name'],'url':'/artist/'+quote(r['name'],safe='')} for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?',(song['id'],))]
    if row['completed_at'] is not None:
        result.update(score=row['user_score_after'], streak=row['streak_after'],
                      game_over=row['streak_after'] == 0, cover_url=song['cover_url'],
                      actual_title=song['title'], actual_artist=song['artist'], actual_album=song['album'])
    return result


@app.route('/trivia')
def trivia_mode():
    return render_template('trivia_mode.html')


@app.route('/api/trivia/round', methods=['GET'])
def api_trivia_round():
    conn = get_db_connection()
    try:
        score_state(conn)
        old = current(conn, session.get('trivia_round_token'))
        if old and old['completed_at'] is None and old['song_id'] is not None:
            return jsonify(payload(conn, old))
        pool = conn.execute("SELECT s.id,COALESCE(ts.attempts,0) attempts FROM songs s LEFT JOIN trivia_stats ts ON ts.song_id=s.id WHERE COALESCE(s.audio_url,'')!=''").fetchall()
        if not pool:
            return jsonify(message='Add songs with audio previews to play Trivia.'), 400
        previous = old['song_id'] if old else None
        candidates = [s for s in pool if s['id'] != previous] or pool
        selected = random.choices(candidates, weights=[exposure_weight(s['attempts']) for s in candidates], k=1)[0]
        song = get_song_full(selected['id'], conn)
        token = uuid.uuid4().hex
        available = proper_album({'title': song['album']})
        conn.execute('INSERT INTO trivia_rounds(token,song_id,album_available) VALUES(?,?,?)', (token,song['id'],int(available)))
        conn.commit()
        session['trivia_round_token'] = token
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/start', methods=['POST'])
def api_trivia_start(token):
    conn = get_db_connection()
    try:
        row = current(conn, token)
        if not row:
            return jsonify(message='Round not found.'), 404
        if row['completed_at'] is not None:
            return jsonify(message='Round already completed.'), 409
        conn.execute('UPDATE trivia_rounds SET started_at=COALESCE(started_at,?) WHERE id=?', (time.time(),row['id']))
        conn.commit()
        return jsonify(payload(conn,current(conn,token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/pause', methods=['POST'])
def api_trivia_pause(token):
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = current(conn,token)
        if not row or row['started_at'] is None or row['completed_at'] is not None:
            return jsonify(message='No active round.'), 409
        pause = bool((request.get_json(silent=True) or {}).get('paused', True))
        now=time.time()
        if pause and row['paused_at'] is None:
            conn.execute('UPDATE trivia_rounds SET paused_at=? WHERE id=?',(now,row['id']))
        elif not pause and row['paused_at'] is not None:
            conn.execute('UPDATE trivia_rounds SET paused_seconds=paused_seconds+?,paused_at=NULL WHERE id=?',(now-row['paused_at'],row['id']))
        conn.commit()
        return jsonify(payload(conn,current(conn,token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/field', methods=['POST'])
def api_trivia_field(token):
    data=request.get_json(silent=True) or {}
    field=data.get('field')
    if field not in FIELDS:
        return jsonify(message='Choose a trivia field.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=current(conn,token)
        if not row or row['started_at'] is None:
            return jsonify(message='Start the round first.'),409
        if field=='album' and not row['album_available']:
            return jsonify(message='This round has no album guess.'),400
        if row['completed_at'] is None and row[field+'_correct'] is None:
            if row['paused_at'] is not None:
                return jsonify(message='Resume the round first.'),409
            if not str(data.get('guess','')).strip():
                return jsonify(message='Enter a guess first.'),400
            grade(conn,row,field,data.get('guess'),get_song_full(row['song_id'],conn),elapsed(row))
            conn.commit()
        return jsonify(payload(conn,current(conn,token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/finish', methods=['POST'])
def api_trivia_finish(token):
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=current(conn,token)
        if not row or row['started_at'] is None:
            return jsonify(message='No active round.'),409
        if row['completed_at'] is not None:
            return jsonify(payload(conn,row,True))
        data=request.get_json(silent=True) or {}
        song=get_song_full(row['song_id'],conn)
        for field in FIELDS:
            grade(conn,row,field,(data.get('guesses') or {}).get(field,''),song,elapsed(row))
        row=current(conn,token)
        points=round_points(row)
        any_correct=any(row[f+'_correct']==1 for f in FIELDS)
        state=score_state(conn)
        final_score=round(float(state['score'])+points,4)
        streak=int(state['streak'])+1 if any_correct else 0
        conn.execute('UPDATE trivia_rounds SET completed_at=?,paused_at=NULL,user_score_after=?,streak_after=? WHERE id=?', (time.time(),final_score,streak,row['id']))
        for key,value in [('trivia_high_score',final_score),('trivia_high_streak',streak)]:
            conn.execute('INSERT INTO global_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)',(key,value))
        conn.commit()
        session['trivia_score']=final_score if any_correct else 0
        session['trivia_streak']=streak
        return jsonify(payload(conn,current(conn,token),True))
    finally:
        conn.close()


def edit_trivia_totals(conn,song_id,data):
    """Sparse manual deltas preserve the detailed history instead of rewriting it."""
    totals=conn.execute('SELECT * FROM trivia_stats WHERE song_id=?',(song_id,)).fetchone()
    totals=dict(totals) if totals else {}
    names=['legacy_attempts','legacy_correct','new_attempts','title_correct','artist_correct','album_attempts','album_correct']
    if 'attempts' in data and 'legacy_attempts' not in data:
        data={**data,'legacy_attempts':int(data['attempts'])-totals.get('new_attempts',0),
              'legacy_correct':int(data.get('correct',0))-sum(totals.get(f+'_correct',0) for f in FIELDS)}
    values={name:int(data.get(name,totals.get(name,0))) for name in names}
    if any(v<0 for v in values.values()) or values['legacy_correct']>2*values['legacy_attempts'] or any(values[f+'_correct']>values['new_attempts'] for f in ('title','artist')) or values['album_attempts']>values['new_attempts'] or values['album_correct']>values['album_attempts']:
        raise ValueError('Correct counts cannot exceed the available field attempts.')
    raw=conn.execute('''SELECT COUNT(*) new_attempts,COALESCE(SUM(title_correct),0) title_correct,
        COALESCE(SUM(artist_correct),0) artist_correct,COALESCE(SUM(album_available),0) album_attempts,
        COALESCE(SUM(album_correct),0) album_correct FROM trivia_rounds WHERE song_id=? AND completed_at IS NOT NULL''',(song_id,)).fetchone()
    delta_names=['new_attempts','title_correct','artist_correct','album_attempts','album_correct']
    params=[song_id,values['legacy_attempts'],values['legacy_correct']]+[values[n]-raw[n] for n in delta_names]
    conn.execute('''INSERT INTO trivia_legacy(song_id,attempts,correct,new_attempts_delta,title_correct_delta,artist_correct_delta,album_attempts_delta,album_correct_delta)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(song_id) DO UPDATE SET attempts=excluded.attempts,correct=excluded.correct,
        new_attempts_delta=excluded.new_attempts_delta,title_correct_delta=excluded.title_correct_delta,
        artist_correct_delta=excluded.artist_correct_delta,album_attempts_delta=excluded.album_attempts_delta,album_correct_delta=excluded.album_correct_delta''',params)
