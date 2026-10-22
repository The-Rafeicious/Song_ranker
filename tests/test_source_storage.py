"""Lossless source compression, current-only migration and retained game data."""
from pathlib import Path
import base64
import json
import sqlite3
import unittest

import test_preferences as fixture
from test_catalog_sources import apple
from songranker.developer import catalog_sources as sources
from songranker.developer.catalog_sources import single_plan
from songranker.storage.database import migrate
from songranker.storage.database_io import capture,readonly,write_export,read_export,rebuild,reconcile
from songranker.storage.source_storage import pack_source,unpack_source,PREFIX,compact_database

class SourceCodecTests(unittest.TestCase):
    def test_lossless_unicode_and_exact_urls(self):
        source=sources.observation(apple(trackName='Beyoncé — 特別',trackViewUrl='https://music.apple.com/gb/album/a/8001?i=9001&x=a%2Fb'),'gb')
        encoded=pack_source(source)
        self.assertTrue(encoded.startswith(PREFIX));self.assertLess(len(encoded),len(json.dumps(source)))
        self.assertEqual(unpack_source(encoded),source)
        self.assertEqual(pack_source(encoded),encoded)

    def test_plain_snapshots_and_tiny_objects_remain_supported(self):
        self.assertEqual(pack_source({}),'{}')
        self.assertEqual(unpack_source('{"missing":null}'),{'missing':None})

    def test_invalid_or_truncated_compression_fails_closed(self):
        good=pack_source(sources.observation(apple(),'gb'))
        for value in ('srz1:!!!',good[:-5],good+'AAAA','[]','not JSON'):
            with self.subTest(value=value[:20]),self.assertRaises(ValueError):unpack_source(value)

class StorageTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect
    offer=fixture.PreferenceTests.offer
    payload=fixture.PreferenceTests.payload
    vote=fixture.PreferenceTests.vote

    def source(self,n):return sources.observation(apple(trackId=9000+n,trackViewUrl='https://music.apple.com/gb/song/'+str(9000+n)), 'gb')

    def old_layout(self):
        for name in ('song_vibe_added','song_vibe_keep_slot','song_vibe_keep_identity','vibe_progress_added'):
            self.conn.execute('DROP TRIGGER '+name)
        self.conn.execute('DROP TABLE vibe_rounds')
        self.conn.execute('DROP TABLE song_vibe_progress')
        self.conn.execute('DROP TABLE song_vibe_positions')
        self.conn.execute('DROP TABLE vibe_maps')
        self.conn.execute('DROP INDEX song_sources_song')
        self.conn.execute('CREATE INDEX song_sources_song ON song_sources(song_id,id DESC)')
        self.conn.execute('PRAGMA user_version=14');self.conn.commit()

    def insert_old(self,sid,n):
        source=self.source(n)
        self.conn.execute('INSERT INTO song_sources(song_id,external_id,storefront,collection_id,snapshot,observed_at) VALUES(?,?,?,?,?,?)',
            (sid,source['track_id'],'gb','8001',json.dumps(source),n))
        self.conn.commit()

    def test_upgrade_keeps_latest_source_and_all_other_stored_values_with_backup(self):
        self.vote();self.old_layout();self.insert_old(1,1);self.insert_old(1,2);self.insert_old(2,3)
        before=capture(self.conn);migrate(self.path);after=capture(self.conn)
        for table in before['tables']:
            if table!='song_sources':self.assertEqual(before['tables'][table],after['tables'][table],table)
        self.assertEqual(sources.current_source(self.conn,1)['source'],self.source(2))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],2)
        self.assertEqual(self.conn.execute('PRAGMA page_size').fetchone()[0],2048)
        backups=list((self.path.parent/'database_backups').glob('pre_upgrade*.db'));self.assertEqual(len(backups),1)
        with readonly(backups[0]) as b:self.assertEqual(b.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],3)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO song_sources(song_id,external_id,storefront,snapshot,observed_at) VALUES(1,'x','gb','{}',1)")
        self.conn.rollback()

    def test_source_update_replaces_one_row_and_invalidates_review_without_growing_history(self):
        first=sources.save_source(self.conn,1,dict(source=self.source(1),observed_at=1));self.conn.commit()
        old=sources.review_fingerprint(self.conn,1);plan=single_plan(self.conn,1)['fingerprint']
        second=sources.save_source(self.conn,1,dict(source=self.source(2),observed_at=2));self.conn.commit()
        self.assertEqual(first,second);self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],1)
        self.assertNotEqual(old,sources.review_fingerprint(self.conn,1));self.assertNotEqual(plan,single_plan(self.conn,1)['fingerprint'])
        sources.save_source(self.conn,1,dict(source=self.source(2),observed_at=99));self.conn.commit()
        self.assertEqual(sources.current_source(self.conn,1)['observed_at'],2)

    def test_compressed_sources_round_trip_full_export_rebuild(self):
        self.vote();sources.save_source(self.conn,1,dict(source=self.source(1),observed_at=1));self.conn.commit()
        export=Path(self.temp.name)/'all.json';target=Path(self.temp.name)/'roundtrip.db'
        write_export(self.path,export);rebuild(read_export(export),target)
        with readonly(target) as b:
            reconcile(capture(self.conn),capture(b));self.assertEqual(sources.current_source(b,1)['source'],self.source(1))

    def test_bad_latest_source_aborts_before_modifying_live_data(self):
        self.old_layout();self.conn.execute("INSERT INTO song_sources(song_id,external_id,storefront,snapshot,observed_at) VALUES(1,'x','gb','invalid JSON',1)");self.conn.commit()
        before=capture(self.conn)
        with self.assertRaises(ValueError):migrate(self.path)
        self.assertEqual(capture(self.conn),before)

    def test_extension_reference_to_obsolete_source_blocks_removal(self):
        self.old_layout();self.insert_old(1,1);self.insert_old(1,2)
        self.conn.execute('CREATE TABLE extension_ref(source_id INTEGER REFERENCES song_sources(id))')
        self.conn.execute('INSERT INTO extension_ref VALUES(1)');self.conn.commit();before=capture(self.conn)
        with self.assertRaises(ValueError):migrate(self.path)
        self.assertEqual(capture(self.conn),before)

    def test_growing_database_moves_to_larger_pages_without_changing_values(self):
        self.conn.execute('CREATE TABLE retained_payload(value TEXT)')
        self.conn.execute('INSERT INTO retained_payload VALUES(?)',('x'*(5*1024*1024),));self.conn.commit()
        before=capture(self.conn)
        self.assertTrue(compact_database(self.path,grow_only=True))
        with readonly(self.path) as reopened:self.assertEqual(reopened.execute('PRAGMA page_size').fetchone()[0],4096)
        self.assertEqual(capture(self.conn),before)

if __name__=='__main__':unittest.main()
