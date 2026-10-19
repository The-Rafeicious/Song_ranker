"""Preference transaction/HTTP regressions; no source/live database is written."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
import json
import sqlite3
import tempfile
import unittest

from songranker.storage.database import initialize_database
from songranker.storage.database_io import (capture, readonly, reconcile, write_export, read_export, rebuild)
from songranker.modes.preferences import (PreferenceError, correct_vote, event_detail, exposure_totals, get_offer, override_rating, rebuild_ratings, reset_preferences, save_vote)
from songranker.services import fetch_songs
from songranker import services
from songranker.modes import games
from songranker.developer import dev
from songranker import pages


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        initialize_database(self.path)
        self.conn = self.connect()
        self.addCleanup(self.conn.close)
        c = self.conn
        c.execute("INSERT INTO albums(id,title) VALUES(1,'Album'),(2,'Other')")
        c.execute("INSERT INTO artists(id,name) VALUES(1,'Artist, One')")
        c.execute("INSERT INTO genres(id,name) VALUES(1,'Tag')")
        for sid in range(1, 11):
            c.execute('INSERT INTO songs(id,title,album_id,track_number,audio_url) VALUES(?,?,?,?,?)',
                (sid, f'Song {sid}', 1 if sid <= 5 else 2, (sid - 1) % 5 + 1, 'preview' if sid <= 4 else ''))
            c.execute('INSERT INTO song_artists VALUES(?,1)', (sid,))
            c.execute('INSERT INTO song_genres VALUES(?,1)', (sid,))
        c.commit()
        self.patches = [patch.object(services, 'DB_NAME', str(self.path)), patch.object(dev, 'DB_NAME', str(self.path))]
        for item in self.patches:
            item.start(); self.addCleanup(item.stop)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
        return c

    def offer(self, owner='owner', mode='standard', pair=(1, 2), conn=None):
        c = conn or self.conn
        return get_offer(c, owner, mode, lambda: tuple(c.execute(
            services.SONG_SELECT + ' WHERE s.id=?', (sid,)).fetchone() for sid in pair))

    def payload(self, offer, winner=None):
        ids = [song['id'] for song in offer['songs']]
        winner = ids[0] if winner is None else winner
        return dict(token=offer['token'], winner_id=winner, loser_id=next(sid for sid in ids if sid != winner),
                    mode=offer['mode'], rules_version=offer['rules_version'])

    def vote(self, winner=1, pair=(1, 2), owner='owner', mode='standard'):
        offer = self.offer(owner, mode, pair)
        return save_vote(self.conn, owner, self.payload(offer, winner))

    def correction(self, event_id, action='void', **values):
        detail = event_detail(self.conn, event_id)
        return dict(request_token='correction-' + str(self.conn.execute('SELECT COUNT(*) FROM preference_corrections').fetchone()[0]) + '-unique-token',
                    action=action, expected_revision=detail['effective']['revision'], fingerprint=detail['fingerprint'], **values)

    def scalar(self, sql):
        return self.conn.execute(sql).fetchone()[0]

    def test_offer_resumes_after_connection_restart_and_contains_no_elo(self):
        first = self.offer()
        with self.connect() as c:
            self.assertEqual(self.offer(conn=c), first)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_offers'), 1)
        for song in first['songs']:
            self.assertFalse({'elo_score','highest_elo','matches_played'} & song.keys())
            self.assertEqual(song['artist_links'][0]['name'], 'Artist, One')

    def test_mode_and_pair_are_server_owned(self):
        first = self.offer()
        second = self.offer(mode='blind')
        self.assertNotEqual(first['token'], second['token'])
        for values in ({'mode':'blind'}, {'loser_id':3}, {'rules_version':2}, {'winner_id':2**80}, {'winner_id':True}):
            with self.subTest(values=values), self.assertRaises(PreferenceError):
                save_vote(self.conn, 'owner', {**self.payload(first), **values})
        result = save_vote(self.conn, 'owner', {**self.payload(first), 'origin':'tournament'})
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM preference_events WHERE origin='ordinary'"), 1)
        self.assertEqual(result['mode'], 'standard')

    def test_unoffered_votes_and_wrong_owner_are_refused(self):
        offered = self.offer()
        with self.assertRaises(PreferenceError):
            save_vote(self.conn, 'owner', {'winner_id':1,'loser_id':2,'mode':'standard'})
        with self.assertRaises(PreferenceError) as failure:
            save_vote(self.conn, 'other owner', self.payload(offered))
        self.assertEqual(failure.exception.status, 404)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 0)

    def test_retries_return_identical_receipt_and_count_once(self):
        offer = self.offer(); data = self.payload(offer)
        first = save_vote(self.conn, 'owner', data)
        self.assertEqual(save_vote(self.conn, 'owner', data), first)
        with self.connect() as c:
            self.assertEqual(save_vote(c, 'owner', data), first)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'), 1)
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'), 2)
        self.assertEqual(exposure_totals(self.conn)[1]['standard'], 1)

    def test_receipt_survives_later_votes_metadata_edits_and_corrections(self):
        offer = self.offer(); data = self.payload(offer)
        first = save_vote(self.conn, 'owner', data)
        self.vote(2, owner='other')
        self.conn.execute("UPDATE songs SET title='New title' WHERE id=1"); self.conn.commit()
        correct_vote(self.conn, first['event_id'], self.correction(first['event_id']))
        self.assertEqual(save_vote(self.conn, 'owner', data), first)
        self.assertEqual(first['winner']['title'], 'Song 1')

    def test_opposite_retry_exposes_saved_receipt_without_second_vote(self):
        offer = self.offer(); first = save_vote(self.conn, 'owner', self.payload(offer))
        with self.assertRaises(PreferenceError) as failure:
            save_vote(self.conn, 'owner', self.payload(offer, 2))
        self.assertEqual(failure.exception.status, 409)
        self.assertEqual(failure.exception.saved_result, first)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 1)

    def test_failure_after_all_updates_rolls_back_the_vote_and_offer(self):
        offer = self.offer()
        with patch('songranker.modes.preferences.receipt', side_effect=RuntimeError('receipt failure')):
            with self.assertRaises(RuntimeError):
                save_vote(self.conn, 'owner', self.payload(offer))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'), 0)
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM preference_offers WHERE status='open'"), 1)
        self.assertFalse(self.conn.in_transaction)

    def test_eight_concurrent_retries_create_one_vote(self):
        offer = self.offer(); data = self.payload(offer); start = Barrier(8)
        def worker(_):
            c = self.connect()
            try:
                start.wait(timeout=3)
                return save_vote(c, 'owner', data)
            finally:
                c.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(worker, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 1)
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'), 2)

    def test_concurrent_offer_requests_share_one_pending_round(self):
        start = Barrier(4)
        def worker(_):
            c = self.connect()
            try:
                start.wait(timeout=3)
                return self.offer(conn=c)
            finally:
                c.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(worker, range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_offers'), 1)

    def test_concurrent_different_outcomes_accept_exactly_one(self):
        offer = self.offer(); start = Barrier(2)
        def worker(winner):
            c = self.connect()
            try:
                start.wait(timeout=3)
                try:
                    return save_vote(c, 'owner', self.payload(offer, winner))
                except PreferenceError as error:
                    return error.status
            finally:
                c.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (1, 2)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertIn(409, results)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 1)

    def test_void_restore_retains_original_and_updates_all_counts(self):
        saved = self.vote(); event_id = saved['event_id']
        original = dict(self.conn.execute('SELECT * FROM preference_events').fetchone())
        data = self.correction(event_id)
        result = correct_vote(self.conn, event_id, data)
        self.assertEqual(correct_vote(self.conn, event_id, data), result)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 0)
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'), 0)
        self.assertEqual(self.scalar('SELECT elo_score FROM songs WHERE id=1'), 1200)
        self.assertEqual(dict(self.conn.execute('SELECT * FROM preference_events').fetchone()), original)
        correct_vote(self.conn, event_id, self.correction(event_id, 'restore'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 1)
        self.assertEqual(self.scalar('SELECT elo_score FROM songs WHERE id=1'), saved['winner']['elo_score'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_corrections'), 2)

    def test_replace_changes_winner_and_mode_without_adding_an_event(self):
        event_id = self.vote()['event_id']
        correct_vote(self.conn, event_id, self.correction(event_id, 'replace', winner_id=2, mode='blind'))
        row = self.conn.execute('SELECT * FROM history').fetchone()
        self.assertEqual((row['id'],row['winner_id'],row['mode']), (event_id,2,'blind'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'), 1)
        self.assertEqual(exposure_totals(self.conn)[1]['standard'], 0)
        self.assertEqual(exposure_totals(self.conn)[1]['blind'], 1)
        self.assertEqual(exposure_totals(self.conn)[1]['public'], 1)
        from songranker.catalog import voting_records
        self.assertEqual(voting_records(self.conn)[1]['blind_losses'], 1)

    def test_void_earlier_vote_replays_later_ratings_but_keeps_raw_snapshot(self):
        first = self.vote(); second = self.vote(2, pair=(2, 3))
        correct_vote(self.conn, first['event_id'], self.correction(first['event_id']))
        row = self.conn.execute('SELECT * FROM history').fetchone()
        self.assertEqual(row['id'], second['event_id'])
        self.assertEqual(row['winner_before'], 1200)
        self.assertEqual(row['winner_after'], 1216)
        raw = self.conn.execute('SELECT * FROM preference_events WHERE id=?', (second['event_id'],)).fetchone()
        self.assertEqual(raw['winner_before'], second['winner']['elo_before'])
        self.assertNotEqual(raw['winner_before'], row['winner_before'])
        self.assertEqual(services.fetch_match_history(self.conn)[0]['history_note'], 'Recalculated')

    def test_stale_revision_fingerprint_and_reused_correction_keys_are_refused(self):
        first = self.vote()['event_id']; second = self.vote(owner='other')['event_id']
        data = self.correction(first)
        correct_vote(self.conn, first, data)
        with self.assertRaises(PreferenceError):
            correct_vote(self.conn, first, {**data,'request_token':'different-key-12345678'})
        with self.assertRaises(PreferenceError):
            correct_vote(self.conn, second, data)
        with self.assertRaises(PreferenceError):
            correct_vote(self.conn, first, {**self.correction(first,'restore'),'fingerprint':'wrong'})

    def test_correction_replay_failure_rolls_back_correction(self):
        event_id = self.vote()['event_id']
        with patch('songranker.modes.preferences.rebuild_ratings', side_effect=RuntimeError('replay failure')):
            with self.assertRaises(RuntimeError):
                correct_vote(self.conn, event_id, self.correction(event_id))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_corrections'), 0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'), 1)

    def test_manual_rating_override_is_idempotent_and_survives_replay(self):
        first = self.vote()['event_id']
        data = {'song_id':2,'new_elo':1400,'expected_elo':1184,'request_token':'manual-rating-key-12345'}
        result = override_rating(self.conn, data)
        self.assertEqual(override_rating(self.conn, data), result)
        self.vote(2, pair=(2, 3))
        correct_vote(self.conn, first, self.correction(first))
        self.assertEqual(self.conn.execute('SELECT winner_before FROM history').fetchone()[0], 1400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_rating_overrides'), 1)
        with self.assertRaises(PreferenceError):
            override_rating(self.conn, {**data,'new_elo':1500})

    def test_stale_or_nonfinite_rating_override_is_refused(self):
        for value in (float('nan'),float('inf'),-1,5001,1400):
            with self.subTest(value=value), self.assertRaises(PreferenceError):
                override_rating(self.conn, {'song_id':1,'new_elo':value,'expected_elo':1100,'request_token':'manual-bad-key-123456'})
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_rating_overrides'), 0)

    def test_reset_invalidates_offers_and_keeps_event_id_high_water(self):
        offer = self.offer(); first = save_vote(self.conn,'owner',self.payload(offer))
        with self.conn:
            reset_preferences(self.conn)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'), 0)
        with self.assertRaises(PreferenceError):
            save_vote(self.conn,'owner',self.payload(offer))
        next_saved = self.vote()
        self.assertGreater(next_saved['event_id'], first['event_id'])
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'), 2)

    def test_exports_rebuild_pending_offers_corrections_and_receipts(self):
        offered = self.offer(); data = self.payload(offered); saved = save_vote(self.conn,'owner',data)
        correct_vote(self.conn,saved['event_id'],self.correction(saved['event_id']))
        pending = self.offer(mode='blind')
        before = capture(self.conn)
        exported = self.path.with_name('all.json'); output = self.path.with_name('rebuilt.db')
        write_export(self.path, exported); rebuild(read_export(exported), output)
        with readonly(output) as target:
            reconcile(before,capture(target))
        c = sqlite3.connect(output);c.row_factory=sqlite3.Row
        try:
            self.assertEqual(save_vote(c,'owner',data),saved)
            self.assertEqual(self.offer(mode='blind',conn=c),pending)
        finally:
            c.close()

    def test_mode_exposures_use_completed_questions_and_entries(self):
        c=self.conn
        c.executescript("""INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct) VALUES('done',1,1,1,1,0,1);
          INSERT INTO trivia_rounds(token,song_id,album_available) VALUES('pending',1,1);
          INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES('guess',1,2,1300,1200,1,2,1);
          INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at) VALUES('guess-pending',1,2,1300,1200,3);
          INSERT INTO tournaments(id,size,scope_type) VALUES(1,8,'global');
          INSERT INTO tournament_entries VALUES(1,1,1),(1,2,2);
          INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(1,'shelf',1,2),(2,'shelf-pending',3,NULL);""")
        for sid in range(1,11):
            album=1 if sid<=5 else 2;pos=(sid-1)%5+1
            for round_id in (1,2):
                c.execute('INSERT INTO album_shelf_items VALUES(?,?,?,?,?,?,?,?)',(round_id,sid,sid,album,album,pos,album,pos))
        c.commit()
        totals=exposure_totals(c)
        self.assertEqual([totals[1][key] for key in ('trivia','guesser','tournament','shelves')],[1,1,1,1])
        self.assertEqual(c.execute('SELECT appearances FROM shelf_album_exposures WHERE album_id=1').fetchone()[0],1)

    def test_schema9_upgrade_verifies_history_or_keeps_an_honest_anchor(self):
        for anchored in (False, True):
            with self.subTest(anchored=anchored):
                path=self.path.with_name('old-'+str(anchored)+'.db')
                c=sqlite3.connect(path)
                c.executescript((Path(__file__).with_name('fixtures')/'schema_v9.sql').read_text())
                c.executemany('INSERT INTO global_stats(key,value) VALUES(?,?)',[('trivia_high_score',0),('trivia_high_streak',221),('trivia_scoring_version',2)])
                c.execute("INSERT INTO songs(id,title,elo_score,matches_played) VALUES(1,'A',?,1),(2,'B',1184,1)",(1500 if anchored else 1216,))
                c.execute("INSERT INTO history(id,winner_id,loser_id,mode,winner_before,winner_after,loser_before,loser_after) VALUES(5,1,2,'standard',1200,1216,1200,1184)")
                c.execute('PRAGMA user_version=9');c.commit();c.close()
                initialize_database(path)
                c=sqlite3.connect(path);c.row_factory=sqlite3.Row
                try:
                    settings=c.execute('SELECT * FROM preference_replay_state').fetchone()
                    self.assertEqual(settings['baseline_kind'],'legacy_anchor' if anchored else 'verified_replay')
                    from songranker.modes.mode_ratings import song_mode_ratings
                    self.assertEqual(song_mode_ratings(c)[1]['standard']['elo'],1216)
                    self.assertEqual(song_mode_ratings(c)[1]['blind']['matches'],0)
                    detail=event_detail(c,5)
                    change=dict(request_token='old-legacy-correct-key',action='void',expected_revision=0,fingerprint=detail['fingerprint'])
                    if anchored:
                        with self.assertRaises(PreferenceError):correct_vote(c,5,change)
                        offered=self.offer(conn=c);saved=save_vote(c,'owner',self.payload(offered))
                        info=event_detail(c,saved['event_id'])
                        correct_vote(c,saved['event_id'],dict(request_token='new-legacy-correct-key',action='void',expected_revision=0,fingerprint=info['fingerprint']))
                        self.assertEqual(c.execute('SELECT elo_score FROM songs WHERE id=1').fetchone()[0],1500)
                    else:
                        correct_vote(c,5,change)
                        self.assertEqual(c.execute('SELECT elo_score FROM songs WHERE id=1').fetchone()[0],1200)
                    self.assertIsNone(c.execute('SELECT offer_token FROM preference_events WHERE id=5').fetchone()[0])
                    self.assertEqual(c.execute("SELECT value FROM global_stats WHERE key='trivia_high_streak'").fetchone()[0],221)
                finally:c.close()

    def test_preference_changes_do_not_regrade_frozen_guesser_answers(self):
        self.conn.execute("INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES('frozen',1,2,1300,1200,1,2,1)")
        self.conn.commit()
        from songranker.modes.special_modes import special_records
        before=special_records(self.conn)[1]['guesser']
        event_id=self.vote()['event_id']
        correct_vote(self.conn,event_id,self.correction(event_id,'replace',winner_id=2,mode='blind'))
        self.assertEqual(special_records(self.conn)[1]['guesser'],before)

    def test_http_receipts_owner_binding_and_admin_permissions(self):
        client=services.app.test_client();other=services.app.test_client()
        offered=client.get('/api/matchup?mode=blind')
        self.assertEqual(offered.status_code,200)
        self.assertEqual(offered.headers['Cache-Control'],'no-store')
        data=self.payload(offered.json)
        first=client.post('/api/vote',json=data)
        self.assertEqual(first.status_code,200)
        self.assertEqual(client.post('/api/vote',json=data).data,first.data)
        self.assertEqual(other.post('/api/vote',json=data).status_code,404)
        self.assertEqual(client.get('/api/dev/preferences').status_code,302)
        with client.session_transaction() as session:session['is_admin']=True
        detail=client.get('/api/dev/preferences/'+str(first.json['event_id'])).json
        change={**self.correction(first.json['event_id']), 'fingerprint':detail['fingerprint']}
        response=client.post('/api/dev/preferences/'+str(first.json['event_id']),json=change)
        self.assertEqual(response.status_code,200)
        self.assertFalse(client.get('/api/dev/preferences').json['items'][0]['active'])
        self.assertEqual(client.get('/api/collection').json['songs'][data['winner_id']-1]['exposures']['public'],0)

    def test_http_invalid_payloads_do_not_write(self):
        client=services.app.test_client()
        for value in ([],{}, {'winner_id':True,'loser_id':2,'mode':'standard'}):
            with self.subTest(value=value):self.assertEqual(client.post('/api/vote',json=value).status_code,400)
        self.assertEqual(client.get('/api/matchup?mode=other').status_code,400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'),0)

    def test_song_removal_voids_influence_preserves_receipt_without_automatic_backup(self):
        client=services.app.test_client();offered=client.get('/api/matchup').json
        data=self.payload(offered);saved=client.post('/api/vote',json=data).json
        with client.session_transaction() as session:session['is_admin']=True
        correct_vote(self.conn,saved['event_id'],self.correction(saved['event_id'],'replace',winner_id=data['loser_id'],mode='blind'))
        response=client.delete('/api/dev/delete_song/'+str(data['winner_id']),json={})
        self.assertEqual(response.status_code,200,response.json)
        self.assertIsNone(response.json['backup'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'),1)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM history'),0)
        self.assertEqual(self.scalar('SELECT SUM(matches_played) FROM songs'),0)
        self.assertEqual(client.post('/api/vote',json=data).json,saved)
        self.assertEqual(client.delete('/api/dev/delete_song/'+str(data['loser_id']),json={}).status_code,200)
        changed=self.conn.execute("SELECT winner_id,loser_id FROM preference_corrections WHERE action='replace'").fetchone()
        self.assertEqual(tuple(changed),(data['loser_id'],data['winner_id']))
        offered_ids=self.conn.execute('SELECT song1_id,song2_id FROM preference_offers WHERE token=?',(data['token'],)).fetchone()
        self.assertEqual(set(offered_ids),{data['winner_id'],data['loser_id']})
        self.assertFalse(self.conn.execute('PRAGMA foreign_key_check').fetchall())


if __name__=='__main__':unittest.main()
