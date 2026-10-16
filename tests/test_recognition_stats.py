"""Read-only Trivia reports against the real mode view, using only memory DBs."""
import sqlite3
import unittest
from unittest.mock import patch

from mode_schema import ensure_mode_schema
from recognition_stats_data import build_recognition_stats
from services import app
import pages

NOW = 1800000000


class RecognitionStatsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,audio_url TEXT);
            CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
            CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT,cover_url TEXT);
            CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
            CREATE TABLE song_genres(song_id INTEGER,genre_id INTEGER);
            CREATE TABLE global_stats(key TEXT PRIMARY KEY,value REAL);
            CREATE TABLE history(id INTEGER PRIMARY KEY);
            CREATE TABLE tournaments(id INTEGER PRIMARY KEY);
            CREATE TABLE tournament_matches(id INTEGER PRIMARY KEY);
        ''')
        ensure_mode_schema(self.conn)
        self.conn.commit()

    def insert(self, table, **values):
        self.conn.execute('INSERT INTO ' + table + ' (' + ','.join(values) + ') VALUES ('
                          + ','.join('?' for _ in values) + ')', tuple(values.values()))

    def seed(self):
        for id, title in [(1, 'Full Album'), (2, 'Song - Single'), (3, 'Unknown Album')]:
            self.insert('albums', id=id, title=title, cover_url='/cover.png')
        for id, name in [(1, 'Artist, One'), (2, 'Other Artist')]:
            self.insert('artists', id=id, name=name, cover_url='/artist.png')
        self.insert('genres', id=1, name='Tag & <text>')
        for id, album, preview in [(1, 1, 'audio'), (2, None, 'audio'), (3, 2, ''), (4, 3, '  '), (5, 1, 'audio')]:
            self.insert('songs', id=id, title='Song ' + str(id), album_id=album, audio_url=preview)
            self.insert('song_artists', song_id=id, artist_id=1)
            self.insert('song_genres', song_id=id, genre_id=1)
        self.insert('song_artists', song_id=1, artist_id=2)
        # Duplicate legacy links must not inflate any group.
        self.insert('song_artists', song_id=1, artist_id=1)
        self.insert('song_genres', song_id=1, genre_id=1)

    def round(self, id, song=1, album=1, answers=(1, 1, 1), **extra):
        values = dict(id=id, token='round-' + str(id), song_id=song, album_available=album,
                      completed_at=NOW - id, title_correct=answers[0], artist_correct=answers[1],
                      album_correct=answers[2], title_seconds=0, artist_seconds=10, album_seconds=30)
        values.update(extra)
        self.insert('trivia_rounds', **values)

    def data(self):
        return build_recognition_stats(self.conn, now=NOW)

    def render(self, data):
        with app.test_request_context('/trivia_stats'):
            return app.jinja_env.get_template('trivia_stats.html').render(**data, app_version='3.4.5')

    def test_empty_rates_and_template(self):
        d = self.data()
        self.assertEqual(d['summary']['rounds'], 0)
        self.assertIsNone(d['summary']['accuracy'])
        self.assertIsNone(d['summary']['average_points'])
        self.assertIsNone(d['coverage']['accuracy'])
        self.assertTrue(all(f['seconds'] is None for f in d['fields']))
        html = self.render(d)
        self.assertIn('No completed rounds yet.', html)
        self.assertIn('aria-valuetext="No attempts yet"', html)
        self.assertNotIn('nan', html.lower())

    def test_full_history_not_recent_hundred_and_incomplete_excluded(self):
        self.seed()
        for id in range(1, 152):
            self.round(id, answers=(1, 1, 1) if id <= 100 else (0, 0, 0))
        self.round(200, completed_at=None)
        d = self.data()
        self.assertEqual(d['summary']['rounds'], 151)
        self.assertEqual(d['summary']['correct'], 300)
        self.assertEqual(d['summary']['available'], 453)
        self.assertEqual(d['summary']['accuracy'], 66.2)
        self.assertEqual(len(d['recent']), 20)
        self.assertEqual([r['id'] for r in d['recent']], list(range(1, 21)))
        self.assertEqual({r['key']: r['count'] for r in d['outcomes']}, dict(perfect=100, partial=0, missed=51))

    def test_missing_album_has_two_eligible_fields_and_can_be_perfect(self):
        self.seed()
        self.round(1, song=2, album=0, answers=(1, 1, None))
        d = self.data()
        self.assertEqual(d['summary']['accuracy'], 100)
        self.assertEqual(d['summary']['available'], 2)
        self.assertEqual(d['fields'][2]['attempts'], 0)
        self.assertIsNone(d['fields'][2]['accuracy'])
        self.assertEqual(d['outcomes'][0]['count'], 1)
        self.assertEqual(d['categories'][1]['best'], [])
        self.assertIn('Album: not applicable', self.render(d))

    def test_groups_pool_fields_not_song_percentages_and_deduplicate_links(self):
        self.seed()
        self.round(1, answers=(1, 0, 1))
        self.round(2, song=2, album=0, answers=(1, 1, None))
        self.round(3, song=2, album=0, answers=(1, 1, None))
        d = self.data()
        artist = {r['id']: r for r in d['categories'][0]['best']}
        self.assertEqual((artist[1]['correct'], artist[1]['attempts'], artist[1]['tested']), (2, 3, 2))
        self.assertEqual((artist[2]['correct'], artist[2]['attempts']), (0, 1))
        tag = d['categories'][2]['best'][0]
        self.assertEqual((tag['correct'], tag['attempts'], tag['accuracy']), (6, 7, 85.7))
        self.assertEqual(d['categories'][1]['best'][0]['accuracy'], 100)

    def test_eligibility_is_historical_even_after_album_changes(self):
        self.seed()
        self.round(1, song=1, album=0, answers=(1, 1, None))
        self.round(2, song=2, album=1, answers=(0, 0, 1))
        self.conn.execute('UPDATE songs SET album_id=NULL WHERE id=1')
        d = self.data()
        self.assertEqual(d['fields'][2]['attempts'], 1)
        self.assertEqual(d['fields'][2]['correct'], 1)
        self.assertEqual(d['categories'][1]['best'], [])
        self.assertIsNone(d['recent'][0]['song']['album_link'])

    def test_adjustments_change_field_totals_but_not_saved_records(self):
        self.seed()
        self.round(1)
        self.insert('trivia_adjustments', song_id=1, new_attempts_delta=3,
                    title_correct_delta=1, artist_correct_delta=0, album_attempts_delta=2,
                    album_correct_delta=1)
        d = self.data()
        self.assertEqual(d['summary']['rounds'], 1)
        self.assertEqual(d['summary']['available'], 11)
        self.assertEqual(d['summary']['correct'], 5)
        self.assertEqual(d['summary']['scored_rounds'], 1)
        self.assertEqual(d['fields'][0]['timed_answers'], 1)

    def test_malformed_adjustments_cannot_create_negative_or_overfull_rates(self):
        self.seed()
        self.insert('trivia_adjustments', song_id=1, new_attempts_delta=2,
                    title_correct_delta=99, artist_correct_delta=-1,
                    album_attempts_delta=90, album_correct_delta=77)
        d = self.data()
        self.assertEqual(d['summary']['available'], 6)
        self.assertEqual(d['summary']['correct'], 4)
        for f in d['fields']:
            self.assertGreaterEqual(f['missed'], 0)
            self.assertLessEqual(f['correct'], f['attempts'])
        self.assertEqual(d['summary']['rounds'], 0)
        self.assertEqual(d['summary']['tested'], 1)

    def test_answer_times_only_use_correct_valid_saved_values_and_keep_zero(self):
        self.seed()
        self.round(1)
        self.round(2, answers=(0, 1, 1), title_seconds=25, artist_seconds=None, album_seconds=-1)
        self.round(3, title_seconds=30, artist_seconds=31, album_seconds=0)
        d = self.data()
        self.assertEqual([(f['seconds'], f['timed_answers']) for f in d['fields']], [(15, 2), (10, 1), (15, 2)])
        self.assertAlmostEqual(d['recent'][0]['points'], .9083)
        self.assertEqual(d['summary']['scored_rounds'], 1)

    def test_points_respect_ineligible_album_and_unknown_results_stay_unknown(self):
        self.seed()
        self.round(1, song=2, album=0, answers=(1, 1, 1))
        self.round(2, answers=(1, None, 1))
        d = self.data()
        self.assertEqual(d['summary']['scored_rounds'], 1)
        self.assertAlmostEqual(d['summary']['points'], .98, places=2)
        self.assertEqual(d['outcomes'][-1]['key'], 'unknown')
        self.assertEqual(d['outcomes'][-1]['count'], 1)
        self.assertIn('Artist: result unavailable', self.render(d))

    def test_preview_coverage_and_unplayed_tracks_stay_separate(self):
        self.seed()
        self.round(1)
        self.round(2, song=3, album=0, answers=(0, 0, None))
        d = self.data()
        self.assertEqual(d['summary']['tested'], 2)
        self.assertEqual(d['coverage'], dict(playable=3, tested=1, untested=2, accuracy=33.3, without_preview=1))
        self.assertEqual({r['id'] for r in d['top_stats']}, {1, 3})

    def test_recent_sorts_completion_times_not_ids_and_windows_exclude_future(self):
        self.seed()
        for id, seconds in enumerate([0, 7*86400, 7*86400+1, 30*86400, 30*86400+1, -10], 1):
            self.round(id, completed_at=NOW-seconds)
        d = self.data()
        self.assertEqual(d['summary']['week'], 2)
        self.assertEqual(d['summary']['month'], 4)
        self.assertEqual([r['id'] for r in d['recent']], [6, 1, 2, 3, 4, 5])

    def test_accuracy_sort_uses_unrounded_ratio_then_exposure(self):
        self.seed()
        for sid, n, c in [(1, 1000, 901), (2, 1000, 902), (3, 1, 1), (4, 2, 2)]:
            self.insert('trivia_adjustments', song_id=sid, new_attempts_delta=n,
                        title_correct_delta=c, artist_correct_delta=c,
                        album_attempts_delta=0, album_correct_delta=0)
        d = self.data()
        self.assertEqual([r['id'] for r in d['top_stats']], [4, 3, 2, 1])
        self.assertEqual([r['id'] for r in d['bottom_stats']], [1, 2, 4, 3])

    def test_long_untrusted_names_escape_and_use_real_relationship_links(self):
        self.seed()
        self.round(1)
        name = 'Long <script>alert(1)</script> & "title" ' * 12
        self.conn.execute('UPDATE songs SET title=? WHERE id=1', (name,))
        html = self.render(self.data())
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('/artist/Artist,%20One', html)
        self.assertIn('/artist/Other%20Artist', html)
        self.assertNotIn('href="/artist/Artist"', html)

    def test_missing_identity_has_no_fake_link_and_does_not_enter_rankings(self):
        self.seed()
        self.round(1, song=None)
        d = self.data()
        self.assertEqual(d['summary']['rounds'], 1)
        self.assertEqual(d['summary']['tested'], 0)
        self.assertEqual(d['top_stats'], [])
        html = self.render(d)
        self.assertIn('Removed track', html)
        self.assertNotIn('/song/None', html)

    def test_query_count_is_bounded_and_projection_makes_no_writes(self):
        self.seed()
        self.round(1)
        self.conn.commit()
        before = '\n'.join(self.conn.iterdump())
        changes = self.conn.total_changes
        statements = []
        self.conn.set_trace_callback(statements.append)
        self.data()
        self.conn.set_trace_callback(None)
        self.assertEqual(len(statements), 9)
        self.assertTrue(all(s.strip().upper().startswith('SELECT') for s in statements))
        self.assertEqual(self.conn.total_changes, changes)
        self.assertEqual('\n'.join(self.conn.iterdump()), before)

    def test_route_uses_one_read_snapshot_and_closes_connection(self):
        data = self.data()
        with patch.object(pages, 'get_db_connection') as get_conn, patch('recognition_stats_data.build_recognition_stats', return_value=data) as build:
            response = app.test_client().get('/trivia_stats')
            self.assertEqual(response.status_code, 200)
            get_conn.return_value.execute.assert_called_once_with('BEGIN')
            build.assert_called_once_with(get_conn.return_value)
            get_conn.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
