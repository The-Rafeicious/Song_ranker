"""Vibe Map migration, four-slot lifecycle, projections and lossless transport."""
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

from songranker.storage.database import initialize_database
from songranker.storage.database_schema import SCHEMA_VERSION
from songranker.storage.database_io import (capture, readonly, reconcile, rebuild,
    sql_dump, validate, write_export, read_export, DatabaseValidationError)
from songranker.storage.vibe_state import MAPS, upgrade_state
from songranker.vibe_maps import song_profiles, with_vibe_maps
from songranker.services import fetch_songs, get_song_full
from songranker.modes.selection_data import with_catalogue_age
from songranker import services, catalog


class VibeMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'songs.db'
        initialize_database(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO songs(id,title,audio_url) VALUES(1,'One','preview'),(2,'Two',NULL)")
        self.conn.commit()

    def place(self, map_id='pace_mood', x=-.75, y=.4):
        self.conn.execute("UPDATE song_vibe_positions SET x=?,y=?,status='placed',updated_at=123 WHERE song_id=1 AND map_id=?", (x,y,map_id))
        self.conn.commit()

    def test_existing_and_future_songs_get_four_independent_slots(self):
        self.assertEqual(self.conn.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(len(MAPS), 4)
        for profile in song_profiles(self.conn, [1,2]).values():
            self.assertEqual(set(profile), {m[0] for m in MAPS})
            self.assertTrue(all(v == dict(x=None,y=None,status='unmapped',updated_at=None,sample_count=0,not_applicable_count=0) for v in profile.values()))
        self.place()
        profile = song_profiles(self.conn,[1])[1]
        self.assertEqual(profile['pace_mood']['x'], -.75)
        self.assertEqual(profile['sound_impact']['status'], 'unmapped')
        self.conn.execute("INSERT INTO songs(id,title) VALUES(3,'Later import')")
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_vibe_positions WHERE song_id=3').fetchone()[0], 4)

    def test_neutral_and_not_applicable_are_different_from_unmapped(self):
        self.place(x=0,y=0)
        self.conn.execute("UPDATE song_vibe_positions SET status='not_applicable',updated_at=124 WHERE song_id=1 AND map_id='sound_impact'")
        profile = song_profiles(self.conn,[1])[1]
        self.assertEqual(profile['pace_mood']['status'], 'placed')
        self.assertEqual(profile['pace_mood']['x'], 0)
        self.assertEqual(profile['sound_impact']['status'], 'not_applicable')
        self.assertIsNone(profile['sound_impact']['x'])

    def test_constraints_refuse_invalid_coordinates_and_missing_identity(self):
        updates = ["x=2,y=0,status='placed',updated_at=1",
                   "x=0,y=-2,status='placed',updated_at=1",
                   "x='text',y=0,status='placed',updated_at=1",
                   "x=0,y=NULL,status='placed',updated_at=1",
                   "x=0,y=0,status='unmapped'", "status='other'",
                   "x=0,y=0,status='placed',updated_at=-1",
                   "x=0,y=0,status='placed',updated_at=NULL",
                   "song_id=2", "map_id='sound_impact'"]
        for update in updates:
            with self.subTest(update=update), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute('UPDATE song_vibe_positions SET '+update+" WHERE song_id=1 AND map_id='pace_mood'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute('DELETE FROM song_vibe_positions WHERE song_id=1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO song_vibe_positions(song_id,map_id) VALUES(1,'fifth')")
        self.conn.execute('DELETE FROM songs WHERE id=1')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_vibe_positions').fetchone()[0],4)
        validate(self.conn)

    def test_reads_include_all_maps_without_duplicate_songs_or_writes(self):
        self.place()
        before = capture(self.conn)
        songs = fetch_songs(self.conn)
        self.assertEqual([s['id'] for s in songs], [1,2])
        self.assertEqual(len(fetch_songs(self.conn,audio_only=True)),1)
        self.assertEqual(get_song_full(1,self.conn)['vibe_maps'], songs[0]['vibe_maps'])
        self.assertIsNone(get_song_full(999,self.conn))
        pool = with_catalogue_age(self.conn, [dict(id=1,elo_score=1200),dict(id=2,elo_score=1200)])
        self.assertEqual(pool[0]['vibe_maps'],songs[0]['vibe_maps'])
        self.assertEqual(pool[0]['elo_score'],1200)
        with patch.object(services,'DB_NAME',str(self.path)):
            data = catalog.collection(True)
        self.assertEqual(len(data['vibe_map_definitions']),4)
        self.assertEqual(data['songs'][0]['vibe_maps'],songs[0]['vibe_maps'])
        self.assertEqual(capture(self.conn),before)

    def test_batched_reads_handle_more_than_sqlite_parameter_limit(self):
        rows = [dict(id=i) for i in range(1,1501)]
        result = with_vibe_maps(self.conn,rows)
        self.assertEqual(len(result),1500)
        self.assertTrue(all(len(row['vibe_maps'])==4 for row in result))

    def test_rebuild_sql_restore_and_restart_preserve_placements(self):
        self.place()
        before = capture(self.conn)
        export = self.folder/'full.json';write_export(self.path,export)
        self.assertEqual(read_export(export),before)
        output = self.folder/'rebuilt.db'
        rebuild(before,output)
        initialize_database(output)
        with readonly(output) as c:
            self.assertEqual(capture(c),before)
        sql = self.folder/'backup.sql';sql.write_text(sql_dump(self.conn))
        restored = self.folder/'restored.db';initialize_database(restored,sql)
        with readonly(restored) as c:
            self.assertEqual(capture(c),before)
        # SQLite's regular iterdump omits the user_version pragma.
        plain = self.folder/'plain.sql';plain.write_text('\n'.join(self.conn.iterdump()))
        plain_restore = self.folder/'plain.db';initialize_database(plain_restore,plain)
        with readonly(plain_restore) as c:
            self.assertEqual(capture(c),before)

    def test_failed_migration_leaves_original_database_and_backup_untouched(self):
        old = self.folder/'v16.db'
        c = sqlite3.connect(old);c.row_factory = sqlite3.Row
        c.executescript(Path(__file__).with_name('fixtures').joinpath('schema_v16.sql').read_text())
        c.execute("INSERT INTO songs(title) VALUES('Keep me')")
        c.execute('PRAGMA user_version=16');c.commit()
        before = capture(c);c.close()
        with patch('songranker.storage.database_io.replace_contents',side_effect=sqlite3.DatabaseError('injected write failure')):
            with self.assertRaises(sqlite3.DatabaseError):initialize_database(old)
        with readonly(old) as c:self.assertEqual(capture(c),before)
        backups = list((self.folder/'database_backups').glob('pre_upgrade_*.db'))
        self.assertEqual(len(backups),1)
        with readonly(backups[0]) as c:self.assertEqual(capture(c),before)

    def test_unmapped_metadata_does_not_change_existing_match_selectors(self):
        import random
        from songranker.modes.selection import choose_match, choose_guess_pair
        songs = [dict(id=i,elo_score=1100+i*25,matches_played=i) for i in range(1,11)]
        annotated = with_vibe_maps(self.conn,songs)
        for selector in (choose_match,choose_guess_pair):
            for seed in range(20):
                original = selector(songs,random.Random(seed))
                projected = selector(annotated,random.Random(seed))
                self.assertEqual([s['id'] for s in original],[s['id'] for s in projected])

    def test_v16_migration_preserves_all_old_facts_and_creates_empty_slots(self):
        old = self.folder/'v16.db'
        c = sqlite3.connect(old);c.row_factory = sqlite3.Row
        c.executescript(Path(__file__).with_name('fixtures').joinpath('schema_v16.sql').read_text())
        c.execute("INSERT INTO competition_state VALUES(1,3,1,'{}')")
        c.execute("INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',1)")
        c.execute("INSERT INTO genres(id,name) VALUES(1,'sad')")
        c.execute("INSERT INTO songs(id,title,elo_score,matches_played) VALUES(7,'Keep title',1345,12)")
        c.execute('INSERT INTO song_genres VALUES(7,1)')
        c.execute('PRAGMA user_version=16');c.commit()
        before = capture(c);c.close()
        initialize_database(old)
        with readonly(old) as c:
            after = capture(c);validate(c)
            self.assertEqual(after['user_version'],SCHEMA_VERSION)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM song_vibe_positions').fetchone()[0],4)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM song_vibe_positions WHERE status='placed'").fetchone()[0],0)
        for name,table in before['tables'].items():
            if name=='listening_observations':continue  # Deliberately retired in schema 20.
            self.assertEqual(after['tables'][name],table,name)
        reconcile(before,after)
        self.assertEqual(upgrade_state(before),upgrade_state(upgrade_state(before)))
        backups = list((old.parent/'database_backups').glob('pre_upgrade_*.db'))
        self.assertEqual(len(backups),1)
        with readonly(backups[0]) as c:self.assertEqual(capture(c),before)
        initialize_database(old)
        self.assertEqual(len(list((old.parent/'database_backups').glob('pre_upgrade_*.db'))),1)

    def test_missing_slot_is_detected_by_validation(self):
        self.conn.execute('DROP TRIGGER song_vibe_keep_slot')
        self.conn.execute("DELETE FROM song_vibe_positions WHERE song_id=1 AND map_id='sound_impact'")
        with self.assertRaises(DatabaseValidationError):validate(self.conn)


if __name__ == '__main__':
    unittest.main()
