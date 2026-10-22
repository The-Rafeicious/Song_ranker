"""Vibe maintenance validation, stale writes and result resets."""
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
from support import catalogue, assert_clean


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


if __name__=='__main__':unittest.main()
