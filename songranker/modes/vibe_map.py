"""Continuous Vibe Map rounds, resumable drafts and compact aggregate results."""
import json
import math
import secrets
import time
from flask import jsonify, request, session

from songranker.services import app, get_db_connection, get_song_full
from songranker.modes.preferences import transaction, owner_hash, snapshot_song
from songranker.modes.selection_data import vibe_song
from songranker.storage.vibe_state import MAPS, VIBE_MAP_VERSION
from songranker.vibe_maps import map_definitions, song_profiles, pass_counts

READJUST_SECONDS = 5
SCALE = 5
KEYS = tuple(values[0] for values in MAPS)


class VibeError(ValueError):
    def __init__(self, message, code='invalid', status=400, **details):
        super().__init__(message);self.code=code;self.status=status;self.details=details


def identifier(value):
    if not isinstance(value,str) or not value.strip() or len(value)>96:
        raise VibeError('A nonempty request_id of at most 96 characters is required.')
    return value


def revision(value):
    if type(value) is not int or not 0<=value<2**63:
        raise VibeError('A valid round revision is required.')
    return value


def placement(data):
    status=data.get('status','placed')
    if status=='not_applicable':
        if data.get('x') is not None or data.get('y') is not None:
            raise VibeError('Not-applicable maps cannot contain coordinates.')
        return status,None,None
    if status!='placed':raise VibeError('Choose a placement or not applicable.')
    values=[]
    for key in ('x','y'):
        value=data.get(key)
        if (isinstance(value,bool) or not isinstance(value,(int,float)) or
            not -SCALE<=value<=SCALE or not math.isfinite(value)):
            raise VibeError('Both coordinates must be finite numbers between -5 and 5.')
        values.append(value/SCALE)
    return status,*values


def public_point(point):
    return dict(status=point['status'],
        x=point['x']*SCALE if point['x'] is not None else None,
        y=point['y']*SCALE if point['y'] is not None else None,
        display_x=round(point['x']*SCALE,2) if point['x'] is not None else None,
        display_y=round(point['y']*SCALE,2) if point['y'] is not None else None)


def radar(points):
    """Eight labelled spokes preserve both axes of all four independent maps."""
    result=[]
    for key,title,x_low,x_high,y_low,y_high in MAPS:
        point=points.get(key,{})
        for axis,low,high in (('x',x_low,x_high),('y',y_low,y_high)):
            value=point.get(axis) if point.get('status')=='placed' else None
            result.append(dict(key=key+'_'+axis,map_id=key,map_title=title,axis=axis,
                low=low,high=high,value=round(value*SCALE,2) if value is not None else None,
                radius=(value+1)/2 if value is not None else None))
    return dict(spokes=result,radius_min=0,radius_max=1,neutral_radius=.5,
                description='Descriptive axes, not quality or performance scores.')


def profile(conn, song_id):
    if type(song_id) is not int or not 0<song_id<2**63:raise VibeError('A positive song ID is required.')
    if not conn.execute('SELECT 1 FROM songs WHERE id=?',(song_id,)).fetchone():
        raise VibeError('Song no longer exists.','missing_song',404)
    points=song_profiles(conn,[song_id])[song_id]
    return dict(song_id=song_id,completed_passes=pass_counts(conn,[song_id])[song_id],
        maps={key:dict(public_point(p),sample_count=p['sample_count'],updated_at=p['updated_at'],
                      not_applicable_count=p['not_applicable_count']) for key,p in points.items()},
        radar=radar(points))


def current(conn, owner):
    return conn.execute('SELECT * FROM vibe_rounds WHERE owner_hash=?',(owner_hash(owner),)).fetchone()


def payload(conn, row, now=None):
    if row is None:return dict(round=None,version=VIBE_MAP_VERSION)
    now=time.time() if now is None else now
    answers=json.loads(row['answers'])
    definitions=map_definitions(conn)
    for definition in definitions:
        definition.update(min=-SCALE,max=SCALE,step=None,display_decimals=2)
    song=get_song_full(row['song_id'],conn)
    result=dict(version=VIBE_MAP_VERSION,token=row['token'],song=snapshot_song(conn,song),
        status=row['status'],revision=row['revision'],map_index=row['map_index'],
        maps=definitions,current_map=definitions[row['map_index']] if row['status']=='active' else None,
        readjust_seconds=READJUST_SECONDS,server_time=now,
        draft=None,advance_at=None,remaining_ms=None,
        saved_maps=[dict(map_id=key,**public_point(answers[key])) for key in KEYS if key in answers])
    if row['draft_status'] is not None:
        result['draft']=dict(public_point(dict(status=row['draft_status'],x=row['draft_x'],y=row['draft_y'])),
                             request_id=row['draft_key'])
        result['advance_at']=row['draft_at']+READJUST_SECONDS
        result['remaining_ms']=max(0,math.ceil((result['advance_at']-now)*1000))
    if row['status']=='complete':
        result['summary']=dict(selection_radar=radar(answers),aggregate=profile(conn,row['song_id']))
    return dict(round=result,version=VIBE_MAP_VERSION)


def require_round(conn,owner,data):
    row=current(conn,owner)
    if not row or not isinstance(data.get('token'),str) or not secrets.compare_digest(row['token'].encode(),data['token'].encode()):
        raise VibeError('This round is no longer current in this browser. Reload its state.','stale_round',409)
    return row


def require_stage(row,data):
    if row['status']!='active':raise VibeError('This round has ended.','ended',409)
    if data.get('map_id')!=KEYS[row['map_index']]:
        raise VibeError('Save the current map before advancing.','wrong_map',409)
    if revision(data.get('revision'))!=row['revision']:
        raise VibeError('This placement was changed in another request. Reload its state.','stale_revision',409)


def start(conn,owner,data):
    with transaction(conn):
        old=current(conn,owner)
        if old and (old['status']=='active' or data.get('previous_token') is None):
            return payload(conn,old)
        if old and data.get('previous_token')!=old['token']:
            raise VibeError('The previous round changed. Reload its state.','stale_round',409)
        chosen=vibe_song(conn,previous=old['song_id'] if old else None)
        if chosen is None:raise VibeError('Add songs before starting Vibe Map.','empty_library',409)
        conn.execute('DELETE FROM vibe_rounds WHERE owner_hash=?',(owner_hash(owner),))
        conn.execute('INSERT INTO vibe_rounds(owner_hash,token,song_id,started_at) VALUES(?,?,?,?)',
            (owner_hash(owner),secrets.token_urlsafe(32),chosen['id'],time.time()))
        return payload(conn,current(conn,owner))


def draft(conn,owner,data):
    with transaction(conn):
        row=require_round(conn,owner,data)
        key=identifier(data.get('request_id'));status,x,y=placement(data)
        if row['status']=='active' and data.get('map_id')==KEYS[row['map_index']] and row['draft_key']==key:
            if ((row['draft_status'],row['draft_x'],row['draft_y'])==(status,x,y) and
                revision(data.get('revision')) in (row['revision']-1,row['revision'])):
                return payload(conn,row)  # Retried draft does not restart its timer.
            raise VibeError('A request_id cannot be reused for a different placement.','request_conflict',409)
        require_stage(row,data)
        conn.execute('''UPDATE vibe_rounds SET draft_status=?,draft_x=?,draft_y=?,draft_at=?,draft_key=?,
                        revision=revision+1 WHERE owner_hash=?''',
                     (status,x,y,time.time(),key,owner_hash(owner)))
        return payload(conn,current(conn,owner))


def advance(conn,owner,data):
    with transaction(conn):
        row=require_round(conn,owner,data);key=identifier(data.get('request_id'))
        if data.get('map_id') not in KEYS:raise VibeError('A valid map_id is required.')
        expected=revision(data.get('revision'));answers=json.loads(row['answers'])
        existing=answers.get(data.get('map_id'))
        if existing:
            if existing['request_id']!=key or existing['revision']!=expected:
                raise VibeError('This map has already been saved.','already_saved',409)
            result=payload(conn,row);result.update(replayed=True,accepted_map=data['map_id']);return result
        if any(answer['request_id']==key for answer in answers.values()):
            raise VibeError('Use a new request_id for each map.','request_conflict',409)
        require_stage(row,data)
        if row['draft_status'] is None:raise VibeError('Place the song on this map first.','missing_draft',409)
        now=time.time();remaining=row['draft_at']+READJUST_SECONDS-now
        if remaining>0:
            raise VibeError('Allow five seconds after the latest adjustment.','readjusting',409,
                            remaining_ms=math.ceil(remaining*1000))
        map_id=KEYS[row['map_index']]
        point=conn.execute('SELECT * FROM song_vibe_positions WHERE song_id=? AND map_id=?',
                           (row['song_id'],map_id)).fetchone()
        if point is None:raise VibeError('This map slot is missing. Check the database.','missing_slot',409)
        if row['draft_status']=='placed':
            count=max(point['sample_count'],int(point['status']=='placed'))
            x=point['x']+(row['draft_x']-point['x'])/(count+1) if count else row['draft_x']
            y=point['y']+(row['draft_y']-point['y'])/(count+1) if count else row['draft_y']
            conn.execute("""UPDATE song_vibe_positions SET x=?,y=?,status='placed',updated_at=?,sample_count=?
                            WHERE song_id=? AND map_id=?""",(x,y,now,count+1,row['song_id'],map_id))
        else:
            # A skip is not a zero sample and must not erase an existing mean.
            conn.execute("""UPDATE song_vibe_positions SET status=CASE WHEN x IS NOT NULL THEN 'placed' ELSE 'not_applicable' END,
                            updated_at=?,not_applicable_count=not_applicable_count+1 WHERE song_id=? AND map_id=?""",
                         (now,row['song_id'],map_id))
        answers[map_id]=dict(status=row['draft_status'],x=row['draft_x'],y=row['draft_y'],
                            request_id=key,revision=expected,submitted_at=now)
        done=row['map_index']==len(MAPS)-1
        conn.execute('''UPDATE vibe_rounds SET map_index=map_index+1,status=?,revision=revision+1,
            draft_status=NULL,draft_x=NULL,draft_y=NULL,draft_at=NULL,draft_key=NULL,answers=?,finished_at=?
            WHERE owner_hash=?''',('complete' if done else 'active',json.dumps(answers,allow_nan=False),
                                  now if done else None,owner_hash(owner)))
        if done:
            saved=conn.execute('UPDATE song_vibe_progress SET completed_passes=completed_passes+1 WHERE song_id=?',(row['song_id'],))
            if saved.rowcount!=1:raise VibeError('The pass counter is missing. Check the database.','missing_counter',409)
        result=payload(conn,current(conn,owner));result.update(replayed=False,accepted_map=map_id);return result


def cancel(conn,owner,data):
    with transaction(conn):
        row=require_round(conn,owner,data)
        expected=revision(data.get('revision'))
        if row['status']=='cancelled' and expected in (row['revision'],row['revision']-1):return payload(conn,row)
        if row['status']!='active' or row['revision']!=expected:
            raise VibeError('This round has changed or ended.','stale_revision',409)
        conn.execute("""UPDATE vibe_rounds SET status='cancelled',finished_at=?,revision=revision+1,
            draft_status=NULL,draft_x=NULL,draft_y=NULL,draft_at=NULL,draft_key=NULL WHERE owner_hash=?""",
                     (time.time(),owner_hash(owner)))
        return payload(conn,current(conn,owner))


def heatmap(conn,kind,entity_id=None):
    scopes={'all':None,'artist':('song_artists','artist_id'),
            'album':None,'tag':('song_genres','genre_id')}
    if kind not in scopes:raise VibeError('Choose all, artist, album or tag.')
    params=[];where=''
    if kind!='all':
        if type(entity_id) is not int or not 0<entity_id<2**63:raise VibeError('A positive entity ID is required.')
        params=[entity_id]
        if kind=='album':where=' WHERE s.album_id=?'
        else:
            table,column=scopes[kind]
            where=f' WHERE EXISTS(SELECT 1 FROM {table} link WHERE link.song_id=s.id AND link.{column}=?)'
    ids=[r[0] for r in conn.execute('SELECT s.id FROM songs s'+where+' ORDER BY s.id',params)]
    profiles=song_profiles(conn,ids)
    result={key:dict(points=[],unmapped=0,not_applicable=0) for key in KEYS}
    for sid,points in profiles.items():
        for key,p in points.items():
            if p['status']=='placed':
                result[key]['points'].append(dict(song_id=sid,x=p['x']*SCALE,y=p['y']*SCALE,
                    sample_count=p['sample_count'],weight=1))
            else:result[key][p['status']]+=1
    return dict(kind=kind,entity_id=entity_id,song_count=len(ids),maps=result,min=-SCALE,max=SCALE)


def browser_owner(create=False):
    if create and 'vibe_owner' not in session:session['vibe_owner']=secrets.token_urlsafe(32)
    return session.get('vibe_owner')


def respond(action, *, write=False):
    data=request.get_json(silent=True) if write else None
    if write and not isinstance(data,dict):return jsonify(message='A JSON object is required.',code='invalid'),400
    conn=get_db_connection()
    try:
        # Reads return one consistent snapshot and never create a round.
        if not write:conn.execute('BEGIN')
        result=action(conn,data)
        response=jsonify(result);response.headers['Cache-Control']='no-store';return response
    except VibeError as error:
        return jsonify(message=str(error),code=error.code,**error.details),error.status
    finally:conn.close()


@app.get('/api/vibe-map/state')
def api_vibe_map_state():
    return respond(lambda c,d:payload(c,current(c,browser_owner())) if browser_owner() else dict(round=None,version=VIBE_MAP_VERSION))


@app.post('/api/vibe-map/round')
def api_vibe_map_round():return respond(lambda c,d:start(c,browser_owner(True),d),write=True)


@app.post('/api/vibe-map/draft')
def api_vibe_map_draft():return respond(lambda c,d:draft(c,browser_owner(),d),write=True)


@app.post('/api/vibe-map/advance')
def api_vibe_map_advance():return respond(lambda c,d:advance(c,browser_owner(),d),write=True)


@app.post('/api/vibe-map/cancel')
def api_vibe_map_cancel():return respond(lambda c,d:cancel(c,browser_owner(),d),write=True)


@app.get('/api/vibe-map/profile/<int:song_id>')
def api_vibe_map_profile(song_id):return respond(lambda c,d:profile(c,song_id))


@app.get('/api/vibe-map/heatmap')
def api_vibe_map_heatmap():
    def read(conn,data):
        value=request.args.get('id')
        try:entity_id=int(value) if value is not None else None
        except ValueError:raise VibeError('A numeric entity ID is required.')
        return heatmap(conn,request.args.get('kind','all'),entity_id)
    return respond(read)
