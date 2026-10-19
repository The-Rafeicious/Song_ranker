"""Standard-library progressive selection/backtest checks; no DB or Flask imports."""
from pathlib import Path
import json
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from challenge_rules import guess_target, trivia_rule, trivia_passed
from selection import choose_guess_pair, gap_positions


def run():
    data = json.loads(Path(__file__).with_name('input_snapshot.json').read_text())
    songs = [dict(id=sid,elo_score=elo) for sid,elo in zip(data['song_ids'],data['ratings'])]
    original = dict(zip(data['song_ids'],data['exposures']['guesser']))
    quantiles = {}
    for first in songs:
        candidates = [s for s in songs if s['elo_score']!=first['elo_score']]
        gaps = [abs(s['elo_score']-first['elo_score']) for s in candidates]
        positions = gap_positions(gaps, 16*sys.float_info.epsilon*max(abs(s['elo_score']) for s in songs))
        quantiles[first['id']] = dict(zip((s['id'] for s in candidates),positions))
    rows = []
    for seed in range(8):
        for streak in (0,10,25,50,100,250):
            rng=random.Random(seed);counts=original.copy();gaps=[];positions=[];seen=set();previous=()
            for _ in range(400):
                first,second=choose_guess_pair(songs,rng,counts=counts,previous=previous,target=guess_target(streak))
                assert first['id']!=second['id'] and first['elo_score']!=second['elo_score']
                positions.append(quantiles[first['id']][second['id']]);gaps.append(abs(first['elo_score']-second['elo_score']))
                previous=(first['id'],second['id']);seen.update(previous)
                for sid in previous:counts[sid]=counts.get(sid,0)+1
            rows.append(dict(seed=seed,streak=streak,target=guess_target(streak),draws=400,
                median_gap=statistics.median(gaps),median_quantile=statistics.median(positions),distinct_tracks=len(seen)))
    for seed in range(8):
        group={r['streak']:r for r in rows if r['seed']==seed}
        assert group[0]['median_quantile']>group[25]['median_quantile']>group[100]['median_quantile']
        assert all(r['distinct_tracks']>200 for r in group.values())
    affine_checks=0
    scaled=[dict(s,elo_score=s['elo_score']*3+20000) for s in songs]
    for seed in range(100):
        first=choose_guess_pair(songs,random.Random(seed),counts=original,target=guess_target(25))
        second=choose_guess_pair(scaled,random.Random(seed),counts=original,target=guess_target(25))
        assert [s['id'] for s in first]==[s['id'] for s in second]
        affine_checks+=1
    classic=progressive=classic_best=progressive_best=0
    for facts in data['trivia_outcomes']:
        classic=classic+1 if any(facts[f+'_correct']==1 for f in ('title','artist','album')) else 0
        rule=trivia_rule(progressive,facts['album_available'])
        progressive=progressive+1 if trivia_passed(dict(facts,streak_rule=rule)) else 0
        classic_best=max(classic_best,classic);progressive_best=max(progressive_best,progressive)
    summary=[]
    for streak in (0,10,25,50,100,250):
        group=[r for r in rows if r['streak']==streak]
        summary.append(dict(streak=streak,target=guess_target(streak),
            median_gap=statistics.median(r['median_gap'] for r in group),
            median_quantile=statistics.median(r['median_quantile'] for r in group),
            minimum_distinct_tracks=min(r['distinct_tracks'] for r in group)))
    return dict(passed=True,source_sha256=data['source_sha256'],seeds=8,draws=len(rows)*400,
        affine_checks=affine_checks,summary=summary,per_seed=rows,
        trivia_backtest=dict(rounds=len(data['trivia_outcomes']),classic_best=classic_best,progressive_best=progressive_best,
            note='Retrospective simulation only. Saved results and records are never rewritten.'))


if __name__=='__main__':
    result=run();output=Path(__file__).with_name('challenge_results.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='per_seed'},indent=2))
