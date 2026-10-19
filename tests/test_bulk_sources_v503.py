"""Atomic reviewed source changes, corrected identities and catalogue preservation."""
import sqlite3
import unittest
from unittest.mock import patch
import test_catalog_sources as fixture
from songranker import services
from songranker.developer import dev_catalog, catalog_sources as sources
from songranker.storage.database_io import capture

class BulkSourcesTests(unittest.TestCase):
    setUp=fixture.CatalogSourceTests.setUp
    connect=fixture.CatalogSourceTests.connect
    client=fixture.CatalogSourceTests.client
    result=fixture.CatalogSourceTests.result
    link=fixture.CatalogSourceTests.link

    def change(self,client,sid,track):
        row,_=self.result(client,fixture.apple(trackId=track,trackName=f'Recording {track}'))
        return dict(song_id=sid,source_token=row['source_token'],fingerprint=client.get(f'/api/dev/song-source/{sid}').json['fingerprint'])

    def save(self,client,changes):return client.post('/api/dev/song-sources/bulk',json=dict(changes=changes))

    def test_saves_current_sources_without_automatic_backup(self):
        client=self.client();before=capture(self.conn)
        response=self.save(client,[self.change(client,1,9001),self.change(client,2,9002)])
        self.assertEqual(response.status_code,200,response.json);self.assertEqual(response.json['count'],2)
        after=capture(self.conn)
        for name,value in before['tables'].items():
            if name!='song_sources':self.assertEqual(value,after['tables'][name],name)
        self.assertEqual({k:v['source']['track_id'] for k,v in sources.current_sources(self.conn).items()},{1:'9001',2:'9002'})
        self.assertIsNone(response.json['backup']);self.assertFalse((self.path.parent/'database_backups').exists())
        self.assertEqual(self.conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_stale_second_song_rolls_back_entire_group(self):
        client=self.client();changes=[self.change(client,1,9001),self.change(client,2,9002)]
        self.conn.execute("UPDATE songs SET title='Changed' WHERE id=2");self.conn.commit();before=capture(self.conn)
        self.assertEqual(self.save(client,changes).status_code,409);self.assertEqual(capture(self.conn),before)

    def test_conflict_outside_group_rolls_back_prior_writes(self):
        client=self.client();row,_=self.result(client,fixture.apple(trackId=9002));self.assertEqual(self.link(client,3,row).status_code,200)
        changes=[self.change(client,1,9001),self.change(client,2,9002)];before=capture(self.conn)
        self.assertEqual(self.save(client,changes).status_code,400);self.assertEqual(capture(self.conn),before)

    def test_misassigned_pair_can_exchange_sources_with_stable_ids(self):
        client=self.client()
        for sid,track in [(1,9001),(2,9002)]:
            row,_=self.result(client,fixture.apple(trackId=track));self.assertEqual(self.link(client,sid,row).status_code,200)
        before=sources.current_sources(self.conn)
        response=self.save(client,[self.change(client,1,9002),self.change(client,2,9001)])
        self.assertEqual(response.status_code,200,response.json);after=sources.current_sources(self.conn)
        self.assertEqual([after[i]['source']['track_id'] for i in (1,2)],['9002','9001'])
        self.assertEqual([after[i]['id'] for i in (1,2)],[before[i]['id'] for i in (1,2)])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],2)

    def test_duplicate_song_recording_bad_token_and_empty_rejected(self):
        client=self.client();one=self.change(client,1,9001);two=self.change(client,2,9001);before=capture(self.conn)
        for changes in ([one,one],[one,two],[one,dict(two,source_token='tampered')],[dict(one,song_id=True)],[]):
            self.assertEqual(self.save(client,changes).status_code,400);self.assertEqual(capture(self.conn),before)

    def test_missing_song_and_cross_browser_offer_are_rejected(self):
        client=self.client();one=self.change(client,1,9001)
        self.assertEqual(self.save(self.client(),[one]).status_code,400)
        self.assertEqual(self.save(client,[dict(one,song_id=999)]).status_code,409)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],0)

    def test_source_save_does_not_call_backup_even_when_backup_storage_is_unavailable(self):
        client=self.client();changes=[self.change(client,1,9001)]
        with patch.object(dev_catalog,'create_database_backup',side_effect=OSError('Unavailable')) as backup:
            response=self.save(client,changes)
        self.assertEqual(response.status_code,200);backup.assert_not_called()

    def test_admin_required_and_batch_limit(self):
        self.assertIn(self.save(services.app.test_client(),[]).status_code,(302,401,403))
        self.assertEqual(self.save(self.client(),[{}]*501).status_code,400)

if __name__=='__main__':unittest.main()
