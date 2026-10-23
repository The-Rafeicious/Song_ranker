"""Schema-20 telemetry retirement with a complete old backup and exact game retention."""
from pathlib import Path
import sqlite3
import unittest
import test_preferences as fixture
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture,readonly,reconcile,sql_dump
from songranker.storage.database_schema import SCHEMA_VERSION
from songranker import services
from songranker.modes import guesser, shelves
from songranker.modes import trivia
from songranker.modes import vibe_map


class RetireListeningTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def legacy(self):
        ddl=Path('tests/fixtures/schema_v18.sql').read_text()
        a=ddl.index('CREATE TABLE IF NOT EXISTS listening_observations')
        b=ddl.index(';',a)+1
        self.conn.executescript(ddl[a:b])
        self.conn.execute('CREATE INDEX listening_song_mode ON listening_observations(song_id,mode)')
        self.conn.execute("INSERT INTO listening_observations(mode,reference,song_key,song_id,seconds,decision_ms,recorded_at) VALUES('standard','1',1,1,12,12000,1)")
        self.conn.execute("UPDATE song_vibe_positions SET x=.25,y=-.5,status='placed',sample_count=3,updated_at=1 WHERE song_id=1")
        self.conn.execute('UPDATE songs SET elo_score=1300 WHERE id=1')
        from support import pre_disc_layout
        pre_disc_layout(self.conn)
        self.conn.execute('PRAGMA user_version=19');self.conn.commit()

    def test_old_data_is_backed_up_then_only_retired_objects_disappear(self):
        self.legacy();before=capture(self.conn);initialize_database(self.path);after=capture(self.conn)
        self.assertEqual(after['user_version'],SCHEMA_VERSION)
        self.assertNotIn('listening_observations',after['tables'])
        for name,data in before['tables'].items():
            if name not in ('listening_observations','songs','album_shelf_items'):self.assertEqual(after['tables'][name],data,name)
        reconcile(before,after)
        backup=next(self.path.parent.joinpath('database_backups').glob('pre_upgrade_*.db'))
        with readonly(backup) as old:self.assertEqual(capture(old),before)
        initialize_database(self.path);self.assertEqual(capture(self.conn),after)
        # Restoring an old SQL export also retires telemetry, retaining the Vibe points.
        old_sql=sql_dump_from_legacy(before,self.temp.name)
        restored=Path(self.temp.name)/'restored.db';initialize_database(restored,old_sql)
        with readonly(restored) as c:reconcile(before,capture(c))

    def test_dependent_extension_blocks_upgrade_without_discarding_it(self):
        self.legacy();self.conn.execute('CREATE VIEW custom_playback AS SELECT * FROM listening_observations');self.conn.commit();before=capture(self.conn)
        with self.assertRaisesRegex(ValueError,'extension depends'):initialize_database(self.path)
        self.assertEqual(capture(self.conn),before)

    def test_public_pages_and_payloads_have_no_listening_process_or_data(self):
        from songranker import pages,catalog
        self.assertTrue(all('listening' not in song for song in catalog.collection()['songs']))
        with services.app.test_client() as client:
            for path in ['/global_stats','/voting_stats','/trivia_stats','/tournament_stats','/elo_guesser_stats','/album_shelves_stats','/game','/trivia','/elo_guesser','/album_shelves']:
                response=client.get(path);self.assertEqual(response.status_code,200,path)
                self.assertNotIn('listening-panel',response.get_data(as_text=True));self.assertNotIn('js/listening.js',response.get_data(as_text=True))


def sql_dump_from_legacy(state,folder):
    # The historical exporter would validate schema 19; construct exactly that
    # snapshot without routing it through the new state's retirement adapter.
    from songranker.storage.database_io import sql_dump
    path=Path(folder)/'old.sql'
    source=Path(folder)/'database_backups'
    old=next(source.glob('pre_upgrade_*.db'))
    with readonly(old) as c:path.write_text(sql_dump(c))
    return path
