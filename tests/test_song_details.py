"""Per-song mode detail reads use complete, effective, public evidence only."""
from unittest.mock import patch
import unittest
from songranker import services
from songranker.catalog import song_stats
from songranker.modes.voting import song_voting_details
from songranker.modes.trivia import song_trivia_details
from songranker.modes.tournament import song_tournament_details
from songranker.modes.guesser import song_guesser_details
from songranker.modes.shelves import song_shelves_details
from songranker.storage.database_io import capture
import test_elo_replay as replay_fixture
from songranker import pages


class SongDetailTests(unittest.TestCase):
    setUp = replay_fixture.EloReplayTests.setUp
    vote = replay_fixture.EloReplayTests.vote

    def test_api_full_detail_is_read_only_and_does_not_hydrate_collection(self):
        self.vote(7,8)
        before = capture(self.conn)
        with patch.object(services, 'DB_NAME', str(self.path)), patch('songranker.catalog.collection', side_effect=AssertionError('No catalogue hydration')):
            client = services.app.test_client()
            self.assertEqual(client.get('/api/song/999/stats').status_code,404)
            response = client.get('/api/song/8/stats')
            self.assertEqual(response.status_code,200)
            data = response.json
            self.assertEqual(data['song_id'],8)
            self.assertEqual(data['voting']['matches'],1)
            self.assertEqual(data['songs']['7']['artists'][0]['name'],'Artist <unsafe>')
            self.assertEqual(data['trivia']['timing'][0]['mean'],None)
            self.assertEqual(data['guesser']['recent'],[])
            self.assertNotIn('token',response.get_data(as_text=True))
        self.assertEqual(capture(self.conn),before)

    def test_voting_mid_table_uses_all_votes_corrections_and_valid_snapshot_counts(self):
        for _ in range(12):
            self.vote(7,8)
        self.vote(8,7,'blind')
        d = song_voting_details(self.conn,7)
        self.assertEqual((d['matches'],d['best_run'],d['current_run']),(13,12,0))
        self.assertEqual((d['recent_wins'],d['recent_matches']),(9,10))
        self.assertEqual(d['opponents_list'],[dict(id=8,wins=12,losses=1)])
        self.conn.execute("INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active) VALUES(13,'void','void',8,7,'blind',0)")
        self.conn.execute('UPDATE preference_rating_projection SET winner_after=NULL WHERE event_id=1')
        d = song_voting_details(self.conn,7)
        self.assertEqual((d['matches'],d['current_run'],d['snapshots']),(12,12,11))

    def test_trivia_full_history_field_eligibility_and_disjoint_windows(self):
        for i in range(110):
            right = int(i>=105)
            self.conn.execute("INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct,title_seconds,artist_seconds) VALUES(?,8,0,?,?,?,1,4,8)",(f't{i}',i+1,right,right))
        self.conn.execute("INSERT INTO trivia_rounds(token,song_id,album_available) VALUES('pending',8,1)")
        d = song_trivia_details(self.conn,8)
        self.assertEqual((d['rounds'],d['perfect']),(110,5))
        self.assertEqual(d['latest'],dict(rounds=5,correct=10,available=10))
        self.assertEqual(d['previous'],dict(rounds=5,correct=0,available=10))
        self.assertEqual(d['timing'][0]['mean'],4)
        self.assertEqual(d['timing'][2]['samples'],0)
        self.assertEqual(len(d['recent']),5)

    def test_guesser_uses_frozen_gap_and_slot_in_both_positions(self):
        for i,(a,b,x,y,chosen) in enumerate([(8,7,1250,1240,1),(7,8,1400,1200,2),(8,7,1200,1230,2)]):
            self.conn.execute('INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES(?,?,?,?,?,0,?,?)',(f'g{i}',a,b,x,y,i+1,chosen))
        self.conn.execute("INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at) VALUES('pending',8,7,9999,1,0)")
        self.conn.execute('UPDATE songs SET elo_score=9999 WHERE id=8')
        d = song_guesser_details(self.conn,8)
        self.assertEqual((d['graded'],d['selected']),(3,2))
        self.assertEqual([r['gap'] for r in d['recent']],[30,200,10])
        self.assertEqual([(r['correct'],r['graded']) for r in d['bands']],[(2,2),(0,1)])

    def test_completed_tournaments_separate_local_results_and_hide_pending(self):
        for tid,scope,status in [(1,'global','completed'),(2,'artist','completed'),(3,'tag','in_progress')]:
            self.conn.execute('INSERT INTO tournaments(id,size,scope_type,status,is_blind,completed_at) VALUES(?,8,?,?,1,?)',(tid,scope,status,'2026-10-31'))
            self.conn.execute('INSERT INTO tournament_entries VALUES(?,8,1)',(tid,))
            self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status) VALUES(?,1,1,8,7,7,8,'completed')",(tid,))
        d = song_tournament_details(self.conn,8)
        self.assertEqual((d['completed'],d['first_exits']),(2,2))
        self.assertEqual([(g['entries'],g['losses']) for g in d['groups']],[(1,1),(1,1)])
        self.assertTrue(all(r['mode']=='blind' and r['finish']=='Out in Quarter-finals' for r in d['recent']))
        self.assertNotIn(3,[r['id'] for r in d['recent']])
        self.assertTrue(all(r['exit']==dict(round='Quarter-finals',opponent_id=7) for r in d['recent']))

    def test_exit_opponent_and_round_survive_podium_playoff_and_hydrate_in_api(self):
        for tid,size,round_no,opponent in [(1,16,1,7),(2,32,1,6),(3,8,2,7)]:
            self.conn.execute("INSERT INTO tournaments(id,size,scope_type,status,completed_at) VALUES(?,?,'global','completed','2026-10-31')",(tid,size))
            self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status) VALUES(?,?,1,8,?,?,8,'completed')",(tid,round_no,opponent,opponent))
        self.conn.execute("UPDATE tournaments SET fourth_place_id=8 WHERE id=3")
        self.conn.execute("UPDATE tournaments SET champion_id=7 WHERE id=1")
        self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status,match_type) VALUES(3,3,1,8,6,6,8,'completed','third_place')")
        self.conn.commit()
        rows={r['id']:r for r in song_tournament_details(self.conn,8)['recent']}
        self.assertEqual(rows[1]['exit'],dict(round='Round of 16',opponent_id=7))
        self.assertEqual(rows[2]['exit'],dict(round='Round of 32',opponent_id=6))
        self.assertEqual((rows[3]['finish'],rows[3]['exit']),('4th',dict(round='Semi-finals',opponent_id=7)))
        champion=next(r for r in song_tournament_details(self.conn,7)['recent'] if r['id']==1)
        self.assertIsNone(champion['exit'])
        with patch.object(services,'DB_NAME',str(self.path)):
            response=services.app.test_client().get('/api/song/8/stats')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['songs']['7']['title'],'Song 7')
        self.conn.execute('DELETE FROM songs WHERE id=7')
        self.conn.commit()
        with patch.object(services,'DB_NAME',str(self.path)):
            response=services.app.test_client().get('/api/song/8/stats')
            self.assertIsNone(response.json['songs']['7'])

    def test_shelves_grades_full_round_and_excluded_album_hides_whole_result(self):
        self.conn.execute("INSERT INTO albums(id,title) VALUES(2,'Other')")
        for rid in (1,2):
            self.conn.execute('INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(?,?,0,?)',(rid,f's{rid}',rid))
            self.conn.execute('INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,answer_slot,answer_position) VALUES(?,1,8,1,1,1,1,1)',(rid,))
            self.conn.execute('INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,answer_slot,answer_position) VALUES(?,2,7,1,1,2,1,2)',(rid,))
        d = song_shelves_details(self.conn,8)
        self.assertEqual((d['graded'],d['perfect']),(2,2))
        self.assertEqual(d['recent'][0]['grade']['order_pairs'],1)
        self.conn.execute('UPDATE album_shelf_items SET album_id=2,album_slot=2,answer_slot=2 WHERE round_id=2 AND song_id=7')
        self.conn.execute('UPDATE albums SET shelves_excluded=1 WHERE id=2')
        self.assertEqual(song_shelves_details(self.conn,8)['rounds'],1)
        self.conn.execute('UPDATE album_shelf_items SET answer_position=NULL,answer_slot=NULL WHERE round_id=1 AND song_id=7')
        d = song_shelves_details(self.conn,8)
        self.assertEqual((d['graded'],d['unknown']),(0,1))
        self.assertIsNone(d['recent'][0]['grade'])
