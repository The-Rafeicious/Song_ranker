from flask import render_template, request, session, jsonify
import random

from services import app, get_db_connection, calculate_new_elo, is_close_match, get_song_full, get_matchup
@app.route('/game')
def index():
    return render_template('app_page.html', page='standard')


@app.route('/api/vote', methods=['POST'])
def api_vote():
    data = request.get_json(silent=True) or {}
    try:
        winner_id, loser_id = int(data['winner_id']), int(data['loser_id'])
    except (KeyError, ValueError, TypeError):
        return jsonify({'message':'Choose two valid songs.'}),400
    if winner_id == loser_id:
        return jsonify({'message':'Songs must be different.'}),400
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        winner, loser = get_song_full(winner_id,conn), get_song_full(loser_id,conn)
        if not winner or not loser: return jsonify({'message':'Song not found.'}),404
        new_w, new_l = calculate_new_elo(winner['elo_score'],loser['elo_score'])
        for song, value in [(winner,new_w),(loser,new_l)]:
            conn.execute('UPDATE songs SET elo_score=?, matches_played=matches_played+1, highest_elo=MAX(highest_elo,?) WHERE id=?',(value,value,song['id']))
        for song in (winner,loser):
            rank=conn.execute('SELECT COUNT(*)+1 FROM songs WHERE elo_score>(SELECT elo_score FROM songs WHERE id=?)',(song['id'],)).fetchone()[0]
            conn.execute('UPDATE songs SET highest_rank=MIN(highest_rank,?) WHERE id=?',(rank,song['id']))
        mode='blind' if data.get('mode')=='blind' else 'standard'
        conn.execute('INSERT INTO history (winner_id,loser_id,mode,created_at,winner_before,winner_after,loser_before,loser_after) VALUES (?,?,?,CURRENT_TIMESTAMP,?,?,?,?)',
                     (winner_id,loser_id,mode,winner['elo_score'],new_w,loser['elo_score'],new_l))
        conn.commit()
        def result(song,value):
            return {**dict(song),'elo_before':song['elo_score'],'elo_score':value,'elo_change':f"{value-song['elo_score']:+.0f}"}
        return jsonify(winner=result(winner,new_w),loser=result(loser,new_l))
    finally:
        conn.close()

@app.route('/api/matchup')
def api_matchup():
    blind=request.args.get('mode')=='blind'
    a,b=get_matchup(blind)
    if not a or not b: return jsonify({'message':'Add at least two songs with previews for blind voting.'}),400
    # Elo remains server-side until the vote is committed.
    return jsonify({'songs':[{k:v for k,v in dict(s).items() if k not in ('elo_score','highest_elo','highest_rank','matches_played')} for s in (a,b)]})


@app.route('/trivia')
def trivia_mode():
    conn = get_db_connection()
    high_score_row = conn.execute('SELECT value FROM global_stats WHERE key = "trivia_high_score"').fetchone()
    high_score = high_score_row['value'] if high_score_row else 0

    if 'trivia_score' not in session: session['trivia_score'] = 0
    if 'trivia_streak' not in session: session['trivia_streak'] = 0

    pool = conn.execute('''
                        SELECT s.id, s.audio_url, COALESCE(ts.attempts, 0) as trivia_attempts
                        FROM songs s
                                 LEFT JOIN trivia_stats ts ON s.id = ts.song_id
                        WHERE s.audio_url IS NOT NULL
                          AND s.audio_url != ""
                        ORDER BY trivia_attempts ASC, RANDOM()
                            LIMIT 30
                        ''').fetchall()
    conn.close()

    if not pool:
        return "No songs with audio previews available to play Trivia."

    song = random.choice(pool)
    return render_template('trivia_mode.html', song=song, score=session['trivia_score'],
                           streak=session['trivia_streak'], high_score=high_score)


@app.route('/api/trivia_guess', methods=['POST'])
def api_trivia_guess():
    data = request.json
    song_id = data['song_id']
    time_taken = float(data.get('time_taken', 30.0))
    timeout = data.get('timeout', False)

    conn = get_db_connection()
    song = get_song_full(song_id, conn)

    title_match = False if timeout else is_close_match(data.get('title_guess', ''), song['title'])
    artist_match = False if timeout else is_close_match(data.get('artist_guess', ''), song['artist'])

    correct_count = sum([title_match, artist_match])
    points = 0
    speed_bonus = 0
    game_over = False

    if correct_count > 0:
        points += (correct_count * 100)
        speed_bonus = max(0, int((1.0 - (time_taken / 30.0)) * 100))
        points += speed_bonus
        session['trivia_streak'] = session.get('trivia_streak', 0) + 1
        session['trivia_score'] = session.get('trivia_score', 0) + points
    else:
        game_over = True

    final_score = session.get('trivia_score', 0)
    high_score_row = conn.execute('SELECT value FROM global_stats WHERE key = "trivia_high_score"').fetchone()
    high_score = high_score_row['value'] if high_score_row else 0

    new_high_score = False
    if final_score > high_score:
        conn.execute('UPDATE global_stats SET value = ? WHERE key = "trivia_high_score"', (final_score,))
        high_score = final_score
        new_high_score = True

    if game_over:
        session['trivia_score'] = 0
        session['trivia_streak'] = 0

    cursor = conn.execute('UPDATE trivia_stats SET attempts = attempts + 1, correct = correct + ? WHERE song_id = ?',
                          (correct_count, song_id))
    if cursor.rowcount == 0:
        conn.execute('INSERT INTO trivia_stats (song_id, attempts, correct) VALUES (?, 1, ?)', (song_id, correct_count))


    conn.commit()
    conn.close()

    return jsonify({
        "actual_title": song['title'],
        "actual_artist": song['artist'],
        "cover_url": song['cover_url'],
        "points_earned": points,
        "speed_bonus": speed_bonus,
        "new_total": final_score,
        "title_correct": title_match,
        "artist_correct": artist_match,
        "game_over": game_over,
        "new_high_score": new_high_score,
        "high_score": high_score
    })


@app.route('/tournament')
def tournament():
    # Pass lists of artists and albums to the frontend so the user can select a specific scope
    conn = get_db_connection()
    artists = [dict(row) for row in
               conn.execute('SELECT id, name FROM artists ORDER BY name COLLATE NOCASE').fetchall()]
    albums = [dict(row) for row in conn.execute(
        'SELECT id, title FROM albums WHERE title != "Unknown Album" AND title NOT LIKE "% - Single" ORDER BY title COLLATE NOCASE').fetchall()]
    conn.close()

    return render_template('tournament.html', artists=artists, albums=albums)


@app.route('/api/generate_bracket')
def api_generate_bracket():
    size = request.args.get('size', 8, type=int)
    scope = request.args.get('scope', 'global')
    scope_id = request.args.get('scope_id', type=int)
    is_blind = request.args.get('is_blind', 'false').lower() == 'true'
    if size not in (8, 16, 32):
        return jsonify({'error': 'Tournament size must be 8, 16, or 32.'}), 400
    if scope not in ('global', 'artist', 'album'):
        return jsonify({'error': 'Invalid tournament scope.'}), 400
    if scope != 'global' and not scope_id:
        return jsonify({'error': 'An artist or album must be selected.'}), 400

    conn = get_db_connection()
    try:
        if scope == 'artist':
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s JOIN song_artists sa ON s.id = sa.song_id
                LEFT JOIN albums al ON s.album_id = al.id
                WHERE sa.artist_id = ? ORDER BY RANDOM() LIMIT ?'''
            params = (scope_id, size)
        elif scope == 'album':
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s LEFT JOIN albums al ON s.album_id = al.id
                WHERE s.album_id = ? ORDER BY RANDOM() LIMIT ?'''
            params = (scope_id, size)
        else:
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s LEFT JOIN albums al ON s.album_id = al.id
                ORDER BY RANDOM() LIMIT ?'''
            params = (size,)

        songs = [dict(row) for row in conn.execute(query, params).fetchall()]
        if len(songs) < size:
            return jsonify({'error': f'Not enough tracks found. Needed {size}, found {len(songs)}.'}), 400
        songs.sort(key=lambda song: song['elo_score'], reverse=True)

        cursor = conn.execute('''INSERT INTO tournaments
                    (size, scope_type, scope_id, status, created_at, updated_at, current_round, points_version, is_blind)
                    VALUES (?, ?, ?, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 1, ?)''',
                              (size, scope, scope_id, is_blind))
        tournament_id = cursor.lastrowid
        for seed, song in enumerate(songs, start=1):
            conn.execute('INSERT INTO tournament_entries (tournament_id, song_id, seed) VALUES (?, ?, ?)',
                         (tournament_id, song['id'], seed))
        # Mirror tournament.html's standard seeding order so persisted matches match the UI.
        seed_order = _tournament_seed_order(size)
        for i in range(0, size, 2):
            song1 = songs[seed_order[i]]
            song2 = songs[seed_order[i + 1]]
            conn.execute('''INSERT INTO tournament_matches
                (tournament_id, round_number, match_number, song1_id, song2_id)
                VALUES (?, 1, ?, ?, ?)''',
                (tournament_id, (i // 2) + 1, song1['id'], song2['id']))
        conn.commit()
        return jsonify({'tournament_id': tournament_id, 'tracks': songs,
                        'matches': _tournament_matches(conn, tournament_id)})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not create tournament')
        return jsonify({'error': 'Could not create tournament.'}), 500
    finally:
        conn.close()


def _tournament_seed_order(size):
    """Return zero-based track indexes in the same bracket seeding order as tournament.html."""
    bracket = [1]
    rounds = size.bit_length() - 1
    for r in range(rounds):
        seed_sum = (2 ** (r + 1)) + 1
        next_bracket = []
        for seed in bracket:
            next_bracket.extend((seed, seed_sum - seed))
        bracket = next_bracket
    return [seed - 1 for seed in bracket]


def _tournament_matches(conn, tournament_id):
    rows = conn.execute('''SELECT id, tournament_id, round_number, match_number,
        song1_id, song2_id, winner_id, loser_id, status, points_awarded, played_at
        FROM tournament_matches WHERE tournament_id = ?
        ORDER BY round_number, match_number''', (tournament_id,)).fetchall()
    return [dict(row) for row in rows]


def _round_points(size, round_number):
    # Normalize the maximum points for a champion to 7 across bracket sizes.
    return round(7 * (2 ** (round_number - 1)) / (size - 1), 4)


@app.route('/api/tournament_vote', methods=['POST'])
def api_tournament_vote():
    data = request.get_json(silent=True) or {}
    tournament_id = data.get('tournament_id')
    match_id = data.get('match_id')
    winner_id = data.get('winner_id')
    loser_id = data.get('loser_id')
    if not all((tournament_id, match_id, winner_id, loser_id)) or winner_id == loser_id:
        return jsonify({'error': 'tournament_id, match_id, distinct winner_id and loser_id are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament = conn.execute('SELECT size, status, is_blind FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        match = conn.execute('SELECT * FROM tournament_matches WHERE id = ? AND tournament_id = ?',
                             (match_id, tournament_id)).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({'error': 'Tournament not found.'}), 404
        if tournament['status'] != 'in_progress':
            conn.rollback()
            return jsonify({'error': 'Tournament is not in progress.'}), 409
        if not match:
            conn.rollback()
            return jsonify({'error': 'Match does not belong to this tournament.'}), 404
        if match['status'] != 'pending':
            conn.rollback()
            return jsonify({'error': 'This match has already been recorded.'}), 409
        if {winner_id, loser_id} != {match['song1_id'], match['song2_id']}:
            conn.rollback()
            return jsonify({'error': 'Winner and loser must be the two songs in this match.'}), 400

        points = _round_points(tournament['size'], match['round_number'])
        conn.execute('''UPDATE tournament_matches SET winner_id = ?, loser_id = ?, status = 'completed',
            points_awarded = ?, played_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (winner_id, loser_id, points, match_id))

        round_rows = conn.execute('''SELECT * FROM tournament_matches
            WHERE tournament_id = ? AND round_number = ? ORDER BY match_number''',
            (tournament_id, match['round_number'])).fetchall()
        if all(row['status'] == 'completed' or row['id'] == match_id for row in round_rows):
            winners = [winner_id if row['id'] == match_id else row['winner_id'] for row in round_rows]
            if len(winners) > 1:
                next_round = match['round_number'] + 1
                for i in range(0, len(winners), 2):
                    conn.execute('''INSERT OR IGNORE INTO tournament_matches
                        (tournament_id, round_number, match_number, song1_id, song2_id)
                        VALUES (?, ?, ?, ?, ?)''',
                        (tournament_id, next_round, (i // 2) + 1, winners[i], winners[i + 1]))
                conn.execute('UPDATE tournaments SET current_round = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                             (next_round, tournament_id))
            else:
                conn.execute('UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (tournament_id,))
        conn.commit()
        return jsonify({'success': True, 'points_awarded': points,
                        'matches': _tournament_matches(conn, tournament_id)})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not record tournament vote')
        return jsonify({'error': 'Could not save this vote.'}), 500
    finally:
        conn.close()


@app.route('/api/tournaments', methods=['GET'])
def api_tournaments_list():
    conn = get_db_connection()
    try:
        rows = conn.execute('''SELECT t.id, t.size, t.scope_type, t.scope_id, t.status,
                    t.champion_id, t.created_at, t.updated_at, t.completed_at, t.is_blind,
                    (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id AND tm.status = 'completed') AS matches_completed,
                    (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id) AS matches_created
                    FROM tournaments t ORDER BY CASE t.status WHEN 'in_progress' THEN 0 ELSE 1 END,
                    COALESCE(t.updated_at, t.timestamp) DESC''').fetchall()
        return jsonify({'tournaments': [dict(row) for row in rows]})
    finally:
        conn.close()


@app.route('/api/tournaments/<int:tournament_id>', methods=['GET'])
def api_tournament_detail(tournament_id):
    conn = get_db_connection()
    try:
        tournament = conn.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        if not tournament:
            return jsonify({'error': 'Tournament not found.'}), 404
        entries = conn.execute('''SELECT e.seed, s.id, s.title, s.audio_url, s.elo_score,
            al.cover_url, (SELECT GROUP_CONCAT(a.name, ', ') FROM song_artists sa
            JOIN artists a ON a.id = sa.artist_id WHERE sa.song_id = s.id) AS artist
            FROM tournament_entries e JOIN songs s ON s.id = e.song_id
            LEFT JOIN albums al ON al.id = s.album_id
            WHERE e.tournament_id = ? ORDER BY e.seed''', (tournament_id,)).fetchall()
        return jsonify({'tournament': dict(tournament), 'entries': [dict(row) for row in entries],
                        'matches': _tournament_matches(conn, tournament_id)})
    finally:
        conn.close()


@app.route('/tournament_stats')
def tournament_stats_page():
    """Render the dedicated tournament leaderboard and history page."""
    return render_template('tournament_stats.html')


@app.route('/api/tournament_stats', methods=['GET'])
def api_tournament_stats():
    """Tournament-only leaderboard; regular Elo and history are not involved."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT s.id, s.title, al.cover_url,
                (SELECT GROUP_CONCAT(a.name, ', ') FROM song_artists sa
                 JOIN artists a ON a.id = sa.artist_id WHERE sa.song_id = s.id) AS artist,
                (SELECT COUNT(*) FROM tournament_entries te WHERE te.song_id = s.id) AS tournaments_entered,
                (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.winner_id = s.id) AS matches_won,
                (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.loser_id = s.id) AS matches_lost,
                (SELECT COALESCE(SUM(tm.points_awarded), 0) FROM tournament_matches tm
                 WHERE tm.winner_id = s.id) AS tournament_points,
                (SELECT COUNT(*) FROM tournaments t WHERE t.champion_id = s.id AND t.status = 'completed') AS championships
            FROM songs s LEFT JOIN albums al ON al.id = s.album_id
            ORDER BY championships DESC, tournament_points DESC,
                CASE WHEN (SELECT COUNT(*) FROM tournament_matches tm
                           WHERE tm.winner_id = s.id OR tm.loser_id = s.id) = 0 THEN -1.0
                     ELSE CAST((SELECT COUNT(*) FROM tournament_matches tm WHERE tm.winner_id = s.id) AS REAL)
                          / (SELECT COUNT(*) FROM tournament_matches tm
                             WHERE tm.winner_id = s.id OR tm.loser_id = s.id) END DESC,
                tournaments_entered DESC, s.title COLLATE NOCASE
        ''').fetchall()
        result = []
        for row in rows:
            item = dict(row)
            played = item['matches_won'] + item['matches_lost']
            item['matches_played'] = played
            item['win_rate'] = round(item['matches_won'] * 100 / played, 2) if played else None
            item['tournament_points'] = round(item['tournament_points'], 4)
            result.append(item)
        return jsonify({'songs': result})
    finally:
        conn.close()


@app.route('/api/tournament_complete', methods=['POST'])
def api_tournament_complete():
    data = request.get_json(silent=True) or {}
    tournament_id = data.get('tournament_id')
    champion_id = data.get('champion_id')
    if not tournament_id or not champion_id:
        return jsonify({'error': 'tournament_id and champion_id are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament = conn.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({'error': 'Tournament not found.'}), 404
        if tournament['status'] == 'completed':
            conn.rollback()
            if tournament['champion_id'] == champion_id:
                return jsonify({'success': True, 'already_completed': True})
            return jsonify({'error': 'Tournament has already been completed.'}), 409
        if tournament['status'] != 'in_progress':
            conn.rollback()
            return jsonify({'error': 'Tournament is not in progress.'}), 409
        pending = conn.execute('''SELECT COUNT(*) FROM tournament_matches
            WHERE tournament_id = ? AND status != 'completed' ''', (tournament_id,)).fetchone()[0]
        final_match = conn.execute('''SELECT winner_id FROM tournament_matches
            WHERE tournament_id = ? ORDER BY round_number DESC, match_number ASC LIMIT 1''',
            (tournament_id,)).fetchone()
        if pending or not final_match or final_match['winner_id'] != champion_id:
            conn.rollback()
            return jsonify({'error': 'All matches must be complete and champion must be the final winner.'}), 409
        conn.execute('''UPDATE tournaments SET champion_id = ?, status = 'completed',
            completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (champion_id, tournament_id))
        conn.execute('UPDATE songs SET tournament_wins = tournament_wins + 1 WHERE id = ?', (champion_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not complete tournament')
        return jsonify({'error': 'Could not complete tournament.'}), 500
    finally:
        conn.close()

