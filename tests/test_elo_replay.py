"""Read-only visual Elo history follows the persisted public rating projection."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from songranker import services
from songranker.modes.voting import build_elo_replay
from songranker.modes.preferences import record_preference
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture


class EloReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'replay.db'
        initialize_database(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO albums(id,title,cover_url) VALUES(1,'Album','cover')")
        self.conn.execute("INSERT INTO artists(id,name) VALUES(1,'Artist <unsafe>')")
        for sid in range(1, 9):
            self.conn.execute('INSERT INTO songs(id,title,album_id,audio_url) VALUES(?,?,1,?)', (sid, f'Song {sid}', f'preview-{sid}'))
            self.conn.execute('INSERT INTO song_artists VALUES(?,1)', (sid,))
        self.conn.commit()

    def vote(self, winner, loser, mode='standard'):
        """Persist a production preference and its actual projected Elo snapshots."""
        self.conn.execute('BEGIN')
        record_preference(self.conn, winner, loser, mode, {sid:dict(id=sid,title=f'Song {sid}') for sid in (winner, loser)})
        self.conn.commit()

    def test_replay_uses_saved_projection_dates_metadata_and_current_endpoint_without_writes(self):
        self.vote(7, 8)
        self.vote(6, 7, 'blind')
        self.conn.execute("UPDATE preference_events SET created_at='2026-10-30 12:00:00' WHERE id=1")
        self.conn.commit()
        before = capture(self.conn)
        data = build_elo_replay(self.conn)
        self.assertEqual(data['total_matches'], 2)
        self.assertEqual(data['frames'][1]['time'], '2026-10-30T12:00:00+00:00')
        projected = dict(self.conn.execute('SELECT * FROM preference_rating_projection WHERE event_id=1').fetchone())
        move = data['frames'][1]['changes'][0]
        self.assertEqual((move['before'], move['after']), (projected['winner_before'], projected['winner_after']))
        current = sorted([dict(r) for r in self.conn.execute('SELECT id,title,elo_score FROM songs')],
                         key=lambda r:(-r['elo_score'], r['title'].casefold(), r['id']))[:5]
        self.assertEqual(data['frames'][-1]['board'], [dict(id=r['id'],elo=r['elo_score']) for r in current])
        self.assertEqual(data['songs'][7]['artist_links'][0]['name'], 'Artist <unsafe>')
        self.assertEqual(data['songs'][7]['album_link']['title'], 'Album')
        self.assertEqual(data['songs'][7]['audio_url'], 'preview-7')
        self.assertEqual(capture(self.conn), before)

    def test_focus_retains_matches_outside_top_five_and_competition_rank(self):
        for _ in range(3):
            self.vote(1, 8)
        data = build_elo_replay(self.conn, 8)
        self.assertEqual(len([f for f in data['frames'] if f['kind']=='vote']), 3)
        self.assertEqual(data['frames'][-1]['focus']['rank'], 8)
        self.assertEqual(data['frames'][-1]['focus']['elo'], self.conn.execute('SELECT elo_score FROM songs WHERE id=8').fetchone()[0])
        self.assertTrue(all(any(c['opponent_id']==1 for c in f['changes'] if c['id']==8) for f in data['frames'] if f['kind']=='vote'))

    def test_manual_adjustments_are_separate_from_opponent_points(self):
        self.vote(1, 2)
        old = self.conn.execute('SELECT elo_score FROM songs WHERE id=8').fetchone()[0]
        self.conn.execute("INSERT INTO preference_rating_overrides(request_token,song_id,song_snapshot,after_event_id,previous_elo,new_elo,created_at) VALUES('manual',8,'{}',1,?,1500,'2026-10-30 13:00:00')", (old,))
        self.conn.execute('UPDATE songs SET elo_score=1500 WHERE id=8')
        self.conn.commit()
        data = build_elo_replay(self.conn)
        adjustment = next(f for f in data['frames'] if f['kind']=='adjustment')
        self.assertEqual(adjustment['changes'], [dict(id=8,before=old,after=1500)])
        self.assertEqual(adjustment['board'][0]['id'], 8)
        self.assertFalse(data['reconciled'])

    def test_missing_snapshot_and_legacy_anchor_never_invent_a_vote(self):
        self.vote(1, 2)
        self.conn.execute('UPDATE preference_rating_projection SET winner_after=NULL')
        self.conn.commit()
        data = build_elo_replay(self.conn)
        self.assertEqual(data['omitted'], 1)
        self.assertTrue(data['reconciled'])
        self.assertFalse(any(f['kind']=='vote' for f in data['frames']))
        self.conn.execute('UPDATE preference_replay_state SET cutoff_event_id=1')
        self.conn.commit()
        data = build_elo_replay(self.conn)
        self.assertTrue(data['anchored'])
        self.assertEqual(data['total_matches'], 0)

    def test_inactive_corrected_results_are_not_replayed_as_votes(self):
        self.vote(1, 2)
        self.conn.execute("INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active) VALUES(1,'void','void',1,2,'standard',0)")
        self.conn.commit()
        data = build_elo_replay(self.conn)
        self.assertEqual(data['total_matches'], 0)
        self.assertFalse(any(f['kind']=='vote' for f in data['frames']))

    def test_api_validates_song_ids_and_does_not_hydrate_collection(self):
        self.vote(1, 2)
        with patch.object(services, 'DB_NAME', str(self.path)):
            client = services.app.test_client()
            self.assertEqual(client.get('/api/voting-replay?song_id=bad').status_code, 400)
            self.assertEqual(client.get('/api/voting-replay?song_id=999').status_code, 404)
            result = client.get('/api/voting-replay?song_id=1')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['focus_id'], 1)
            page = client.get('/voting_stats').get_data(as_text=True)
            self.assertIn('data-elo-replay', page)
            self.assertEqual(page.count('/js/elo_replay.js?'), 1)

    def test_focus_skips_distant_votes_but_retains_neighbour_changes(self):
        for sid in range(1,9):
            value = 1800 - sid * 50
            self.conn.execute('UPDATE songs SET elo_score=? WHERE id=?', (value,sid))
            self.conn.execute('INSERT INTO preference_rating_seeds VALUES(?,?,0,?,9999)',(sid,value,value))
        self.conn.commit()
        self.vote(8, 7)
        for _ in range(3):
            self.vote(1, 2)
        self.vote(6, 7)
        data = build_elo_replay(self.conn, 8)
        votes = [f for f in data['frames'] if f['kind']=='vote']
        self.assertEqual([f['ordinal'] for f in votes], [1, 5])
        self.assertEqual(data['frames'][-1]['focus']['rank'], 8)
        self.assertTrue(all(next(r for r in f['board'] if r['id']==8)['slot']==2 for f in data['frames']))
        self.assertTrue(all({r['id'] for r in f['board']} <= {5,6,7,8} for f in data['frames']))

    def test_focus_window_keeps_two_above_two_below_and_centres_at_edges(self):
        self.vote(1, 2)
        for sid in range(1,9):
            data = build_elo_replay(self.conn, sid)
            for frame in data['frames']:
                own = next(r for r in frame['board'] if r['id']==sid)
                self.assertEqual(own['slot'], 2)
                self.assertLessEqual(sum(r['slot']<2 for r in frame['board']), 2)
                self.assertLessEqual(sum(r['slot']>2 for r in frame['board']), 2)
                self.assertEqual(frame['focus']['elo'], own['elo'])

    def test_tournament_public_projections_are_included_once(self):
        from songranker.modes.preferences import save_tournament_preference
        self.conn.execute("INSERT INTO tournaments(id,size,scope_type,is_blind,elo_policy_version,elo_weight) VALUES(1,8,'global',1,1,1)")
        self.conn.execute("INSERT INTO tournament_matches(id,tournament_id,round_number,match_number,song1_id,song2_id) VALUES(1,1,1,1,7,8)")
        tournament = dict(self.conn.execute('SELECT * FROM tournaments WHERE id=1').fetchone())
        match = dict(self.conn.execute('SELECT * FROM tournament_matches WHERE id=1').fetchone())
        save_tournament_preference(self.conn, tournament, match, 7, 8)
        self.conn.commit()
        data = build_elo_replay(self.conn)
        votes = [f for f in data['frames'] if f['kind']=='vote']
        self.assertEqual(data['total_matches'], 1)
        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0]['origin'], 'tournament')
        self.assertEqual(votes[0]['mode'], 'blind')

    def test_unavailable_focused_rating_is_not_fabricated(self):
        self.conn.execute('UPDATE songs SET elo_score=NULL WHERE id=8')
        self.conn.commit()
        data = build_elo_replay(self.conn, 8)
        self.assertFalse(data['focus_available'])
        self.assertFalse(any('focus' in f for f in data['frames']))
        self.assertFalse(any(r['id']==8 for f in data['frames'] for r in f['board']))

    def test_song_replay_begins_at_its_first_available_vote(self):
        for _ in range(6):
            self.vote(1, 2)
        self.vote(8, 7)
        data = build_elo_replay(self.conn, 8)
        self.assertTrue(data['has_song_votes'])
        self.assertEqual(data['frames'][0]['kind'], 'vote')
        self.assertEqual(data['frames'][0]['ordinal'], 7)
        self.assertTrue(any(c['id']==8 for c in data['frames'][0]['changes']))
        self.assertTrue(all(f['ordinal']>=7 for f in data['frames']))
        no_votes = build_elo_replay(self.conn, 6)
        self.assertFalse(no_votes['has_song_votes'])
        self.assertEqual(len(no_votes['frames']), 1)
