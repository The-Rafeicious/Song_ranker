"""Eight-tag policy: backed-up migration, atomic APIs and storage guards."""
import sqlite3
import unittest
from unittest.mock import patch
from pathlib import Path
import test_preferences as fixture
from songranker import services
from songranker.developer import dev, dev_tags, dev_system
from songranker.storage.database import migrate
from songranker.storage.database_io import capture, reconcile
from songranker.storage.tag_limits import tag_names
from songranker.storage.database_schema import SCHEMA_VERSION


class TagLimitTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def client(self):
        client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        return client

    def extra_tags(self):
        self.conn.executemany('INSERT INTO genres(id,name) VALUES(?,?)',[(i,'Tag '+str(i)) for i in range(2,12)])
        self.conn.commit()

    def fill(self,sid=1):
        self.conn.executemany('INSERT INTO song_genres VALUES(?,?)',[(sid,i) for i in range(2,9)])
        self.conn.commit()

    def test_metadata_counts_unique_names_and_rejects_nine_without_writes(self):
        self.assertEqual(tag_names(' Pop, pop, Ｐｏｐ, Sad, ,sad '),['Pop','Sad'])
        before=capture(self.conn)
        for route in ('/api/dev/add_song','/api/dev/edit_song/1'):
            response=self.client().post(route,json=dict(title='Song',artist='Artist',genres=','.join('New '+str(i) for i in range(9))))
            self.assertEqual(response.status_code,400,response.json)
            self.assertIn('8 tags',response.json['message'])
        self.assertEqual(before,capture(self.conn))

    def test_song_editor_saves_eight_distinct_tags(self):
        self.extra_tags()
        response=self.client().post('/api/dev/edit_song/1',json=dict(title='Song 1',artist='Artist, One',album='Album',genres=','.join(['Tag']+['Tag '+str(i) for i in range(2,9)]+['tag'])))
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_genres WHERE song_id=1').fetchone()[0],8)

    def old_layout(self):
        from support import pre_disc_layout
        pre_disc_layout(self.conn)
        # Simulate schema 15 rather than relabelling a schema-17 database.
        for name in ('song_vibe_added','song_vibe_keep_slot','song_vibe_keep_identity','vibe_progress_added'):
            self.conn.execute('DROP TRIGGER '+name)
        self.conn.execute('DROP TABLE vibe_rounds')
        self.conn.execute('DROP TABLE song_vibe_progress')
        self.conn.execute('DROP TABLE song_vibe_positions')
        self.conn.execute('DROP TABLE vibe_maps')

    def test_failed_upgrade_leaves_original_memberships_and_version(self):
        self.extra_tags();self.old_layout()
        for name in ('song_tags_limit_insert','song_tags_limit_update'):self.conn.execute('DROP TRIGGER '+name)
        self.conn.executemany('INSERT INTO song_genres VALUES(1,?)',[(i,) for i in range(2,12)])
        self.conn.execute('PRAGMA user_version=15');self.conn.commit();before=capture(self.conn)
        with patch('songranker.storage.database_io.replace_contents',side_effect=sqlite3.DatabaseError('injected failure')):
            with self.assertRaises(sqlite3.DatabaseError):migrate(self.path)
        self.assertEqual(before,capture(self.conn))
        self.assertTrue(list((self.path.parent/'database_backups').glob('*.db')))

    def test_eight_and_duplicate_tags_save_and_ninth_bulk_add_rolls_back(self):
        self.extra_tags();self.fill()
        with self.assertRaises(sqlite3.IntegrityError):self.conn.execute('INSERT INTO song_genres VALUES(1,9)')
        self.conn.rollback()
        self.conn.execute('INSERT OR IGNORE INTO song_genres VALUES(1,8)');self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_genres WHERE song_id=1').fetchone()[0],8)
        before=capture(self.conn)
        response=self.client().post('/api/dev/bulk_songs',json=dict(song_ids=[2,1],action='add_tags',tag_ids=[9]))
        self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(before,capture(self.conn))

    def test_workbench_checks_result_union_not_chosen_count_and_remove_still_works(self):
        self.extra_tags();self.fill();client=self.client();before=capture(self.conn)
        for payload in (dict(action='add_tags',tag_ids=[9]),dict(action='replace_tags',tag_ids=list(range(1,10))),dict(action='add_tags',new_tags=['New'])):
            response=client.post('/api/dev/tags/review',json=dict(song_ids=[1,2])|payload)
            self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(before,capture(self.conn))
        response=client.post('/api/dev/tags/review',json=dict(song_ids=[1],action='add_tags',tag_ids=[8]))
        self.assertEqual(response.status_code,200,response.json)
        response=client.post('/api/dev/tags/review',json=dict(song_ids=[1],action='replace_tags',tag_ids=list(range(2,10))))
        self.assertEqual(response.status_code,200,response.json)
        saved=client.post('/api/dev/tags/apply',json=dict(review_token=response.json['review_token']))
        self.assertEqual(saved.status_code,200,saved.json)
        self.assertEqual([r[0] for r in self.conn.execute('SELECT genre_id FROM song_genres WHERE song_id=1 ORDER BY genre_id')],list(range(2,10)))
        response=client.post('/api/dev/tags/review',json=dict(song_ids=[1],action='remove_tags',tag_ids=list(range(1,12))))
        self.assertEqual(response.status_code,200,response.json)

    def test_trigger_guards_moves_and_allows_changing_tag_at_capacity(self):
        self.extra_tags();self.fill()
        with self.assertRaises(sqlite3.IntegrityError):self.conn.execute('UPDATE song_genres SET song_id=1,genre_id=9 WHERE song_id=2')
        self.conn.rollback()
        self.conn.execute('UPDATE song_genres SET genre_id=9 WHERE song_id=1 AND genre_id=8');self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_genres WHERE song_id=1').fetchone()[0],8)

    def test_upgrade_keeps_earliest_link_order_and_backup_then_is_idempotent(self):
        self.extra_tags();self.old_layout()
        for name in ('song_tags_limit_insert','song_tags_limit_update'):self.conn.execute('DROP TRIGGER '+name)
        # Deliberately different from tag-ID order; keep the earliest saved links.
        order=[11,10,9,8,7,6,5,4,3,2]
        self.conn.executemany('INSERT INTO song_genres VALUES(1,?)',[(i,) for i in order])
        self.conn.execute('PRAGMA user_version=15');self.conn.commit();before=capture(self.conn)
        migrate(self.path)
        self.assertEqual([r[0] for r in self.conn.execute('SELECT genre_id FROM song_genres WHERE song_id=1 ORDER BY rowid')],[1]+order[:7])
        self.assertEqual(self.conn.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
        after=capture(self.conn);reconcile(before,after)
        for name,data in before['tables'].items():
            if name not in ('song_genres','songs','album_shelf_items','albums'):self.assertEqual(data,after['tables'][name],name)
        backups=list((self.path.parent/'database_backups').glob('*.db'));self.assertEqual(len(backups),1)
        old=sqlite3.connect(backups[0]);self.assertEqual(old.execute('SELECT COUNT(*) FROM song_genres WHERE song_id=1').fetchone()[0],11);old.close()
        migrate(self.path);self.assertEqual(after,capture(self.conn));self.assertEqual(backups,list((self.path.parent/'database_backups').glob('*.db')))


if __name__=='__main__':unittest.main()
