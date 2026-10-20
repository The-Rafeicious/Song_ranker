"""Optional bounded browser playback measurements, stored with accepted game facts."""
import math
import time


def record(conn,mode,reference,offered,selected,payload):
    if not isinstance(payload,dict) or payload.get('version')!=1:return
    ms=payload.get('decision_ms');entries=payload.get('songs')
    if isinstance(ms,bool) or not isinstance(ms,(int,float)) or not math.isfinite(ms) or not 0<=ms<=7200000:return
    if not isinstance(entries,list) or len(entries)>32:return
    allowed=set(offered);values={}
    for item in entries:
        if not isinstance(item,dict):continue
        sid,seconds=item.get('song_id'),item.get('seconds')
        if type(sid) is not int or sid not in allowed or isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds):continue
        if not 0<=seconds<=min(7200,ms/1000+.25):continue
        if sid in values:return # Duplicate song reports are ambiguous; retain no invented measurement.
        values[sid]=seconds
    # A partial sample must not be mistaken for zero listening on missing participants.
    if set(values)!=allowed:return
    for sid,seconds in values.items():
        conn.execute('''INSERT OR IGNORE INTO listening_observations
            (mode,reference,song_key,song_id,seconds,decision_ms,selected,recorded_at)
            VALUES(?,?,?,?,?,?,?,?)''',(mode,str(reference),sid,sid,round(seconds,3),round(ms,1),
                int(sid==selected) if selected is not None else None,time.time()))


def summary(conn,mode='global'):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='listening_observations'").fetchone():
        return dict(samples=0,decisions=0,seconds=0,mean=None,modes=[])
    mode='trivia' if mode=='recognition' else mode
    clause='' if mode in ('global','history','voting') else ' WHERE mode=?'
    args=() if not clause else (mode,)
    if mode=='voting':clause=" WHERE mode IN ('standard','blind','tournament')";args=()
    rows=[dict(r) for r in conn.execute('SELECT * FROM listening_observations'+clause,args)]
    total=sum(r['seconds'] for r in rows)
    return dict(samples=len(rows),decisions=len({(r['mode'],r['reference']) for r in rows}),seconds=round(total,1),
        mean=round(total/len(rows),2) if rows else None,
        modes=[dict(mode=m,samples=len(group),seconds=round(sum(r['seconds'] for r in group),1),
                    mean=round(sum(r['seconds'] for r in group)/len(group),2))
               for m in ('standard','blind','tournament','trivia','guesser','shelves')
               if (group:=[r for r in rows if r['mode']==m])])


def song_summaries(conn):
    return {r['song_id']:dict(r) for r in conn.execute('''SELECT song_id,COUNT(*) samples,
        ROUND(SUM(seconds),2) seconds,ROUND(AVG(seconds),2) mean,
        ROUND(AVG(CASE WHEN selected=1 THEN seconds END),2) chosen_mean,
        ROUND(AVG(CASE WHEN selected=0 THEN seconds END),2) other_mean
        FROM listening_observations WHERE song_id IS NOT NULL GROUP BY song_id''')}
