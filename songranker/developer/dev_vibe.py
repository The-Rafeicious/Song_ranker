"""Authenticated Vibe Map maintenance; catalogue and preference facts stay separate."""
import hashlib
import json
import math
import time
from flask import jsonify,request
from songranker.services import app,admin_required,get_db_connection
from songranker.vibe_maps import map_definitions
from songranker.storage.vibe_state import MAPS
from songranker.storage.competition_reset import reset_vibes

KEYS={m[0] for m in MAPS}


def record(conn,song_id):
    song=conn.execute('SELECT id,title FROM songs WHERE id=?',(song_id,)).fetchone()
    if song is None:raise LookupError('Song not found.')
    rows=[dict(r) for r in conn.execute('SELECT * FROM song_vibe_positions WHERE song_id=? ORDER BY map_id',(song_id,))]
    progress=conn.execute('SELECT completed_passes FROM song_vibe_progress WHERE song_id=?',(song_id,)).fetchone()
    rounds=[dict(r) for r in conn.execute('SELECT * FROM vibe_rounds WHERE song_id=? ORDER BY owner_hash',(song_id,))]
    fingerprint=hashlib.sha256(json.dumps([rows,list(progress) if progress else None,rounds],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(song=dict(song),maps=[dict(m,**next(r for r in rows if r['map_id']==m['id'])) for m in map_definitions(conn)],
                completed_passes=progress[0],version=fingerprint,active_rounds=sum(r['status']=='active' for r in rounds))


def count(value,label):
    if type(value) is not int or not 0<=value<=1000000:raise ValueError(label+' must be a whole number from 0 to 1000000.')
    return value


def coordinate(value):
    if type(value) not in (float,int) or not math.isfinite(value) or not -5<=value<=5:
        raise ValueError('Coordinates must be finite numbers from -5 to 5.')
    return round(value,2)/5


def edit_record(conn,song_id,data,delete=False):
    current=record(conn,song_id)
    if data.get('version')!=current['version']:raise RuntimeError('Vibe data changed. Reload the song before editing.')
    if delete:
        if data.get('confirmation')!='DELETE VIBE':raise ValueError('Type DELETE VIBE to confirm.')
        reset_vibes(conn,song_id)
    else:
        maps=data.get('maps')
        if not isinstance(maps,dict) or set(maps)!=KEYS:raise ValueError('Provide all four maps.')
        parsed=[]
        for key in sorted(KEYS):
            point=maps[key]
            if not isinstance(point,dict):raise ValueError('Invalid map.')
            state=point.get('status');samples=count(point.get('sample_count'),'Samples');skips=count(point.get('not_applicable_count'),'Skipped samples')
            if state=='unmapped':
                if samples or skips:raise ValueError('An unplaced map must have zero samples.')
                x=y=updated=None
            elif state=='placed':
                if samples<1:raise ValueError('A placed map needs at least one sample.')
                x,y=coordinate(point.get('x')),coordinate(point.get('y'));updated=time.time()
                old=next(m for m in current['maps'] if m['id']==key)
                if old['status']=='placed':
                    if round(old['x']*5,2)==round(point['x'],2):x=old['x']
                    if round(old['y']*5,2)==round(point['y'],2):y=old['y']
            elif state=='not_applicable':
                if samples or not skips:raise ValueError('A skipped map needs skipped samples only.')
                x=y=None;updated=time.time()
            else:raise ValueError('Choose placed, unplaced or skipped.')
            parsed.append((x,y,state,updated,samples,skips,song_id,key))
        passes=count(data.get('completed_passes'),'Completed passes')
        if passes>min(row[4]+row[5] for row in parsed):raise ValueError('Completed passes cannot exceed the sample count of any map.')
        # Discard pending contributions before replacing averaged points.
        conn.execute('DELETE FROM vibe_rounds WHERE song_id=?',(song_id,))
        conn.executemany('UPDATE song_vibe_positions SET x=?,y=?,status=?,updated_at=?,sample_count=?,not_applicable_count=? WHERE song_id=? AND map_id=?',parsed)
        conn.execute('UPDATE song_vibe_progress SET completed_passes=? WHERE song_id=?',(passes,song_id))
    return record(conn,song_id)


@app.get('/api/dev/vibe')
@admin_required
def vibe_records():
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        query=request.args.get('q','').strip()[:200]
        try:offset=max(0,int(request.args.get('offset','0')))
        except ValueError:return jsonify(message='Invalid page.'),400
        if offset>10000000:return jsonify(message='Invalid page.'),400
        term='%'+query+'%'
        where=" WHERE (s.title LIKE ? OR CAST(s.id AS TEXT)=? OR a.title LIKE ? OR EXISTS(SELECT 1 FROM song_artists sa JOIN artists ar ON ar.id=sa.artist_id WHERE sa.song_id=s.id AND ar.name LIKE ?))"
        params=(term,query,term,term)
        total=conn.execute('SELECT COUNT(*) FROM songs s LEFT JOIN albums a ON a.id=s.album_id'+where,params).fetchone()[0]
        rows=[dict(r) for r in conn.execute('''SELECT s.id,s.title,a.title AS album,p.completed_passes,
            (SELECT COUNT(*) FROM song_vibe_positions v WHERE v.song_id=s.id AND v.status='placed') AS placed
            FROM songs s LEFT JOIN albums a ON a.id=s.album_id JOIN song_vibe_progress p ON p.song_id=s.id'''+where+' ORDER BY placed DESC,s.id LIMIT 30 OFFSET ?',(*params,offset))]
        return jsonify(items=rows,total=total,offset=offset,limit=30)
    finally:conn.close()


@app.route('/api/dev/vibe/<int:song_id>',methods=['GET','POST','DELETE'])
@admin_required
def vibe_record(song_id):
    conn=get_db_connection()
    try:
        conn.execute('BEGIN' if request.method=='GET' else 'BEGIN IMMEDIATE')
        if request.method=='GET':return jsonify(record(conn,song_id))
        data=request.get_json(silent=True)
        if not isinstance(data,dict):raise ValueError('Provide a JSON object.')
        result=edit_record(conn,song_id,data,request.method=='DELETE')
        conn.commit()
        return jsonify(**result,message='Vibe data deleted.' if request.method=='DELETE' else 'Vibe data saved. Pending rounds for this song cleared.')
    except LookupError as error:return jsonify(message=str(error)),404
    except RuntimeError as error:return jsonify(message=str(error)),409
    except ValueError as error:return jsonify(message=str(error)),400
    finally:conn.close()
