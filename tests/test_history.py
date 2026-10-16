"""Regression coverage for the populated Match History page's VS-row contract."""
import sqlite3
import unittest
from unittest.mock import patch

from services import app, fetch_match_history
import pages
import games


class MatchHistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,elo_score REAL);
            CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
            CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
            CREATE TABLE history(id INTEGER PRIMARY KEY,winner_id INTEGER,loser_id INTEGER,
                mode TEXT,created_at TEXT,winner_before REAL,winner_after REAL,
                loser_before REAL,loser_after REAL);
            INSERT INTO albums VALUES(1,'Album <one>','cover-one'),(2,'Two - Single',''),(3,'Unknown Album','');
            INSERT INTO songs VALUES(1,'Song <one>',1,1400),(2,'Song two',2,1100),(3,'Song three',3,1200);
            INSERT INTO artists VALUES(1,'Name, With Comma'),(2,'Guest & Friend');
            INSERT INTO song_artists VALUES(1,1),(1,2),(1,2),(2,1);
        ''')

    def vote(self, winner=1, loser=2, mode='standard'):
        self.conn.execute('''INSERT INTO history(winner_id,loser_id,mode,created_at,
            winner_before,winner_after,loser_before,loser_after) VALUES(?,?,?,'2026-10-16 12:00:00',
            1200,1216,1200,1184)''', (winner, loser, mode))

    def request(self, **kwargs):
        self.conn.commit()
        def connection():
            result = sqlite3.connect(':memory:')
            result.row_factory = sqlite3.Row
            self.conn.backup(result)
            return result
        with patch('pages.get_db_connection', side_effect=connection):
            return app.test_client().get('/history', **kwargs)

    def test_populated_page_renders_both_modes_and_saved_ratings(self):
        self.vote(); self.vote(winner=2, loser=1, mode='blind')
        response = self.request()
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(html.count('data-match-id='), 2)
        for text in ['data-match-mode="standard"', 'data-match-mode="blind"',
                     'href="/song/1"', 'Song &lt;one&gt;', '1216', '1184', '+16', '-16']:
            self.assertIn(text, html)
        self.assertNotIn('Current Elo', html)
        self.assertLess(html.index('data-match-id="2"'), html.index('data-match-id="1"'))

    def test_empty_page(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="history-empty" >No matches', response.get_data(as_text=True))

    def test_artist_relationships_preserve_names_and_deduplicate(self):
        self.vote()
        row = fetch_match_history(self.conn)[0]
        self.assertEqual([a['name'] for a in row['winner_song']['artist_links']],
                         ['Guest & Friend', 'Name, With Comma'])
        html = self.request().get_data(as_text=True)
        self.assertIn('href="/artist/Name,%20With%20Comma"', html)
        self.assertIn('Guest &amp; Friend', html)
        self.assertIn('href="/album/Album%20%3Cone%3E"', html)
        self.assertNotIn('href="/album/Two%20-%20Single"', html)

    def test_missing_album_artists_and_snapshots_render_current_elo(self):
        self.vote(winner=3)
        self.conn.execute('UPDATE history SET winner_before=NULL,winner_after=NULL,loser_before=NULL')
        self.conn.execute('UPDATE songs SET album_id=NULL WHERE id=3')
        response = self.request()
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for text in ['Unknown artist', 'Current Elo', 'Elo after match']:
            self.assertIn(text, html)
        self.assertNotIn('href="/album/Unknown', html)

    def test_legacy_history_without_snapshot_columns(self):
        self.conn.execute('DROP TABLE history')
        self.conn.execute('''CREATE TABLE history(id INTEGER PRIMARY KEY,winner_id INTEGER,
            loser_id INTEGER,mode TEXT,created_at TEXT)''')
        self.conn.execute("INSERT INTO history VALUES(1,1,2,'standard',NULL)")
        response = self.request()
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Current Elo', html)
        self.assertIn('Date unavailable', html)

    def test_scope_limits_order_and_deleted_tracks(self):
        for n in range(55):
            self.vote(winner=1 if n % 2 else 3)
        self.vote(winner=99)
        self.assertEqual(len(fetch_match_history(self.conn)), 50)
        self.assertEqual(fetch_match_history(self.conn, limit=1)[0]['id'], 55)
        rows = fetch_match_history(self.conn, song_id=1, limit=500)
        self.assertEqual(len(rows), 27)
        self.assertTrue(all(1 in (r['winner_id'], r['loser_id']) for r in rows))
        self.assertEqual(len(fetch_match_history(self.conn, limit=0)), 1)
        self.assertEqual(self.request().status_code, 200)

    def test_batch_limit_handles_1000_distinct_tracks(self):
        self.conn.executemany('INSERT INTO songs VALUES(?,?,NULL,1200)',
                              [(n, 'Track ' + str(n)) for n in range(4, 1001)])
        for n in range(1, 1000, 2):
            self.vote(winner=n, loser=n + 1)
        if hasattr(self.conn, 'setlimit'):  # Available on Python 3.11+.
            self.conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)
        self.assertEqual(len(fetch_match_history(self.conn, limit=9999)), 500)

    def test_reader_is_read_only(self):
        self.vote()
        before = self.conn.total_changes
        statements = []
        self.conn.set_trace_callback(statements.append)
        fetch_match_history(self.conn)
        self.assertEqual(self.conn.total_changes, before)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))

    def test_allowed_phone_and_denied_device(self):
        self.vote()
        allowed = next(iter(app.extensions['song_ranker_security']['allowed']))
        response = self.request(base_url='http://192.168.1.20:5000',
                                environ_overrides={'REMOTE_ADDR': str(allowed)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.request(environ_overrides={'REMOTE_ADDR': '203.0.113.254'}).status_code, 403)
        denied = app.test_client().get('/dev/login', environ_overrides={'REMOTE_ADDR': str(allowed)})
        self.assertEqual(denied.status_code, 403)

    def test_connection_closes_if_history_read_fails(self):
        connection = sqlite3.connect(':memory:')
        with patch('pages.get_db_connection', return_value=connection), \
             patch('pages.fetch_match_history', side_effect=RuntimeError('read failed')):
            with app.test_request_context('/history'), self.assertRaises(RuntimeError):
                pages.history()
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')


if __name__ == '__main__':
    unittest.main()
