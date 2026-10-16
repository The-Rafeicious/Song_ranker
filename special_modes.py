"""Elo predictions and album-order quizzes. Neither writes voting/trivia records."""
from collections import defaultdict
import math
import random
import secrets
import time

from flask import jsonify, render_template, request, session
from services import app, get_db_connection


def grade_shelf(items):
    """0.5 membership points + up to 2.5 relative-order points per track."""
    result=[]
    for item in items:
        siblings=[other for other in items if other['album_slot']==item['album_slot']
                  and other['item_slot']!=item['item_slot']]
        membership=item['answer_slot']==item['album_slot']
        comparisons=len(siblings)
        right=sum(membership and other['answer_slot']==other['album_slot'] and
                  ((item['track_number']<other['track_number']) ==
                   (item['answer_position']<other['answer_position'])) for other in siblings)
        order_points=2.5*right/comparisons if comparisons else 0
        result.append(dict(item_slot=item['item_slot'],song_id=item['song_id'],
            album_id=item['album_id'],album_correct=int(membership),
            order_right=right,order_pairs=comparisons,
            answer_slot=item['answer_slot'],answer_position=item['answer_position'],
            points=.5*int(membership)+order_points,available=3 if comparisons else .5))
    points=sum(row['points'] for row in result)
    available=sum(row['available'] for row in result)
    return dict(points=points,available=available,
        accuracy=100*points/available if available else None,
        album_correct=sum(row['album_correct'] for row in result),
        order_right=sum(row['order_right'] for row in result),
        order_pairs=sum(row['order_pairs'] for row in result),items=result)


def special_records(conn):
    """Derive song figures and global mode records from answered rounds only."""
    keys=('guess_attempts','guess_correct','shelf_attempts','shelf_album_correct',
          'shelf_order_right','shelf_order_pairs','shelf_points','shelf_available')
    songs={r['id']:{key:0 for key in keys} for r in conn.execute('SELECT id FROM songs')}
    guess_rows=[dict(r) for r in conn.execute('SELECT * FROM elo_guess_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at,id')]
    streak=best=correct=0
    for row in guess_rows:
        row['correct']=int((row['chosen_slot']==1) == (row['elo1']>row['elo2']))
        correct+=row['correct'];streak=streak+1 if row['correct'] else 0;best=max(best,streak)
        row['streak']=streak
        for sid in (row['song1_id'],row['song2_id']):
            if sid in songs:
                songs[sid]['guess_attempts']+=1;songs[sid]['guess_correct']+=row['correct']
    shelf_items=defaultdict(list)
    for row in conn.execute('''SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
                              WHERE r.completed_at IS NOT NULL ORDER BY r.id,i.item_slot'''):
        shelf_items[row['round_id']].append(dict(row))
    shelf_rows=[]
    for round_row in conn.execute('SELECT id,completed_at FROM album_shelf_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at,id'):
        graded=grade_shelf(shelf_items[round_row['id']])
        shelf_rows.append(dict(round_row,
            song_ids=[item['song_id'] for item in shelf_items[round_row['id']]],
            album_ids=list(dict.fromkeys(item['album_id'] for item in shelf_items[round_row['id']])),
            **{k:v for k,v in graded.items() if k!='items'}))
        for item in graded['items']:
            if item['song_id'] not in songs:continue
            s=songs[item['song_id']];s['shelf_attempts']+=1
            for key,value in [('shelf_album_correct',item['album_correct']),('shelf_order_right',item['order_right']),
                              ('shelf_order_pairs',item['order_pairs']),('shelf_points',item['points']),('shelf_available',item['available'])]:s[key]+=value
    points=sum(r['points'] for r in shelf_rows);available=sum(r['available'] for r in shelf_rows)
    summary=dict(guesser=dict(rounds=len(guess_rows),correct=correct,points=correct,
        accuracy=100*correct/len(guess_rows) if guess_rows else None,streak=streak,best_streak=best),
        shelves=dict(rounds=len(shelf_rows),points=points,available=available,
            accuracy=100*points/available if available else None,
            best_points=max((r['points'] for r in shelf_rows),default=0),
            perfect=sum(abs(r['points']-r['available'])<1e-8 for r in shelf_rows),
            tracks=sum(len(shelf_items[r['id']]) for r in shelf_rows),
            album_correct=sum(r['album_correct'] for r in shelf_rows),
            order_right=sum(r['order_right'] for r in shelf_rows),
            order_pairs=sum(r['order_pairs'] for r in shelf_rows),
            albums_played=conn.execute('''SELECT COUNT(DISTINCT i.album_id) FROM album_shelf_items i
                JOIN album_shelf_rounds r ON r.id=i.round_id JOIN albums a ON a.id=i.album_id
                WHERE r.completed_at IS NOT NULL''').fetchone()[0]))
    return songs,summary,guess_rows[-30:][::-1],shelf_rows[-30:][::-1]


def display_song(conn,sid,include_album=True):
    row=conn.execute('''SELECT s.id,s.title,s.audio_url,a.title album,a.cover_url,
        a.id album_id FROM songs s LEFT JOIN albums a ON a.id=s.album_id WHERE s.id=?''',(sid,)).fetchone()
    if not row:return None
    song=dict(row)
    song['artists']=[dict(r) for r in conn.execute('''SELECT a.id,a.name FROM song_artists sa
        JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=? ORDER BY a.name''',(sid,))]
    if not include_album:
        for key in ('album','album_id','cover_url'):song.pop(key,None)
    return song


@app.route('/elo_guesser')
def elo_guesser():return render_template('app_page.html',page='guesser')


@app.route('/elo_guesser_stats')
def guesser_stats():
    from guesser_stats_data import build_guesser_stats
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        data=build_guesser_stats(conn,history_page=request.args.get('history_page',1,type=int))
    finally:
        conn.close()
    return render_template('guesser_stats.html',**data)

@app.route('/album_shelves')
def album_shelves():return render_template('app_page.html',page='shelves')

@app.route('/album_shelves_stats')
def shelf_stats():
    from shelves_stats_data import build_shelves_stats
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        data=build_shelves_stats(conn,history_page=request.args.get('history_page',1,type=int),
                                album_page=request.args.get('album_page',1,type=int),
                                selected=request.args.get('round',type=int))
    finally:
        conn.close()
    return render_template('shelves_stats.html',show_albums='album_page' in request.args,**data)

@app.route('/mode_rankings/<mode>')
def special_rankings(mode):
    if mode not in ('trivia','tournament','guesser','shelves'):return 'Unknown mode',404
    return render_template('app_page.html',page='mode_rankings_'+mode)


@app.route('/api/elo-guesser/round',methods=['POST'])
def guess_round():
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM elo_guess_rounds WHERE token=? AND completed_at IS NULL',
                         (session.get('guess_token',''),)).fetchone()
        if row and (not display_song(conn,row['song1_id']) or not display_song(conn,row['song2_id'])):
            conn.execute('DELETE FROM elo_guess_rounds WHERE id=?',(row['id'],));row=None
        if not row:
            # Pending questions older than a day have no statistical value.
            conn.execute('DELETE FROM elo_guess_rounds WHERE completed_at IS NULL AND started_at<?',(time.time()-86400,))
            counts={r[0]:r[1] for r in conn.execute('''SELECT sid,COUNT(*) FROM (
                SELECT song1_id sid FROM elo_guess_rounds WHERE completed_at IS NOT NULL
                UNION ALL SELECT song2_id FROM elo_guess_rounds WHERE completed_at IS NOT NULL) GROUP BY sid''')}
            pool=[dict(r) for r in conn.execute('SELECT id,elo_score FROM songs')
                  if isinstance(r['elo_score'],(int,float)) and math.isfinite(r['elo_score'])]
            if len(pool)<2 or len({s['elo_score'] for s in pool})<2:
                return jsonify(message='Add two tracks with different Elo ratings to play.'),400
            first=random.choices(pool,weights=[1/math.sqrt(1+counts.get(s['id'],0)) for s in pool])[0]
            different=[s for s in pool if s['elo_score']!=first['elo_score']]
            second=random.choices(different,weights=[(1 if 40<=abs(s['elo_score']-first['elo_score'])<=250 else .25)/math.sqrt(1+counts.get(s['id'],0)) for s in different])[0]
            pair=[first,second];random.shuffle(pair);token=secrets.token_urlsafe(24)
            cur=conn.execute('INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at) VALUES(?,?,?,?,?,?)',
                (token,pair[0]['id'],pair[1]['id'],pair[0]['elo_score'],pair[1]['elo_score'],time.time()))
            session['guess_token']=token;row=conn.execute('SELECT * FROM elo_guess_rounds WHERE id=?',(cur.lastrowid,)).fetchone()
        conn.commit()
        return jsonify(token=row['token'],songs=[display_song(conn,row['song1_id']),display_song(conn,row['song2_id'])],records=special_records(conn)[1]['guesser'])
    finally:conn.close()


@app.route('/api/elo-guesser/answer',methods=['POST'])
def guess_answer():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('song_id'),int) or isinstance(data['song_id'],bool):
        return jsonify(message='Choose one of the offered songs.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM elo_guess_rounds WHERE token=?',(session.get('guess_token',''),)).fetchone()
        if not row or data.get('token')!=row['token']:return jsonify(message='This question is no longer active. Load a new pair.'),409
        if row['completed_at'] is not None:return jsonify(message='This answer is already saved.'),409
        if not row['song1_id'] or not row['song2_id']:return jsonify(message='A track was deleted. Load a new pair.'),409
        if data['song_id'] not in (row['song1_id'],row['song2_id']):return jsonify(message='Choose an offered track.'),400
        slot=1 if data['song_id']==row['song1_id'] else 2
        conn.execute('UPDATE elo_guess_rounds SET chosen_slot=?,completed_at=? WHERE id=?',(slot,time.time(),row['id']))
        conn.commit();correct=int((slot==1)==(row['elo1']>row['elo2']))
        return jsonify(correct=bool(correct),points=correct,ratings=[row['elo1'],row['elo2']],records=special_records(conn)[1]['guesser'])
    finally:conn.close()


def shelf_pool(conn):
    """The existing numbered/proper-album pool, shared by the picker and stats."""
    pool=[dict(r) for r in conn.execute('''SELECT s.id,s.album_id,s.track_number FROM songs s JOIN albums a ON a.id=s.album_id
        WHERE TRIM(a.title)!='' AND LOWER(TRIM(a.title))!='unknown album'
        AND LOWER(TRIM(a.title)) NOT LIKE '% - single' AND typeof(s.track_number)='integer' AND s.track_number>0
        AND NOT EXISTS(SELECT 1 FROM songs other WHERE other.album_id=s.album_id
          AND other.track_number=s.track_number AND other.id!=s.id)''')]
    grouped=defaultdict(list)
    for song in pool:grouped[song['album_id']].append(song)
    # A shelf must offer an ordering question, not a singleton album clue.
    return {id:tracks for id,tracks in grouped.items() if len(tracks)>=2}


def shelf_candidates(conn,count):
    grouped=shelf_pool(conn)
    ids=list(grouped)
    def feasible(available,n):
        return len(available)>=n and sum(sorted((len(grouped[id]) for id in available),reverse=True)[:n])>=10
    possible=[n for n in ([count] if count else [2,3]) if feasible(ids,n)]
    if not possible:return None
    # Uniform choice gives a genuine 50/50 split when both sizes are feasible.
    n=random.choice(possible)
    recent=[r[0] for r in conn.execute('SELECT id FROM album_shelf_rounds ORDER BY started_at DESC,id DESC LIMIT 5')]
    recent_albums=[{r[0] for r in conn.execute('SELECT DISTINCT album_id FROM album_shelf_items WHERE round_id=?',(rid,))} for rid in recent]
    last=recent_albums[0] if recent_albums else set()
    fresh=[id for id in ids if id not in last]
    if feasible(fresh,n):ids=fresh
    exposure={r[0]:r[1] for r in conn.execute('''SELECT album_id,COUNT(DISTINCT i.round_id)
        FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
        WHERE r.completed_at IS NOT NULL GROUP BY album_id''')}
    chosen=[]
    while len(chosen)<n:
        remaining=[id for id in ids if id not in chosen]
        slots_left=n-len(chosen)-1
        # Every draw must leave enough capacity to complete a ten-track round.
        eligible=[id for id in remaining if sum(len(grouped[x]) for x in chosen)+len(grouped[id])+
                  sum(sorted((len(grouped[x]) for x in remaining if x!=id),reverse=True)[:slots_left])>=10]
        weights=[1/(math.sqrt(1+exposure.get(id,0))*(1+sum(5-age for age,albums in enumerate(recent_albums) if id in albums))) for id in eligible]
        chosen.append(random.choices(eligible,weights=weights)[0])
    allocation={id:2 for id in chosen}
    while sum(allocation.values())<10:
        available=[id for id in chosen if allocation[id]<len(grouped[id])]
        smallest=min(allocation[id] for id in available)
        allocation[random.choice([id for id in available if allocation[id]==smallest])]+=1
    counts={r[0]:r[1] for r in conn.execute('SELECT song_id,COUNT(*) FROM album_shelf_items WHERE answer_slot IS NOT NULL GROUP BY song_id')}
    selected=[]
    for id in chosen:
        remaining=list(grouped[id])
        for _ in range(allocation[id]):
            song=random.choices(remaining,weights=[1/math.sqrt(1+counts.get(x['id'],0)) for x in remaining])[0]
            selected.append(song);remaining.remove(song)
    random.shuffle(selected)
    return chosen,selected


def shelf_payload(conn,row):
    items=[dict(r) for r in conn.execute('SELECT * FROM album_shelf_items WHERE round_id=? ORDER BY item_slot',(row['id'],))]
    albums=[]
    for slot in sorted({i['album_slot'] for i in items}):
        id=next(i['album_id'] for i in items if i['album_slot']==slot)
        a=conn.execute('SELECT id,title,cover_url FROM albums WHERE id=?',(id,)).fetchone()
        if not a:return None
        albums.append(dict(a,slot=slot))
    songs=[]
    for item in items:
        s=display_song(conn,item['song_id'],False)
        if not s:return None
        s.pop('artists',None)
        songs.append(dict(s,slot=item['item_slot']))
    return dict(token=row['token'],albums=albums,songs=songs)


@app.route('/api/album-shelves/round',methods=['POST'])
def shelf_round():
    data=request.get_json(silent=True) or {}
    if not isinstance(data,dict) or type(data.get('album_count',0)) is not int or data.get('album_count',0) not in (0,2,3):
        return jsonify(message='Choose automatic, two or three albums.'),400
    count=data.get('album_count',0);conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM album_shelf_rounds WHERE token=? AND completed_at IS NULL',(session.get('shelf_token',''),)).fetchone()
        if row and data.get('fresh') is True:
            conn.execute('DELETE FROM album_shelf_rounds WHERE id=?',(row['id'],));row=None
        if row:
            payload=shelf_payload(conn,row)
            if not payload or (count and len(payload['albums'])!=count):
                conn.execute('DELETE FROM album_shelf_rounds WHERE id=?',(row['id'],));row=None
        if not row:
            conn.execute('DELETE FROM album_shelf_rounds WHERE completed_at IS NULL AND started_at<?',(time.time()-86400,))
            candidate=shelf_candidates(conn,count)
            if not candidate:return jsonify(message='Need ten numbered tracks across two or three proper albums, with at least two tracks per album. Gaps are fine.'),400
            albums,tracks=candidate;token=secrets.token_urlsafe(24)
            cur=conn.execute('INSERT INTO album_shelf_rounds(token,started_at) VALUES(?,?)',(token,time.time()))
            for slot,song in enumerate(tracks,1):
                conn.execute('INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number) VALUES(?,?,?,?,?,?)',
                    (cur.lastrowid,slot,song['id'],song['album_id'],albums.index(song['album_id'])+1,song['track_number']))
            session['shelf_token']=token;row=conn.execute('SELECT * FROM album_shelf_rounds WHERE id=?',(cur.lastrowid,)).fetchone()
            payload=shelf_payload(conn,row)
        conn.commit();return jsonify(**payload)
    finally:conn.close()


@app.route('/api/album-shelves/answer',methods=['POST'])
def shelf_answer():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('placements'),dict):return jsonify(message='Place every offered track once.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM album_shelf_rounds WHERE token=?',(session.get('shelf_token',''),)).fetchone()
        if not row or data.get('token')!=row['token']:return jsonify(message='This shelf round is no longer active.'),409
        if row['completed_at'] is not None:return jsonify(message='This answer is already saved.'),409
        items=[dict(i) for i in conn.execute('SELECT * FROM album_shelf_items WHERE round_id=?',(row['id'],))]
        if any(not i['song_id'] or not i['album_id'] for i in items):return jsonify(message='A track or album was deleted. Start a new round.'),409
        offered={i['item_slot'] for i in items};slots={str(i['album_slot']) for i in items};p=data['placements']
        if set(p)!=slots or any(not isinstance(v,list) for v in p.values()):return jsonify(message='Use the offered album shelves.'),400
        flat=[x for v in p.values() for x in v]
        if any(type(x) is not int for x in flat) or len(flat)!=10 or len(set(flat))!=10 or set(flat)!=offered:
            return jsonify(message='Each of the ten offered tracks must appear exactly once.'),400
        by_slot={i['item_slot']:i for i in items}
        for slot,ids in p.items():
            for position,id in enumerate(ids,1):
                by_slot[id].update(answer_slot=int(slot),answer_position=position)
                conn.execute('UPDATE album_shelf_items SET answer_slot=?,answer_position=? WHERE round_id=? AND item_slot=?',
                    (int(slot),position,row['id'],id))
        conn.execute('UPDATE album_shelf_rounds SET completed_at=? WHERE id=?',(time.time(),row['id']))
        conn.commit();graded=grade_shelf(items)
        answers=[dict(slot=i['item_slot'],album_slot=i['album_slot'],track_number=i['track_number']) for i in items]
        return jsonify(**graded,answers=answers)
    finally:conn.close()


@app.route('/api/special-modes/stats')
def special_stats():
    conn=get_db_connection()
    try:
        songs,summary,guesses,shelves=special_records(conn)
        for row in guesses:row.pop('token',None)
        albums=[dict(row) for row in conn.execute('''
            SELECT a.id,a.title,a.cover_url,COUNT(DISTINCT r.id) AS rounds,
                COUNT(*) AS attempts,SUM(i.answer_slot=i.album_slot) AS correct
            FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
            JOIN albums a ON a.id=i.album_id WHERE r.completed_at IS NOT NULL
            GROUP BY a.id ORDER BY rounds DESC,a.title COLLATE NOCASE''')]
        by_round=defaultdict(list)
        for row in conn.execute('''SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
                WHERE r.completed_at IS NOT NULL'''):
            by_round[row['round_id']].append(dict(row))
        order=defaultdict(lambda:dict(order_right=0,order_pairs=0))
        for items in by_round.values():
            for item in grade_shelf(items)['items']:
                for key in ('order_right','order_pairs'):order[item['album_id']][key]+=item[key]
        for album in albums:album.update(order[album['id']])
        return jsonify(summary=summary,songs=songs,guess_history=guesses,shelf_history=shelves,
                       participating_albums=albums)
    finally:conn.close()
