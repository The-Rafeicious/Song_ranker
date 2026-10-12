from flask import render_template, request, redirect, url_for, session, jsonify
import requests
import re
import sqlite3
import os
from datetime import datetime

from apple_access import apple_lookup, AppleRequestError
from track_numbers import parse_track_number, check_track_position, track_position_conflicts, TrackNumberConflict
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


def apple_metadata(track):
    """Use existing library fields; do not invent positions for multi-disc releases."""
    disc_count = track.get('discCount', 1) or 1
    disc_number = track.get('discNumber', 1) or 1
    source_number = track.get('trackNumber')
    try:
        number = parse_track_number(source_number) if int(disc_count) == 1 and int(disc_number) == 1 else None
    except (ValueError, TypeError):
        number = None
    return {
        'title': track.get('trackName', 'Unknown'),
        'artist': track.get('artistName', 'Unknown'),
        'album': track.get('collectionName', ''),
        'cover_url': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
        'audio_url': track.get('previewUrl', ''),
        'track_number': number,
        'release_date': (track.get('releaseDate') or '')[:10],
        'genres': track.get('primaryGenreName', ''),
        'source_track_number': source_number, 'disc_number': disc_number, 'disc_count': disc_count
    }


def apple_lookup_url(link):
    from urllib.parse import urlsplit, parse_qs, urlencode
    parsed = urlsplit(link)
    if parsed.hostname not in ('music.apple.com', 'www.music.apple.com'):
        raise ValueError('Invalid Apple Music link.')
    track_id = (parse_qs(parsed.query).get('i') or [None])[0]
    album_id = re.search(r'(?:id)?(\d+)/?$', parsed.path)
    identifier = track_id if track_id and track_id.isdigit() else (album_id.group(1) if album_id else None)
    if not identifier:
        raise ValueError('Invalid Apple Music link.')
    region = parsed.path.strip('/').split('/')[0]
    params = {'id': identifier, 'entity': 'song', 'limit': 200}
    if re.fullmatch(r'[a-zA-Z]{2}', region):
        params['country'] = region.lower()
    return 'https://itunes.apple.com/lookup?' + urlencode(params)


@app.route('/api/dev/search_apple')
@admin_required
def api_search_apple():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    try:
        if 'music.apple.com' in query:
            url = apple_lookup_url(query)
        else:
            from urllib.parse import urlencode
            url = 'https://itunes.apple.com/search?' + urlencode({'term':query,'entity':'song','limit':10,'explicit':'Yes'})
        response = apple_lookup(url)
        return jsonify([apple_metadata(track) for track in response.get('results', [])
                        if track.get('trackName') and track.get('kind', 'song') == 'song'])
    except AppleRequestError as exc:
        return exc.response()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


def song_metadata(data):
    title = str(data.get('title') or '').strip()
    if 'music.apple.com' in title:
        tracks = apple_lookup(apple_lookup_url(title)).get('results', [])
        tracks = [t for t in tracks if t.get('trackName') and t.get('kind', 'song') == 'song']
        if len(tracks) != 1:
            raise ValueError('Use Apple Music search to choose a song from this album link.')
        imported = apple_metadata(tracks[0])
        # A metadata refresh must retain custom tags and an explicitly supplied
        # position when Apple cannot provide an album-wide position.
        genre_names = [g.strip() for g in (str(data.get('genres') or '') + ',' + imported['genres']).split(',') if g.strip()]
        retained = {}
        for name in genre_names:
            retained.setdefault(name.casefold(), name)
        imported['genres'] = ', '.join(retained.values())
        if imported['track_number'] is None and data.get('track_number') not in (None, ''):
            imported['track_number'] = data['track_number']
        data = {**data, **imported}
        title = str(data.get('title') or '').strip()
    if not title:
        raise ValueError('Title is required.')
    release_date = str(data.get('release_date') or '').strip()
    if release_date:
        try:
            release_date = datetime.strptime(release_date, '%Y-%m-%d').date().isoformat()
        except ValueError:
            raise ValueError('Invalid release date.')
    return {**data, 'title': title, 'artist':str(data.get('artist') or '').strip(),
            'album':str(data.get('album') or '').strip() or f'{title} - Single',
            'cover_url':data.get('cover_url') or '', 'audio_url':data.get('audio_url') or '',
            'genres':str(data.get('genres') or '').strip(), 'release_date':release_date}


def write_song(data, song_id=None):
    """Resolve metadata and check the final album slot in one transaction."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM songs WHERE id=?', (song_id,)).fetchone() if song_id is not None else None
        if song_id is not None and not old:
            conn.rollback()
            return jsonify({'message':'Song not found.'}), 404
        number = parse_track_number(data.get('track_number', old['track_number'] if old else None))
        if song_id is None:
            existing = conn.execute('''SELECT s.id FROM songs s JOIN song_artists sa ON s.id=sa.song_id
                JOIN artists a ON sa.artist_id=a.id WHERE s.title=? COLLATE NOCASE AND a.name LIKE ?''',
                (data['title'], f"%{data['artist'][:10]}%")).fetchone()
            if existing:
                conn.rollback()
                return jsonify({'message':f"'{data['title']}' by {data['artist']} already exists."}), 400
        album_id = get_or_create_album(conn, data['album'], data['cover_url'], data['release_date'])
        check_track_position(conn, album_id, number, song_id)
        if song_id is None:
            cursor = conn.execute('''INSERT INTO songs (title,album_id,audio_url,track_number,elo_score,matches_played)
                VALUES (?,?,?,?,1200,0)''', (data['title'],album_id,data['audio_url'],number))
            song_id = cursor.lastrowid
            message = f"Added '{data['title']}'"
        else:
            conn.execute('''UPDATE songs SET title=?,album_id=?,audio_url=?,track_number=? WHERE id=?''',
                (data['title'],album_id,data['audio_url'],number,song_id))
            conn.execute('DELETE FROM song_artists WHERE song_id=?',(song_id,))
            conn.execute('DELETE FROM song_genres WHERE song_id=?',(song_id,))
            message = 'Song updated successfully.'
        link_artists_to_song(conn, song_id, data['artist'], default_cover=data['cover_url'])
        link_genres_to_song(conn, song_id, data['genres'])
        conn.commit()
        return jsonify({'status':'success','message':message,'song_id':song_id,
                        'updated_song':{'title':data['title'],'artist':data['artist'],'cover_url':data['cover_url']}})
    except TrackNumberConflict as exc:
        conn.rollback()
        return jsonify({'message':str(exc)}),409
    except (ValueError,TypeError) as exc:
        conn.rollback()
        return jsonify({'message':str(exc)}),400
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return jsonify({'message':str(exc)}),409
    finally:
        conn.close()


@app.route('/api/dev/add_song', methods=['POST'])
@admin_required
def api_add_song():
    try:
        data = song_metadata(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'message':str(exc)}),400
    except AppleRequestError as exc:
        return exc.response()
    except requests.RequestException:
        return jsonify({'message':'Apple Music lookup unavailable.'}),502
    return write_song(data)


@app.route('/api/dev/edit_song/<int:song_id>', methods=['POST'])
@admin_required
def api_edit_song(song_id):
    try:
        data = song_metadata(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'message':str(exc)}),400
    except AppleRequestError as exc:
        return exc.response()
    except requests.RequestException:
        return jsonify({'message':'Apple Music lookup unavailable.'}),502
    return write_song(data, song_id)


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
    conn.execute('DELETE FROM trivia_rounds WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM trivia_adjustments WHERE song_id=?',(song_id,))
    conn.execute('DELETE FROM history WHERE winner_id = ? OR loser_id = ?', (song_id, song_id))
    conn.execute('DELETE FROM tournament_entries WHERE song_id=?',(song_id,))
    for column in ('song1_id','song2_id','winner_id','loser_id'):
        conn.execute(f'UPDATE tournament_matches SET {column}=NULL WHERE {column}=?',(song_id,))
    for column in ('champion_id','runner_up_id','third_place_id','fourth_place_id'):
        conn.execute(f'UPDATE tournaments SET {column}=NULL WHERE {column}=?',(song_id,))
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
    description = data.get('description')
    if description is not None and (not isinstance(description, str) or len(description) > 2000):
        return jsonify({'message':'Tag info must be text, up to 2,000 characters.'}),400
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM genres WHERE id=?',(genre_id,)).fetchone():
        conn.close(); return jsonify({'message':'Record not found.'}),404
    if conn.execute('SELECT 1 FROM genres WHERE LOWER(name)=LOWER(?) AND id!=?',(data['name'].strip(),genre_id)).fetchone():
        conn.close(); return jsonify({'message':'Tag already exists.'}),400
    conn.execute('UPDATE genres SET name = ? WHERE id = ?', (data.get('name', '').strip(), genre_id))
    if description is not None:
        conn.execute('UPDATE genres SET description=? WHERE id=?', (description.strip(), genre_id))

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
    tables = ['songs','artists','albums','genres','history','trivia_stats','tournaments','tournament_entries','tournament_matches','elo_guess_rounds','album_shelf_rounds','album_shelf_items']
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
        'tournament_matches':'SELECT COUNT(*) FROM tournament_matches','trivia_rounds':'SELECT COUNT(*) FROM trivia_rounds','elo_guesses':'SELECT COUNT(*) FROM elo_guess_rounds WHERE completed_at IS NOT NULL','shelf_rounds':'SELECT COUNT(*) FROM album_shelf_rounds WHERE completed_at IS NOT NULL'}.items()}
    conn.close(); return jsonify({'keep':keep,'clear':clear})


def reset_competition_data(scope):
    """Keep the library and reset only the requested competition records."""
    conn=None
    try:
        backup_path=create_database_backup('pre_reset_'+scope)
        conn=get_db_connection()
        conn.execute('BEGIN IMMEDIATE')
        if scope in ('all','matches'):
            conn.execute('DELETE FROM history')
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_elo_changes'").fetchone():
                conn.execute('DELETE FROM legacy_elo_changes')
            conn.execute('UPDATE songs SET elo_score=1200,matches_played=0,highest_elo=1200,highest_rank=9999')
        if scope in ('all','trivia'):
            conn.execute('DELETE FROM trivia_rounds')
            conn.execute('DELETE FROM trivia_adjustments')
            conn.execute("UPDATE global_stats SET value=0 WHERE key IN ('trivia_high_score','trivia_high_streak')")
            conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_scoring_version',2) ON CONFLICT(key) DO UPDATE SET value=2")
        if scope in ('all','tournaments'):
            for table in ('tournament_matches','tournament_entries','tournaments'):
                conn.execute(f'DELETE FROM {table}')
            conn.execute('UPDATE songs SET tournament_wins=0')
        if scope in ('all','guesser'):
            conn.execute('DELETE FROM elo_guess_rounds')
        if scope in ('all','shelves'):
            conn.execute('DELETE FROM album_shelf_rounds')
        if scope=='all':
            conn.execute("UPDATE global_stats SET value=CASE WHEN key='trivia_scoring_version' THEN 2 ELSE 0 END")
        conn.commit()
        if scope in ('all','trivia'):
            for key in ('trivia_score','trivia_streak','trivia_round_token','trivia_scoring_version'):
                session.pop(key,None)
        if scope in ('all','guesser'):session.pop('guess_token',None)
        if scope in ('all','shelves'):session.pop('shelf_token',None)
        labels={'guesser':'Elo Guesser history','shelves':'Album Shelves history','all':'All competition data','matches':'Elo and match history','trivia':'Trivia history and records','tournaments':'Tournament history and records'}
        return jsonify(status='success',message=labels[scope]+' reset. Music library kept.',backup=os.path.basename(backup_path))
    except Exception:
        if conn:conn.rollback()
        app.logger.exception('Competition reset failed')
        return jsonify(message='Could not reset these records.'),500
    finally:
        if conn:conn.close()


@app.route('/api/dev/reset-history/<scope>',methods=['POST'])
@admin_required
def api_dev_reset_history(scope):
    if scope not in ('matches','trivia','tournaments','guesser','shelves'):
        return jsonify(message='Choose match, trivia, tournament, Elo Guesser or Album Shelves history.'),400
    phrases={'guesser':'RESET GUESSER','shelves':'RESET SHELVES','matches':'RESET MATCHES','trivia':'RESET TRIVIA','tournaments':'RESET TOURNAMENTS'}
    if (request.get_json(silent=True) or {}).get('confirmation')!=phrases[scope]:
        return jsonify(message='Type '+phrases[scope]+' to confirm.'),400
    return reset_competition_data(scope)


@app.route('/api/dev/special-round/<mode>/<int:round_id>',methods=['POST'])
@admin_required
def delete_special_round(mode,round_id):
    table={'guesser':'elo_guess_rounds','shelves':'album_shelf_rounds'}.get(mode)
    if not table:return jsonify(message='Unknown mode.'),400
    backup=create_database_backup('manual_mode_delete')
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        deleted=conn.execute(f'DELETE FROM {table} WHERE id=?',(round_id,)).rowcount
        if not deleted:return jsonify(message='Round not found.'),404
        conn.commit()
        return jsonify(message='Round deleted. Other modes and music kept.',backup=os.path.basename(backup))
    finally:conn.close()


@app.route('/api/dev/reset-database', methods=['POST'])
@admin_required
def api_dev_reset_database():
    if (request.get_json(silent=True) or {}).get('confirmation') != 'RESET COMPETITION':
        return jsonify(message='Type RESET COMPETITION to confirm.'),400
    return reset_competition_data('all')


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
        conn.execute('DELETE FROM trivia_rounds WHERE song_id=?', (song_id,))
        conn.execute('DELETE FROM trivia_adjustments WHERE song_id=?',(song_id,))

        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': 'Trivia statistics deleted for this song.'})
    from trivia import edit_trivia_totals
    try:
        edit_trivia_totals(conn,song_id,request.get_json(silent=True) or {})
        conn.commit()
        return jsonify(status='success',message='Trivia statistics updated.')
    except (ValueError,TypeError) as exc:
        conn.rollback()
        return jsonify(message=str(exc)),400
    finally:
        conn.close()


@app.route('/api/dev/integrity', methods=['GET'])
@admin_required
def api_dev_integrity():
    conn=get_db_connection(); integrity=[r[0] for r in conn.execute('PRAGMA integrity_check').fetchall()]
    fk=[list(r) for r in conn.execute('PRAGMA foreign_key_check').fetchall()]
    duplicates={}
    for table,column in (('songs','title'),('artists','name'),('albums','title')):
        duplicates[table]=[dict(r) for r in conn.execute(f'''SELECT LOWER(TRIM({column})) AS key,COUNT(*) AS count,GROUP_CONCAT(id) AS ids
            FROM {table} GROUP BY LOWER(TRIM({column})) HAVING COUNT(*)>1 ORDER BY count DESC LIMIT 50''').fetchall()]
    conflicts=track_position_conflicts(conn)
    conn.close(); return jsonify({'integrity':integrity,'foreign_key_errors':fk,'duplicates':duplicates,'track_number_conflicts':conflicts})


@app.route('/api/dev/activity', methods=['GET'])
@admin_required
def api_dev_activity():
    conn=get_db_connection()
    votes=[dict(r) for r in conn.execute('''SELECT h.id,h.created_at,w.id AS winner_id,w.title AS winner,l.id AS loser_id,l.title AS loser,
        CASE WHEN h.mode='legacy_tournament' THEN 'legacy tournament' WHEN h.mode = 'blind' THEN 'blind' WHEN h.mode = 'standard' THEN 'non-blind' ELSE 'unknown' END AS mode FROM history h
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


@app.route('/api/dev/bulk_songs', methods=['POST'])
@admin_required
def api_dev_bulk_songs():
    data=request.get_json(silent=True) or {}
    conn=get_db_connection()
    try:
        ids=list(dict.fromkeys(int(i) for i in data.get('song_ids',[])))
        if not ids: raise ValueError('Select at least one song.')
        conn.execute('BEGIN IMMEDIATE')
        placeholders=','.join('?' for _ in ids)
        rows=conn.execute(f'SELECT id,title,album_id,track_number FROM songs WHERE id IN ({placeholders})',ids).fetchall()
        if len(rows)!=len(ids): raise ValueError('One of the selected songs no longer exists.')
        action=data.get('action')
        if action=='move_album':
            album_id=int(data.get('album_id'))
            if not conn.execute('SELECT 1 FROM albums WHERE id=?',(album_id,)).fetchone(): raise ValueError('Choose an existing album.')
            clear=data.get('clear_track_numbers') is True
            occupied={r['track_number']:r['title'] for r in conn.execute(f'SELECT title,track_number FROM songs WHERE album_id=? AND id NOT IN ({placeholders}) AND track_number IS NOT NULL',[album_id]+ids)}
            if not clear:
                for row in rows:
                    n=row['track_number']
                    if n is not None and n in occupied: raise ValueError(f"Track {n} conflicts: {row['title']} / {occupied[n]}. Clear selected track numbers or edit their positions first.")
                    if n is not None: occupied[n]=row['title']
            # Release positions first, then restore them atomically in the destination.
            conn.execute(f'UPDATE songs SET track_number=NULL WHERE id IN ({placeholders})',ids)
            for row in rows:
                conn.execute('UPDATE songs SET album_id=?,track_number=? WHERE id=?',(album_id,None if clear else row['track_number'],row['id']))
        elif action in ('add_tags','remove_tags'):
            tags=list(dict.fromkeys(int(i) for i in data.get('tag_ids',[])))
            if not tags: raise ValueError('Choose at least one tag.')
            if any(not conn.execute('SELECT 1 FROM genres WHERE id=?',(i,)).fetchone() for i in tags): raise ValueError('A selected tag no longer exists.')
            for song_id in ids:
                for tag_id in tags:
                    if action=='add_tags': conn.execute('INSERT OR IGNORE INTO song_genres(song_id,genre_id) VALUES(?,?)',(song_id,tag_id))
                    else: conn.execute('DELETE FROM song_genres WHERE song_id=? AND genre_id=?',(song_id,tag_id))
        else: raise ValueError('Choose a bulk action.')
        conn.commit()
        return jsonify(status='success',message=f'Updated {len(ids)} songs.',updated=len(ids))
    except (ValueError,TypeError,sqlite3.IntegrityError) as exc:
        conn.rollback()
        return jsonify(message=str(exc)),400
    finally: conn.close()


@app.route('/api/dev/trivia-records', methods=['POST'])
@admin_required
def api_dev_trivia_records():
    import math
    data=request.get_json(silent=True) or {}
    try:
        score=float(data['high_score']);streak=int(data['high_streak'])
        if not math.isfinite(score) or score<0 or streak<0: raise ValueError()
    except (KeyError,ValueError,TypeError): return jsonify(message='Use a non-negative score and whole-number streak.'),400
    conn=get_db_connection()
    try:
        for key,value in [('trivia_high_score',score),('trivia_high_streak',streak)]:
            conn.execute('INSERT INTO global_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
        conn.commit()
        return jsonify(status='success',message='Trivia records updated.')
    finally: conn.close()

@app.route('/api/dev/tournaments/<int:tournament_id>/placements', methods=['POST'])
@admin_required
def api_dev_tournament_placements(tournament_id):
    data=request.get_json(silent=True) or {};conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament=conn.execute('SELECT * FROM tournaments WHERE id=?',(tournament_id,)).fetchone()
        if not tournament or tournament['status']!='completed': raise ValueError('Finish this tournament before correcting its podium.')
        final=conn.execute("SELECT * FROM tournament_matches WHERE tournament_id=? AND match_type='bracket' ORDER BY round_number DESC LIMIT 1",(tournament_id,)).fetchone()
        bronze=conn.execute("SELECT * FROM tournament_matches WHERE tournament_id=? AND match_type='third_place'",(tournament_id,)).fetchone()
        if not final or final['status']!='completed': raise ValueError('This legacy bracket has no saved final to edit.')
        champion=int(data.get('champion_id'));third=int(data.get('third_place_id')) if bronze else None
        for match,winner in [(final,champion)]+([(bronze,third)] if bronze else []):
            if winner not in (match['song1_id'],match['song2_id']) or winner is None: raise ValueError('Select a participant from each saved match.')
            loser=match['song2_id'] if winner==match['song1_id'] else match['song1_id']
            conn.execute('UPDATE tournament_matches SET winner_id=?,loser_id=? WHERE id=?',(winner,loser,match['id']))
        runner=final['song2_id'] if champion==final['song1_id'] else final['song1_id']
        fourth=(bronze['song2_id'] if third==bronze['song1_id'] else bronze['song1_id']) if bronze else None
        conn.execute('UPDATE tournaments SET champion_id=?,runner_up_id=?,third_place_id=?,fourth_place_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(champion,runner,third,fourth,tournament_id))
        conn.execute("UPDATE songs SET tournament_wins=(SELECT COUNT(*) FROM tournaments t WHERE t.champion_id=songs.id AND t.status='completed')")
        conn.commit();return jsonify(status='success',message='Podium and deciding match results updated.')
    except (ValueError,TypeError) as exc:
        conn.rollback();return jsonify(message=str(exc)),400
    finally:conn.close()
