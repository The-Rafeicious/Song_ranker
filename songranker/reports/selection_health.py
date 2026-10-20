"""Read-only selector diagnostics using the production pools, counts and kernels."""
import math
from collections import defaultdict
from statistics import fmean

from songranker.modes import selection as S
from songranker.modes.selection_data import (with_catalogue_age, mode_counts, previous_preference, previous_guess, shelf_history)
from songranker.modes.challenge_rules import guess_target


def normalize(weights):
    total=math.fsum(weights)
    return [w/total if total else 0.0 for w in weights]


def build_selection_health(conn, context=None):
    context=context or {}
    songs=[dict(r) for r in conn.execute('SELECT id,title,album_id,elo_score,audio_url FROM songs ORDER BY id')]
    songs=with_catalogue_age(conn,songs)
    albums={r['id']:dict(r) for r in conn.execute('SELECT id,title FROM albums')}
    valid=S.rated_pool(songs)
    previews=[s for s in songs if str(s.get('audio_url') or '').strip(' ')]
    preview_ids={s['id'] for s in previews}
    tagged=conn.execute('SELECT COUNT(DISTINCT sg.song_id) FROM song_genres sg JOIN genres g ON g.id=sg.genre_id JOIN songs s ON s.id=sg.song_id').fetchone()[0]
    from songranker.modes.special_modes import shelf_pool
    groups=shelf_pool(conn)
    shelf_ids={s['id'] for tracks in groups.values() for s in tracks}
    history=shelf_history(conn)
    album_counts={r['album_id']:r['appearances'] for r in conn.execute('SELECT * FROM shelf_album_exposures')}
    run=None
    if context.get('challenge_owner'):
        run=conn.execute("SELECT * FROM challenge_runs WHERE owner=? AND mode='guesser' AND ended_at IS NULL ORDER BY id DESC LIMIT 1",(context['challenge_owner'],)).fetchone()
    streak=0
    if run:
        from songranker.modes.challenges import progress
        streak=progress(conn,run['id'],'guesser')['streak']
    last_trivia=None
    if context.get('challenge_owner'):
        active=conn.execute("SELECT id FROM challenge_runs WHERE owner=? AND mode='trivia' AND ended_at IS NULL ORDER BY id DESC LIMIT 1",(context['challenge_owner'],)).fetchone()
        if active:last_trivia=conn.execute('SELECT song_id FROM trivia_rounds WHERE run_id=? ORDER BY id DESC LIMIT 1',(active['id'],)).fetchone()
    if last_trivia is None and context.get('trivia_round_token'):
        last_trivia=conn.execute('SELECT song_id FROM trivia_rounds WHERE token=?',(context['trivia_round_token'],)).fetchone()
    last_guess=set(previous_guess(conn,context.get('guess_token')))
    from songranker.elo_history import tournament_appearances
    first_rounds=tournament_appearances(conn)
    pools=[]
    def pool(key,label,rows,counts,*,previous=(),rule='base',unit='tracks',kind='song',ready=True):
        rows=list(rows);n=len(rows);values=[S.nonnegative(counts.get(s['id'],0)) for s in rows]
        base=S.exposure_probabilities(values,[s.get('added_at',0) for s in rows]);weights=list(base);excluded=set(previous)
        if rule=='pair':
            if n-len(excluded & {s['id'] for s in rows})<2:excluded.clear()
            weights=[0 if s['id'] in excluded else w for s,w in zip(rows,base)]
        elif rule=='single' and n>1:weights=[0 if s['id'] in excluded else w for s,w in zip(rows,base)]
        elif rule=='guess':weights=[w*(S.GUESS_PREVIOUS if s['id'] in excluded else 1) for s,w in zip(rows,base)]
        probabilities=normalize(weights) if ready else [0.0]*n
        mean=fmean(values) if n else None
        entries=[dict(id=s['id'],name=s.get('title',''),album=albums.get(s.get('album_id'),{}).get('title',''),
            exposure=c,base_probability=b,probability=p,cooling=s['id'] in excluded and p==0)
            for s,c,b,p in zip(rows,values,base,probabilities)]
        eligible=sum(p>0 for p in probabilities)
        from songranker.reports.data_health import exposure_health
        spread=S.rating_spread(s['elo_score'] for s in rows) if rows and 'elo_score' in rows[0] else None
        health=exposure_health(values,spread)
        pools.append(dict(health=health,policy=S.policy(values),first_round_exposures=sum(first_rounds.get(s['id'],{}).get(key,0) for s in rows) if key in ('standard','blind') else None,key=key,label=label,kind=kind,unit=unit,ready=ready,eligible=n,available=eligible,
            tested=sum(c>0 for c in values),untested=sum(c==0 for c in values),
            coverage=100*sum(c>0 for c in values)/n if n else None,total=sum(values),mean=mean,
            below=sum(c<mean for c in values) if n else 0,spread=S.rating_spread(s['elo_score'] for s in rows) if rows and 'elo_score' in rows[0] else None,
            min_share=min((p for p in probabilities if p>0),default=None),max_share=max(probabilities,default=None),
            effective=1/math.fsum(p*p for p in probabilities) if any(probabilities) else None,
            rows=sorted(entries,key=lambda r:(-r['probability'],r['name'].casefold(),r['id']))))
    for key,label in [('standard','Non-blind voting'),('blind','Blind voting')]:
        rows=[s for s in valid if key=='standard' or s['id'] in preview_ids]
        pool(key,label,rows,mode_counts(conn,key),previous=previous_preference(conn,key,context.get('preference_owner')),rule='pair',ready=len(rows)>=2)
    pool('trivia','Trivia',previews,mode_counts(conn,'trivia'),previous=tuple(last_trivia) if last_trivia else (),rule='single',ready=bool(previews))
    tournament_counts=mode_counts(conn,'tournament')
    pool('tournament','Tournament · non-blind',valid,tournament_counts,ready=len(valid)>=8)
    pool('tournament_blind','Tournament · blind',[s for s in valid if s['id'] in preview_ids],tournament_counts,ready=len([s for s in valid if s['id'] in preview_ids])>=8)
    pool('guesser','Elo Guesser',valid,mode_counts(conn,'guesser'),previous=last_guess,rule='guess',ready=len({s['elo_score'] for s in valid})>=2)
    pool('shelves','Album Shelves · albums',[dict(id=aid,title=albums[aid]['title']) for aid in groups],album_counts,kind='album',unit='albums',ready=bool(groups))
    possible=[n for n in (2,3) if S.shelves_feasible(groups,list(groups),n)]
    if not possible:
        pools[-1]['ready']=False
        for row in pools[-1]['rows']:row['probability']=0
        pools[-1].update(available=0,min_share=None,max_share=None,effective=None)
    from songranker.reports.data_health import coverage_health
    def coverage(label,count):return dict(label=label,count=count,total=len(songs),percent=100*count/len(songs) if songs else None,health=coverage_health(count,len(songs)))
    has_details=conn.execute("SELECT 1 FROM sqlite_master WHERE name='song_details'").fetchone()
    bad=conn.execute('SELECT COUNT(*) FROM song_details WHERE preview_bad=1').fetchone()[0] if has_details else 0
    updates={}
    from songranker.modes.judgements import available
    if available(conn):
        from songranker.modes.judgement_selection import diagnostics
        updates={key:diagnostics(conn,key) for key in ('spotlight','vibe')}
    return dict(preview_flags=bad,total=len(songs),quality=[coverage('Preview URLs present',len(previews)),coverage('Tagged tracks',tagged),
        coverage('Finite Elo',len(valid)),coverage('Shelves-eligible tracks',len(shelf_ids))],pools=pools,mode_updates=updates,
        weights=dict(exploration=S.EXPLORATION,shortfall=1-S.EXPLORATION,match_floor=S.MATCH_FLOOR,
            match_close=S.MATCH_CLOSENESS,guess_floor=S.GUESS_FLOOR,guess_target=S.GUESS_TARGET_WEIGHT,
            guess_width=S.GUESS_WIDTH,previous=S.GUESS_PREVIOUS),
        challenge=dict(current_run=bool(run),streak=streak,target=guess_target(streak),
            samples=[dict(streak=n,target=guess_target(n)) for n in (0,10,25,50,100)]),
        shelves=dict(albums=len(groups),tracks=len(shelf_ids),formats=possible,
            formats_share=100/len(possible) if possible else None,last_albums=len(history[-1]) if history else 0,
            cycles=[dict(size=n,cycle=len(groups)/n) for n in possible]))
