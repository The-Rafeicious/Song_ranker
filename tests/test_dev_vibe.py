"""Vibe maintenance validation, stale writes and catalogue-only merge cleanup."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import test_preferences as fixture
from songranker import services
from songranker.developer import dev,dev_vibe
from songranker.storage.database_io import capture,readonly
from songranker.modes import vibe_map
from tools.prepare_vibe_merge import prepare,catalogue,assert_clean


class DevVibeTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def client(self,admin=True):
        client=services.app.test_client()
        if admin:
            with client.session_transaction() as session:session['is_admin']=True
        return client

    def payload(self,client=None):
        record=(client or self.client()).get('/api/dev/vibe/1').json
        return dict(version=record['version'],completed_passes=1,maps={m['id']:dict(status='placed',x=2.51,y=-3.12,sample_count=2,not_applicable_count=0) for m in record['maps']})

    def test_authenticated_edit_averages_preserves_catalogue_and_clears_rounds(self):
        client=self.client();before=catalogue(self.conn)
        active=vibe_map.start(self.conn,'test-owner',{})
        # Selection is random; register a round for the song being edited too.
        self.conn.execute('UPDATE vibe_rounds SET song_id=1');self.conn.commit()
        payload=self.payload(client)
        response=client.post('/api/dev/vibe/1',json=payload)
        self.assertEqual(response.status_code,200,response.json)
        row=self.conn.execute("SELECT x,y,sample_count FROM song_vibe_positions WHERE song_id=1 LIMIT 1").fetchone()
        self.assertAlmostEqual(row['x'],2.51/5);self.assertAlmostEqual(row['y'],-3.12/5)
        self.assertEqual(row['sample_count'],2)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM vibe_rounds').fetchone()[0],0)
        self.assertEqual(catalogue(self.conn),before)
        self.assertEqual(client.post('/api/dev/vibe/1',json=payload).status_code,409)
        self.assertEqual(client.get('/api/dev/vibe?q=Artist').json['total'],10)
        self.assertEqual(client.get('/api/dev/vibe?q=not-found').json['total'],0)
        self.assertEqual(client.get('/api/dev/vibe/999').status_code,404)
        self.assertNotEqual(self.client(False).get('/api/dev/vibe').status_code,200)

    def test_invalid_values_and_stale_drafts_never_partially_write(self):
        client=self.client();original=self.payload(client);before=capture(self.conn)
        for name,value in [('x',6),('y',True),('x',float('inf')),('sample_count',0),('sample_count',1.5),('not_applicable_count',-1),('status','bad')]:
            payload=deepcopy(original);payload['maps']['pace_mood'][name]=value
            self.assertEqual(client.post('/api/dev/vibe/1',json=payload).status_code,400)
            self.assertEqual(capture(self.conn),before)
        bad=deepcopy(original);bad['completed_passes']=3
        self.assertEqual(client.post('/api/dev/vibe/1',json=bad).status_code,400)
        self.assertEqual(client.post('/api/dev/vibe/1',json=[]).status_code,400)
        self.assertEqual(client.delete('/api/dev/vibe/1',json=original).status_code,400)
        # A newly opened game draft changes the version even before any map is saved.
        with patch.object(vibe_map,'vibe_song',return_value={'id':1}):vibe_map.start(self.conn,'owner',{})
        self.assertEqual(client.post('/api/dev/vibe/1',json=original).status_code,409)

    def test_clear_map_song_and_mode_retain_four_slots_and_other_modes(self):
        client=self.client();data=self.payload(client)
        client.post('/api/dev/vibe/1',json=data)
        data=self.payload(client);data['maps']['pace_mood']=dict(status='unmapped',sample_count=0,not_applicable_count=0);data['completed_passes']=0
        self.assertEqual(client.post('/api/dev/vibe/1',json=data).status_code,200)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM song_vibe_positions WHERE song_id=1 AND status='placed'").fetchone()[0],3)
        version=client.get('/api/dev/vibe/1').json['version']
        self.assertEqual(client.delete('/api/dev/vibe/1',json=dict(version=version,confirmation='DELETE VIBE')).status_code,200)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_vibe_positions WHERE song_id=1').fetchone()[0],4)
        self.conn.execute('UPDATE songs SET elo_score=1300 WHERE id=2');self.conn.commit()
        self.assertEqual(client.post('/api/dev/reset-history/vibe',json=dict(confirmation='RESET VIBE')).status_code,200)
        self.assertEqual(self.conn.execute('SELECT elo_score FROM songs WHERE id=2').fetchone()[0],1300)
        self.assertEqual(client.post('/api/dev/reset-database',json=dict(confirmation='RESET COMPETITION')).status_code,200)
        assert_clean(self.conn)


class MergePreparationTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def test_preview_apply_export_and_one_time_guard(self):
        client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=.2,y=.4,sample_count=1,updated_at=1 WHERE song_id=1")
        self.conn.execute('UPDATE song_vibe_progress SET completed_passes=1 WHERE song_id=1')
        self.conn.execute('UPDATE songs SET elo_score=1400,matches_played=5,tournament_wins=2 WHERE id=1')
        self.conn.execute("UPDATE song_details SET preview_note='Keep catalogue note' WHERE song_id=1")
        from songranker.modes.preferences import save_vote
        offer=fixture.PreferenceTests.offer(self)
        # Real preference writer plus saved/in-progress rows from the other modes.
        save_vote(self.conn,'owner',fixture.PreferenceTests.payload(self,offer))
        self.conn.execute("INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct) VALUES('quiz',1,1,1,1,1,0)")
        self.conn.execute("INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES('guess',1,2,1200,1300,1,2,2)")
        self.conn.execute("INSERT INTO album_shelf_rounds(id,token,started_at) VALUES(1,'shelf',1)")
        self.conn.execute("INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number) VALUES(1,1,1,1,1,1)")
        self.conn.execute("INSERT INTO tournaments(id,size,scope_type,status) VALUES(1,8,'global','in_progress')")
        self.conn.execute("INSERT INTO tournament_entries VALUES(1,1,1)")
        self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id) VALUES(1,1,1,1,2)")
        self.conn.execute("INSERT INTO listening_observations(mode,reference,song_key,song_id,seconds,decision_ms,recorded_at) VALUES('standard','1',1,1,2,2000,1)")

        self.conn.commit();kept=catalogue(self.conn);before=capture(self.conn)
        export=Path(self.temp.name)/'database_backup.sql'
        preview=prepare(self.path,export)
        self.assertFalse(preview['applied']);self.assertEqual(preview['mapped_positions'],4)
        self.assertEqual(capture(self.conn),before);self.assertFalse(export.exists())
        with self.assertRaises(ValueError):prepare(self.path,export,True,'wrong')
        result=prepare(self.path,export,True,'RESET TEST COMPETITION')
        self.assertTrue(result['applied']);assert_clean(self.conn);self.assertEqual(catalogue(self.conn),kept)
        with readonly(result['backup']) as old:self.assertEqual(capture(old),before)
        clone=sqlite3.connect(':memory:');clone.row_factory=sqlite3.Row;self.addCleanup(clone.close)
        clone.executescript(export.read_text());assert_clean(clone);self.assertEqual(catalogue(clone),kept)
        after=capture(self.conn)
        self.assertFalse(prepare(self.path,export,True,'RESET TEST COMPETITION')['applied'])
        self.assertEqual(capture(self.conn),after)
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=0,y=0,sample_count=1,updated_at=2 WHERE song_id=1");self.conn.commit()
        newer=capture(self.conn)
        with self.assertRaises(ValueError):prepare(self.path,export,True,'RESET TEST COMPETITION')
        self.assertEqual(capture(self.conn),newer)

    def test_extensions_are_not_silently_kept_as_match_data(self):
        self.conn.execute('CREATE TABLE extra_results (score INTEGER)');self.conn.commit()
        with self.assertRaises(ValueError):prepare(self.path)


    def test_failed_catalogue_verification_rolls_back_every_result_change(self):
        self.conn.execute('UPDATE songs SET elo_score=1500 WHERE id=1');self.conn.commit();before=capture(self.conn)
        original=catalogue(self.conn)
        with patch('tools.prepare_vibe_merge.catalogue',side_effect=[original,{}]):
            with self.assertRaisesRegex(ValueError,'Catalogue verification'):
                prepare(self.path,Path(self.temp.name)/'snapshot.sql',True,'RESET TEST COMPETITION')
        self.assertEqual(capture(self.conn),before)

    def test_failed_export_can_retry_without_resetting_or_another_backup(self):
        output=Path(self.temp.name)/'snapshot.sql'
        with patch('tools.prepare_vibe_merge.export_sql',side_effect=OSError('Export denied')):
            with self.assertRaisesRegex(ValueError,'Cleanup committed'):
                prepare(self.path,output,True,'RESET TEST COMPETITION')
        assert_clean(self.conn)
        backups=list((self.path.parent/'database_backups').glob('pre_merge_vibe_v11_*.db'))
        self.assertEqual(len(backups),1)
        result=prepare(self.path,output,True,'RESET TEST COMPETITION')
        self.assertFalse(result['applied']);self.assertTrue(output.exists())
        self.assertEqual(list((self.path.parent/'database_backups').glob('pre_merge_vibe_v11_*.db')),backups)
