from flask import render_template, request, redirect, url_for, session, jsonify
import requests
import re
import sqlite3
import os
from datetime import datetime

from services import app, DB_NAME, DEV_PIN, admin_required, get_db_connection, git_push, init_db, export_rankings, create_database_backup, get_or_create_album, link_artists_to_song, link_genres_to_song
@app.route('/dev/login', methods=['GET', 'POST'])
def dev_login():
    if request.method == 'POST':
        pin = request.form.get('pin')
        if pin == DEV_PIN:
            session['is_admin'] = True
            return redirect(url_for('dev_dashboard'))
        return render_template('dev_login.html', error="Invalid PIN")
    return render_template('dev_login.html')


@app.route('/dev/logout')
def dev_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


@app.route('/dev/dashboard')
@admin_required
def dev_dashboard():
    return render_template('app_page.html', page='dev')


@app.route('/api/dev/search_apple')
@admin_required
def api_search_apple():
    """Queries Apple Music for a text search or direct link and returns JSON."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    if "music.apple.com" in query:
        match = re.search(r'[?&]i=(\d+)', query)
        if not match:
            return jsonify({"error": "Invalid link"}), 400
        url = f"https://itunes.apple.com/lookup?id={match.group(1)}"
    else:
        from urllib.parse import urlencode
        url = 'https://itunes.apple.com/search?' + urlencode({'term':query,'entity':'song','limit':10,'explicit':'Yes'})

    try:
        response = requests.get(url, timeout=5).json()
        results = []
        for track in response.get('results', []):
            results.append({
                'title': track.get('trackName', 'Unknown'),
                'artist': track.get('artistName', 'Unknown'),
                'album': track.get('collectionName', ''),
                'cover_url': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
                'audio_url': track.get('previewUrl', '')
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/dev/add_song', methods=['POST'])
@admin_required
def api_add_song():
    """Adds a new song, creating and linking albums/artists in the relational database."""
    data = request.json
    title = data.get('title', '').strip()
    artist = data.get('artist', '').strip()
    album = data.get('album', '').strip()
    if not album:
        album = f"{title} - Single"
    cover_url = data.get('cover_url', '')
    audio_url = data.get('audio_url', '')

    conn = get_db_connection()

    # Check for duplicate track by same title & primary artist
    existing = conn.execute('''
                            SELECT s.id
                            FROM songs s
                                     JOIN song_artists sa ON s.id = sa.song_id
                                     JOIN artists a ON sa.artist_id = a.id
                            WHERE s.title = ? COLLATE NOCASE
                              AND a.name LIKE ?
                            ''', (title, f"%{artist[:10]}%")).fetchone()

    if existing:
        conn.close()
        return jsonify({"status": "error", "message": f"'{title}' by {artist} already exists."}), 400

    # 1. Resolve Album
    album_id = get_or_create_album(conn, album, cover_url)

    # 2. Insert Song
    cursor = conn.execute('''
                          INSERT INTO songs (title, album_id, audio_url, elo_score, matches_played)
                          VALUES (?, ?, ?, 1200, 0)
                          ''', (title, album_id, audio_url))
    song_id = cursor.lastrowid

    # 3. Resolve & Link Artists
    link_artists_to_song(conn, song_id, artist, default_cover=cover_url)

    genres = data.get('genres', '').strip()
    link_genres_to_song(conn, song_id, genres)

    # 4. Initialize Trivia Stats row


    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Added '{title}'"})


@app.route('/api/dev/edit_song/<int:song_id>', methods=['POST'])
@admin_required
def api_edit_song(song_id):
    """Updates an existing song and re-links its relational dependencies."""
    data = request.json
    title = data.get('title', '').strip()
    artist = data.get('artist', '').strip()
    album = data.get('album', '').strip()
    cover_url = data.get('cover_url', '')
    audio_url = data.get('audio_url', '')

    # Intercept Apple Music links pasted into the title box
    if "music.apple.com" in title:
        match = re.search(r'[?&]i=(\d+)', title)
        if not match:
            return jsonify({"status": "error", "message": "Invalid Apple Music link."}), 400

        lookup_url = f"https://itunes.apple.com/lookup?id={match.group(1)}"
        try:
            response = requests.get(lookup_url, timeout=5).json()
            if response['resultCount'] > 0:
                track = response['results'][0]
                title = track.get('trackName', 'Unknown')
                artist = track.get('artistName', 'Unknown')
                album = track.get('collectionName', '')
                cover_url = track.get('artworkUrl100', '').replace('100x100bb', '300x300bb')
                audio_url = track.get('previewUrl', '')
            else:
                return jsonify({"status": "error", "message": "Link returned no data."}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if not album:
        album = f"{title} - Single"

    if not title:
        return jsonify({'message':'Title is required.'}),400
    try:
        track_number=int(data['track_number']) if data.get('track_number') not in ('',None) else None
        if track_number is not None and track_number<0: raise ValueError()
    except (ValueError,TypeError): return jsonify({'message':'Invalid track number.'}),400
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM songs WHERE id=?',(song_id,)).fetchone():
        conn.close(); return jsonify({'message':'Song not found.'}),404
    conn.execute('UPDATE songs SET track_number=? WHERE id=?',(track_number,song_id))

    # 1. Update/Link Album
    album_id = get_or_create_album(conn, album, cover_url)

    # 2. Update Core Song Row
    conn.execute('''
                 UPDATE songs
                 SET title     = ?,
                     album_id  = ?,
                     audio_url = ?
                 WHERE id = ?
                 ''', (title, album_id, audio_url, song_id))

    # 3. Refresh Artist Links (remove old associations and apply new ones)
    conn.execute('DELETE FROM song_artists WHERE song_id = ?', (song_id,))
    link_artists_to_song(conn, song_id, artist, default_cover=cover_url)

    genres = data.get('genres', '').strip()
    conn.execute('DELETE FROM song_genres WHERE song_id = ?', (song_id,))
    link_genres_to_song(conn, song_id, genres)

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Song updated successfully.",
        "updated_song": {
            "title": title,
            "artist": artist,
            "cover_url": cover_url
        }
    })


@app.route('/api/dev/delete_song/<int:song_id>', methods=['DELETE'])
@admin_required
def api_delete_song(song_id):
    """Deletes a song and redistributes its net Elo impact to the rest of the database."""
    conn = get_db_connection()

    song = conn.execute('SELECT elo_score FROM songs WHERE id = ?', (song_id,)).fetchone()
    if not song:
        conn.close()
        return jsonify({"status": "error", "message": "Song not found."}), 404

    active = conn.execute("SELECT t.id FROM tournament_entries e JOIN tournaments t ON t.id=e.tournament_id WHERE e.song_id=? AND t.status='in_progress' LIMIT 1",(song_id,)).fetchone()
    if active:
        conn.close()
        return jsonify({'message':f"Finish or delete tournament #{active['id']} before deleting this song."}),409

    elo_difference = song['elo_score'] - 1200

    conn.execute('DELETE FROM song_artists WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM song_genres WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM trivia_stats WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM history WHERE winner_id = ? OR loser_id = ?', (song_id, song_id))
    conn.execute('DELETE FROM tournament_entries WHERE song_id=?',(song_id,))
    for column in ('song1_id','song2_id','winner_id','loser_id'):
        conn.execute(f'UPDATE tournament_matches SET {column}=NULL WHERE {column}=?',(song_id,))
    conn.execute('UPDATE tournaments SET champion_id=NULL WHERE champion_id=?',(song_id,))
    conn.execute('DELETE FROM songs WHERE id = ?', (song_id,))

    remaining_songs = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    if remaining_songs > 0 and elo_difference != 0:
        adjustment = elo_difference / remaining_songs
        conn.execute('UPDATE songs SET elo_score = elo_score + ?', (adjustment,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Song deleted. System Elo conserved."})


@app.route('/api/dev/edit_artist/<int:artist_id>', methods=['POST'])
@admin_required
def api_edit_artist(artist_id):
    data = request.json
    if not str(data.get('name','')).strip():
        return jsonify({'message':'A name is required.'}),400
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM artists WHERE id=?',(artist_id,)).fetchone():
        conn.close(); return jsonify({'message':'Record not found.'}),404
    conn.execute('UPDATE artists SET name = ?, cover_url = ? WHERE id = ?',
                 (data.get('name', '').strip(), data.get('cover_url', ''), artist_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Artist updated successfully."})


@app.route('/api/dev/delete_artist/<int:artist_id>', methods=['DELETE'])
@admin_required
def api_delete_artist(artist_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_artists WHERE artist_id = ?', (artist_id,))
    conn.execute('DELETE FROM artists WHERE id = ?', (artist_id,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Artist deleted."})


@app.route('/api/dev/edit_album/<int:album_id>', methods=['POST'])
@admin_required
def api_edit_album(album_id):
    data = request.json
    if not str(data.get('title','')).strip():
        return jsonify({'message':'A name is required.'}),400
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM albums WHERE id=?',(album_id,)).fetchone():
        conn.close(); return jsonify({'message':'Record not found.'}),404
    conn.execute('UPDATE albums SET title = ?, cover_url = ?, release_date = ? WHERE id = ?',
                 (data.get('title', '').strip(), data.get('cover_url', ''), data.get('release_date', ''), album_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album updated successfully."})


@app.route('/api/dev/delete_album/<int:album_id>', methods=['DELETE'])
@admin_required
def api_delete_album(album_id):
    conn = get_db_connection()
    conn.execute('UPDATE songs SET album_id = NULL WHERE album_id = ?', (album_id,))
    conn.execute('DELETE FROM albums WHERE id = ?', (album_id,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album deleted. Associated songs updated."})


@app.route('/api/dev/edit_genre/<int:genre_id>', methods=['POST'])
@admin_required
def api_edit_genre(genre_id):
    data = request.json
    if not str(data.get('name','')).strip():
        return jsonify({'message':'A name is required.'}),400
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM genres WHERE id=?',(genre_id,)).fetchone():
        conn.close(); return jsonify({'message':'Record not found.'}),404
    if conn.execute('SELECT 1 FROM genres WHERE LOWER(name)=LOWER(?) AND id!=?',(data['name'].strip(),genre_id)).fetchone():
        conn.close(); return jsonify({'message':'Tag already exists.'}),400
    conn.execute('UPDATE genres SET name = ? WHERE id = ?', (data.get('name', '').strip(), genre_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre updated successfully."})


@app.route('/api/dev/delete_genre/<int:genre_id>', methods=['DELETE'])
@admin_required
def api_delete_genre(genre_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_genres WHERE genre_id = ?', (genre_id,))
    conn.execute('DELETE FROM genres WHERE id = ?', (genre_id,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre deleted."})


@app.route('/api/dev/overview', methods=['GET'])
@admin_required
def api_dev_overview():
    conn = get_db_connection()
    tables = ['songs','artists','albums','genres','history','trivia_stats','tournaments','tournament_entries','tournament_matches']
    counts = {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}
    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    fk_errors = len(conn.execute('PRAGMA foreign_key_check').fetchall())
    conn.close()
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    backups=[]
    if os.path.isdir(backup_dir):
        for name in sorted(os.listdir(backup_dir), reverse=True):
            full=os.path.join(backup_dir,name)
            if os.path.isfile(full) and name.endswith('.db'):
                backups.append({'name':name,'size':os.path.getsize(full),'modified':datetime.fromtimestamp(os.path.getmtime(full)).isoformat(timespec='seconds')})
    return jsonify({'counts':counts,'integrity':integrity,'foreign_key_errors':fk_errors,'backups':backups})


@app.route('/api/dev/backup', methods=['POST'])
@admin_required
def api_dev_backup():
    try:
        path=create_database_backup('manual')

        return jsonify({'status':'success','message':'Database backup created.','backup':os.path.basename(path)})
    except Exception as exc:
        app.logger.exception('Backup failed'); return jsonify({'status':'error','message':f'Backup failed: {exc}'}),500


@app.route('/api/dev/restore-backup', methods=['POST'])
@admin_required
def api_dev_restore_backup():
    data = request.get_json(silent=True) or {}
    name = os.path.basename(str(data.get('filename', '')))
    if not name.endswith('.db') or not name.startswith(('manual_', 'pre_reset_', 'pre_restore_', 'song_ranker_', 'pre_upgrade_')):
        return jsonify({'status': 'error', 'message': 'Choose a valid Song Ranker backup file.'}), 400
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    source_path = os.path.join(backup_dir, name)
    if not os.path.isfile(source_path):
        return jsonify({'status': 'error', 'message': 'Backup file not found.'}), 404
    current_backup = None
    try:
        # Verify the candidate backup before touching the live database.
        check = sqlite3.connect(source_path)
        try:
            required={'songs','albums','artists','song_artists','song_genres','genres'}
            tables={r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables):
                return jsonify({'message':'This backup does not contain a complete relational music library.'}),400
            columns={r[1] for r in check.execute('PRAGMA table_info(songs)')}
            if 'album_id' not in columns:
                return jsonify({'message':'Choose a relational Song Ranker v2 backup. The older flat-schema database is kept separately.'}),400
            result = check.execute('PRAGMA integrity_check').fetchone()[0]
            if result != 'ok':
                return jsonify({'status': 'error', 'message': f'Backup failed integrity check: {result}'}), 400
        finally:
            check.close()
        import tempfile
        from pathlib import Path
        from database import migrate
        with tempfile.TemporaryDirectory(dir=backup_dir, prefix='restore_check_') as temporary:
            candidate=Path(temporary)/'candidate.db'
            candidate_source=sqlite3.connect(source_path)
            candidate_dest=sqlite3.connect(candidate)
            try: candidate_source.backup(candidate_dest)
            finally: candidate_source.close(); candidate_dest.close()
            migrate(candidate)
            validation=sqlite3.connect(candidate)
            try:
                if validation.execute('PRAGMA foreign_key_check').fetchall():
                    return jsonify({'message':'Backup has broken library references.'}),400
            finally: validation.close()
        current_backup = create_database_backup('pre_restore')
        source = sqlite3.connect(source_path, timeout=30)
        destination = sqlite3.connect(DB_NAME, timeout=30)
        try:
            source.backup(destination)
            integrity = destination.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity != 'ok':
                raise sqlite3.DatabaseError(f'Restored database failed integrity check: {integrity}')
        finally:
            destination.close(); source.close()
        init_db()
        conn = get_db_connection()

        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': f'Restored {name}. A safety backup was saved as {os.path.basename(current_backup)}.'})
    except Exception as exc:
        if current_backup:
            recovery=sqlite3.connect(current_backup)
            target=sqlite3.connect(DB_NAME)
            try: recovery.backup(target)
            finally: recovery.close(); target.close()
        app.logger.exception('Backup restore failed')
        return jsonify({'status': 'error', 'message': f'Restore failed: {exc}'}), 500


@app.route('/api/dev/reset-preview', methods=['GET'])
@admin_required
def api_dev_reset_preview():
    conn=get_db_connection()
    keep={k:conn.execute(q).fetchone()[0] for k,q in {
        'songs':'SELECT COUNT(*) FROM songs','artists':'SELECT COUNT(*) FROM artists','albums':'SELECT COUNT(*) FROM albums','genres':'SELECT COUNT(*) FROM genres',
        'song_artist_links':'SELECT COUNT(*) FROM song_artists','song_genre_links':'SELECT COUNT(*) FROM song_genres'}.items()}
    clear={k:conn.execute(q).fetchone()[0] for k,q in {
        'votes_and_history':'SELECT COUNT(*) FROM history','trivia_stats':'SELECT COUNT(*) FROM trivia_stats','tournaments':'SELECT COUNT(*) FROM tournaments',
        'tournament_matches':'SELECT COUNT(*) FROM tournament_matches'}.items()}
    conn.close(); return jsonify({'keep':keep,'clear':clear})


@app.route('/api/dev/reset-database', methods=['POST'])
@admin_required
def api_dev_reset_database():
    data=request.get_json(silent=True) or {}
    if data.get('confirmation') != 'RESET COMPETITION':
        return jsonify({'status':'error','message':'Type RESET COMPETITION to confirm.'}),400
    try:
        backup_path=create_database_backup('pre_reset')
        conn=get_db_connection(); conn.execute('PRAGMA foreign_keys=ON')
        for table in ('tournament_matches','tournament_entries','tournaments','history','trivia_stats'):
            conn.execute(f'DELETE FROM {table}')
        conn.execute('UPDATE songs SET elo_score=1200,matches_played=0,highest_elo=1200,highest_rank=9999,tournament_wins=0')
        conn.execute('UPDATE global_stats SET value=0')
        conn.execute("INSERT INTO global_stats (key,value) VALUES ('trivia_high_score',0) ON CONFLICT(key) DO UPDATE SET value=0")

        conn.commit(); conn.close()
        return jsonify({'status':'success','message':'Competition reset. Songs, albums, artists, genres, and their music links were kept.','backup':os.path.basename(backup_path)})
    except Exception as exc:
        app.logger.exception('Database reset failed'); return jsonify({'status':'error','message':f'Reset failed: {exc}'}),500


@app.route('/api/dev/elo-correction', methods=['POST'])
@admin_required
def api_dev_elo_correction():
    data = request.get_json(silent=True) or {}
    try:
        song_id = int(data.get('song_id'))
        new_elo = float(data.get('new_elo'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Enter a valid song ID and numeric Elo value.'}), 400
    if not 0 <= new_elo <= 5000:
        return jsonify({'status': 'error', 'message': 'Elo must be between 0 and 5000.'}), 400
    conn = get_db_connection()
    song = conn.execute('SELECT id,title,elo_score FROM songs WHERE id=?', (song_id,)).fetchone()
    if not song:
        conn.close(); return jsonify({'status': 'error', 'message': 'Song not found.'}), 404
    conn.execute('UPDATE songs SET elo_score=? WHERE id=?', (new_elo, song_id))

    conn.commit(); conn.close()
    return jsonify({'status': 'success', 'message': f"Updated {song['title']} from {round(song['elo_score'])} to {round(new_elo)} Elo.."})


@app.route('/api/dev/trivia/<int:song_id>', methods=['POST', 'DELETE'])
@admin_required
def api_dev_edit_trivia(song_id):
    conn = get_db_connection()
    if not conn.execute('SELECT id FROM songs WHERE id=?', (song_id,)).fetchone():
        conn.close(); return jsonify({'status': 'error', 'message': 'Song not found.'}), 404
    if request.method == 'DELETE':
        conn.execute('DELETE FROM trivia_stats WHERE song_id=?', (song_id,))

        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': 'Trivia statistics deleted for this song.'})
    data = request.get_json(silent=True) or {}
    try:
        attempts = int(data.get('attempts', 0)); correct = int(data.get('correct', 0))
    except (TypeError, ValueError):
        conn.close(); return jsonify({'status': 'error', 'message': 'Attempts and correct must be whole numbers.'}), 400
    if attempts < 0 or correct < 0 or correct > attempts * 2:
        conn.close(); return jsonify({'status': 'error', 'message': 'Values must be non-negative and correct fields cannot exceed twice the attempts.'}), 400
    conn.execute('INSERT INTO trivia_stats (song_id,attempts,correct) VALUES (?,?,?) ON CONFLICT(song_id) DO UPDATE SET attempts=excluded.attempts,correct=excluded.correct', (song_id, attempts, correct))

    conn.commit(); conn.close()
    return jsonify({'status': 'success', 'message': 'Trivia statistics updated.'})


@app.route('/api/dev/integrity', methods=['GET'])
@admin_required
def api_dev_integrity():
    conn=get_db_connection(); integrity=[r[0] for r in conn.execute('PRAGMA integrity_check').fetchall()]
    fk=[list(r) for r in conn.execute('PRAGMA foreign_key_check').fetchall()]
    duplicates={}
    for table,column in (('songs','title'),('artists','name'),('albums','title')):
        duplicates[table]=[dict(r) for r in conn.execute(f'''SELECT LOWER(TRIM({column})) AS key,COUNT(*) AS count,GROUP_CONCAT(id) AS ids
            FROM {table} GROUP BY LOWER(TRIM({column})) HAVING COUNT(*)>1 ORDER BY count DESC LIMIT 50''').fetchall()]
    conn.close(); return jsonify({'integrity':integrity,'foreign_key_errors':fk,'duplicates':duplicates})


@app.route('/api/dev/activity', methods=['GET'])
@admin_required
def api_dev_activity():
    conn=get_db_connection()
    votes=[dict(r) for r in conn.execute('''SELECT h.id,h.created_at,w.id AS winner_id,w.title AS winner,l.id AS loser_id,l.title AS loser,
        CASE WHEN h.is_tournament_match THEN 'tournament' WHEN h.mode = 'blind' THEN 'blind' WHEN h.mode = 'standard' THEN 'non-blind' ELSE 'unknown' END AS mode FROM history h
        LEFT JOIN songs w ON w.id=h.winner_id LEFT JOIN songs l ON l.id=h.loser_id ORDER BY h.id DESC LIMIT 100''').fetchall()]
    tournaments=[dict(r) for r in conn.execute('''SELECT t.id,t.size,t.scope_type,t.scope_id,t.champion_id,t.timestamp,t.status,t.created_at,t.completed_at,
        (SELECT COUNT(*) FROM tournament_matches m WHERE m.tournament_id=t.id) AS match_count FROM tournaments t ORDER BY t.id DESC LIMIT 100''').fetchall()]
    conn.close(); return jsonify({'votes':votes,'tournaments':tournaments})


@app.route('/api/dev/tournaments/<int:tournament_id>', methods=['DELETE'])
@admin_required
def api_dev_delete_tournament(tournament_id):
    conn=get_db_connection()
    if not conn.execute('SELECT id FROM tournaments WHERE id=?',(tournament_id,)).fetchone():
        conn.close(); return jsonify({'message':'Tournament not found.'}),404
    conn.execute('DELETE FROM tournament_matches WHERE tournament_id=?',(tournament_id,)); conn.execute('DELETE FROM tournament_entries WHERE tournament_id=?',(tournament_id,)); conn.execute('DELETE FROM tournaments WHERE id=?',(tournament_id,))

    conn.commit(); conn.close(); return jsonify({'status':'success','message':'Tournament and bracket records deleted.'})


@app.route('/api/dev/sync', methods=['POST'])
@admin_required
def api_sync():
    """Endpoint to trigger a manual database push."""
    success = git_push()
    if success:
        return jsonify({"status": "success", "message": "Database synced to GitHub!"})
    return jsonify({"status": "error", "message": "Failed to sync to GitHub."}), 500


@app.route('/api/dev/export', methods=['POST'])
@admin_required
def api_export():
    """Endpoint to manually trigger a database text export."""
    try:
        export_rankings()
        return jsonify({"status": "success", "message": "Database snapshot saved to txt file!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Export failed: {str(e)}"}), 500

