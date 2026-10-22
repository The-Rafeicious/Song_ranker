from flask import render_template, request, session, jsonify, redirect
import random

from songranker.modes.selection import tournament_tracks
from songranker.services import (app, get_db_connection, calculate_new_elo, is_close_match, get_song_full, get_matchup)
@app.route('/game')
def index():
    if request.args.get('mode')=='guesser':return redirect('/elo_guesser')
    return render_template('app_page.html', page='standard')


def _preference_error(error):
    payload = {'message': str(error)}
    if getattr(error, 'saved_result', None) is not None:
        payload['saved_result'] = error.saved_result
    return jsonify(payload), error.status


@app.route('/api/vote', methods=['POST'])
def api_vote():
    from songranker.modes.preferences import (save_vote, PreferenceError)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message='Submit a valid vote object.'), 400
    conn = get_db_connection()
    try:
        return jsonify(save_vote(conn, session.get('preference_owner'), data))
    except PreferenceError as error:
        return _preference_error(error)
    finally:
        conn.close()


@app.route('/api/matchup')
def api_matchup():
    import secrets
    from songranker.modes.preferences import (get_offer, PreferenceError)
    from songranker.modes.selection_data import preference_pair
    owner = session.get('preference_owner')
    if not owner:
        owner = secrets.token_urlsafe(32)
        session['preference_owner'] = owner
    mode = request.args.get('mode', 'standard')
    conn = get_db_connection()
    try:
        payload = get_offer(conn, owner, mode,
            lambda: preference_pair(conn, mode, owner))
        response = jsonify(payload)
        response.headers['Cache-Control'] = 'no-store'
        return response
    except PreferenceError as error:
        return _preference_error(error)
    finally:
        conn.close()


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
    if scope not in ('global', 'artist', 'album', 'tag'):
        return jsonify({'error': 'Invalid tournament scope.'}), 400
    if scope != 'global' and not scope_id:
        return jsonify({'error': 'Select an artist, album or tag.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conditions=[];params=[]
        if scope=='artist':
            conditions.append('EXISTS(SELECT 1 FROM song_artists sa WHERE sa.song_id=s.id AND sa.artist_id=?)');params.append(scope_id)
        elif scope=='album':
            conditions.append('s.album_id=?');params.append(scope_id)
        elif scope=='tag':
            conditions.append('EXISTS(SELECT 1 FROM song_genres sg WHERE sg.song_id=s.id AND sg.genre_id=?)');params.append(scope_id)
        if is_blind:
            conditions.append("TRIM(COALESCE(s.audio_url,''))!=''")
        where=' WHERE '+' AND '.join(conditions) if conditions else ''
        pool=[dict(r) for r in conn.execute("""SELECT s.id,s.title,s.audio_url,s.elo_score,al.cover_url,
            (SELECT GROUP_CONCAT(a.name,', ') FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=s.id) artist,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.status='completed' AND (tm.winner_id=s.id OR tm.loser_id=s.id)) tournament_matches,
            (SELECT COUNT(*) FROM tournaments t WHERE t.status='completed' AND t.champion_id=s.id) championships
            FROM songs s LEFT JOIN albums al ON al.id=s.album_id"""+where+' ORDER BY s.id',params)]
        if len(pool)<size:
            return jsonify(error=f'Not enough eligible tracks. Needed {size}, found {len(pool)}.'),400
        from songranker.modes.selection_data import mode_counts
        from songranker.modes.selection_data import with_catalogue_age
        pool=with_catalogue_age(conn,pool)
        songs=tournament_tracks(pool,size,counts=mode_counts(conn,'tournament'))
        if songs is None:
            return jsonify(error='Not enough tracks with valid Elo for this bracket.'),400

        cursor = conn.execute('''INSERT INTO tournaments
                    (size, scope_type, scope_id, status, created_at, updated_at, current_round, points_version, is_blind, playoff_enabled,
                     elo_policy_version,elo_weight)
                    VALUES (?, ?, ?, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 1, ?, 1, 1, ?)''',
                              (size, scope, scope_id, is_blind, 1 if scope == 'global' else 0.5))
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
                        'matches': _tournament_matches(conn, tournament_id),
                        'elo_policy_version': 1, 'elo_weight': 1 if scope == 'global' else 0.5})
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
        song1_id, song2_id, winner_id, loser_id, status, points_awarded, played_at, match_type
        FROM tournament_matches WHERE tournament_id = ?
        ORDER BY round_number, match_number''', (tournament_id,)).fetchall()
    return [dict(row) for row in rows]


def _round_points(size, round_number):
    # Normalize the maximum points for a champion to 7 across bracket sizes.
    return round(7 * (2 ** (round_number - 1)) / (size - 1), 4)


@app.route('/api/tournament_vote', methods=['POST'])
def api_tournament_vote():
    data = request.get_json(silent=True) or {}
    from songranker.modes.preferences import (integer, PreferenceError)
    if not isinstance(data, dict):
        return jsonify(error='Submit a tournament vote object.'),400
    try:
        tournament_id, match_id, winner_id, loser_id = (
            integer(data.get(key), key.replace('_', ' '))
            for key in ('tournament_id','match_id','winner_id','loser_id'))
    except PreferenceError as error:
        return jsonify(error=str(error)),error.status
    if not all((tournament_id, match_id, winner_id, loser_id)) or winner_id == loser_id:
        return jsonify({'error': 'tournament_id, match_id, distinct winner_id and loser_id are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament = conn.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        match = conn.execute('SELECT * FROM tournament_matches WHERE id = ? AND tournament_id = ?',
                             (match_id, tournament_id)).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({'error': 'Tournament not found.'}), 404
        if match and tournament['elo_policy_version'] == 1 and match['status'] == 'completed':
            conn.rollback()
            if (winner_id, loser_id) != (match['winner_id'], match['loser_id']):
                return jsonify(error='This match already has a different saved result.'),409
            event = conn.execute('SELECT * FROM preference_events WHERE tournament_match_id=?', (match_id,)).fetchone()
            from songranker.modes.preferences import receipt
            return jsonify(success=True, points_awarded=match['points_awarded'],
                           preference_event_id=event['id'] if event else None,
                           elo_result=receipt(event) if event else None,
                           matches=_tournament_matches(conn, tournament_id))
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

        final_round=tournament['size'].bit_length()-1
        if tournament['playoff_enabled'] and match['match_type']=='bracket' and match['round_number']==final_round:
            bronze=conn.execute("SELECT status FROM tournament_matches WHERE tournament_id=? AND match_type='third_place'",(tournament_id,)).fetchone()
            if not bronze or bronze['status']!='completed':
                return jsonify(error='Play the third-place playoff before the final.'),409
        points = (_round_points(tournament['size'],final_round-1)*.5
                  if match['match_type']=='third_place' else _round_points(tournament['size'], match['round_number']))
        conn.execute('''UPDATE tournament_matches SET winner_id = ?, loser_id = ?, status = 'completed',
            points_awarded = ?, played_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (winner_id, loser_id, points, match_id))
        from songranker.modes.preferences import (save_tournament_preference, receipt)
        event_id = save_tournament_preference(conn, tournament, match, winner_id, loser_id)
        elo_result = receipt(conn.execute('SELECT * FROM preference_events WHERE id=?', (event_id,)).fetchone()) if event_id else None

        round_rows = conn.execute('''SELECT * FROM tournament_matches
            WHERE tournament_id = ? AND round_number = ? AND match_type='bracket' ORDER BY match_number''',
            (tournament_id, match['round_number'])).fetchall()
        if match['match_type']=='bracket' and all(row['status'] == 'completed' or row['id'] == match_id for row in round_rows):
            winners = [winner_id if row['id'] == match_id else row['winner_id'] for row in round_rows]
            if len(winners) > 1:
                next_round = match['round_number'] + 1
                for i in range(0, len(winners), 2):
                    conn.execute('''INSERT OR IGNORE INTO tournament_matches
                        (tournament_id, round_number, match_number, song1_id, song2_id)
                        VALUES (?, ?, ?, ?, ?)''',
                        (tournament_id, next_round, (i // 2) + 1, winners[i], winners[i + 1]))
                if tournament['playoff_enabled'] and next_round==final_round:
                    losers=[row['loser_id'] for row in conn.execute("SELECT loser_id FROM tournament_matches WHERE tournament_id=? AND round_number=? AND match_type='bracket' ORDER BY match_number",(tournament_id,match['round_number']))]
                    conn.execute("INSERT OR IGNORE INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,match_type) VALUES(?,?,0,?,?,'third_place')",(tournament_id,final_round,losers[0],losers[1]))
                conn.execute('UPDATE tournaments SET current_round = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                             (next_round, tournament_id))
            else:
                conn.execute('UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (tournament_id,))

        conn.commit()
        return jsonify({'success': True, 'points_awarded': points, 'preference_event_id': event_id, 'elo_result': elo_result,
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
                    t.champion_id, t.created_at, t.updated_at, t.completed_at, t.is_blind, t.playoff_enabled,t.runner_up_id,t.third_place_id,t.fourth_place_id,
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
    """Read-only tournament dashboard; ranking APIs and game actions stay separate."""
    from songranker.reports.tournament_stats_data import build_tournament_stats
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        data = build_tournament_stats(conn, selected=request.args.get('tournament', type=int),
                                      archive_page=request.args.get('archive_page', 1, type=int))
    finally:
        conn.close()
    return render_template('tournament_stats.html', **data)


@app.route('/api/tournament_stats', methods=['GET'])
def api_tournament_stats():
    """Tournament-only leaderboard; regular Elo and history are not involved."""
    from songranker.catalog import (collection, ranked)
    rows=[]
    for song in ranked(collection(),'songs'):
        played=song['tournament_wins']+song['tournament_losses']
        rows.append({**{key:song[key] for key in ('id','title','artist','cover_url','championships','runner_ups','third_places','fourth_places','podiums','tournament_points')},'tournaments_entered':song['tournament_appearances'],
                     'matches_won':song['tournament_wins'],'matches_lost':song['tournament_losses'],
                     'matches_played':played,'win_rate':round(100*song['tournament_wins']/played,2) if played else None})
    rows.sort(key=lambda r:(-r['championships'],-r['tournament_points'],r['title']))
    return jsonify(songs=rows)


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
        final_match = conn.execute('''SELECT winner_id,loser_id FROM tournament_matches
            WHERE tournament_id = ? AND match_type='bracket' ORDER BY round_number DESC, match_number ASC LIMIT 1''',
            (tournament_id,)).fetchone()
        if pending or not final_match or final_match['winner_id'] != champion_id:
            conn.rollback()
            return jsonify({'error': 'All matches must be complete and champion must be the final winner.'}), 409
        bronze=conn.execute("SELECT winner_id,loser_id FROM tournament_matches WHERE tournament_id=? AND match_type='third_place' AND status='completed'",(tournament_id,)).fetchone()
        conn.execute('''UPDATE tournaments SET runner_up_id=?,third_place_id=?,fourth_place_id=?,champion_id = ?, status = 'completed',
            completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (final_match['loser_id'],bronze['winner_id'] if bronze else None,bronze['loser_id'] if bronze else None,champion_id, tournament_id))
        conn.execute('UPDATE songs SET tournament_wins = tournament_wins + 1 WHERE id = ?', (champion_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not complete tournament')
        return jsonify({'error': 'Could not complete tournament.'}), 500
    finally:
        conn.close()

