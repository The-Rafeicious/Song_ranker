"""Endpoint display hotfix regressions; pure calculator inputs, no DB writes."""
import unittest
import overall
from test_patch_v3342 import population_data, result


class EndpointDisplayTests(unittest.TestCase):
    def test_imperfect_best_and_worst_records_keep_margin_from_endpoints(self):
        rows=[dict(composite_score=value) for value in [0.000001,35,65,99.999999]]
        overall.apply_percentiles(rows)
        self.assertEqual(rows[0]['score'],2)
        self.assertEqual(rows[-1]['score'],98)
        self.assertEqual(rows[0]['rank_percentile'],0)
        self.assertEqual(rows[-1]['rank_percentile'],100)
        self.assertTrue(all(0<r['score']<100 for r in rows))

    def test_absolute_composites_can_still_use_absolute_endpoints(self):
        rows=[dict(composite_score=value) for value in [0,20,80,100]]
        overall.apply_percentiles(rows)
        self.assertEqual([r['score'] for r in rows],[0,34,66,100])

    def test_tied_imperfect_leaders_share_the_adjusted_midrank(self):
        rows=[dict(composite_score=value) for value in [30,70,70]]
        overall.apply_percentiles(rows)
        self.assertEqual([r['score'] for r in rows],[2,74,74])
        self.assertEqual(sum(r['score'] for r in rows)/3,50)

    def test_uncertain_undefeated_song_is_not_automatically_perfect(self):
        data=population_data()
        song=result(data)['entities']['songs'][0]
        self.assertEqual(song['rank_percentile'],100)
        self.assertLess(song['composite_score'],100)
        self.assertEqual(song['score'],98)

    def test_missing_a_podium_prevents_perfect_overall_even_when_ranked_first(self):
        data=population_data()
        data['songs'][-1]=population_data(plays=20)['songs'][-1]
        data['tournaments']=[dict(id=1,status='completed',size=8,champion_id=1)]
        data['tournament_entries']=[dict(tournament_id=1,song_id=sid) for sid in [1,20]]
        song=next(r for r in result(data,True)['entities']['songs'] if r['id']==20)
        podium=next(m for c in song['contributions'] for m in c['metrics'] if m['key']=='tournament_podium')
        self.assertEqual(podium['raw'],0)
        self.assertEqual(song['rank_percentile'],100)
        self.assertEqual(song['score'],98)

    def test_ordinary_scores_keep_order_and_the_population_center(self):
        rows=[dict(composite_score=value) for value in [20,30,40,60,70,80]]
        overall.apply_percentiles(rows)
        self.assertEqual([r['score'] for r in rows],sorted(r['score'] for r in rows))
        self.assertEqual(sum(r['score'] for r in rows)/len(rows),50)
        self.assertEqual(rows[-1]['score']-rows[0]['score'],96)

    def test_empty_or_ineligible_records_have_no_rank_or_display_score(self):
        rows=[dict(composite_score=None),dict(composite_score=100,eligible=False)]
        overall.apply_percentiles(rows)
        self.assertTrue(all(r['score'] is None and r['rank_percentile'] is None for r in rows))


if __name__=='__main__':unittest.main()
