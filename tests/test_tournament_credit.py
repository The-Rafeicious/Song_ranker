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
            for scope,cap in [('artist',.02),('album',.005)]:
                self.assertAlmostEqual(sum(weights[1,t['id']] for t in data['tournaments'] if t['scope_type']==scope),min(repeats*cap,1.5*cap))
            stats=song_performance(data)[1];expected=1.5+min(repeats,1.5)*.025
            self.assertAlmostEqual(stats['championships'],expected)
            self.assertAlmostEqual(stats['tournament_points'],7*expected)
            self.assertAlmostEqual(stats['tournament_wins'],expected)
            self.assertAlmostEqual(stats['tournament_appearances'],expected)
            self.assertEqual(song_performance(data,competitive=False)[1]['championships'],2+2*repeats)

    def test_local_only_has_no_competition_evidence(self):
        data=self.data(broad=False)
        self.assertTrue(all(value==0 for value in song_performance(data)[1].values()))
        self.assertEqual(song_performance(data,competitive=False)[1]['championships'],20)

    def test_overall_uses_weighted_evidence_instead_of_raw_counters(self):
        data=self.data(repeats=1000)
        for s in data['songs']:s.update(tournament_wins=999999,tournament_losses=0,tournament_appearances=999999)
        facts=features(data)[1]
        self.assertAlmostEqual(facts['tournament_points']['n'],1.5375)
        self.assertAlmostEqual(facts['mode_appearances']['tournament'],1.5375)
        self.assertAlmostEqual(facts['tournament_wins']['n'],1.5375)
        local=features(self.data(broad=False))[1]
        self.assertIsNone(local['tournament_podium']['value'])
        self.assertEqual(local['mode_appearances']['tournament'],0)

    def test_scope_order_and_unknown_legacy_policy(self):
        data=self.data(repeats=1);weights=tournament_weights(data)
        self.assertEqual([weights[1,i] for i in range(1,5)],[1,.5,.02,.005])
        del data['tournaments'][0]['scope_type']
        data['tournaments'][1]['scope_type']='unknown'
        self.assertEqual(tournament_weights(data)[1,1],1)
        self.assertEqual(tournament_weights(data)[1,2],0)
