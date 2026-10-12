import sqlite3
import unittest
import test_app as fixture
from pages import global_mode_details


class Patch325Checks(unittest.TestCase):
    setUp = fixture.AppChecks.setUp
    db = fixture.AppChecks.db

    def test_global_fields_respect_single_denominators_and_adjustments(self):
        with self.db() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('DELETE FROM trivia_rounds')
            conn.execute('DELETE FROM trivia_adjustments')
            ids = [row[0] for row in conn.execute('SELECT id FROM songs LIMIT 3')]
            conn.execute('INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct) VALUES(?,?,1,1,1,1,0)', ('v325-album',ids[0]))
            conn.execute('INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct) VALUES(?,?,0,1,1,0,NULL)', ('v325-single',ids[1]))
            conn.execute('INSERT INTO trivia_rounds(token,song_id,album_available) VALUES(?,?,1)', ('v325-unfinished',ids[2]))
            conn.execute('INSERT INTO trivia_adjustments(song_id,new_attempts_delta,title_correct_delta,artist_correct_delta) VALUES(?,1,1,1)', (ids[1],))
            details = global_mode_details(conn)
        fields = {row['label']: row for row in details['trivia_fields']}
        self.assertEqual(fields['Song']['accuracy'],100)
        self.assertEqual(fields['Artist']['attempts'],3)
        self.assertAlmostEqual(fields['Artist']['accuracy'],66.7)
        self.assertEqual(fields['Album']['attempts'],1)
        self.assertEqual(fields['Album']['accuracy'],0)
        self.assertEqual(details['trivia_tested'],2)
        self.assertEqual(details['trivia_over_ninety'],0)

    def test_global_placements_require_completed_brackets(self):
        with self.db() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('DELETE FROM tournament_matches')
            conn.execute('DELETE FROM tournament_entries')
            conn.execute('DELETE FROM tournaments')
            a,b,c = [row[0] for row in conn.execute('SELECT id FROM songs LIMIT 3')]
            conn.execute("INSERT INTO tournaments(id,size,scope_type,status,champion_id,runner_up_id,third_place_id) VALUES(90001,4,'global','completed',?,?,?)",(a,b,c))
            conn.execute("INSERT INTO tournaments(id,size,scope_type,status,champion_id) VALUES(90002,4,'global','in_progress',?)",(c,))
            conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status,points_awarded) VALUES(90001,2,1,?,?,?,?,'completed',2)",(a,b,a,b))
            conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,status) VALUES(90002,1,1,?,?,'pending')",(a,c))
            details=global_mode_details(conn)
        self.assertEqual(details['tournaments_completed'],1)
        self.assertEqual([row['count'] for row in details['tournament_places']],[1,1,1])
        self.assertEqual(details['tournament_matches'],1)
        self.assertEqual(details['tournament_points'],2)
        self.assertEqual([row['id'] for row in details['latest_podium']],[a,b,c])
        self.assertEqual(details['tournament_leaders'][0]['id'],a)

    def test_trivia_asset_and_empty_global_stats_render(self):
        asset=self.c.get('/static/js/trivia.js?v=3.2.5')
        self.assertEqual(asset.status_code,200)
        asset.close()
        page=self.c.get('/trivia').text
        from version import APP_VERSION
        self.assertIn('/static/js/trivia.js?v='+APP_VERSION,page)
        self.assertIn('Trivia script is missing',page)
        with self.db() as conn:
            for table in ('history','trivia_rounds','trivia_adjustments','tournament_matches','tournament_entries','tournaments','song_artists','song_genres','songs','artists','albums','genres'):
                conn.execute('DELETE FROM '+table)
        response=self.c.get('/global_stats')
        self.assertEqual(response.status_code,200)
        self.assertIn('Elo Distribution',response.text)
        self.assertIn('Above 90%',response.text)
        self.assertIn('Third place',response.text)


if __name__ == '__main__':
    unittest.main()
