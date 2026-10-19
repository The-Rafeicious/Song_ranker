"""Authenticated import/source review, album inspection and atomic Singles moves."""
import os
from flask import jsonify,request

from songranker.services import (app, admin_required, get_db_connection, get_song_full, create_database_backup, get_or_create_album)
from songranker.developer.catalog_sources import (current_source, public_source, source_summaries, unpack, save_source, review_fingerprint)
from songranker.developer.catalog_operations import (single_plan, remove_empty_album)


@app.route('/api/dev/song-sources')
@admin_required
def song_sources():
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        return jsonify(songs=source_summaries(conn))
    finally:conn.close()


@app.route('/api/dev/song-source/<int:song_id>',methods=['GET','POST'])
@admin_required
def song_source(song_id):
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE' if request.method=='POST' else 'BEGIN')
        song=get_song_full(song_id,conn)
        if not song:return jsonify(message='Song not found.'),404
        fingerprint=review_fingerprint(conn,song_id)
        if request.method=='GET':
            saved=current_source(conn,song_id)
            return jsonify(song=dict(song),fingerprint=fingerprint,source_id=saved['id'] if saved else None,
                current=dict(public_source(saved['source']),observed_at=saved['observed_at'],title=saved['source'].get('title') or song['title'],artist=saved['source'].get('artist') or song['artist']) if saved else None,
                history=[])  # Compatibility field; only the current source is stored.
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(message='Choose a reviewed Apple result.'),400
        if data.get('fingerprint')!=fingerprint:return jsonify(message='This song changed. Review its source again.'),409
        for key in ('refresh_metadata','use_source_album'):
            if key in data and type(data[key]) is not bool:return jsonify(message='Choose which source fields to use.'),400
        verified=unpack(data.get('source_token'))
        if data.get('use_source_album') and not data.get('refresh_metadata'):
            return jsonify(message='Choose a metadata refresh to use the source album.'),400
        if data.get('refresh_metadata'):
            from songranker.developer.dev import (song_metadata, write_song)
            payload=song_metadata(dict(source_token=data['source_token'],genres=song['genres']))
            if not data.get('use_source_album'):
                payload.update(album=song['album'] or f"{song['title']} - Single",track_number=song['track_number'])
            payload.update(_expected_source_fingerprint=fingerprint,_source_refresh=True,
                           _use_source_album=data.get('use_source_album') is True,remove_empty_album=True)
            conn.rollback();conn.close();conn=None
            return write_song(payload,song_id)
        source_id=save_source(conn,song_id,verified)
        conn.commit()
        return jsonify(status='success',song_id=song_id,source_id=source_id,source=public_source(verified['source']),
            message='Apple source saved. Local names, preview and placement kept.')
    except ValueError as error:
        if conn:conn.rollback()
        return jsonify(message=str(error)),400
    finally:
        if conn:conn.close()


@app.route('/api/dev/song-sources/bulk',methods=['POST'])
@admin_required
def bulk_song_sources():
    """Apply only explicitly reviewed identities, atomically, without catalogue edits."""
    data=request.get_json(silent=True)
    changes=data.get('changes') if isinstance(data,dict) else None
    if not isinstance(changes,list) or not 1<=len(changes)<=500:
        return jsonify(message='Review between 1 and 500 song sources.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        reviewed=[];songs=set();tracks=set()
        for change in changes:
            if not isinstance(change,dict) or type(change.get('song_id')) is not int or change['song_id']<=0:
                raise ValueError('Each reviewed source needs a song ID.')
            song_id=change['song_id']
            if song_id in songs:raise ValueError('A song can only have one selected source.')
            songs.add(song_id)
            fingerprint=review_fingerprint(conn,song_id)
            if fingerprint is None:return jsonify(message=f'Song #{song_id} no longer exists. Review the group again.'),409
            if change.get('fingerprint')!=fingerprint:
                return jsonify(message=f'Song #{song_id} changed. Review its source again; nothing was saved.'),409
            verified=unpack(change.get('source_token'))
            track=verified['source']['track_id']
            if track in tracks:raise ValueError('The same Apple recording cannot be chosen for two songs.')
            tracks.add(track);reviewed.append((song_id,verified))
        # Every selected song has a reviewed replacement and track IDs are unique.
        # Ignore their old identities so a wrongly assigned pair can be exchanged;
        # links held by songs outside this group still cause a complete rollback.
        results=[]
        for song_id,verified in reviewed:
            source_id=save_source(conn,song_id,verified,replacing=songs)
            results.append(dict(song_id=song_id,source_id=source_id,source=public_source(verified['source'])))
        conn.commit()
        return jsonify(status='success',songs=results,count=len(results),backup=None,
            message=f'{len(results)} song sources saved. Local metadata and placement kept.')
    except ValueError as error:
        conn.rollback();return jsonify(message=str(error)),400
    finally:conn.close()


@app.route('/api/dev/album-tracks/<int:album_id>')
@admin_required
def album_tracks(album_id):
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        album=conn.execute('SELECT * FROM albums WHERE id=?',(album_id,)).fetchone()
        if not album:return jsonify(message='Album not found.'),404
        songs=[dict(r) for r in conn.execute('''SELECT id,title,track_number,audio_url,release_date,release_date_origin
            FROM songs WHERE album_id=? ORDER BY track_number IS NULL,track_number,title COLLATE NOCASE,id''',(album_id,))]
        summaries=source_summaries(conn)
        for song in songs:song['source_summary']=summaries[song['id']]
        return jsonify(album=dict(album),songs=songs)
    finally:conn.close()


@app.route('/api/dev/single/<int:song_id>',methods=['GET','POST'])
@admin_required
def song_single(song_id):
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE' if request.method=='POST' else 'BEGIN')
        plan=single_plan(conn,song_id)
        if not plan:return jsonify(message='Song not found.'),404
        if request.method=='GET':return jsonify(plan)
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('remove_empty_album',True)) is not bool:
            return jsonify(message='Review the Singles move first.'),400
        if plan['already_single']:
            return jsonify(status='success',song_id=song_id,message='This song is already in a Single.',already_single=True)
        if data.get('fingerprint')!=plan['fingerprint']:
            return jsonify(message='The song or albums changed. Review the move again.'),409
        album=plan['source_album']
        destination=get_or_create_album(conn,plan['destination_title'],album['cover_url'] if album else None,plan['release_date'])
        conn.execute('UPDATE songs SET album_id=?,track_number=NULL,release_date=?,release_date_origin=? WHERE id=?',
            (destination,plan['release_date'] or None,plan['release_date_origin'],song_id))
        cleanup=remove_empty_album(conn,album['id']) if album and data.get('remove_empty_album',True) else dict(removed=False,reason='Previous album kept.')
        conn.commit()
        return jsonify(status='success',song_id=song_id,album_id=destination,release_date=plan['release_date'],
            album_cleanup=cleanup,message='Moved to a hidden Single. Song ID, game records and release date kept.',backup=None)
    except ValueError as error:
        conn.rollback();return jsonify(message=str(error)),400
    finally:conn.close()
