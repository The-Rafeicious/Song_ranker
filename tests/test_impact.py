"""Impact evidence, shrinkage and browser/server parity."""
import json
import math
import subprocess
import unittest
from songranker.impact import calibrate, measure


class ImpactTests(unittest.TestCase):
    def test_tested_only_distinct_evidence_and_lighter_prior(self):
        songs=[dict(id=i,elo_score=elo,matches_played=count) for i,elo,count in [(1,1400,1),(2,1200,5),(3,9999,0)]]
        peers=[songs,songs[:1],songs]
        context=calibrate(songs,peers)
        self.assertEqual(context['baseline'],1300)
        self.assertAlmostEqual(context['prior_tracks'],math.sqrt(2))
        value=measure([songs[0],songs[0],songs[2]],context)
        self.assertEqual(value['impact_tracks'],1)
        self.assertAlmostEqual(value['impact_score'],1300+100/(1+math.sqrt(2)))
        self.assertIsNone(measure([songs[2]],context)['impact_score'])
        self.assertEqual(songs[0]['elo_score'],1400)

    def test_empty_flat_and_broad_catalogues_remain_finite(self):
        self.assertIsNone(measure([],calibrate([],[]))['impact_score'])
        songs=[dict(id=i,elo_score=1200,matches_played=1) for i in range(1000)]
        context=calibrate(songs,[songs])
        self.assertEqual(measure(songs,context)['impact_score'],1200)
        self.assertGreater(measure(songs,context)['impact_support'],.96)
        invalid=[dict(id=1001,elo_score=float('nan'),matches_played=4)]
        self.assertIsNone(measure(invalid,context)['impact_score'])

    def test_javascript_matches_python_for_sparse_and_wide_ratings(self):
        songs=[dict(id=i,elo_score=800+i*103,matches_played=i%3) for i in range(18)]
        groups=[songs[:1],songs[1:5],songs[2:14],songs[10:],[]]
        expected=[measure(g,calibrate(songs,groups)) for g in groups]
        code="""const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('static/js/ui.js','utf8'));const x=JSON.parse(process.argv[1]),model=window.SongRankerUI.impactModel(x.songs,x.groups);console.log(JSON.stringify(x.groups.map(g=>model.measure(g))));"""
        actual=json.loads(subprocess.check_output(['node','-e',code,json.dumps(dict(songs=songs,groups=groups))],text=True))
        for left,right in zip(expected,actual):
            for key,value in left.items():
                if value is None:self.assertIsNone(right[key])
                else:self.assertAlmostEqual(value,right[key])
