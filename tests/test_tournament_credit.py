"""Selective repetition cannot dominate cross-library tournament evidence."""
import unittest
from songranker.catalog import tournament_weights, song_performance
from songranker.overall import features


class TournamentCreditTests(unittest.TestCase):
    def data(self, broad=True, repeats=10):
        scopes=(['global','tag'] if broad else [])+['artist']*repeats+['album']*repeats
        brackets=[dict(id=i+1,scope_type=scope,status='completed',size=8,champion_id=1) for i,scope in enumerate(scopes)]
        return dict(songs=[dict(id=1),dict(id=2)],tournaments=brackets,
                    tournament_entries=[dict(song_id=s,tournament_id=t['id']) for t in brackets for s in (1,2)],
                    tournament_matches=[dict(id=t['id'],tournament_id=t['id'],song1_id=1,song2_id=2,winner_id=1,loser_id=2,status='completed',points_awarded=7,round_number=3,match_type='bracket') for t in brackets])

    def test_repetition_shares_a_cap_in_all_achievements(self):
        for repeats in (1,10,1000):
            data=self.data(repeats=repeats);weights=tournament_weights(data)
            for scope in ('artist','album'):
                self.assertAlmostEqual(sum(weights[1,t['id']] for t in data['tournaments'] if t['scope_type']==scope),0)
            stats=song_performance(data)[1];expected=2
            self.assertAlmostEqual(stats['championships'],expected)
            self.assertAlmostEqual(stats['tournament_points'],7*expected)
            self.assertAlmostEqual(stats['tournament_wins'],expected)
            self.assertAlmostEqual(stats['tournament_appearances'],expected)
            self.assertEqual(song_performance(data,competitive=False)[1]['championships'],2+2*repeats)

    def test_tag_and_global_results_have_equal_competition_and_overall_credit(self):
        data=self.data(repeats=0)
        global_only={**data, 'tournaments':[data['tournaments'][0]], 'tournament_entries':[e for e in data['tournament_entries'] if e['tournament_id']==1], 'tournament_matches':[m for m in data['tournament_matches'] if m['tournament_id']==1]}
        tag_only={**data, 'tournaments':[data['tournaments'][1]], 'tournament_entries':[e for e in data['tournament_entries'] if e['tournament_id']==2], 'tournament_matches':[m for m in data['tournament_matches'] if m['tournament_id']==2]}
        self.assertEqual(song_performance(global_only),song_performance(tag_only))
        self.assertEqual(features(global_only),features(tag_only))

    def test_local_results_leave_all_overall_features_identical(self):
        self.assertEqual(features(self.data(repeats=0)),features(self.data(repeats=1000)))

    def test_local_only_has_no_competition_evidence(self):
        data=self.data(broad=False)
        self.assertTrue(all(value==0 for value in song_performance(data)[1].values()))
        self.assertEqual(song_performance(data,competitive=False)[1]['championships'],20)

    def test_overall_uses_weighted_evidence_instead_of_raw_counters(self):
        data=self.data(repeats=1000)
        for s in data['songs']:s.update(tournament_wins=999999,tournament_losses=0,tournament_appearances=999999)
        facts=features(data)[1]
        self.assertAlmostEqual(facts['tournament_points']['n'],2)
        self.assertAlmostEqual(facts['mode_appearances']['tournament'],2)
        self.assertAlmostEqual(facts['tournament_wins']['n'],2)
        local=features(self.data(broad=False))[1]
        self.assertIsNone(local['tournament_podium']['value'])
        self.assertEqual(local['mode_appearances']['tournament'],0)

    def test_scope_order_and_unknown_legacy_policy(self):
        data=self.data(repeats=1);weights=tournament_weights(data)
        self.assertEqual([weights[1,i] for i in range(1,5)],[1,1,0,0])
        del data['tournaments'][0]['scope_type']
        data['tournaments'][1]['scope_type']='unknown'
        self.assertEqual(tournament_weights(data)[1,1],1)
        self.assertEqual(tournament_weights(data)[1,2],0)
