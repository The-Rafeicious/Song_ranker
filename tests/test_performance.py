import unittest

from catalog import aggregate_performance, song_performance


class PerformanceChecks(unittest.TestCase):
    def setUp(self):
        self.data = {
            'songs': [
                {'id': 1, 'attempts': 1, 'correct': 2},
                {'id': 2, 'attempts': 9, 'correct': 0},
                {'id': 3, 'attempts': 0, 'correct': 0},
                {'id': 4, 'attempts': 0, 'correct': 0},
            ],
            'tournaments': [
                {'id': 1, 'size': 8, 'status': 'completed', 'champion_id': 1},
                {'id': 2, 'size': 8, 'status': 'in_progress', 'champion_id': 3},
                {'id': 3, 'size': 8, 'status': 'completed', 'champion_id': 1},
            ],
            'tournament_entries': [
                {'tournament_id': t, 'song_id': s}
                for t in (1, 2) for s in range(1, 5)
            ],
            'tournament_matches': [
                self.match(1, 2, 1, 3, .5),
                self.match(1, 2, 2, 4, .5),
                self.match(1, 3, 1, 2, 1),
                self.match(2, 2, 3, 1, .5),
                self.match(2, 3, 2, 4, 1, 'pending'),
            ],
        }

    @staticmethod
    def match(tournament, round_number, winner, loser, points, status='completed'):
        return dict(tournament_id=tournament, round_number=round_number,
                    song1_id=winner, song2_id=loser, winner_id=winner,
                    loser_id=loser, points_awarded=points, status=status)

    def test_saved_matches_and_completed_championships(self):
        stats = song_performance(self.data)
        self.assertEqual(stats[1]['championships'], 2)
        self.assertEqual(stats[3]['championships'], 0)
        self.assertEqual(stats[1]['tournament_wins'], 2)
        self.assertEqual(stats[1]['tournament_losses'], 1)
        self.assertEqual(stats[1]['tournament_points'], 1.5)
        self.assertEqual(stats[2]['tournament_wins'], 1)

    def test_placements_and_distinct_top_four_finishes(self):
        stats = song_performance(self.data)
        self.assertEqual(stats[2]['runner_ups'], 1)
        self.assertEqual(stats[3]['semifinals'], 1)
        self.assertEqual(stats[4]['semifinals'], 1)
        self.assertEqual([stats[s]['top_four_finishes'] for s in range(1, 5)], [2, 1, 1, 1])

    def test_unfinished_brackets_have_no_final_placements(self):
        self.data['tournaments'][0]['status'] = 'in_progress'
        stats = song_performance(self.data)
        self.assertEqual(stats[1]['championships'], 1)
        self.assertEqual(stats[2]['runner_ups'], 0)
        self.assertEqual(stats[3]['semifinals'], 0)
        self.assertEqual(stats[1]['tournament_wins'], 2)

    def test_duplicate_entries_and_missing_songs(self):
        self.data['tournament_entries'] += [{'tournament_id': 1, 'song_id': 1},
                                           {'tournament_id': 1, 'song_id': 999}]
        self.data['tournament_matches'].append(self.match(1, 3, 999, 1, 5))
        stats = song_performance(self.data)
        self.assertEqual(stats[1]['tournament_appearances'], 3)
        self.assertEqual(stats[1]['tournament_losses'], 1)
        self.assertNotIn(999, stats)

    def test_recognisability_pools_attempts_not_track_percentages(self):
        stats = aggregate_performance(self.data['songs'])
        self.assertEqual(stats['recognition_score'], 10)
        self.assertEqual(stats['recognition_attempts'], 10)
        self.assertEqual(stats['recognition_correct'], 2)
        self.assertEqual(stats['tested_tracks'], 2)

    def test_one_song_contributes_once(self):
        stats = song_performance(self.data)
        song = {**self.data['songs'][0], **stats[1]}
        total = aggregate_performance([song, song])
        self.assertEqual(total['championships'], 2)
        self.assertEqual(total['recognition_attempts'], 1)
        self.assertEqual(total['tournament_points'], 1.5)

    def test_untested_and_empty_groups_are_unranked(self):
        self.assertIsNone(aggregate_performance([])['recognition_score'])
        self.assertIsNone(aggregate_performance([self.data['songs'][2]])['recognition_score'])
        self.assertEqual(aggregate_performance([])['championships'], 0)


if __name__ == '__main__':
    unittest.main()
