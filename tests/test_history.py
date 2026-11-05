"""Cross-mode archive dates, scope, pagination, privacy and saved result rendering."""
import unittest
from unittest.mock import patch
import test_elo_replay as fixture
from songranker import services, pages
from songranker.modes import voting, tournament, shelves, trivia
from songranker.reports.stats_activity import match_archive
from songranker.storage.database_io import capture


class HistoryTests(unittest.TestCase):
    setUp = fixture.EloReplayTests.setUp

    def seed(self):
        """Store results on UTC boundaries with repeated collection membership."""
        self.conn.execute("INSERT INTO genres(id,name) VALUES(1,'Tag')")
        self.conn.executemany('INSERT INTO song_genres VALUES(?,1)', [(1,), (2,)])
        self.conn.execute("INSERT INTO preference_events(winner_id,loser_id,mode,origin,created_at) VALUES(1,2,'standard','ordinary','2026-11-01 23:59:59')")
        self.conn.execute("INSERT INTO preference_events(winner_id,loser_id,mode,origin,created_at) VALUES(2,3,'blind','ordinary','2026-11-02 00:00:00')")
        self.conn.execute("INSERT INTO tournaments(id,size,scope_type,status,champion_id,runner_up_id,third_place_id,completed_at) VALUES(1,8,'global','completed',1,2,3,'2026-11-01 12:00:00')")
        self.conn.execute("INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,title_seconds) VALUES('trivia',1,0,1793534400,1,0,2.5)")
        self.conn.execute("INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(1,'shelf',1793534400,1793534400)")
        self.conn.executemany('INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,answer_slot,answer_position) VALUES(1,?,?,1,1,?,1,?)', [(1,1,1,2),(2,2,2,1)])
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=0.5,y=-0.5,updated_at=1793534400,sample_count=2 WHERE song_id=1 AND map_id='pace_mood'")
        self.conn.commit()

    def test_union_scope_date_and_no_writes(self):
        self.seed()
        before = capture(self.conn)
        data = match_archive(self.conn, {'from':'2026-11-01','to':'2026-11-01'})
        self.assertEqual(data['archive_total'], 5)
        self.assertEqual({r['family'] for r in data['events']}, {'elo','tournament','recognition','shelves','vibe'})
        for kind in ('songs','albums','artists','tags'):
            scoped = match_archive(self.conn, {'entity':kind,'target':'1','from':'2026-11-01','to':'2026-11-01'})
            self.assertEqual(scoped['archive_total'], 5)
        self.assertEqual(match_archive(self.conn, {'mode':'blind'})['archive_total'], 1)
        self.assertEqual(match_archive(self.conn, {'mode':'blind','origin':'ordinary'})['archive_total'], 1)
        self.assertEqual(match_archive(self.conn, {'mode':'standard','origin':'ordinary'})['archive_total'], 1)
        self.assertEqual(match_archive(self.conn, {'mode':'all','entity':'songs','target':'999'})['archive_total'], 0)
        self.assertEqual(capture(self.conn), before)

    def test_page_bounds_and_invalid_dates(self):
        self.seed()
        self.conn.executemany("INSERT INTO preference_events(winner_id,loser_id,mode,origin,created_at) VALUES(1,2,'standard','ordinary',?)", [('2026-11-03 12:00:00',)]*25)
        data = match_archive(self.conn, {'mode':'voting','page':'9999'})
        self.assertEqual(data['archive_page'], 2)
        self.assertEqual(len(data['events']), 7)
        self.assertEqual(match_archive(self.conn, {'page':'bad'})['archive_page'], 1)
        self.assertTrue(match_archive(self.conn, {'from':'bad'})['archive_errors'])
        self.assertEqual(match_archive(self.conn, {'from':'2026-11-03','to':'2026-11-01'})['events'], [])

    def test_results_and_rendering(self):
        self.seed()
        archive = match_archive(self.conn, {})
        shelf = next(r for r in archive['events'] if r['family']=='shelves')
        self.assertEqual([i['answer_position'] for i in shelf['shelves'][0]['tracks']], [1,2])
        self.assertEqual(shelf['shelves'][0]['tracks'][0]['outcome'], 'Order affected')
        rec = next(r for r in archive['events'] if r['family']=='recognition')
        self.assertEqual([r['correct'] for r in rec['fields']], [1,0])
        with patch.object(voting, 'get_db_connection', side_effect=lambda: self.open_connection()):
            response = services.app.test_client().get('/history?from=2026-11-01&to=2026-11-01')
        self.assertEqual(response.status_code, 200)
        text = response.text
        for fragment in ('Correct: shelf 1, disc 1, track', '✓ Correct', '✕ Missed', '/tournament/1/bracket', 'Retained maps', 'Artist &lt;unsafe&gt;'):
            self.assertIn(fragment, text)
        self.assertLess(text.index('href="/history"'), text.index('href="/voting_stats"'))

    def seed_complete_bracket(self):
        """Save a full eight-track bracket with collection-specific early exits."""
        self.conn.execute("INSERT INTO albums(id,title) VALUES(2,'Other album')")
        self.conn.execute("INSERT INTO artists(id,name) VALUES(2,'Other artist')")
        self.conn.execute("INSERT INTO genres(id,name) VALUES(2,'Other tag')")
        self.conn.execute("UPDATE songs SET album_id=2 WHERE id IN (7,8)")
        self.conn.execute("DELETE FROM song_artists WHERE song_id IN (7,8)")
        self.conn.executemany('INSERT INTO song_artists VALUES(?,2)', [(7,), (8,)])
        self.conn.executemany('INSERT INTO song_genres VALUES(?,2)', [(5,), (6,)])
        self.conn.executemany('INSERT INTO tournament_entries VALUES(1,?,?)', [(i,i) for i in range(1,9)])
        self.conn.execute('UPDATE tournaments SET fourth_place_id=4 WHERE id=1')
        for stage, index, winner, loser, kind in [(1,1,1,5,'bracket'),(1,2,3,6,'bracket'),(1,3,2,7,'bracket'),(1,4,4,8,'bracket'),(2,1,1,3,'bracket'),(2,2,2,4,'bracket'),(3,0,3,4,'third_place'),(3,1,1,2,'bracket')]:
            self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status,points_awarded,match_type) VALUES(1,?,?,?,?,?,?,'completed',99,?)", (stage,index,winner,loser,winner,loser,kind))
        self.conn.commit()

    def test_tournament_entries_include_early_exits_points_and_collection_tracks(self):
        self.seed()
        self.seed_complete_bracket()
        before = capture(self.conn)
        all_entries = match_archive(self.conn, {'mode':'tournament'})['events'][0]['entries']
        self.assertEqual(len(all_entries), 8)
        self.assertEqual({r['song_id']:r['points'] for r in all_entries}, {1:6,2:3,3:2,4:1,5:0,6:0,7:0,8:0})
        for kind, target, expected in [('songs',5,{5}),('albums',2,{7,8}),('artists',2,{7,8}),('tags',2,{5,6})]:
            result = match_archive(self.conn, {'mode':'tournament','entity':kind,'target':str(target)})['events'][0]
            self.assertTrue(result['entries_filtered'])
            self.assertEqual({r['song_id'] for r in result['entries']}, expected)
            self.assertTrue(all(r['place']=='Joint 5–8' and r['exit']=='Out in Quarter-finals' for r in result['entries']))
        with patch.object(voting, 'get_db_connection', side_effect=self.open_connection):
            html = services.app.test_client().get('/history?mode=tournament&entity=tags&target=2').text
        self.assertIn('Matching entries · 2', html)
        self.assertIn('Joint 5–8', html)
        self.assertIn('Out in Quarter-finals', html)
        self.assertNotIn('Dates use UTC.', html)
        self.assertNotIn('Completed brackets and their first-round', html)
        self.assertEqual(capture(self.conn), before)

    def test_combined_voting_filter_and_unknown_entry_points(self):
        self.seed()
        self.seed_complete_bracket()
        mid = self.conn.execute('SELECT id FROM tournament_matches WHERE tournament_id=1 AND round_number=1 AND match_number=1').fetchone()[0]
        self.conn.execute("INSERT INTO preference_events(winner_id,loser_id,mode,origin,tournament_id,tournament_match_id,rating_weight,created_at) VALUES(1,5,'standard','tournament',1,?,1,'2026-11-01 12:00:00')", (mid,))
        result = match_archive(self.conn, {'mode':'voting'})
        self.assertEqual(result['archive_total'],3)
        self.assertEqual(result['archive_totals'],{'voting':3})
        self.assertEqual({r['activity'] for r in result['events']}, {'voting','first_round'})
        self.assertNotIn('first_round', dict(result['archive_modes']))
        self.assertEqual(match_archive(self.conn, {'mode':'first_round'})['archive_total'],3)
        self.assertEqual(match_archive(self.conn, {'mode':'blind','origin':'ordinary'})['archive_total'],1)
        self.conn.execute('DELETE FROM tournament_matches WHERE tournament_id=1')
        entries = match_archive(self.conn, {'mode':'tournament'})['events'][0]['entries']
        self.assertTrue(all(r['points'] is None for r in entries))

    def open_connection(self):
        import sqlite3
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_excluded_shelves_and_private_brackets(self):
        self.seed()
        self.conn.execute("UPDATE albums SET shelves_excluded=1 WHERE id=1")
        self.conn.execute("UPDATE tournaments SET status='in_progress',is_blind=1 WHERE id=1")
        self.conn.execute("INSERT INTO tournament_matches(id,tournament_id,round_number,match_number,song1_id,song2_id) VALUES(1,1,1,1,1,2)")
        self.conn.execute("INSERT INTO preference_events(winner_id,loser_id,mode,origin,tournament_id,tournament_match_id,rating_weight,created_at) VALUES(1,2,'blind','tournament',1,1,1,'2026-11-01 12:00:00')")
        data = match_archive(self.conn, {})
        self.assertNotIn('shelves', data['archive_totals'])
        self.assertNotIn('tournament', data['archive_totals'])
        self.assertNotIn('first_round', data['archive_totals'])


if __name__ == '__main__':
    unittest.main()
