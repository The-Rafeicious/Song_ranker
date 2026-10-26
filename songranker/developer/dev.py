from flask import render_template, request, redirect, url_for, session, jsonify, abort
import json
from pathlib import Path
import requests
import re
import sqlite3
import os
from datetime import datetime
from songranker.apple_access import apple_lookup, AppleRequestError
from songranker.developer.catalog_sources import parse_track_number
from songranker.developer.catalog_sources import check_track_position
from songranker.developer.catalog_sources import track_position_conflicts
from songranker.developer.catalog_sources import TrackNumberConflict
from songranker.services import app, DEV_PIN, admin_required, get_db_connection, get_song_full, export_rankings, create_database_backup, get_or_create_album, link_artists_to_song, link_genres_to_song
from songranker.developer import dev_vibe

DEV_NAVIGATION = json.loads(Path(__file__).with_name('navigation.json').read_text())


def developer_page(view):
    """Render a focused Dev task using the shared navigation registry and shell."""
    pages = {row[0]: row for row in DEV_NAVIGATION['pages']}
    areas = {row[0]: row for row in DEV_NAVIGATION['areas']}
    if view not in pages and view not in areas:
        abort(404)
    title = pages[view][3] if view in pages else areas[view][1]
    return render_template('dev.html', page='dev', dev_title=title,
                           dev_context=dict(DEV_NAVIGATION, view=view))


def json_fields():
    """Legacy maintenance forms treat a missing/non-object payload as empty."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


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
    return redirect('/')


@app.route('/dev/dashboard')
@admin_required
def dev_dashboard():
    """Keep existing dashboard bookmarks while serving the focused Dev workspace."""
    view = request.args.get('view', 'overview')
    known = {row[0] for row in DEV_NAVIGATION['pages']}
    return developer_page(view if view in known else 'overview')


@app.get('/dev/<area>')
@admin_required
def dev_area(area):
    """Open the Library, Mode edits or Tools landing page."""
    if area not in {row[0] for row in DEV_NAVIGATION['areas']}:
        abort(404)
    return developer_page(area)


@app.get('/dev/<area>/<task>')
@admin_required
def dev_task(area, task):
    """Resolve a registered task URL without accepting unlisted Dev destinations."""
    row = next((r for r in DEV_NAVIGATION['pages'] if r[1:3] == [area, task]), None)
    if row is None:
        abort(404)
    return developer_page(row[0])


def apple_lookup_url(link):
    """Derive a bounded song lookup URL from a supported Apple Music track or album
    link.
    """
    from urllib.parse import urlsplit, parse_qs, urlencode
    if not isinstance(link,str):raise ValueError('Invalid Apple Music link.')
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
    from urllib.parse import urlencode, urlsplit, parse_qs
    from songranker.developer.catalog_sources import (offer, catalogue_matches, store_code)
    query=request.args.get('q','').strip()
    if not query:return jsonify([])
    try:
        country=store_code(request.args.get('country','gb'))
        if 'music.apple.com' in query:
            url=apple_lookup_url(query)
            country=parse_qs(urlsplit(url).query).get('country',['us'])[0]
        else:
            url='https://itunes.apple.com/search?'+urlencode(dict(term=query,media='music',entity='song',
                                                                 limit=100,explicit='Yes',country=country))
        response=apple_lookup(url);results=[];seen=set()
        for track in response.get('results',[]):
            if not isinstance(track,dict) or not isinstance(track.get('trackName'),str) or not track['trackName'].strip() or track.get('kind','song')!='song':continue
            try:row=offer(track,country)
            except (ValueError,TypeError):continue
            track_id=row['source']['track_id']
            if track_id not in seen:results.append(row);seen.add(track_id)
        conn=get_db_connection()
        try:
            conn.execute('BEGIN')
            return jsonify(catalogue_matches(conn,results))
        finally:conn.close()
    except AppleRequestError as exc:return exc.response()
    except ValueError as exc:return jsonify(message=str(exc)),400


def verified_song_source(data):
    """Resolve signed offers or older Apple fields; never discard source intent."""
    from songranker.developer.catalog_sources import (unpack, observation, identifier, store_code)
    from urllib.parse import urlsplit, parse_qs, urlencode
    import time
    if 'source_token' in data:
        return unpack(data['source_token'])
    source=data.get('source')
    if source is not None and not isinstance(source,dict):
        raise ValueError('Choose an Apple search result or an exact Apple song link.')
    source=source or {}
    id_fields=[(source,'track_id'),*( (data,key) for key in ('apple_track_id','apple_id','trackId') )]
    has_id=any(key in fields for fields,key in id_fields)
    raw_id=next((fields[key] for fields,key in id_fields if key in fields),None)
    link_fields=[(source,'track_url'),*( (data,key) for key in ('apple_url','track_url','trackViewUrl') )]
    has_link=any(key in fields for fields,key in link_fields)
    link=next((fields[key] for fields,key in link_fields if key in fields),None)
    title=str(data.get('title') or '').strip()
    if not link and 'music.apple.com' in title:link=title
    if not (source or has_id or has_link or link or data.get('import_source')=='apple'):
        return None
    track_id=identifier(raw_id) if raw_id is not None else None
    if has_id and not track_id:
        raise ValueError('Apple track ID is invalid. Search again or use an exact Apple song link.')
    country=store_code(source.get('storefront') or data.get('country') or 'gb')
    if link:
        url=apple_lookup_url(link)
        params=parse_qs(urlsplit(url).query)
        country=params.get('country',['us'])[0]
        # A track hint and a song link must identify the same recording.
        linked_id=(parse_qs(urlsplit(link).query).get('i') or [None])[0]
        if linked_id is None and '/song/' in urlsplit(link).path:
            linked_id=params['id'][0]
        if track_id and linked_id and track_id!=identifier(linked_id):
            raise ValueError('The Apple ID and song link differ. Choose the recording again.')
        track_id=track_id or identifier(linked_id)
    elif track_id:
        url='https://itunes.apple.com/lookup?'+urlencode(dict(id=track_id,entity='song',country=country))
    else:
        raise ValueError('Apple source details are missing. Search again before adding this song.')
    tracks=[t for t in apple_lookup(url).get('results',[]) if isinstance(t,dict)
            and t.get('trackName') and t.get('kind','song')=='song'
            and (track_id is None or identifier(t.get('trackId'))==track_id)]
    if len(tracks)!=1:
        raise ValueError('Use Apple Music search to choose an exact song from this release.')
    return dict(source=observation(tracks[0],country),observed_at=time.time())


def song_metadata(data):
    """Validate manual song fields and merge verified Apple metadata while retaining
    explicit edit intent.
    """
    if not isinstance(data,dict):raise ValueError('Send song fields as an object.')
    data={key:value for key,value in data.items() if not key.startswith('_')}
    supplied_date='release_date' in data;verified=verified_song_source(data)
    title=str(data.get('title') or '').strip()
    if verified:
        imported=verified['source']['metadata']
        genres=[g.strip() for g in (str(data.get('genres') or '')+','+imported['genres']).split(',') if g.strip()]
        retained={}
        for name in genres:retained.setdefault(name.casefold(),name)
        number=imported['track_number']
        if number is None and data.get('track_number') not in (None,''):number=data['track_number']
        data={**data,**imported,'genres':', '.join(retained.values()),'track_number':number}
        title=data['title'];supplied_date=True
    from songranker.storage.tag_limits import tag_names, check_count
    names=tag_names(data.get('genres'))
    check_count(len(names))
    data['genres']=', '.join(names)
    if not title:raise ValueError('Title is required.')
    release_date=str(data.get('release_date') or '').strip()
    if release_date:
        try:release_date=datetime.strptime(release_date,'%Y-%m-%d').date().isoformat()
        except ValueError:raise ValueError('Invalid release date.')
    return {**data,'title':title,'artist':str(data.get('artist') or '').strip(),
        'album':str(data.get('album') or '').strip() or f'{title} - Single',
        'cover_url':data.get('cover_url') or '','audio_url':data.get('audio_url') or '',
        'genres':str(data.get('genres') or '').strip(),'release_date':release_date,
        '_verified':verified,'_date_supplied':supplied_date,
        '_artist_names':[verified['source']['artist']] if verified else None}


def write_song(data, song_id=None):
    """Resolve metadata and check the final album slot in one transaction."""
    conn = get_db_connection()
    try:
        from songranker.developer.catalog_sources import (catalogue_matches, source_conflict, save_source, current_source, public_source, normalized, review_fingerprint, artist_names as source_artist_names)
        from songranker.developer.catalog_sources import single_title
        from songranker.developer.catalog_sources import remove_empty_album
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM songs WHERE id=?', (song_id,)).fetchone() if song_id is not None else None
        if song_id is not None and not old:
            conn.rollback()
            return jsonify({'message':'Song not found.'}), 404
        if data.get('_expected_source_fingerprint') and review_fingerprint(conn,song_id)!=data['_expected_source_fingerprint']:
            return jsonify(message='This song changed while you reviewed it. Open its source again.'),409
        verified=data.get('_verified')
        if verified:
            conflict=source_conflict(conn,song_id,verified['source'])
            if conflict:
                conn.rollback()
                if song_id is None:
                    saved=current_source(conn,conflict['song_id'])
                    return jsonify(status='success',already_present=True,song_id=conflict['song_id'],
                        source_id=saved['id'],source=public_source(saved['source']),
                        message='This Apple track is already in the library.')
                return jsonify(message=f"This Apple track is already linked to song #{conflict['song_id']}."),409
        number = parse_track_number(data.get('track_number', old['track_number'] if old else None))
        disc = parse_track_number(data.get('disc_number', old['disc_number'] if old else 1))
        if disc is None:raise ValueError('Disc number must be a positive whole number.')
        if song_id is None:
            probe=dict(title=data['title'],artist=data['artist'],source={'track_id':''})
            matches=catalogue_matches(conn,[probe])[0]['library_matches']
            if matches and data.get('allow_duplicate') is not True:
                conn.rollback()
                return jsonify(message='Matching titles already exist. Review the Apple version or choose Add separately.',library_matches=matches),409
        placement=data.get('placement','keep')
        if placement not in ('keep','single'):raise ValueError('Choose the original release or a Single.')
        if placement=='single':
            data={**data,'album':single_title(conn,data['title'],data['artist'],song_id)}
            number=None;disc=1
        date_for_album=data['release_date'] if old is None or data.get('_use_source_album') else None
        album_id = get_or_create_album(conn, data['album'], data['cover_url'], date_for_album)
        check_track_position(conn, album_id, number, song_id, disc)
        day=data['release_date'] if data.get('_date_supplied') else old['release_date'] if old else None
        origin=('apple' if verified else 'manual') if day else None
        if old and day==old['release_date']:origin=old['release_date_origin']
        artist_names=data.get('_artist_names')
        if verified:artist_names=source_artist_names(conn,verified['source']['artist'])
        if old and artist_names is None:
            previous=get_song_full(song_id,conn)
            if normalized(data['artist'])==normalized(previous['artist']):
                artist_names=[r[0] for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?',(song_id,))]
        if song_id is None:
            cursor = conn.execute('''INSERT INTO songs (title,album_id,audio_url,track_number,disc_number,elo_score,matches_played,release_date,release_date_origin)
                VALUES (?,?,?,?,?,1200,0,?,?)''', (data['title'],album_id,data['audio_url'],number,disc,day,origin))
            song_id = cursor.lastrowid
            message = f"Added '{data['title']}'"
        else:
            conn.execute('''UPDATE songs SET title=?,album_id=?,audio_url=?,track_number=?,disc_number=?,release_date=?,release_date_origin=? WHERE id=?''',
                (data['title'],album_id,data['audio_url'],number,disc,day,origin,song_id))
            conn.execute('DELETE FROM song_artists WHERE song_id=?',(song_id,))
            conn.execute('DELETE FROM song_genres WHERE song_id=?',(song_id,))
            message = 'Song updated successfully.'
        link_artists_to_song(conn, song_id, data['artist'], default_cover=data['cover_url'],artist_names=artist_names)
        link_genres_to_song(conn, song_id, data['genres'])
        source_id=save_source(conn,song_id,verified) if verified else None
        cleanup=None
        if old and old['album_id']!=album_id and data.get('remove_empty_album') is True:
            cleanup=remove_empty_album(conn,old['album_id'])
        conn.commit()
        return jsonify({'status':'success','message':message,'song_id':song_id,
                        'source_id':source_id,'source':public_source(verified['source']) if verified else None,
                        'album_cleanup':cleanup,
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
        data = song_metadata(request.get_json(silent=True))
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
        data = song_metadata(request.get_json(silent=True))
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
    """Keep vote facts, void their influence, remove links, then replay surviving ratings."""
    from songranker.modes.preferences import (void_song_votes, rebuild_ratings, PreferenceError)
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM songs WHERE id=?', (song_id,)).fetchone():
            return jsonify(message='Song not found.'), 404
        active = conn.execute("SELECT t.id FROM tournament_entries e JOIN tournaments t ON t.id=e.tournament_id WHERE e.song_id=? AND t.status='in_progress' LIMIT 1", (song_id,)).fetchone()
        if active:
            return jsonify(message=f"Finish or delete tournament #{active['id']} before deleting this song."), 409
        void_song_votes(conn, song_id)
        conn.execute('DELETE FROM song_artists WHERE song_id=?', (song_id,))
        conn.execute('DELETE FROM song_genres WHERE song_id=?', (song_id,))
        conn.execute('DELETE FROM trivia_rounds WHERE song_id=? AND run_id IS NULL', (song_id,))
        conn.execute('DELETE FROM trivia_adjustments WHERE song_id=?', (song_id,))
        conn.execute('DELETE FROM tournament_entries WHERE song_id=?', (song_id,))
        for column in ('song1_id','song2_id','winner_id','loser_id'):
            conn.execute(f'UPDATE tournament_matches SET {column}=NULL WHERE {column}=?', (song_id,))
        for column in ('champion_id','runner_up_id','third_place_id','fourth_place_id'):
            conn.execute(f'UPDATE tournaments SET {column}=NULL WHERE {column}=?', (song_id,))
        conn.execute('DELETE FROM songs WHERE id=?', (song_id,))
        rebuild_ratings(conn)
        conn.commit()
        return jsonify(status='success', message='Song removed. Its saved votes remain in the correction history; surviving ratings were rebuilt.', backup=None)
    except PreferenceError as error:
        conn.rollback()
        return jsonify(message=str(error)), error.status
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def edit_catalogue_record(table, record_id, fields):
    """Validate editable entity fields and always release the database connection."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message='Send catalogue fields as an object.'), 400
    title = fields[0]
    if not isinstance(data.get(title), str) or not data[title].strip():
        return jsonify(message='A name is required.'), 400
    values = {}
    for key in fields:
        value = data.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, str):
            return jsonify(message=f'{key.replace("_", " ").capitalize()} must be text.'), 400
        values[key] = value.strip()
    if table == 'albums' and 'shelves_excluded' in data:
        if type(data['shelves_excluded']) is not bool:
            return jsonify(message='Album Shelves exclusion must be true or false.'), 400
        values['shelves_excluded'] = int(data['shelves_excluded'])
    if 'description' in values and len(values['description']) > 2000:
        return jsonify(message='Tag info must be text, up to 2,000 characters.'), 400
    day = values.get('release_date')
    if day:
        try:
            values['release_date'] = datetime.strptime(day, '%Y-%m-%d').date().isoformat()
        except ValueError:
            return jsonify(message='Invalid release date.'), 400
    # Table/column names come only from the fixed route definitions below.
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute(f'SELECT 1 FROM {table} WHERE id=?', (record_id,)).fetchone():
            return jsonify(message='Record not found.'), 404
        if table == 'genres':
            if conn.execute('SELECT 1 FROM genres WHERE LOWER(name)=LOWER(?) AND id!=?',
                            (values['name'], record_id)).fetchone():
                return jsonify(message='Tag already exists.'), 400
            if data.get('description') is None:
                values.pop('description', None)
        assignments = ', '.join(key + '=?' for key in values)
        conn.execute(f'UPDATE {table} SET {assignments} WHERE id=?', (*values.values(), record_id))
        conn.commit()
        return jsonify(status='success', message='Catalogue record updated.')
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify(message='This change conflicts with an existing catalogue record.'), 409
    finally:
        conn.close()


@app.route('/api/dev/edit_artist/<int:artist_id>', methods=['POST'])
@admin_required
def api_edit_artist(artist_id):
    return edit_catalogue_record('artists', artist_id, ('name', 'cover_url'))


def delete_catalogue_record(table, record_id):
    """Remove an entity and its catalogue links, preserving referenced game facts."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute(f'SELECT 1 FROM {table} WHERE id=?', (record_id,)).fetchone():
            return jsonify(message='Record not found.'), 404
        if table == 'albums':
            conn.execute('UPDATE songs SET album_id=NULL WHERE album_id=?', (record_id,))
        else:
            links, column = ('song_artists', 'artist_id') if table == 'artists' else ('song_genres', 'genre_id')
            conn.execute(f'DELETE FROM {links} WHERE {column}=?', (record_id,))
        conn.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))
        conn.commit()
        return jsonify(status='success', message='Catalogue record deleted.')
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify(message='This record is still referenced. Review its saved results before deleting it.'), 409
    finally:
        conn.close()


@app.route('/api/dev/delete_artist/<int:artist_id>', methods=['DELETE'])
@admin_required
def api_delete_artist(artist_id):
    return delete_catalogue_record('artists', artist_id)


@app.route('/api/dev/edit_album/<int:album_id>', methods=['POST'])
@admin_required
def api_edit_album(album_id):
    return edit_catalogue_record('albums', album_id, ('title', 'cover_url', 'release_date'))


@app.route('/api/dev/delete_album/<int:album_id>', methods=['DELETE'])
@admin_required
def api_delete_album(album_id):
    return delete_catalogue_record('albums', album_id)


@app.route('/api/dev/edit_genre/<int:genre_id>', methods=['POST'])
@admin_required
def api_edit_genre(genre_id):
    return edit_catalogue_record('genres', genre_id, ('name', 'description'))


@app.route('/api/dev/delete_genre/<int:genre_id>', methods=['DELETE'])
@admin_required
def api_delete_genre(genre_id):
    return delete_catalogue_record('genres', genre_id)


@app.route('/api/dev/overview', methods=['GET'])
@admin_required
def api_dev_overview():
    # Keep the older response shape; inventory and backup discovery have one owner.
    from songranker.developer.dev_system import inventory, backups
    state = inventory()
    return jsonify(counts={row['name']:row['rows'] for row in state['inventory']},
                   schema_version=state['schema'], integrity=state['integrity'],
                   foreign_key_errors=state['foreign_key_errors'],
                   backups=[dict(row, size=row['bytes']) for row in backups()])


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
    from songranker.developer.dev_system import restore_database
    return restore_database()


@app.route('/api/dev/reset-preview', methods=['GET'])
@admin_required
def api_dev_reset_preview():
    conn=get_db_connection()
    keep={k:conn.execute(q).fetchone()[0] for k,q in {
        'songs':'SELECT COUNT(*) FROM songs','artists':'SELECT COUNT(*) FROM artists','albums':'SELECT COUNT(*) FROM albums','genres':'SELECT COUNT(*) FROM genres',
        'song_artist_links':'SELECT COUNT(*) FROM song_artists','song_genre_links':'SELECT COUNT(*) FROM song_genres'}.items()}
    clear={k:conn.execute(q).fetchone()[0] for k,q in {
        'votes_and_history':'SELECT COUNT(*) FROM history','trivia_stats':'SELECT COUNT(*) FROM trivia_stats','tournaments':'SELECT COUNT(*) FROM tournaments',
        'tournament_matches':'SELECT COUNT(*) FROM tournament_matches','trivia_rounds':'SELECT COUNT(*) FROM trivia_rounds','elo_guesses':'SELECT COUNT(*) FROM elo_guess_rounds WHERE completed_at IS NOT NULL','vibe_songs':"SELECT COUNT(DISTINCT song_id) FROM song_vibe_positions WHERE status!='unmapped'",'shelf_rounds':'SELECT COUNT(*) FROM album_shelf_rounds WHERE completed_at IS NOT NULL'}.items()}
    conn.close(); return jsonify({'keep':keep,'clear':clear})


def reset_competition_data(scope):
    """Keep the library and reset only the requested competition records."""
    conn=None
    try:
        conn=get_db_connection()
        conn.execute('BEGIN IMMEDIATE')
        from songranker.storage.competition_reset import reset_results
        reset_results(conn,scope)
        conn.commit()
        if scope in ('all','trivia'):
            for key in ('trivia_score','trivia_streak','trivia_round_token','trivia_scoring_version'):
                session.pop(key,None)
        if scope in ('all','guesser'):session.pop('guess_token',None)
        if scope in ('all','shelves'):session.pop('shelf_token',None)
        labels={'vibe':'Vibe Map selections','guesser':'Elo Guesser history','shelves':'Album Shelves history','all':'All competition data','matches':'Elo and match history','trivia':'Trivia history and records','tournaments':'Tournament history and records'}
        return jsonify(status='success',message=labels[scope]+' reset. Music library kept.',backup=None)
    except Exception:
        if conn:conn.rollback()
        app.logger.exception('Competition reset failed')
        return jsonify(message='Could not reset these records.'),500
    finally:
        if conn:conn.close()


@app.route('/api/dev/reset-history/<scope>',methods=['POST'])
@admin_required
def api_dev_reset_history(scope):
    if scope not in ('matches','trivia','tournaments','guesser','shelves','vibe'):
        return jsonify(message='Choose match, trivia, tournament, Elo Guesser, Album Shelves or Vibe Map data.'),400
    phrases={'vibe':'RESET VIBE','guesser':'RESET GUESSER','shelves':'RESET SHELVES','matches':'RESET MATCHES','trivia':'RESET TRIVIA','tournaments':'RESET TOURNAMENTS'}
    if json_fields().get('confirmation')!=phrases[scope]:
        return jsonify(message='Type '+phrases[scope]+' to confirm.'),400
    return reset_competition_data(scope)


@app.route('/api/dev/special-round/<mode>/<int:round_id>',methods=['POST'])
@admin_required
def delete_special_round(mode,round_id):
    table={'guesser':'elo_guess_rounds','shelves':'album_shelf_rounds'}.get(mode)
    if not table:return jsonify(message='Unknown mode.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if mode=='guesser' and conn.execute('SELECT 1 FROM elo_guess_rounds WHERE id=? AND run_id IS NOT NULL',(round_id,)).fetchone():
            return jsonify(message='This answer belongs to a challenge run. Reset Elo Guesser history to remove challenge runs.'),409
        deleted=conn.execute(f'DELETE FROM {table} WHERE id=?',(round_id,)).rowcount
        if not deleted:return jsonify(message='Round not found.'),404
        conn.commit()
        return jsonify(message='Round deleted. Other modes and music kept.',backup=None)
    finally:conn.close()


@app.route('/api/dev/reset-database', methods=['POST'])
@admin_required
def api_dev_reset_database():
    if json_fields().get('confirmation') != 'RESET COMPETITION':
        return jsonify(message='Type RESET COMPETITION to confirm.'),400
    return reset_competition_data('all')


@app.route('/api/dev/elo-correction', methods=['POST'])
@admin_required
def api_dev_elo_correction():
    from songranker.modes.preferences import (override_rating, PreferenceError)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message='Submit a valid rating correction.'), 400
    conn = get_db_connection()
    try:
        return jsonify(override_rating(conn, data))
    except PreferenceError as error:
        return jsonify(message=str(error)), error.status
    finally:
        conn.close()


@app.route('/api/dev/preferences', methods=['GET'])
@admin_required
def api_dev_preferences():
    from songranker.modes.preferences import event_detail
    limit = min(50, max(1, request.args.get('limit', 25, type=int)))
    offset = min(2147483647, max(0, request.args.get('offset', 0, type=int)))
    conn = get_db_connection()
    try:
        rows = conn.execute('SELECT id FROM preference_events ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        items = []
        for row in rows:
            detail = event_detail(conn, row['id'])
            effective = detail['effective']
            items.append({'id': row['id'], 'created_at': effective['created_at'], 'mode': effective['mode'],
                'active': bool(effective['active']), 'revision': effective['revision'], 'songs': detail['songs'],
                'winner_id': effective['winner_id'], 'correctable': detail['correctable'],
                'origin': effective['origin'], 'rating_weight': effective['rating_weight'],
                'tournament_id': effective['tournament_id']})
        return jsonify(items=items, total=conn.execute('SELECT COUNT(*) FROM preference_events').fetchone()[0], offset=offset, limit=limit)
    finally:
        conn.close()


@app.route('/api/dev/preferences/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def api_dev_preference(event_id):
    from songranker.modes.preferences import (event_detail, correct_vote, PreferenceError)
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            return jsonify(event_detail(conn, event_id))
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(message='Submit a valid vote correction.'), 400
        return jsonify(correct_vote(conn, event_id, data))
    except PreferenceError as error:
        return jsonify(message=str(error)), error.status
    finally:
        conn.close()


@app.route('/api/dev/trivia/<int:song_id>', methods=['POST', 'DELETE'])
@admin_required
def api_dev_edit_trivia(song_id):
    conn = get_db_connection()
    if not conn.execute('SELECT id FROM songs WHERE id=?', (song_id,)).fetchone():
        conn.close(); return jsonify({'status': 'error', 'message': 'Song not found.'}), 404
    if request.method == 'DELETE':
        if conn.execute('SELECT 1 FROM trivia_rounds WHERE song_id=? AND run_id IS NOT NULL',(song_id,)).fetchone():
            conn.close()
            return jsonify(message='This track belongs to a challenge run. Edit field totals to adjust recognisability, or reset Trivia history to remove runs.'),409
        conn.execute('DELETE FROM trivia_rounds WHERE song_id=?', (song_id,))
        conn.execute('DELETE FROM trivia_adjustments WHERE song_id=?',(song_id,))

        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': 'Trivia statistics deleted for this song.'})
    from songranker.modes.trivia import edit_trivia_totals
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
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT id FROM tournaments WHERE id=?',(tournament_id,)).fetchone():
            return jsonify({'message':'Tournament not found.'}),404
        from songranker.modes.preferences import void_tournament_preferences
        void_tournament_preferences(conn, tournament_id)
        conn.execute('DELETE FROM tournament_matches WHERE tournament_id=?',(tournament_id,))
        conn.execute('DELETE FROM tournament_entries WHERE tournament_id=?',(tournament_id,))
        conn.execute('DELETE FROM tournaments WHERE id=?',(tournament_id,))
        conn.execute("UPDATE songs SET tournament_wins=(SELECT COUNT(*) FROM tournaments t WHERE t.champion_id=songs.id AND t.status='completed')")
        conn.commit()
        return jsonify({'status':'success','message':'Tournament deleted. Its first-round Elo influence was removed; original preference facts are retained.'})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not delete tournament')
        return jsonify(message='Could not delete this tournament.'),500
    finally:
        conn.close()


@app.route('/api/dev/sync', methods=['POST'])
@admin_required
def api_sync():
    from songranker.developer.dev_system import upload_database
    return upload_database()


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
    from songranker.developer.dev_tags import identifiers
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(message='Send a bulk change as an object.'),400
    conn=get_db_connection()
    try:
        ids=identifiers(data.get('song_ids'),'Songs',maximum=500)
        conn.execute('BEGIN IMMEDIATE')
        placeholders=','.join('?' for _ in ids)
        rows=conn.execute(f'SELECT id,title,album_id,disc_number,track_number FROM songs WHERE id IN ({placeholders})',ids).fetchall()
        if len(rows)!=len(ids): raise ValueError('One of the selected songs no longer exists.')
        action=data.get('action')
        if action=='move_album':
            album_id=data.get('album_id')
            if type(album_id) is not int or album_id<=0:raise ValueError('Choose an existing album.')
            if type(data.get('clear_track_numbers',False)) is not bool:raise ValueError('Choose whether to clear track numbers.')
            if not conn.execute('SELECT 1 FROM albums WHERE id=?',(album_id,)).fetchone(): raise ValueError('Choose an existing album.')
            clear=data.get('clear_track_numbers') is True
            target_disc=parse_track_number(data.get('disc_number'))
            occupied={(r['disc_number'],r['track_number']):r['title'] for r in conn.execute(f'SELECT title,disc_number,track_number FROM songs WHERE album_id=? AND id NOT IN ({placeholders}) AND track_number IS NOT NULL',[album_id]+ids)}
            if not clear:
                for row in rows:
                    n=row['track_number'];position=(target_disc or row['disc_number'],n)
                    if n is not None and position in occupied: raise ValueError(f"Disc {position[0]}, track {n} conflicts: {row['title']} / {occupied[position]}. Choose another disc, clear track numbers or edit positions first.")
                    if n is not None: occupied[position]=row['title']
            # Release positions first, then restore them atomically in the destination.
            conn.execute(f'UPDATE songs SET track_number=NULL WHERE id IN ({placeholders})',ids)
            for row in rows:
                conn.execute('UPDATE songs SET album_id=?,disc_number=?,track_number=? WHERE id=?',(album_id,target_disc or row['disc_number'],None if clear else row['track_number'],row['id']))
        elif action in ('add_tags','remove_tags'):
            tags=identifiers(data.get('tag_ids'),'Tags',maximum=500)
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
    data=json_fields()
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
    data=json_fields();conn=get_db_connection()
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
