"""Album-only Shelves exclusions, preserved rounds and lossless schema upgrades."""
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

import test_preferences as fixture
from songranker import services
from songranker.modes import trivia
from songranker.catalog import proper_album
from songranker.modes.shelves import shelf_pool
from songranker.overall import shelf_eligible_ids
from songranker.storage.database import initialize_database, migrate
from songranker.storage.database_io import capture, readonly, reconcile, write_export, read_export, rebuild


class AlbumShelvesTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def client(self):
        client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        return client

    def edit(self,flag,**extra):
        return self.client().post('/api/dev/edit_album/1',json=dict(title='Album',cover_url='',release_date='',shelves_excluded=flag,**extra))

    def test_flag_only_excludes_shelves_and_can_be_reversed(self):
        self.conn.execute("UPDATE albums SET cover_url='',release_date='' WHERE id=1");self.conn.commit()
        before=capture(self.conn)
        self.assertIn(1,shelf_pool(self.conn))
        self.assertEqual(self.edit(True).status_code,200)
        self.assertNotIn(1,shelf_pool(self.conn))
        album=dict(self.conn.execute('SELECT * FROM albums WHERE id=1').fetchone())
        self.assertTrue(proper_album(album))
        songs=[dict(r) for r in self.conn.execute('SELECT * FROM songs')]
        self.assertFalse({s['id'] for s in songs if s['album_id']==1}&shelf_eligible_ids(dict(songs=songs,albums=[dict(r) for r in self.conn.execute('SELECT * FROM albums')])))
        after=capture(self.conn)
        for table in before['tables']:
            if table!='albums':self.assertEqual(before['tables'][table],after['tables'][table],table)
        self.assertEqual(self.edit(False).status_code,200)
        self.assertIn(1,shelf_pool(self.conn))
        self.assertEqual(capture(self.conn),before)

    def test_saved_round_can_still_be_graded_after_exclusion(self):
        client=self.client()
        offered=client.post('/api/album-shelves/round',json={'album_count':2})
        self.assertEqual(offered.status_code,200,offered.json)
        rows=[dict(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')]
        self.assertTrue(any(r['album_id']==1 for r in rows))
        self.assertEqual(self.edit(True).status_code,200)
        placements={str(slot):[r['item_slot'] for r in sorted(rows,key=lambda r:(r['disc_number'],r['track_number'])) if r['album_slot']==slot] for slot in (1,2)}
        result=client.post('/api/album-shelves/answer',json=dict(token=offered.json['token'],placements=placements))
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['points'],30)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM album_shelf_items').fetchone()[0],10)

    def test_new_rounds_use_other_albums_and_old_clients_preserve_flag(self):
        self.conn.execute("INSERT INTO albums(id,title) VALUES(3,'Third album')")
        for sid in range(11,16):self.conn.execute('INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,3,?)',(sid,f'Track {sid}',sid-10))
        self.conn.commit()
        self.assertEqual(self.edit(True).status_code,200)
        result=self.client().post('/api/dev/edit_album/1',json=dict(title='Album',cover_url='',release_date=''))
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.conn.execute('SELECT shelves_excluded FROM albums WHERE id=1').fetchone()[0],1)
        for _ in range(3):
            response=self.client().post('/api/album-shelves/round',json={'album_count':2})
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual({a['id'] for a in response.json['albums']},{2,3})

    def test_excluded_history_is_hidden_everywhere_and_returns_when_included(self):
        from songranker.catalog import collection, special_records
        from songranker.modes.shelves import build_shelves_stats
        from songranker.overall import features, topology
        client=self.client()
        offered=client.post('/api/album-shelves/round',json={'album_count':2}).json
        rows=[dict(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')]
        placements={str(slot):[r['item_slot'] for r in sorted(rows,key=lambda r:(r['disc_number'],r['track_number'])) if r['album_slot']==slot] for slot in (1,2)}
        self.assertEqual(client.post('/api/album-shelves/answer',json=dict(token=offered['token'],placements=placements)).status_code,200)
        baseline=special_records(self.conn)
        self.assertEqual(baseline[1]['shelves']['rounds'],1)
        old=collection(include_overall_sources=True)
        self.edit(True)
        data=collection(include_overall_sources=True)
        self.assertNotEqual(topology(old),topology(data))
        self.assertEqual(data['special_modes']['shelves']['rounds'],0)
        self.assertTrue(all(s['shelf_attempts']==0 for s in data['songs']))
        self.assertTrue(all(not s['shelves_eligible'] for s in data['songs'] if s['album_id']==1))
        self.assertTrue(all(s['shelves_eligible'] for s in data['songs'] if s['album_id']==2))
        self.assertTrue(all(s['mode_appearances']['shelves']==0 for s in features(data).values()))
        self.assertEqual(special_records(self.conn)[3],[])
        self.assertEqual(client.get('/api/special-modes/stats').json['participating_albums'],[])
        report=build_shelves_stats(self.conn)
        self.assertEqual(report['summary']['rounds'],0)
        from songranker.reports.stats_activity import build_activity
        self.assertEqual(build_activity(self.conn,'shelves')['total'],0)
        self.assertEqual(build_activity(self.conn,'global')['total'],0)
        self.assertNotIn('Album</a>',client.get('/album_shelves_stats').get_data(as_text=True))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM album_shelf_items').fetchone()[0],10)
        self.edit(False)
        self.assertEqual(special_records(self.conn),baseline)

    def test_new_trivia_skips_excluded_album_name_but_preserves_album(self):
        self.conn.execute("UPDATE songs SET audio_url='' WHERE album_id=2")
        self.conn.commit()
        self.edit(True)
        response=self.client().get('/api/trivia/round',headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertFalse(response.json['album_available'])
        self.assertNotIn('album',response.json['fields'])
        self.assertTrue(proper_album(dict(self.conn.execute('SELECT * FROM albums WHERE id=1').fetchone())))

    def test_dedicated_bracket_page_has_missing_record_404(self):
        self.assertEqual(self.client().get('/tournament/9999/bracket').status_code,404)

    def test_invalid_flags_are_rejected_without_changes_and_auth_is_required(self):
        before=capture(self.conn)
        for value in ('false','true',0,1,None,[],{}):
            self.assertEqual(self.edit(value).status_code,400,value)
            self.assertEqual(capture(self.conn),before)
        self.assertIn(services.app.test_client().post('/api/dev/edit_album/1',json=dict(title='Album',shelves_excluded=True)).status_code,(302,403))

    def test_flag_survives_sql_and_lossless_export_rebuild(self):
        self.edit(True)
        export=Path(self.temp.name)/'export.json';rebuilt=Path(self.temp.name)/'rebuilt.db'
        write_export(self.path,export);rebuild(read_export(export),rebuilt)
        with readonly(rebuilt) as conn:reconcile(capture(self.conn),capture(conn))
        sql=Path(self.temp.name)/'flagged.sql';sql.write_text('\n'.join(self.conn.iterdump()))
        restored=Path(self.temp.name)/'sql.db';initialize_database(restored,sql)
        with readonly(restored) as conn:
            self.assertEqual(conn.execute('SELECT shelves_excluded FROM albums WHERE id=1').fetchone()[0],1)
            self.assertNotIn(1,shelf_pool(conn))

    def test_schema_21_upgrade_and_unversioned_dump_default_to_included(self):
        # Build the previous complete layout, including its old album definition.
        old_schema=(Path('data/schema.sql').read_text().replace(",\n    shelves_excluded INTEGER NOT NULL DEFAULT 0 CHECK(shelves_excluded IN (0,1))",''))
        old=Path(self.temp.name)/'old.db';c=sqlite3.connect(old);c.executescript(old_schema)
        from songranker.storage.vibe_state import seed_definitions
        seed_definitions(c)
        c.execute("INSERT INTO albums(id,title) VALUES(42,'Grouped singles')")
        c.execute("INSERT INTO songs(id,title,album_id) VALUES(77,'Track',42)")
        c.execute("INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',2)")
        c.execute('PRAGMA user_version=21');c.commit()
        dump=Path(self.temp.name)/'old.sql';dump.write_text('\n'.join(c.iterdump()));c.close()
        restored=Path(self.temp.name)/'old-restored.db';initialize_database(restored,dump);migrate(old)
        for path in (old,restored):
            with readonly(path) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],22)
                self.assertEqual(tuple(conn.execute('SELECT id,title,shelves_excluded FROM albums').fetchone()),(42,'Grouped singles',0))
                self.assertEqual(tuple(conn.execute('SELECT id,album_id FROM songs').fetchone()),(77,42))
                before=capture(conn)
            migrate(path)
            with readonly(path) as conn:self.assertEqual(capture(conn),before)
        self.assertTrue(list(old.parent.glob('database_backups/pre_upgrade_*.db')))

if __name__=='__main__':unittest.main()
