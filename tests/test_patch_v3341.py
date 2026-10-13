"""Regression checks for the collection lookups. No database is opened or changed."""
import unittest
from unittest.mock import patch
import overall
from services import app


def fixture():
    return {
        'songs': [
            dict(id=1, title='Measured', artist_ids=[10, 10], tag_ids=[30, 30], album_id=20,
                 elo_score=1300, highest_elo=1350, matches_played=12,
                 voting=dict(matches=12, standard_matches=12, standard_wins=9)),
            dict(id=2, title='Untested', artist_ids=[10], tag_ids=[30], album_id=20),
            dict(id=3, title='Single', artist_ids=[11], tag_ids=[], album_id=21,
                 voting=dict(standard_matches=4, standard_wins=1)),
        ],
        'artists': [dict(id=10, name='Artist'), dict(id=11, name='Other'), dict(id=12, name='Empty')],
        'albums': [dict(id=20, title='Album'), dict(id=21, title='Track - Single'), dict(id=22, title='Empty')],
        'tags': [dict(id=30, name='Tag'), dict(id=31, name='Empty')],
    }


class OverallLookupTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.client = app.test_client()
        self.source = patch.object(overall, 'collection', return_value=self.data)
        self.source.start()
        self.addCleanup(self.source.stop)

    def detail(self, kind, entity_id):
        response = self.client.get('/api/overall/details', query_string=dict(type=kind, id=entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        return response.get_json()['entity']

    def test_artist_album_and_tag_include_each_linked_song_once(self):
        for kind, entity_id in [('artists', 10), ('albums', 20), ('tags', 30)]:
            with self.subTest(kind=kind):
                row = self.detail(kind, entity_id)
                self.assertEqual([song['id'] for song in row['linked_songs']], [1, 2])
                self.assertEqual((row['track_count'], row['tested_tracks']), (2, 1))

    def test_counted_scores_and_confidence_reconstruct_collection_score(self):
        row = self.detail('artists', 10)
        tracks = row['linked_songs']
        unknown = next(song for song in tracks if song['id'] == 2)
        self.assertIsNone(unknown['score'])
        self.assertEqual(unknown['counted_score'], 50.0)
        self.assertAlmostEqual(row['mean_score'], sum(s['counted_score'] for s in tracks) / 2)
        effective = sum(s['evidence'] / 100 for s in tracks)
        self.assertAlmostEqual(row['effective_songs'], effective)
        confidence = effective / (effective + row['group_prior_songs'])
        self.assertAlmostEqual(row['group_confidence'], confidence * 100)
        self.assertAlmostEqual(row['composite_score'], row['prior_score'] + (row['mean_score'] - row['prior_score']) * confidence)

    def test_empty_collections_remain_unknown(self):
        for kind, entity_id in [('artists', 12), ('albums', 22), ('tags', 31)]:
            with self.subTest(kind=kind):
                row = self.detail(kind, entity_id)
                self.assertEqual(row['linked_songs'], [])
                self.assertEqual(row['effective_songs'], 0)
                self.assertIsNone(row['score'])
                self.assertIsNone(row['mean_score'])

    def test_all_untested_collection_has_prior_mean_and_no_score(self):
        self.data['songs'] = [self.data['songs'][1]]
        row = self.detail('tags', 30)
        self.assertIsNone(row['score'])
        self.assertEqual(row['mean_score'], 50.0)
        self.assertEqual(row['effective_songs'], 0)
        self.assertEqual(row['linked_songs'][0]['counted_score'], 50.0)

    def test_song_detail_still_exposes_the_metric_breakdown(self):
        row = self.detail('songs', 1)
        parts = [metric for mode in row['contributions'] for metric in mode['metrics']]
        self.assertGreater(len(parts), 0)
        self.assertAlmostEqual(sum(m['weight'] * m['adjusted'] / 100 for m in parts), row['raw_score'])
        self.assertAlmostEqual(row['composite_score'], row['raw_score'])
        self.assertNotIn('linked_songs', row)

    def test_default_overall_payload_and_scores_are_unchanged_by_diagnostics(self):
        plain = overall.evaluate(self.data, force=True)
        detailed = overall.evaluate(self.data, force=True, details=True)
        for kind in ('songs', 'artists', 'albums', 'tags'):
            for left, right in zip(plain['entities'][kind], detailed['entities'][kind]):
                self.assertEqual(left['id'], right['id'])
                self.assertEqual(left['score'], right['score'])
                self.assertEqual(left['evidence'], right['evidence'])
                self.assertNotIn('linked_songs', left)
                self.assertNotIn('mean_score', left)

    def test_single_is_inspectable_but_still_excluded_from_album_rankings(self):
        row = self.detail('albums', 21)
        self.assertFalse(row['eligible'])
        self.assertEqual([s['id'] for s in row['linked_songs']], [3])
        self.assertIsNotNone(row['composite_score'])
        self.assertIsNone(row['score'])

    def test_invalid_and_missing_lookup_requests(self):
        for query, status in [('type=unknown&id=1', 400), ('type=tags&id=bad', 400),
                              ('type=artists&id=9999', 404)]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/overall/details?' + query).status_code, status)


if __name__ == '__main__':
    unittest.main()
