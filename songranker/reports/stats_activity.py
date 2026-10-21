"""Dated, completed result trends. Counts and pooled rates share one read snapshot."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from math import isfinite

COLORS = {'standard':'Non-blind', 'blind':'Blind', 'recognition':'Trivia',
          'tournament':'Tournament', 'guesser':'Elo Guesser', 'shelves':'Album Shelves', 'vibe':'Vibe Map'}


def timestamp(value):
    try:
        if isinstance(value, (int, float)):
            value = float(value)
            if not isfinite(value): return None
            return datetime.fromtimestamp(value, timezone.utc)
        value = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def latest_vibe_saves(conn):
    """One retained update per song, not an invented log of completed passes."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='song_vibe_positions'").fetchone():
        return []
    return [dict(row) for row in conn.execute("""SELECT v.song_id,MAX(v.updated_at) AS updated_at,
        SUM(v.status='placed') AS placed,COUNT(*) AS selected
        FROM song_vibe_positions v JOIN songs s ON s.id=v.song_id
        WHERE v.status!='unmapped' GROUP BY v.song_id""")]


def build_activity(conn, mode, now=None):
    current = timestamp(now) if now is not None else datetime.now(timezone.utc)
    start = current.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=13)
    days = {str((start+timedelta(days=n)).date()):dict(date=str((start+timedelta(days=n)).date()),
            count=0,parts=defaultdict(int),right=0,denominator=0) for n in range(14)}
    known = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    undated = 0
    def rows(table):
        return [dict(r) for r in conn.execute('SELECT * FROM '+table)] if table in known else []
    def add(when, kind, right=0, denominator=0):
        nonlocal undated
        date = timestamp(when)
        if date is None: undated += 1; return
        if date>current or date.date().isoformat() not in days: return
        item=days[date.date().isoformat()];item['count']+=1;item['parts'][kind]+=1
        item['right']+=right;item['denominator']+=denominator
    if mode in ('global','voting','history') and 'history' in known:
        from songranker.elo_history import source_sql
        for row in conn.execute('SELECT * FROM '+source_sql(conn)):
            r=dict(row)
            if r.get('mode') not in ('standard','blind') or r.get('winner_id')==r.get('loser_id'):continue
            a,b=r.get('winner_before'),r.get('loser_before')
            usable=all(isinstance(x,(float,int)) and isfinite(x) for x in (a,b)) and a!=b
            # First-round Elo is visually a tournament result, still just one Elo event.
            kind='tournament' if r.get('origin')=='tournament' else r['mode']
            weight=r.get('rating_weight',1)
            add(r.get('created_at'),kind,weight*int(a<b) if usable else 0,weight*int(usable))
    if mode in ('global','recognition'):
        for row in rows('trivia_rounds'):
            if row.get('completed_at') is None:continue
            eligible=['title','artist']+(['album'] if row.get('album_available') else [])
            values=[row.get(f+'_correct') for f in eligible]
            graded=all(v in (0,1) for v in values)
            add(row['completed_at'],'recognition',sum(v==1 for v in values) if graded else 0,len(values) if graded else 0)
    if mode in ('global','tournament'):
        for row in rows('tournaments'):
            if row.get('status')=='completed':
                add(row.get('completed_at') or row.get('timestamp') or row.get('created_at'),'tournament')
    if mode in ('global','guesser'):
        for row in rows('elo_guess_rounds'):
            if row.get('completed_at') is None:continue
            a,b=row.get('elo1'),row.get('elo2');slot=row.get('chosen_slot')
            valid=slot in (1,2) and all(isinstance(x,(float,int)) and isfinite(x) for x in (a,b)) and a!=b
            add(row['completed_at'],'guesser',int((slot==1)==(a>b)) if valid else 0,int(valid))
    if mode in ('global','shelves'):
        from songranker.reports.shelves_stats_data import can_grade
        from songranker.modes.special_modes import grade_shelf
        groups=defaultdict(list)
        for item in rows('album_shelf_items'):groups[item['round_id']].append(item)
        for row in rows('album_shelf_rounds'):
            if row.get('completed_at') is None:continue
            items=groups[row['id']]
            valid=can_grade(items,row.get('rules_version',1))
            result=grade_shelf(items) if valid else {}
            # Same order denominator as the existing Shelves dashboard.
            add(row['completed_at'],'shelves',result.get('order_right',0),result.get('order_pairs',0))
    if mode=='global':
        for row in latest_vibe_saves(conn):add(row['updated_at'],'vibe')
    result=list(days.values());maximum=max((d['count'] for d in result),default=0)
    segments=[];segment=[]
    for n,day in enumerate(result):
        day['rate']=100*day['right']/day['denominator'] if day['denominator'] else None
        day['x']=round(24+n*552/13,2);day['y']=round(120-100*day['rate']/100,2) if day['rate'] is not None else None
        day['height']=round(100*day['count']/maximum,4) if maximum else 0
        day['bars']=[dict(kind=k,label=COLORS[k],count=v,height=100*v/day['count']) for k,v in day.pop('parts').items()]
        if day['rate'] is None:
            if segment:segments.append(segment);segment=[]
        else:segment.append(f"{day['x']},{day['y']}")
    if segment:segments.append(segment)
    numerator=sum(d['right'] for d in result);denominator=sum(d['denominator'] for d in result)
    kinds={b['kind'] for day in result for b in day['bars']}
    rate_label={'voting':'Lower-rated wins','history':'Lower-rated wins','recognition':'Field accuracy',
                'guesser':'Pick accuracy','shelves':'Track order'}.get(mode)
    return dict(mode=mode,days=result,segments=[' '.join(s) for s in segments],total=sum(d['count'] for d in result),
        current=sum(d['count'] for d in result[7:]),previous=sum(d['count'] for d in result[:7]),
        active=sum(d['count']>0 for d in result),rate=100*numerator/denominator if denominator else None,
        right=numerator,denominator=denominator,rate_label=rate_label,undated=undated,
        legend=[dict(kind=k,label=COLORS[k],count=sum(b['count'] for d in result for b in d['bars'] if b['kind']==k)) for k in COLORS if k in kinds])


def attach_reports(conn, data, mode, now=None):
    data['pulse_data']=build_activity(conn, mode, now=now)
    from songranker.listening import summary as listening_summary
    data['listening_data']=listening_summary(conn,mode)
    if mode=='tournament':
        from songranker.elo_history import source_sql
        rows=[dict(r) for r in conn.execute('SELECT * FROM '+source_sql(conn)+" WHERE origin='tournament'")]
        data['tournament_elo']=dict(standard=sum(r['mode']=='standard' for r in rows),blind=sum(r['mode']=='blind' for r in rows),total=len(rows),full=sum(r['rating_weight']==1 for r in rows),
            half=sum(r['rating_weight']==.5 for r in rows),
            tracks=len({sid for r in rows for sid in (r['winner_id'],r['loser_id']) if sid is not None}))
        from songranker.services import fetch_match_history
        data['tournament_elo_history']=fetch_match_history(conn,origin='tournament',limit=4) if rows else []
    return data
