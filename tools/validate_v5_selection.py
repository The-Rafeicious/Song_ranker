"""Reproduce staged selector draws; optionally compare a saved V4 selection.py.

Run from the app root. --output is always a new JSON file. No database writes,
Flask imports, external services, or changes to any song ranking are performed.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import random
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from songranker.modes import selection

FIXED_NOW=1800000000


def simulate(policy,label,seeds,rounds):
    results=[]
    for seed in range(seeds):
        rng=random.Random(seed);pool=[dict(id=i,elo_score=1200,added_at=0) for i in range(80)]
        counts={i:0 for i in range(80)};previous=()
        for step in range(rounds):
            if step==1500:
                for sid in range(80,90):pool.append(dict(id=sid,elo_score=1200,added_at=FIXED_NOW));counts[sid]=0
            a,b=policy.choose_match(pool,rng,counts=counts,previous=previous);previous=(a['id'],b['id'])
            for song in (a,b):counts[song['id']]+=1
            latent=lambda song:1200+180*math.sin(song['id']*.27)
            probability=1/(1+10**((latent(b)-latent(a))/400))
            winner=0 if rng.random()<probability else 1
            expected=1/(1+10**((b['elo_score']-a['elo_score'])/400))
            delta=32*((1 if winner==0 else 0)-expected)
            by_id={s['id']:s for s in pool};by_id[a['id']]['elo_score']+=delta;by_id[b['id']]['elo_score']-=delta
            if step in (99,999,1699,rounds-1):
                values=list(counts.values());mean=statistics.fmean(values)
                results.append(dict(policy=label,seed=seed,round=step+1,mean=mean,cv=statistics.pstdev(values)/mean,
                    min=min(values),max=max(values),new_mean=statistics.fmean(counts[i] for i in range(80,90)) if step>=1500 else None))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,help='Saved V4.1.6 selection.py for comparison')
    parser.add_argument('--seeds',type=int,default=8);parser.add_argument('--rounds',type=int,default=3000)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.seeds<1 or args.rounds<1700:parser.error('Use at least one seed and 1700 rounds.')
    policies=[]
    if args.reference:
        spec=importlib.util.spec_from_file_location('selector_reference',args.reference);reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
        policies.append(('V4.1.6',reference))
    policies.append(('V5',selection));results=[]
    with patch.object(selection.time,'time',return_value=FIXED_NOW):
        for label,policy in policies:results+=simulate(policy,label,args.seeds,args.rounds)
    summary=[]
    for stage in (100,1000,1700,args.rounds):
        for label,_ in policies:
            rows=[r for r in results if r['policy']==label and r['round']==stage]
            summary.append(dict(policy=label,rounds=stage,mean=round(statistics.fmean(r['mean'] for r in rows),2),
                exposure_cv=round(statistics.fmean(r['cv'] for r in rows),4),least=round(statistics.fmean(r['min'] for r in rows),2),
                most=round(statistics.fmean(r['max'] for r in rows),2),new_mean=round(statistics.fmean(r['new_mean'] for r in rows),2) if rows[0]['new_mean'] is not None else None))
    report=dict(seeds=args.seeds,rounds_per_seed=args.rounds,starting_tracks=80,added_tracks=10,added_after_round=1500,results=summary)
    text=json.dumps(report,indent=2)+'\n'
    if args.output:
        with args.output.open('x') as f:f.write(text)
    print(text,end='')


if __name__=='__main__':main()
