"""Read-only standard/blind voting report. No migrations or counter writes."""
from songranker.reports.stats_activity import attach_reports
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from math import ceil, isfinite
from statistics import median, mean, pstdev

from songranker.catalog import (proper_album, versus_metadata)

HISTORY_SIZE = 10
MODES = ('standard', 'blind')


def finite(value):
    try:
        value = float(value)
        return value if isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def percent(n, total):
    return round(100*n/total, 1) if total else None


def average(values):
    values = list(values)
    return round(mean(values), 2) if values else None


def saved_date(value):
    try:
        if isinstance(value, (float, int)):
            date = datetime.fromtimestamp(value, timezone.utc)
        else:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
        return dict(seconds=date.timestamp(), iso=date.isoformat())
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def build_voting_stats(conn, now=None, history_mode='all', history_page=1, history_origin='all'):
    """Caller supplies a SELECT snapshot. Rates pool outcomes, never percentages."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r['id']: dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums = {r['id']: dict(r) for r in conn.execute('SELECT * FROM albums')}
    tags = {r['id']: dict(r) for r in conn.execute('SELECT * FROM genres')}
    artist_ids, tag_ids = defaultdict(set), defaultdict(set)
    for r in conn.execute('SELECT song_id,artist_id FROM song_artists'):
        if r['artist_id'] in artists:
            artist_ids[r['song_id']].add(r['artist_id'])
    for r in conn.execute('SELECT song_id,genre_id FROM song_genres'):
        if r['genre_id'] in tags:
            tag_ids[r['song_id']].add(r['genre_id'])
    songs = {}
    for raw in conn.execute('SELECT * FROM songs'):
        s = dict(raw)
        s.update(versus_metadata(albums.get(s.get('album_id')), [artists[a] for a in artist_ids[s['id']]]))
        s.update(elo_score=finite(s.get('elo_score')), highest_elo=finite(s.get('highest_elo')),
                 wins=0, losses=0, standard_wins=0, standard_losses=0, blind_wins=0, blind_losses=0,
                 net=0, snapshots=0, best_run=0, current_run=0, run_complete=True)
        songs[s['id']] = s

    def identity(sid):
        return songs.get(sid) or dict(id=None, title='Removed track', cover_url='', artist_links=[], album_link=None, elo_score=None)

    from songranker.elo_history import source_sql
    matches, tournament_matches, skipped = [], [], 0
    for raw in conn.execute(f"SELECT * FROM {source_sql(conn)} WHERE mode IN ('standard','blind')"):
        r = dict(raw)
        if r.get('winner_id') is None or r.get('loser_id') is None or r['winner_id'] == r['loser_id']:
            skipped += 1
            continue
        wb, wa, lb, la = [finite(r.get(k)) for k in ('winner_before', 'winner_after', 'loser_before', 'loser_after')]
        before = wb is not None and lb is not None and isfinite(wb-lb)
        snapshot = before and wa is not None and la is not None and isfinite(wa-wb) and isfinite(la-lb) and wa >= wb and la <= lb
        r.update(winner_before=wb, winner_after=wa, loser_before=lb, loser_after=la,
                 winner=identity(r['winner_id']), loser=identity(r['loser_id']), date=saved_date(r.get('created_at')),
                 gap=abs(wb-lb) if before else None, upset=wb < lb if before else None,
                 level=wb == lb if before else False, gain=wa-wb if snapshot else None,
                 loss=lb-la if snapshot else None, snapshot=snapshot)
        (tournament_matches if r.get('origin')=='tournament' else matches).append(r)
    ordinary_matches=list(matches)
    matches+=tournament_matches
    matches.sort(key=lambda r: ((r['date'] or {}).get('seconds', float('-inf')), r['id']))
    for r in matches:
        for sid, won, delta in [(r['winner_id'], True, r['gain']), (r['loser_id'], False, -r['loss'] if r['loss'] is not None else None)]:
            if sid not in songs:
                continue
            s = songs[sid]
            s['wins' if won else 'losses'] += r.get('rating_weight',1)
            s[r['mode']+('_wins' if won else '_losses')] += r.get('rating_weight',1)
            if delta is not None:
                s['net'] += delta
                s['snapshots'] += 1
            if not r['date'] or r['date']['seconds'] > now:
                s['run_complete'] = False
            else:
                s['current_run'] = s['current_run']+1 if won else 0
                s['best_run'] = max(s['best_run'], s['current_run'])
    for s in songs.values():
        s['matches'] = s['wins']+s['losses']
        s['win_rate'] = percent(s['wins'], s['matches'])
        s['net'] = round(s['net'], 2)
        for mode in MODES:
            s[mode+'_matches'] = s[mode+'_wins']+s[mode+'_losses']
            s[mode+'_rate'] = percent(s[mode+'_wins'], s[mode+'_matches'])
        if not s['run_complete']:
            s['best_run'] = None

    def result_totals(rows):
        rated = [r for r in rows if r['gap'] is not None]
        unequal = [r for r in rated if not r['level']]
        changes = [r for r in rows if r['snapshot']]
        days = {r['date']['iso'][:10] for r in rows if r['date'] and r['date']['seconds'] <= now}
        live = {sid for r in rows for sid in (r['winner_id'], r['loser_id']) if sid in songs}
        weight=lambda group:sum(r.get('rating_weight',1) for r in group)
        upsets=weight([r for r in unequal if r['upset']]); unequal_weight=weight(unequal)
        return dict(matches=len(rows), effective_matches=weight(rows), rated=len(rated), unequal=unequal_weight,
                    upsets=upsets, upset_rate=percent(upsets, unequal_weight),
                    level=len(rated)-len(unequal), snapshots=len(changes), active_days=len(days), tracks=len(live),
                    avg_gain=average(r['gain'] for r in changes), avg_gap=round(sum(r['gap']*r.get('rating_weight',1) for r in rated)/weight(rated),2) if weight(rated) else None)

    summary = result_totals(matches)
    summary.update(undated=sum(not r['date'] for r in matches), skipped=skipped,
                   removed=sum(r['winner_id'] not in songs or r['loser_id'] not in songs for r in matches))
    modes = [dict(mode=m, title='Non-blind' if m=='standard' else 'Blind', **result_totals([r for r in matches if r['mode']==m])) for m in MODES]
    for m in modes:
        m['share'] = percent(m['matches'], len(matches))
    tested = [s for s in songs.values() if s['matches']]
    coverage = dict(total=len(songs), voted=len(tested), unplayed=len(songs)-len(tested), share=percent(len(tested), len(songs)),
                    both=sum(bool(s['standard_matches'] and s['blind_matches']) for s in songs.values()),
                    standard_only=sum(bool(s['standard_matches'] and not s['blind_matches']) for s in songs.values()),
                    blind_only=sum(bool(s['blind_matches'] and not s['standard_matches']) for s in songs.values()))
    windows = []
    for n in (7, 30):
        group = [r for r in matches if r['date'] and now-n*86400 <= r['date']['seconds'] <= now]
        windows.append(dict(days=n, standard=sum(r['mode']=='standard' for r in group), blind=sum(r['mode']=='blind' for r in group), **result_totals(group)))
    calendar = Counter((r['date']['iso'][:10], r['mode']) for r in matches if r['date'] and r['date']['seconds'] <= now)
    today = datetime.fromtimestamp(now, timezone.utc).date()
    activity = [dict(date=(today-timedelta(days=n)).isoformat(), standard=calendar[((today-timedelta(days=n)).isoformat(),'standard')], blind=calendar[((today-timedelta(days=n)).isoformat(),'blind')]) for n in reversed(range(14))]
    day_totals = Counter()
    for (day, mode), n in calendar.items():
        day_totals[day] += n
    busiest = sorted(day_totals.items(), key=lambda p: (-p[1], p[0]))[0] if day_totals else None
    valid_dates = [r['date'] for r in matches if r['date'] and r['date']['seconds'] <= now]
    activity_summary = dict(avg_day=round(sum(day_totals.values())/len(day_totals),1) if day_totals else None,first=min(valid_dates,key=lambda d:d['seconds']) if valid_dates else None,
                            latest=max(valid_dates,key=lambda d:d['seconds']) if valid_dates else None,
                            busiest_day=busiest[0] if busiest else '—', busiest_votes=busiest[1] if busiest else 0,
                            max_day=max((d['standard']+d['blind'] for d in activity),default=0))
    ratings = [s['elo_score'] for s in songs.values() if s['elo_score'] is not None]
    distribution = dict(median=round(median(ratings),1) if ratings else None, highest=max(ratings) if ratings else None,
                        lowest=min(ratings) if ratings else None, spread=round(pstdev(ratings),1) if ratings else None,
                        rated=len(ratings), unavailable=len(songs)-len(ratings), bands=[])
    for low, high, label in [(None,1000,'Below 1000')]+[(n,n+50,f'{n}–<{n+50}') for n in range(1000,1400,50)]+[(1400,None,'1400+')]:
        group = [s for s in songs.values() if s['elo_score'] is not None and (low is None or s['elo_score']>=low) and (high is None or s['elo_score']<high)]
        distribution['bands'].append(dict(label=label, count=len(group), share=percent(len(group),len(ratings)), voted=sum(bool(s['matches']) for s in group)))
    unequal = [r for r in matches if r['gap'] is not None and not r['level']]
    snapshots = [r for r in matches if r['snapshot']]
    movement = dict(avg_gain=average(r['gain'] for r in snapshots), avg_loss=average(r['loss'] for r in snapshots),
                    total=round(sum(r['gain'] for r in snapshots),2), largest_gain=max((r['gain'] for r in snapshots),default=None),
                    largest_upset=max((r['gap'] for r in unequal if r['upset']),default=None),
                    missing=len(matches)-len(snapshots), drift=round(sum(r['gain']-r['loss'] for r in snapshots),6))
    gaps = []
    for low, high, label in [(0,50,'Under 50'),(50,100,'50–<100'),(100,200,'100–<200'),(200,400,'200–<400'),(400,None,'400+')]:
        group = [r for r in matches if r['gap'] is not None and low<=r['gap'] and (high is None or r['gap']<high)]
        gaps.append(dict(label=label, **result_totals(group)))
    by_pair = defaultdict(list)
    for r in matches:
        by_pair[tuple(sorted((r['winner_id'], r['loser_id'])))].append(r)
    pairs = []
    for (a,b), rows in by_pair.items():
        if len(rows)<2:
            continue
        a_wins = sum(r.get('rating_weight',1) for r in rows if r['winner_id']==a)
        vote_weight = sum(r.get('rating_weight',1) for r in rows)
        pairs.append(dict(first=identity(a), second=identity(b), first_wins=a_wins, second_wins=vote_weight-a_wins, vote_weight=vote_weight,
                          standard=sum(r['mode']=='standard' for r in rows), blind=sum(r['mode']=='blind' for r in rows), matches=len(rows)))
    pairs.sort(key=lambda p: (-p['matches'],p['first']['title'].casefold(),p['second']['title'].casefold()))
    both = [s for s in tested if s['standard_matches']>=3 and s['blind_matches']>=3]
    for s in both:
        s['blind_lift'] = round(100*s['blind_wins']/s['blind_matches']-100*s['standard_wins']/s['standard_matches'],1)
    def top(rows, metric, reverse=True):
        return sorted(rows,key=lambda s:(-s[metric] if reverse else s[metric], -s['matches'],s['title'].casefold(),s['id']))[:5]

    def category(kind,title,entities,links):
        rows=[]
        for eid, entity in entities.items():
            if kind=='album' and not proper_album(entity):
                continue
            tracks=[s for s in songs.values() if eid in links(s)]
            appearances=sum(s['matches'] for s in tracks)
            if not appearances:
                continue
            wins=sum(s['wins'] for s in tracks)
            rows.append(dict(id=eid,name=entity.get('name',entity.get('title','')),cover_url=entity.get('cover_url') or '',
                             wins=wins, losses=appearances-wins, matches=appearances, tested=sum(bool(s['matches']) for s in tracks),
                             win_rate=percent(wins,appearances), standard=sum(s['standard_matches'] for s in tracks),blind=sum(s['blind_matches'] for s in tracks)))
        return dict(kind=kind,title=title,most=sorted(rows,key=lambda r:(-r['matches'],r['name'].casefold(),r['id']))[:5],
                    best=sorted((r for r in rows if r['matches']>=5),key=lambda r:(-r['wins']/r['matches'],-r['matches'],r['name'].casefold(),r['id']))[:5])
    history_mode=history_mode if history_mode in MODES else 'all'
    history_origin=history_origin if history_origin in ('ordinary','tournament') else 'all'
    elo_matches=sorted(matches,key=lambda r:((r['date'] or {}).get('seconds',float('-inf')),r['id']))
    latest=list(reversed(elo_matches));filtered=[r for r in latest if (history_mode=='all' or r['mode']==history_mode) and (history_origin=='all' or (r.get('origin')=='tournament')==(history_origin=='tournament'))]
    elo_summary=dict(total=len(elo_matches),ordinary=len(ordinary_matches),tournament=len(tournament_matches),full=sum(r.get('rating_weight')==1 for r in tournament_matches),half=sum(r.get('rating_weight')==.5 for r in tournament_matches),gain=sum(r['gain'] or 0 for r in tournament_matches))
    source_modes=[dict(origin=origin,mode=mode,**result_totals([r for r in matches if (r.get('origin')=='tournament')==(origin=='tournament') and r['mode']==mode])) for origin in ('ordinary','tournament') for mode in MODES]
    pages=max(1,ceil(len(filtered)/HISTORY_SIZE))
    try:
        history_page=max(1,min(int(history_page),pages))
    except (ValueError,TypeError,OverflowError):
        history_page=1
    start=(history_page-1)*HISTORY_SIZE
    from songranker.modes.mode_ratings import comparison_report
    return attach_reports(conn, dict(source_modes=source_modes,tournament_history=sorted(tournament_matches,key=lambda r:r['id'],reverse=True)[:4],elo_summary=elo_summary,history_origin=history_origin,split_elo=comparison_report(conn, songs.values()),summary=summary,modes=modes,coverage=coverage,windows=windows,activity=activity,activity_summary=activity_summary,
                distribution=distribution,movement=movement,gaps=gaps,pairs=pairs[:5],unique_pairs=len(by_pair),repeated_pairs=len(pairs),
                upsets=sorted((r for r in unequal if r['upset']),key=lambda r:(-r['gap'],-r['id']))[:5],
                gains=sorted(snapshots,key=lambda r:(-r['gain'],-r['id']))[:5],
                leaders=top([s for s in tested if s['elo_score'] is not None],'elo_score'),most_played=top(tested,'matches'),
                most_wins=top(tested,'wins'),best_rates=sorted((s for s in tested if s['matches']>=5),key=lambda s:(-s['wins']/s['matches'],-s['matches'],s['title'].casefold(),s['id']))[:5],
                gain_tracks=top([s for s in tested if s['snapshots'] and s['net']>0],'net'),loss_tracks=top([s for s in tested if s['snapshots'] and s['net']<0],'net',False),
                runs=top([s for s in tested if s['best_run'] is not None and s['best_run']>0],'best_run'),
                blind_lift=top([s for s in both if s['blind_lift']>0],'blind_lift'),standard_lift=top([s for s in both if s['blind_lift']<0],'blind_lift',False),
                categories=[category('artist','Artist records',artists,lambda s:artist_ids[s['id']]),
                            category('album','Album records',albums,lambda s:[s.get('album_id')]),
                            category('tag','Tag records',tags,lambda s:tag_ids[s['id']])],
                history=filtered[start:start+HISTORY_SIZE],history_mode=history_mode,history_page=history_page,history_pages=pages,
                history_total=len(filtered),history_start=start+1 if filtered else 0,history_end=min(start+HISTORY_SIZE,len(filtered))), 'voting', now=now)
