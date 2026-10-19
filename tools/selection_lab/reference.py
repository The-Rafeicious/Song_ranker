"""Offline V4 selector experiments. Never opens or modifies an app database.

Historical reference. Run with Python 3 and NumPy: python reference.py
Input is the included anonymous feature snapshot. Results describe simulations,
not measured player satisfaction, future accuracy, or deployed app behaviour.
"""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import math
import random
import statistics
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parent
DATA=json.loads(ROOT.joinpath('input_snapshot.json').read_text())
SEEDS=list(range(40413,40421))
POLICIES=('legacy','inverse','deficit')
EXPLORE=.10
CHECKS=[]

def check(name,condition):
    CHECKS.append(dict(name=name,passed=bool(condition)))
    if not condition:raise AssertionError(name)

def weights(counts,policy):
    """One natural count unit is the prior; no library-size/count thresholds."""
    x=np.maximum(0,np.asarray(counts,dtype=float))
    if not len(x):return x
    if policy=='legacy':return .25+.75/np.sqrt(1+x)
    if policy=='inverse':need=1/(1+x)
    elif policy=='deficit':need=1+np.maximum(0,float(x.mean())-x)
    else:raise ValueError(policy)
    return EXPLORE/len(x)+(1-EXPLORE)*need/need.sum()

def choose(rng,w):
    if len(w)==0 or not np.all(np.isfinite(w)) or np.any(w<0) or float(w.sum())<=0:
        raise ValueError('No valid eligible distribution')
    return int(np.searchsorted(np.cumsum(w),rng.random()*float(w.sum()),side='right'))

def spread(ratings):
    x=np.asarray(ratings,dtype=float)
    if not len(x) or not np.all(np.isfinite(x)):raise ValueError('Finite ratings required')
    for lo,hi in ((.25,.75),(.10,.90)):
        v=float(np.quantile(x,hi)-np.quantile(x,lo))
        if v>0:return v
    unique=np.unique(x)
    return float(np.median(np.diff(unique))) if len(unique)>1 else 0.0

def pair(rng,counts,ratings,policy,previous=()):
    n=len(counts)
    if n<2:return None
    first_w=weights(counts,policy).copy()
    if policy!='legacy' and n-len(set(previous))>=2:
        first_w[list(previous)]=0
    first=choose(rng,first_w)
    remaining=np.arange(n)!=first
    if policy!='legacy' and n-len(set(previous))>=2:
        remaining[list(previous)]=False
    indexes=np.flatnonzero(remaining)
    gap=np.abs(ratings[indexes]-ratings[first])
    if policy=='legacy':
        elo=.12+.88*np.exp(-((gap-110)/145)**2)
        similar=1/(1+np.abs(counts[indexes]-counts[first])/12)
        second_w=weights(counts[indexes],policy)*elo*(.35+.65*similar)
    else:
        scale=spread(ratings)
        closeness=1/(1+(gap/scale)**2) if scale else np.ones(len(gap))
        # 20% broad shoulder; live scale replaces fixed Elo distances.
        second_w=weights(counts,policy)[indexes]*(.20+.80*closeness)
    second=int(indexes[choose(rng,second_w)])
    return (second,first) if rng.random()<.5 else (first,second)

def summary(values):
    return dict(median=float(np.median(values)),minimum=float(min(values)),maximum=float(max(values)))

def metrics(counts):
    counts=np.asarray(counts,dtype=float)
    return dict(cv=float(counts.std()/counts.mean()) if counts.mean() else 0,
                p90_p10=float(np.quantile(counts,.9)-np.quantile(counts,.1)),
                minimum=float(counts.min()),maximum=float(counts.max()))

def pair_trial(policy,scenario,seed):
    rng=random.Random(seed);r=np.asarray(DATA['ratings'],dtype=float).copy()
    c=np.asarray(DATA['exposures']['public'],dtype=float).copy()
    added=0;new_start=None
    if scenario=='live':rounds=1500
    elif scenario=='growth':
        # A mature library, then 100 new tracks after 500 saved questions.
        c[:]=20;rounds=2000
    elif scenario=='skew':c[:]=0;c[:50]=100;rounds=1500
    elif scenario=='evolving':rounds=3000
    else:raise ValueError(scenario)
    initial_zero=set(np.flatnonzero(c==0));previous=();pairs=[];new_seen=set();new_95=None
    old_mean_at_growth=None;ratings_sum=float(r.sum())
    for t in range(rounds):
        if scenario=='growth' and t==500:
            added=100;new_start=len(c);old_mean_at_growth=float(c.mean())
            c=np.r_[c,np.zeros(added)];r=np.r_[r,np.full(added,1200.)]
            ratings_sum=float(r.sum())
        offered=pair(rng,c,r,policy,previous)
        if offered is None:raise AssertionError('Feasible pool unexpectedly empty')
        a,b=offered;c[a]+=1;c[b]+=1
        pairs.append(tuple(sorted(offered)))
        if new_start is not None:
            new_seen.update(x for x in offered if x>=new_start)
            if len(new_seen)>=95 and new_95 is None:new_95=t-500+1
        if scenario=='evolving':
            # Synthetic consistent preference ordering with 20% reversals.
            va=DATA['ratings'][a];vb=DATA['ratings'][b]
            winner=a if ((va>vb)==(rng.random()<.8)) else b;loser=b if winner==a else a
            delta=32/(1+10**((r[winner]-r[loser])/400))
            r[winner]+=delta;r[loser]-=delta
        previous=offered
    out=metrics(c)
    out['rounds']=rounds
    out['distinct_pairs']=len(set(pairs))/len(pairs)
    out['adjacent_shared_song']=sum(bool(set(a)&set(b)) for a,b in zip(pairs,pairs[1:]))/max(1,len(pairs)-1)
    out['initial_zero_remaining']=sum(c[x]==0 for x in initial_zero)
    if added:
        out.update(new_95_rounds=new_95,new_95_reached=new_95 is not None,
                   old_new_mean_gap=float(c[:new_start].mean()-c[new_start:].mean()),
                   new_mean=float(c[new_start:].mean()),old_mean=float(c[:new_start].mean()),
                   initial_old_mean=old_mean_at_growth)
    if scenario=='evolving':
        out['elo_sum_error']=abs(float(r.sum())-ratings_sum)
        out['final_rating_span']=float(np.ptp(r))
    return out

def rank_positions(values,tolerance=0.0):
    """Midranks retain equal values; no arbitrary tie splitting."""
    v=np.asarray(values);order=np.argsort(v,kind='stable');out=np.empty(len(v),dtype=float)
    i=0
    while i<len(v):
        j=i+1
        while j<len(v) and abs(v[order[j]]-v[order[i]])<=tolerance:j+=1
        out[order[i:j]]=(i+j-1)/2
        i=j
    return out/max(1,len(v)-1)

def guess_pair(rng,counts,ratings,streak,policy='deficit',previous=()):
    if len(ratings)<2 or len(set(ratings))<2:return None
    w=weights(counts,policy).copy()
    # Cooldown is a preference, never a reason to reject a feasible question.
    if previous:w[list(previous)]*=.25
    a=choose(rng,w)
    ix=np.flatnonzero(ratings!=ratings[a]);gaps=np.abs(ratings[ix]-ratings[a])
    if policy=='legacy':s=(np.where((gaps>=40)&(gaps<=250),1.,.25)/np.sqrt(1+counts[ix]))
    else:
        # Group differences smaller than floating-point subtraction resolution.
        tolerance=16*np.finfo(float).eps*max(1.,float(np.max(np.abs(ratings))))
        positions=rank_positions(gaps,tolerance);target=.60/(1+streak/10)
        kernel=.05+.95*np.exp(-.5*((positions-target)/.10)**2)
        s=weights(counts,policy)[ix]*kernel
        if previous:s[np.isin(ix,previous)]*=.25
    b=int(ix[choose(rng,s)])
    return a,b

def guess_trial(streak,seed,policy='deficit'):
    rng=random.Random(seed);r=np.asarray(DATA['ratings'],dtype=float)
    c=np.asarray(DATA['exposures']['guesser'],dtype=float).copy();normalized=[];previous=()
    span=spread(r)
    for _ in range(1500):
        a,b=guess_pair(rng,c,r,streak,policy,previous=previous);c[a]+=1;c[b]+=1
        normalized.append(abs(r[a]-r[b])/span);previous=(a,b)
    return dict(median_gap_units=float(np.median(normalized)),mean_gap_units=float(np.mean(normalized)),**metrics(c))

def draw_entries(rng,counts,size,policy):
    if len(counts)<size:return None
    w=weights(counts,policy);chosen=[]
    for _ in range(size):
        idx=choose(rng,w);chosen.append(idx);w[idx]=0
    return chosen

def single_trial(policy,seed):
    rng=random.Random(seed);c=np.asarray(DATA['exposures']['trivia'],dtype=float).copy();previous=None
    for _ in range(3000):
        w=weights(c,policy)
        if previous is not None:w[previous]=0
        selected=choose(rng,w);c[selected]+=1;previous=selected
    return metrics(c)

def mode_voting_trial(mode,policy,seed):
    rng=random.Random(seed);r=np.asarray(DATA['ratings'],dtype=float)
    target=np.asarray(DATA['exposures'][mode],dtype=float).copy()
    public=np.asarray(DATA['exposures']['public'],dtype=float).copy();previous=()
    untested=np.flatnonzero(target==0)
    for _ in range(1500):
        a,b=pair(rng,public if policy=='legacy' else target,r,policy,previous)
        target[[a,b]]+=1;public[[a,b]]+=1;previous=(a,b)
    return dict(**metrics(target),untested_remaining=int(np.sum(target[untested]==0)))

def tournament_trial(policy,seed):
    rng=random.Random(seed);c=np.asarray(DATA['exposures']['tournament_entries'],dtype=float).copy()
    # Original uses match exposure, including advancing tracks; version 4 uses entries.
    original=np.asarray(DATA['exposures']['tournament_matches'],dtype=float).copy()
    for _ in range(200):
        size=rng.choice([8,16,32]);chosen=draw_entries(rng,original if policy=='legacy' else c,size,policy)
        c[chosen]+=1
        if policy=='legacy':
            # Winners selected independently from entry fairness, with an explicit fixed strength order.
            active=list(chosen)
            while len(active)>1:
                next_round=[]
                for a,b in zip(active[::2],active[1::2]):
                    original[a]+=1;original[b]+=1
                    next_round.append(a if DATA['ratings'][a]>DATA['ratings'][b] else b)
                active=next_round
    return metrics(c)

def feasible(groups,available,n):
    return len(available)>=n and sum(sorted((len(groups[i]) for i in available),reverse=True)[:n])>=10

def shelf_draw(rng,groups,album_counts,track_counts,history,policy,count=0):
    ids=list(groups);possible=[n for n in ([count] if count else [2,3]) if feasible(groups,ids,n)]
    if not possible:return None
    n=rng.choice(possible);last=set(history[-1]) if history else set()
    fresh=[x for x in ids if x not in last]
    if feasible(groups,fresh,n):ids=fresh
    all_ids=list(groups);positions={x:i for i,x in enumerate(all_ids)}
    base=weights([album_counts.get(x,0) for x in all_ids],policy)
    chosen=[]
    for _ in range(n):
        remaining=[x for x in ids if x not in chosen];slots_left=n-len(chosen)-1
        eligible=[x for x in remaining if sum(len(groups[i]) for i in chosen)+len(groups[x])+sum(sorted((len(groups[i]) for i in remaining if i!=x),reverse=True)[:slots_left])>=10]
        ws=[]
        for x in eligible:
            if policy=='legacy':
                recent=history[-5:][::-1];recency=1/(1+sum(5-age for age,albums in enumerate(recent) if x in albums))
                ws.append(recency/math.sqrt(1+album_counts.get(x,0)))
            else:
                age=next((age for age,albums in enumerate(reversed(history)) if x in albums),None)
                expected_cycle=len(all_ids)/n
                recency=1.0 if age is None else 1-math.exp(-(age+1)/expected_cycle)
                ws.append(base[positions[x]]*recency)
        chosen.append(eligible[choose(rng,np.asarray(ws))])
    allocation={x:2 for x in chosen}
    while sum(allocation.values())<10:
        available=[x for x in chosen if allocation[x]<len(groups[x])];smallest=min(allocation[x] for x in available)
        allocation[rng.choice([x for x in available if allocation[x]==smallest])]+=1
    selected=[]
    for x in chosen:
        remaining=list(groups[x]);full_w=weights([track_counts[i] for i in groups[x]],policy)
        indexes={sid:i for i,sid in enumerate(groups[x])}
        for _ in range(allocation[x]):
            ws=np.asarray([1/math.sqrt(1+track_counts[i]) if policy=='legacy' else full_w[indexes[i]] for i in remaining])
            sid=remaining.pop(choose(rng,ws));selected.append(sid)
    rng.shuffle(selected)
    return chosen,selected

def shelf_trial(policy,seed):
    rng=random.Random(seed);groups={int(k):v for k,v in DATA['shelf_groups'].items()}
    ac={int(k):v for k,v in DATA['album_exposure'].items()};tc=np.asarray(DATA['exposures']['shelves'],dtype=float).copy()
    history=[list(x) for x in DATA['recent_shelf_albums']];formats=collections.Counter()
    for _ in range(400):
        albums,tracks=shelf_draw(rng,groups,ac,tc,history,policy);formats[len(albums)]+=1
        if len(tracks)!=10 or len(set(tracks))!=10:raise AssertionError('Invalid shelf allocation')
        for x in albums:ac[x]=ac.get(x,0)+1
        tc[tracks]+=1;history.append(albums)
    return dict(album_cv=metrics([ac.get(i,0) for i in groups])['cv'],
                track_cv=metrics(tc[sorted({i for v in groups.values() for i in v})])['cv'],
                within_album_cv=float(np.mean([metrics(tc[tracks])['cv'] for tracks in groups.values()])),
                two_album_share=formats[2]/400)

def properties():
    rng=random.Random(991)
    for n in (1,2,3,8,50,507,5000):
        for initial in ('zero','uniform','skew','large'):
            c=np.zeros(n) if initial=='zero' else np.ones(n)*20 if initial=='uniform' else np.r_[1000,np.zeros(n-1)] if initial=='skew' else np.arange(n)*10000.
            for policy in ('inverse','deficit'):
                w=weights(c,policy)
                check(f'finite positive probabilities {n} {initial} {policy}',np.all(np.isfinite(w)) and np.all(w>0) and abs(float(w.sum())-1)<1e-12)
                check(f'exploration floor {n} {initial} {policy}',float(w.min())>=EXPLORE/n-1e-15)
    for scale in (.01,.1,1,10,100):
        c=np.asarray(DATA['exposures']['public'],float);r=np.asarray(DATA['ratings'],float)
        base=random.Random(101);scaled=random.Random(101)
        a=[pair(base,c,r,'deficit') for _ in range(60)]
        b=[pair(scaled,c,9000+scale*r,'deficit') for _ in range(60)]
        check(f'affine rating invariance {scale}',a==b)
        base=random.Random(102);scaled=random.Random(102)
        a=[guess_pair(base,c,r,25) for _ in range(60)]
        b=[guess_pair(scaled,c,9000+scale*r,25) for _ in range(60)]
        check(f'affine guess invariance {scale}',a==b)
    c=np.asarray([0,1,5,30,100.])
    for policy in ('inverse','deficit'):
        base=weights(c,policy);repeated=weights(np.tile(c,4),policy).reshape(4,5).sum(axis=0)
        check(f'catalog replication invariance {policy}',np.allclose(base,repeated,atol=1e-14))
    for ratings in ([1200],[1200,1200],[1200,1201],[1200,1200,99999],[1000]*20,[0]+[1200]*18+[50000]):
        r=np.asarray(ratings,dtype=float);c=np.zeros(len(r))
        for seed in range(10):
            p=pair(random.Random(seed),c,r,'deficit')
            check(f'pair valid size {len(r)} seed {seed} unique {len(set(r))}',p is None if len(r)<2 else p is not None and p[0]!=p[1])
            g=guess_pair(random.Random(seed),c,r,100)
            check(f'guess valid size {len(r)} seed {seed} unique {len(set(r))}',g is None if len(set(r))<2 else g is not None and r[g[0]]!=r[g[1]])
    for capacities in ([5,5],[2,2,6],[2,2,2,2,2],[2,3],[2,3,5],[20,2],[2,2,2,10],[2,2,2]):
        groups={};sid=0
        for a,size in enumerate(capacities):groups[a]=list(range(sid,sid+size));sid+=size
        for count in (0,2,3):
            can=any(feasible(groups,list(groups),k) for k in ([count] if count else [2,3]))
            hist=[];tc=np.zeros(sid);ac={}
            for seed in range(10):
                out=shelf_draw(random.Random(seed),groups,ac,tc,hist,'deficit',count)
                check(f'shelf feasibility {capacities} {count} {seed}',(out is not None)==can)
                if out:
                    albums,tracks=out
                    check(f'shelf integrity {capacities} {count} {seed}',len(tracks)==len(set(tracks))==10 and all(sum(i in groups[a] for i in tracks)>=2 for a in albums))
                    hist.append(albums)
    for size in (8,16,32):
        for n in (size-1,size,size+10):
            entry=draw_entries(rng,np.zeros(n),size,'deficit')
            check(f'tournament feasibility {size} {n}',entry is None if n<size else len(entry)==len(set(entry))==size)

def source_parity():
    spec=importlib.util.spec_from_file_location('legacy_selection',ROOT/'legacy_selection.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    a=random.Random(551);b=random.Random(551);c=np.asarray(DATA['exposures']['public'],float);r=np.asarray(DATA['ratings'],float)
    for t in range(100):
        rows=[dict(id=i,elo_score=float(r[i]),matches_played=float(c[i])) for i in range(len(c))]
        offered=module.choose_match(rows,a);expected=tuple(s['id'] for s in offered);got=pair(b,c,r,'legacy')
        check(f'shipped Standard selector parity {t}',expected==got)
        c[list(expected)]+=1

def trivia_backtest():
    result={}
    for policy in ('classic','content_after_10','content_then_all'):
        streak=best=breaks=0
        for row in DATA['trivia_outcomes']:
            title=bool(row['title_correct']);artist=bool(row['artist_correct']);album=bool(row['album_correct']);available=bool(row['album_available'])
            good=title or artist or album
            if policy!='classic' and streak>=10:good=title or (available and album)
            if policy=='content_then_all' and streak>=25:good=title and (album if available else True)
            if good:streak+=1;best=max(best,streak)
            else:breaks+=1;streak=0
        result[policy]=dict(best_streak=best,failed_rounds=breaks)
    return result

def aggregate(rows):
    keys=set.intersection(*(set(row) for row in rows))
    return {key:summary([r[key] for r in rows if r[key] is not None]) for key in sorted(keys) if isinstance(rows[0][key],(int,float)) and all(r[key] is not None for r in rows)}

def main():
    start=time.perf_counter();source_parity();properties();print('Source parity and invariant checks passed',len(CHECKS),flush=True)
    results=dict(seeds=SEEDS,exploration=EXPLORE,numpy_version=np.__version__,python_version=sys.version.split()[0],snapshot_sha256=DATA['source_sha256'],checks=CHECKS,pairs={},voting_by_mode={},trivia={},tournament={},shelves={},guesser={},trivia_backtest=trivia_backtest())
    for scenario in ('live','growth','skew','evolving'):
        results['pairs'][scenario]={}
        for policy in POLICIES:
            rows=[pair_trial(policy,scenario,seed) for seed in SEEDS]
            results['pairs'][scenario][policy]=dict(summary=aggregate(rows),runs=rows)
            print('Pair test',scenario,policy,results['pairs'][scenario][policy]['summary']['cv'],flush=True)
    for mode in ('standard','blind'):
        results['voting_by_mode'][mode]={}
        for policy in ('legacy','deficit'):
            rows=[mode_voting_trial(mode,policy,seed) for seed in SEEDS]
            results['voting_by_mode'][mode][policy]=dict(summary=aggregate(rows),runs=rows)
            print('Voting mode',mode,policy,results['voting_by_mode'][mode][policy]['summary'],flush=True)
    for policy in ('legacy','deficit'):
        for name,fn in [('trivia',single_trial),('tournament',tournament_trial),('shelves',shelf_trial)]:
            rows=[fn(policy,seed) for seed in SEEDS]
            results[name][policy]=dict(summary=aggregate(rows),runs=rows)
            print('Mode test',name,policy,results[name][policy]['summary'],flush=True)
    for streak in (0,10,25,50):
        rows=[guess_trial(streak,seed) for seed in SEEDS]
        results['guesser'][str(streak)]=dict(summary=aggregate(rows),runs=rows)
        print('Guesser stage',streak,results['guesser'][str(streak)]['summary']['median_gap_units'],flush=True)
    rows=[guess_trial(0,seed,'legacy') for seed in SEEDS]
    results['guesser']['legacy']=dict(summary=aggregate(rows),runs=rows)
    check('harder Guesser stages reduce median normalized gap in every seed',all(
        results['guesser']['0']['runs'][i]['median_gap_units']>=results['guesser']['10']['runs'][i]['median_gap_units']>=results['guesser']['25']['runs'][i]['median_gap_units']>=results['guesser']['50']['runs'][i]['median_gap_units'] for i in range(len(SEEDS))))
    check('K 32 remains zero sum in evolving simulations',all(
        run['elo_sum_error']<1e-7 for policy in POLICIES for run in results['pairs']['evolving'][policy]['runs']))
    results['elapsed_seconds']=time.perf_counter()-start
    ROOT.joinpath('results.json').write_text(json.dumps(results,indent=2,default=lambda x:x.item()))
    print('Complete',round(results['elapsed_seconds'],2),'seconds',flush=True)

if __name__=='__main__':main()
