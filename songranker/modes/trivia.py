"""Field-by-field trivia: one persisted round, with summaries derived by a view."""
import time
import uuid
import re
import json
from urllib.parse import quote
from flask import request, session, jsonify, render_template
from songranker.services import (app, get_db_connection, get_song_full, is_close_match)
from songranker.catalog import proper_album
from songranker.modes.selection import choose_single
from songranker.modes.selection_data import mode_counts
from songranker.modes import challenges

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
    keys = dict(conn.execute("SELECT key,value FROM global_stats WHERE key IN ('trivia_high_score','trivia_high_streak')"))
    if session.get('trivia_scoring_version') != 2:
        session.update(trivia_score=0, trivia_streak=0, trivia_scoring_version=2)
    return {'score': session.get('trivia_score', 0), 'streak': session.get('trivia_streak', 0),
            'high_score': keys.get('trivia_high_score', 0), 'high_streak': keys.get('trivia_high_streak', 0)}


def current(conn, token):
    row = conn.execute('SELECT * FROM trivia_rounds WHERE token=?', (token,)).fetchone()
    if row and row['run_id'] is not None:
        return row if challenges.owns_round(conn, row, 'trivia') else None
    return row if token == session.get('trivia_round_token') else None


def round_song(conn, row):
    return json.loads(row['answer_snapshot']) if row['answer_snapshot'] else get_song_full(row['song_id'], conn)


def freeze_song(conn, song):
    facts = {key: song[key] for key in ('id','title','artist','album','album_id','audio_url','cover_url')}
    facts['artist_answers'] = [dict(r) for r in conn.execute('''SELECT a.id,a.name FROM artists a
        JOIN song_artists sa ON sa.artist_id=a.id WHERE sa.song_id=? ORDER BY a.id''', (song['id'],))]
    return json.dumps(facts, ensure_ascii=False, separators=(',', ':'))


def actual_answers(conn, song):
    artists = [r['name'] for r in song['artist_answers']] if 'artist_answers' in song else [r['name'] for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?', (song['id'],))]
    return {'title': song['title'], 'artist': song['artist'] or '', 'album': song['album'] or ''}, artists


def trivia_match(guess, actual, field):
    """Bracketed additions are optional; the meaningful base must still match."""
    if field not in ('title', 'album'):
        return is_close_match(guess, actual)
    def base(value):
        # Innermost groups first so nested credits/edition notes are safe.
        value = str(value or '')
        for _ in range(8):
            stripped = re.sub(r'\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}', ' ', value)
            if stripped == value:
                break
            value = stripped
        return ' '.join(value.split())
    canonical = base(actual)
    return is_close_match(base(guess), canonical) if canonical else is_close_match(guess, actual)


def grade(conn, row, field, guess, song, seconds):
    if row[field+'_correct'] is not None or field == 'album' and not row['album_available']:
        return
    answers, artists = actual_answers(conn, song)
    correct = trivia_match(str(guess or ''), answers[field], field)
    if field == 'artist':
        correct = correct or any(is_close_match(str(guess or ''), artist) for artist in artists)
    conn.execute(f'UPDATE trivia_rounds SET {field}_correct=?,{field}_seconds=? WHERE id=?',
                 (int(correct), min(30, max(0, seconds)), row['id']))


def payload(conn, row, reveal=False):
    song = round_song(conn, row)
    classic = score_state(conn)
    if row['rules_version'] == challenges.RULES_VERSION:
        state = challenges.progress(conn, row['run_id'], 'trivia')
        best = challenges.records(conn, 'trivia')
        state.update(high_score=best['best_score'], high_streak=best['best_streak'])
        requirement = challenges.TRIVIA_LABELS[row['streak_rule']]
    else:
        state = classic
        requirement = 'Classic round · any correct answer keeps the streak going.'
    result = {**state, 'token': row['token'], 'song_id': row['song_id'], 'audio_url': song['audio_url'],
              'rules_version': row['rules_version'], 'streak_before': row['streak_before'],
              'streak_rule': row['streak_rule'], 'streak_requirement': requirement,
              'classic_records': {'best_score': classic['high_score'], 'best_streak': classic['high_streak']},
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
            answer['links']=[{'name':song['title'],'url':f"/song/{song['id']}"}] if row['song_id'] is not None else []
        elif field=='album':
            album = conn.execute('SELECT title FROM albums WHERE id=?', (song['album_id'],)).fetchone()
            answer['links']=[{'name':song['album'],'url':'/album/'+quote(album['title'],safe='')}] if album else []
        else:
            answer['links']=[]
            if 'artist_answers' in song:
                for artist in song['artist_answers']:
                    live = conn.execute('SELECT name FROM artists WHERE id=?', (artist['id'],)).fetchone()
                    if live:
                        answer['links'].append({'name':artist['name'],'url':'/artist/'+quote(live['name'],safe='')})
            else:
                answer['links']=[{'name':r['name'],'url':'/artist/'+quote(r['name'],safe='')} for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?',(song['id'],))]
    if row['completed_at'] is not None:
        result.update(score=row['user_score_after'], streak=row['streak_after'],
                      game_over=row['streak_after'] == 0, cover_url=song['cover_url'],
                      streak_passed=bool(row['streak_passed']) if row['streak_passed'] is not None else row['streak_after'] != 0,
                      actual_title=song['title'], actual_artist=song['artist'], actual_album=song['album'])
    return result


@app.route('/trivia')
def trivia_mode():
    return render_template('trivia_mode.html')


@app.route('/api/trivia/round', methods=['GET'])
def api_trivia_round():
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        old = current(conn, session.get('trivia_round_token'))
        if old and old['rules_version'] == 1 and old['completed_at'] is None and old['song_id'] is not None:
            return jsonify(payload(conn, old))
        run = challenges.active_run(conn, 'trivia')
        pending = challenges.pending_round(conn, run, 'trivia')
        if pending:
            conn.commit()
            session['trivia_round_token'] = pending['token']
            return jsonify(payload(conn, pending))
        pool = conn.execute("SELECT s.id FROM songs s WHERE TRIM(COALESCE(s.audio_url,''))!='' ORDER BY s.id").fetchall()
        if not pool:
            return jsonify(message='Add songs with audio previews to play Trivia.'), 400
        last = conn.execute('SELECT song_id FROM trivia_rounds WHERE run_id=? ORDER BY id DESC LIMIT 1', (run['id'],)).fetchone()
        previous = last['song_id'] if last else old['song_id'] if old else None
        from songranker.modes.selection_data import with_catalogue_age
        pool=with_catalogue_age(conn,pool)
        selected = choose_single(pool, counts=mode_counts(conn, 'trivia'), previous=previous)
        song = get_song_full(selected['id'], conn)
        token = uuid.uuid4().hex
        available = proper_album({'title': song['album']})
        state = challenges.progress(conn, run['id'], 'trivia')
        conn.execute('''INSERT INTO trivia_rounds(token,song_id,album_available,run_id,rules_version,
            streak_before,streak_rule,answer_snapshot) VALUES(?,?,?,?,?,?,?,?)''',
            (token,song['id'],int(available),run['id'],challenges.RULES_VERSION,state['streak'],
             challenges.trivia_rule(state['streak'], available),freeze_song(conn, song)))
        conn.commit()
        session['trivia_round_token'] = token
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/start', methods=['POST'])
def api_trivia_start(token):
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
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
    data = request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('paused',True),bool):
        return jsonify(message='Choose whether to pause the round.'),400
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = current(conn,token)
        if not row or row['started_at'] is None or row['completed_at'] is not None:
            return jsonify(message='No active round.'), 409
        pause = data.get('paused', True)
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
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('guess',''),str):
        return jsonify(message='Enter a text guess.'),400
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
            grade(conn,row,field,data.get('guess'),round_song(conn,row),elapsed(row))
            conn.commit()
        return jsonify(payload(conn,current(conn,token)))
    finally:
        conn.close()


@app.route('/api/trivia/<token>/finish', methods=['POST'])
def api_trivia_finish(token):
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('guesses') or {},dict):
        return jsonify(message='Send the round guesses as fields.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=current(conn,token)
        if not row or row['started_at'] is None:
            return jsonify(message='No active round.'),409
        if row['completed_at'] is not None:
            return jsonify(payload(conn,row,True))
        if row['rules_version'] == challenges.RULES_VERSION and row['paused_at'] is not None:
            return jsonify(message='Resume the round first.'),409
        song=round_song(conn,row)
        for field in FIELDS:
            grade(conn,row,field,(data.get('guesses') or {}).get(field,''),song,elapsed(row))
        row=current(conn,token)
        points=round_points(row)
        classic = row['rules_version'] == 1
        passed = any(row[f+'_correct']==1 for f in FIELDS) if classic else challenges.trivia_passed(row)
        state=score_state(conn) if classic else challenges.progress(conn,row['run_id'],'trivia')
        final_score=round(float(state['score'])+points,4)
        streak=int(state['streak'])+1 if passed else 0
        now = time.time()
        conn.execute('UPDATE trivia_rounds SET completed_at=?,paused_at=NULL,user_score_after=?,streak_after=?,streak_passed=? WHERE id=?', (now,final_score,streak,int(passed),row['id']))
        if classic:
            for key,value in [('trivia_high_score',final_score),('trivia_high_streak',streak)]:
                conn.execute('INSERT INTO global_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)',(key,value))
        else:
            challenges.close_on_miss(conn,row['run_id'],passed,now)
        from songranker.listening import record as record_listening
        record_listening(conn,'trivia',row['id'],[row['song_id']],None,data.get('listening'))
        conn.commit()
        if classic:
            session['trivia_score']=final_score if passed else 0
            session['trivia_streak']=streak
        return jsonify(payload(conn,current(conn,token),True))
    finally:
        conn.close()


def edit_trivia_totals(conn,song_id,data):
    """Sparse manual deltas preserve the detailed history instead of rewriting it."""
    totals=conn.execute('SELECT * FROM trivia_stats WHERE song_id=?',(song_id,)).fetchone()
    totals=dict(totals) if totals else {}
    names=['new_attempts','title_correct','artist_correct','album_attempts','album_correct']
    if set(data)-set(names):
        raise ValueError('Use song, artist and album field counts; legacy totals are no longer supported.')
    values={name:int(data.get(name,totals.get(name,0))) for name in names}
    if any(v<0 for v in values.values()) or any(values[f+'_correct']>values['new_attempts'] for f in ('title','artist')) or values['album_attempts']>values['new_attempts'] or values['album_correct']>values['album_attempts']:
        raise ValueError('Correct counts cannot exceed the available field attempts.')
    raw=conn.execute('''SELECT COUNT(*) new_attempts,COALESCE(SUM(title_correct),0) title_correct,
        COALESCE(SUM(artist_correct),0) artist_correct,COALESCE(SUM(album_available),0) album_attempts,
        COALESCE(SUM(album_correct),0) album_correct FROM trivia_rounds WHERE song_id=? AND completed_at IS NOT NULL''',(song_id,)).fetchone()
    delta_names=['new_attempts','title_correct','artist_correct','album_attempts','album_correct']
    deltas=[values[n]-raw[n] for n in delta_names]
    if not any(deltas):
        conn.execute('DELETE FROM trivia_adjustments WHERE song_id=?',(song_id,))
        return
    conn.execute('''INSERT INTO trivia_adjustments(song_id,new_attempts_delta,title_correct_delta,artist_correct_delta,album_attempts_delta,album_correct_delta)
        VALUES(?,?,?,?,?,?) ON CONFLICT(song_id) DO UPDATE SET
        new_attempts_delta=excluded.new_attempts_delta,title_correct_delta=excluded.title_correct_delta,
        artist_correct_delta=excluded.artist_correct_delta,album_attempts_delta=excluded.album_attempts_delta,album_correct_delta=excluded.album_correct_delta''',[song_id]+deltas)
