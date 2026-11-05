"""Dated, completed result trends. Counts and pooled rates share one read snapshot."""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from math import isfinite

COLORS = {'standard':'Non-blind', 'blind':'Blind', 'recognition':'Trivia',
          'tournament':'Tournament', 'shelves':'Album Shelves', 'vibe':'Vibe Map'}


def coverage_milestone(counts):
    """Find the first unfinished whole-appearance target in the current eligible pool.

    Recompute from evidence on every report; new eligible records reset the target.
    Fractional effective votes only complete a milestone at its actual threshold.
    """
    counts = list(counts)
    target = int(min(counts)) + 1 if counts else 1
    reached = sum(value >= target for value in counts)
    return dict(target=target, reached=reached, total=len(counts),
                share=round(100 * reached / len(counts), 1) if counts else None)


def timestamp(value):
    """Parse supported saved times as finite UTC datetimes, preserving unavailable
    dates as null.
    """
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


def build_activity(conn, mode, now=None, tournament_ids=None):
    """Build fourteen days of mode activity, previous/current-week totals and graded
    success rates.
    """
    current = timestamp(now) if now is not None else datetime.now(timezone.utc)
    start = current.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=13)
    days = {str((start+timedelta(days=n)).date()):dict(date=str((start+timedelta(days=n)).date()),
            count=0,parts=defaultdict(int),right=0,denominator=0) for n in range(14)}
    known = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    undated = 0
    def rows(table):
        """Read a known activity source table while tolerating its absence in
        historical fixtures.
        """
        return [dict(r) for r in conn.execute('SELECT * FROM '+table)] if table in known else []
    def add(when, kind, right=0, denominator=0):
        """Add an in-window dated result and its success denominator, counting
        undated records separately.
        """
        nonlocal undated
        date = timestamp(when)
        if date is None: undated += 1; return
        if date>current or date.date().isoformat() not in days: return
        item=days[date.date().isoformat()];item['count']+=1;item['parts'][kind]+=1
        item['right']+=right;item['denominator']+=denominator
    if mode in ('global','voting','history') and 'history' in known:
        from songranker.catalog import source_sql
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
            if tournament_ids is not None and row['id'] not in tournament_ids:continue
            if row.get('status')=='completed':
                add(row.get('completed_at') or row.get('timestamp') or row.get('created_at'),'tournament')

    if mode in ('global','shelves'):
        from songranker.modes.shelves import can_grade
        from songranker.modes.shelves import grade_shelf, shelf_report_filter
        groups=defaultdict(list)
        for item in rows('album_shelf_items'):groups[item['round_id']].append(item)
        visible={r['id'] for r in conn.execute(f'SELECT r.id FROM album_shelf_rounds r WHERE {shelf_report_filter(conn)}')}
        for row in rows('album_shelf_rounds'):
            if row['id'] not in visible:continue
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
                'shelves':'Track order'}.get(mode)
    return dict(mode=mode,days=result,segments=[' '.join(s) for s in segments],total=sum(d['count'] for d in result),
        current=sum(d['count'] for d in result[7:]),previous=sum(d['count'] for d in result[:7]),
        active=sum(d['count']>0 for d in result),rate=100*numerator/denominator if denominator else None,
        right=numerator,denominator=denominator,rate_label=rate_label,undated=undated,
        legend=[dict(kind=k,label=COLORS[k],count=sum(b['count'] for d in result for b in d['bars'] if b['kind']==k)) for k in COLORS if k in kinds])


def attach_reports(conn, data, mode, now=None, tournament_ids=None):
    """Attach shared activity charts and effective tournament Elo history to a mode
    report.
    """
    data['pulse_data']=build_activity(conn, mode, now=now, tournament_ids=tournament_ids)
    if mode=='tournament':
        from songranker.catalog import source_sql
        rows=[dict(r) for r in conn.execute('SELECT * FROM '+source_sql(conn)+" WHERE origin='tournament'")]
        data['tournament_elo']=dict(standard=sum(r['mode']=='standard' for r in rows),blind=sum(r['mode']=='blind' for r in rows),total=len(rows),full=sum(r['rating_weight']==1 for r in rows),
            half=sum(r['rating_weight']==.5 for r in rows),
            tracks=len({sid for r in rows for sid in (r['winner_id'],r['loser_id']) if sid is not None}))
        data['tournament_elo']['points_only'] = conn.execute("""SELECT COUNT(*) FROM tournament_matches m JOIN tournaments t ON t.id=m.tournament_id
            WHERE t.scope_type IN ('artist','album') AND m.round_number=1 AND m.match_type='bracket'
            AND m.status='completed' AND m.winner_id IS NOT NULL AND m.loser_id IS NOT NULL AND m.winner_id!=m.loser_id""").fetchone()[0]
    if mode=='tournament' and tournament_ids is not None:data['tournament_elo']['points_only']=0
    return data


def match_archive(conn, args):
    """Page a read-only cross-mode archive before hydrating results.

    Dates are inclusive UTC days. Entity membership uses the current catalogue;
    a round is counted once even when several matching tracks participated.
    Vibe stores retained placements, not an immutable lifetime attempt log.
    """
    from math import ceil
    from songranker.catalog import source_sql, versus_metadata
    from songranker.modes.shelves import shelf_report_filter, can_grade, grade_shelf

    mode = args.get('mode', 'all')
    if mode not in ('all', 'standard', 'blind', 'voting', 'first_round', 'tournament', 'recognition', 'shelves', 'vibe'):
        mode = 'all'
    origin = args.get('origin', 'all')
    visibility = args.get('visibility', 'all')
    if visibility not in ('standard', 'blind'):
        visibility = 'all'
    if origin in ('ordinary', 'tournament') and mode in ('standard', 'blind'):
        visibility = mode
    if origin in ('ordinary', 'tournament'):
        mode = 'voting' if origin == 'ordinary' else 'first_round'
    kind = args.get('entity', 'songs')
    if kind not in ('songs', 'albums', 'artists', 'tags'):
        kind = 'songs'
    try:
        target = min(2**63-1, max(0, int(args.get('target', 0))))
    except (ValueError, TypeError):
        target = 0
    dates, errors = {}, []
    for key in ('from', 'to'):
        value = args.get(key, '')
        try:
            dates[key] = datetime.strptime(value, '%Y-%m-%d').date().isoformat() if value else ''
        except ValueError:
            dates[key] = ''
            errors.append('Choose a valid ' + key + ' date.')
    if dates['from'] and dates['to'] and dates['from'] > dates['to']:
        errors.append('The end date must be on or after the start date.')
    membership = {
        'songs': 's.id=?', 'albums': 's.album_id=?',
        'artists': 'EXISTS (SELECT 1 FROM song_artists sa WHERE sa.song_id=s.id AND sa.artist_id=?)',
        'tags': 'EXISTS (SELECT 1 FROM song_genres sg WHERE sg.song_id=s.id AND sg.genre_id=?)',
    }[kind]
    source = source_sql(conn)
    cte = f"""WITH selected AS (SELECT s.id FROM songs s WHERE {membership}),
    events AS (
      SELECT 'elo' family,h.id,CASE WHEN h.origin='tournament' THEN 'first_round' ELSE 'voting' END activity,
        h.mode visibility,julianday(h.created_at) moment,
        (h.winner_id IN selected OR h.loser_id IN selected) matched
        FROM {source} h WHERE h.mode IN ('standard','blind') AND h.winner_id!=h.loser_id
        AND NOT EXISTS (SELECT 1 FROM tournaments private WHERE private.id=h.tournament_id
          AND private.is_blind=1 AND private.status!='completed')
      UNION ALL SELECT 'tournament',t.id,'tournament',CASE WHEN t.is_blind THEN 'blind' ELSE 'standard' END,
        julianday(COALESCE(t.completed_at,t.timestamp)),
        (EXISTS(SELECT 1 FROM tournament_entries e WHERE e.tournament_id=t.id AND e.song_id IN selected)
         OR t.champion_id IN selected OR t.runner_up_id IN selected OR t.third_place_id IN selected
         OR EXISTS(SELECT 1 FROM tournament_matches m WHERE m.tournament_id=t.id
           AND (m.song1_id IN selected OR m.song2_id IN selected)))
        FROM tournaments t WHERE t.status='completed'
      UNION ALL SELECT 'recognition',id,'recognition','',julianday(completed_at,'unixepoch'),song_id IN selected
        FROM trivia_rounds WHERE completed_at IS NOT NULL
      UNION ALL SELECT 'shelves',r.id,'shelves','',julianday(r.completed_at,'unixepoch'),
        EXISTS(SELECT 1 FROM album_shelf_items i WHERE i.round_id=r.id AND i.song_id IN selected)
        FROM album_shelf_rounds r WHERE {shelf_report_filter(conn)}
      UNION ALL SELECT 'vibe',p.song_id || ':' || p.map_id,'vibe','',julianday(p.updated_at,'unixepoch'),p.song_id IN selected
        FROM song_vibe_positions p WHERE p.status!='unmapped' AND p.updated_at IS NOT NULL
    ), filtered AS (SELECT * FROM events WHERE (?='all' OR activity=? OR (family='elo' AND visibility=?))
      AND (?='all' OR visibility=?)
      AND (?=0 OR matched) AND (?='' OR moment>=julianday(?))
      AND (?='' OR moment<julianday(?)+1)) """
    params = (target, mode, mode, mode, visibility, visibility, target, dates['from'], dates['from'], dates['to'], dates['to'])
    totals = {r['activity']: r['n'] for r in conn.execute(cte + 'SELECT activity,COUNT(*) n FROM filtered GROUP BY activity', params)} if not errors else {}
    total = sum(totals.values())
    pages = max(1, ceil(total / 20))
    try:
        page = max(1, min(pages, int(args.get('page', 1))))
    except (ValueError, TypeError):
        page = 1
    rows = [dict(r) for r in conn.execute(cte + 'SELECT *,datetime(moment) date FROM filtered ORDER BY moment DESC,family,id DESC LIMIT 20 OFFSET ?', (*params, (page-1)*20))] if not errors else []
    songs = {}

    def song(sid):
        """Hydrate only visible identities, retaining explicit deleted-track gaps."""
        if sid not in songs:
            raw = conn.execute('SELECT s.*,a.title album_title,a.cover_url FROM songs s LEFT JOIN albums a ON a.id=s.album_id WHERE s.id=?', (sid,)).fetchone()
            if raw:
                item = dict(raw)
                artists = [dict(r) for r in conn.execute('SELECT a.id,a.name FROM artists a JOIN song_artists sa ON sa.artist_id=a.id WHERE sa.song_id=?', (sid,))]
                item.update(versus_metadata(dict(id=item['album_id'], title=item['album_title'], cover_url=item['cover_url']), artists))
                songs[sid] = item
            else:
                songs[sid] = None
        return songs[sid]

    for row in rows:
        family, rid = row['family'], row['id']
        if family == 'elo':
            match = dict(conn.execute(f'SELECT * FROM {source} WHERE id=?', (rid,)).fetchone())
            match.update(winner_song=song(match['winner_id']), loser_song=song(match['loser_id']))
            row['result'] = match
        elif family == 'tournament':
            bracket = dict(conn.execute('SELECT * FROM tournaments WHERE id=?', (rid,)).fetchone())
            row['result'] = bracket
            row['podium'] = [dict(place=label, song=song(bracket[key])) for key,label in [('champion_id','1st'),('runner_up_id','2nd'),('third_place_id','3rd')]]
        elif family == 'recognition':
            result = dict(conn.execute('SELECT * FROM trivia_rounds WHERE id=?', (rid,)).fetchone())
            row['song'] = song(result['song_id'])
            row['fields'] = [dict(label=label, correct=result[key+'_correct'], seconds=result[key+'_seconds']) for key,label in [('title','Title'),('artist','Artist'),('album','Album')] if key!='album' or result['album_available']]
        elif family == 'shelves':
            items = [dict(r) for r in conn.execute('SELECT * FROM album_shelf_items WHERE round_id=? ORDER BY answer_slot,answer_position,item_slot', (rid,))]
            rules = conn.execute('SELECT rules_version FROM album_shelf_rounds WHERE id=?', (rid,)).fetchone()[0]
            grade = grade_shelf(items) if can_grade(items, rules) else None
            row['grade'] = grade
            graded = {i['item_slot']: i for i in grade['items']} if grade else {}
            slots = {}
            for item in items:
                slots.setdefault(item['album_slot'], item['album_id'])
            for item in items:
                if item['answer_slot'] is not None:
                    slots.setdefault(item['answer_slot'], None)
            row['shelves'] = []
            for slot, aid in sorted(slots.items()):
                album = conn.execute('SELECT * FROM albums WHERE id=?', (aid,)).fetchone()
                group = dict(slot=slot, album=dict(album) if album else None, tracks=[])
                for item in items:
                    if item['answer_slot'] == slot or (item['answer_slot'] is None and item['album_slot']==slot):
                        result = graded.get(item['item_slot'])
                        item.update(song=song(item['song_id']), result=result,
                            outcome='Unavailable' if result is None else 'Wrong album' if not result['album_correct'] else 'Correct' if result['order_right']==result['order_pairs'] else 'Order affected')
                        group['tracks'].append(item)
                row['shelves'].append(group)
        else:
            sid, map_id = rid.split(':', 1)
            row['song'] = song(int(sid))
            row['result'] = dict(conn.execute('SELECT p.*,m.title,m.x_low,m.x_high,m.y_low,m.y_high FROM song_vibe_positions p JOIN vibe_maps m ON m.id=p.map_id WHERE p.song_id=? AND p.map_id=?', (sid,map_id)).fetchone())
    selected = None
    if target:
        table, label = {'songs':('songs','title'), 'albums':('albums','title'), 'artists':('artists','name'), 'tags':('genres','name')}[kind]
        record = conn.execute(f'SELECT {label} name FROM {table} WHERE id=?', (target,)).fetchone()
        selected = record['name'] if record else 'Record unavailable'
    filters = dict(mode=mode, visibility=visibility, entity=kind, target=target or '', **dates)
    return dict(events=rows, archive_filters=filters, selected_name=selected, archive_errors=errors,
        archive_total=total, archive_totals=totals, archive_page=page, archive_pages=pages,
        archive_start=(page-1)*20+1 if total else 0, archive_end=min(page*20,total),
        archive_modes=[('all','All modes'),('voting','Voting'),('first_round','Tournament first rounds'),('standard','Non-blind Elo'),('blind','Blind Elo'),('tournament','Tournament podiums'),('recognition','Trivia'),('shelves','Album Shelves'),('vibe','Vibe Map')])
