"""Schema 9 recovery/integrity regressions. Only temporary databases are written."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch
from types import SimpleNamespace
import hashlib
import json
import shutil
import runpy
import sys
import sqlite3
import tempfile
import unittest

from songranker.storage import database
from songranker.storage import database_io as io
from songranker.storage.database_access import MaintenanceGate
from songranker.storage.database_schema import (SCHEMA_VERSION, create_objects)
from songranker.developer import db_tools


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(path):
    with io.snapshot(path) as conn:
        return io.capture(conn)


def fixture(path):
    c = sqlite3.connect(path)
    c.executescript((Path(__file__).with_name('fixtures') / 'schema_v9.sql').read_text())
    c.executemany('INSERT INTO global_stats(key,value) VALUES(?,?)', [('trivia_high_score',0),('trivia_high_streak',0),('trivia_scoring_version',2)])
    c.execute("INSERT INTO albums(id,title,release_date) VALUES(5,'Album','2001-02-03'),(6,'Other','2002')")
    c.execute("INSERT INTO artists(id,name) VALUES(3,'Artist, One')")
    c.execute("INSERT INTO genres(id,name,description) VALUES(9,'Tag','Description')")
    for i in range(1, 11):
        c.execute('INSERT INTO songs(id,title,album_id,track_number,audio_url) VALUES(?,?,?,?,?)',
                  (i * 10, f'Song {i}', 5 if i <= 5 else 6, (i - 1) % 5 + 1, 'https://example.test/preview'))
        c.execute('INSERT INTO song_artists VALUES(?,3)', (i * 10,))
        c.execute('INSERT INTO song_genres VALUES(?,9)', (i * 10,))
    c.execute("INSERT INTO history(id,winner_id,loser_id,mode,created_at,winner_before,winner_after,loser_before,loser_after) "
              "VALUES(12,10,20,'blind','2026-01-01 12:00:00',1200,1216,1200,1184)")
    c.execute('UPDATE songs SET matches_played=1,elo_score=CASE id WHEN 10 THEN 1216 ELSE 1184 END WHERE id IN (10,20)')
    c.execute("INSERT INTO trivia_rounds(id,token,song_id,album_available,started_at,completed_at,title_correct,artist_correct,album_correct,title_seconds,artist_seconds,album_seconds,user_score_after,streak_after) "
              "VALUES(25,'trivia-done',10,1,20,50,1,0,1,9,30,20,1.2345,2)")
    c.execute("INSERT INTO trivia_rounds(id,token,song_id,album_available,started_at,paused_at,paused_seconds) VALUES(26,'trivia-pending',20,0,60,64,2)")
    c.execute('UPDATE global_stats SET value=221 WHERE key=\'trivia_high_streak\'')
    c.execute('UPDATE global_stats SET value=25.5 WHERE key=\'trivia_high_score\'')
    c.execute("INSERT INTO tournaments(id,size,scope_type,scope_id,status,created_at,is_blind) VALUES(70,8,'artist',3,'active','2026-01-01',1)")
    c.execute('INSERT INTO tournament_entries VALUES(70,10,1),(70,20,2)')
    c.execute("INSERT INTO tournament_matches(id,tournament_id,round_number,match_number,song1_id,song2_id) VALUES(72,70,1,1,10,20)")
    c.execute("INSERT INTO elo_guess_rounds(id,token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES(80,'guess-done',10,20,1220,1190,1,2,1)")
    c.execute("INSERT INTO elo_guess_rounds(id,token,song1_id,song2_id,elo1,elo2,started_at) VALUES(81,'guess-pending',20,30,1190,1200,3)")
    c.execute("INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(90,'shelf-done',1,2)")
    for i in range(1, 11):
        slot = 1 if i <= 5 else 2
        c.execute('INSERT INTO album_shelf_items VALUES(?,?,?,?,?,?,?,?)',
                  (90, i, i * 10, 5 if slot == 1 else 6, slot, (i - 1) % 5 + 1, slot, (i - 1) % 5 + 1))
    # A deleted ID must stay reserved even though max(history.id) is much lower.
    c.execute('INSERT INTO history(id,winner_id,loser_id) VALUES(2000,10,20)')
    c.execute('DELETE FROM history WHERE id=2000')
    c.execute('PRAGMA user_version=8')
    c.commit()
    c.close()


class DatabaseFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'source.db'
        fixture(self.db)

    def test_upgrade_preserves_all_values_views_sequences_and_pending_rounds(self):
        before = state(self.db)
        database.migrate(self.db)
        after = state(self.db)
        io.reconcile(before, after)
        self.assertEqual(after['user_version'], SCHEMA_VERSION)
        self.assertEqual(after['sequences']['preference_events'], 2000)
        backups = list((self.root / 'database_backups').glob('pre_upgrade_*.db'))
        self.assertEqual(len(backups), 1)
        io.reconcile(before, state(backups[0]))
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute('INSERT INTO preference_events(winner_id,loser_id) VALUES(10,20)').lastrowid, 2001)
        c.rollback(); c.close()

    def test_migration_is_idempotent_and_fresh_upgrade_definitions_match(self):
        database.migrate(self.db)
        before = fingerprint(self.db)
        database.migrate(self.db)
        self.assertEqual(fingerprint(self.db), before)
        fresh = self.root / 'fresh.db'
        database.initialize_database(fresh)
        self.assertEqual(state(self.db)['objects'], state(fresh)['objects'])

    def test_round_trip_export_rebuild_keeps_grades_metadata_and_ids(self):
        before = state(self.db)
        before_hash = fingerprint(self.db)
        export = self.root / 'all.json'
        io.write_export(self.db, export)
        output = self.root / 'rebuilt.db'
        io.rebuild(io.read_export(export), output)
        io.reconcile(before, state(output))
        self.assertEqual(fingerprint(self.db), before_hash)
        # Exercise the actual grading functions, not a duplicate implementation.
        from songranker.modes.special_modes import special_records
        from songranker.modes.trivia import round_points
        with io.readonly(self.db) as a, io.readonly(output) as b:
            self.assertEqual(special_records(a), special_records(b))
            old = a.execute('SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL').fetchall()
            new = b.execute('SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL').fetchall()
            self.assertEqual([round_points(r) for r in old], [round_points(r) for r in new])

    def test_extension_tables_blobs_rowids_views_indexes_and_triggers_survive(self):
        c = sqlite3.connect(self.db)
        c.executescript('''CREATE TABLE extra_notes(body TEXT, payload BLOB);
            INSERT INTO extra_notes(rowid,body,payload) VALUES(99,'kept',X'00FF10');
            CREATE INDEX extra_body ON extra_notes(body);
            CREATE VIEW extra_summary AS SELECT body,length(payload) n FROM extra_notes;
            CREATE TRIGGER extra_insert AFTER INSERT ON artists BEGIN
              INSERT INTO extra_notes(body) VALUES(NEW.name); END;''')
        c.close()
        before = state(self.db)
        database.migrate(self.db)
        io.reconcile(before, state(self.db))
        with io.readonly(self.db) as c:
            self.assertEqual(tuple(c.execute('SELECT rowid,body,payload FROM extra_notes').fetchone()),
                             (99, 'kept', b'\x00\xff\x10'))
        self.assertIn('extra_notes', io.audit(self.db)['preserved_extensions'])

    def test_unknown_managed_column_refuses_upgrade_without_losing_values(self):
        c = sqlite3.connect(self.db)
        c.execute('ALTER TABLE songs ADD COLUMN private_note TEXT')
        c.execute("UPDATE songs SET private_note='preserve this'")
        c.commit(); c.close()
        before = fingerprint(self.db)
        with self.assertRaisesRegex(io.DatabaseValidationError, 'Unsupported columns'):
            database.migrate(self.db)
        self.assertEqual(fingerprint(self.db), before)

    def test_generated_extension_column_is_not_silently_discarded(self):
        c = sqlite3.connect(self.db)
        c.execute('ALTER TABLE songs ADD COLUMN title_length INTEGER GENERATED ALWAYS AS (length(title)) VIRTUAL')
        c.commit(); c.close()
        before = fingerprint(self.db)
        with self.assertRaisesRegex(io.DatabaseValidationError, 'dedicated migration'):
            database.migrate(self.db)
        self.assertEqual(fingerprint(self.db), before)

    def test_failure_after_drop_rolls_back_the_entire_upgrade(self):
        before = fingerprint(self.db)
        def fail(conn, data):
            conn.execute('DROP VIEW trivia_stats')
            conn.execute('DROP TABLE history')
            raise RuntimeError('injected failure')
        with patch.object(io, 'replace_contents', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                database.migrate(self.db)
        self.assertEqual(fingerprint(self.db), before)
        self.assertEqual(io.audit(self.db)['counts']['history'], 1)

    def test_concurrent_write_during_preparation_aborts_without_losing_that_write(self):
        original = io.create_backup
        def writer(path, prefix):
            result = original(path, prefix)
            c = sqlite3.connect(path)
            c.execute("UPDATE global_stats SET value=222 WHERE key='trivia_high_streak'")
            c.commit(); c.close()
            return result
        with patch.object(io, 'create_backup', side_effect=writer):
            with self.assertRaisesRegex(io.DatabaseValidationError, 'changed during'):
                database.migrate(self.db)
        with io.readonly(self.db) as c:
            self.assertEqual(c.execute("SELECT value FROM global_stats WHERE key='trivia_high_streak'").fetchone()[0], 222)
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 8)

    def test_future_schema_is_rejected_unchanged(self):
        c = sqlite3.connect(self.db); c.execute('PRAGMA user_version=999'); c.close()
        before = fingerprint(self.db)
        with self.assertRaisesRegex(io.DatabaseValidationError, 'newer app'):
            database.migrate(self.db)
        self.assertEqual(fingerprint(self.db), before)

    def test_sql_backup_restores_before_empty_creation_even_without_git(self):
        dump = self.root / 'database_backup.sql'
        with io.readonly(self.db) as c:
            dump.write_text('\n'.join(c.iterdump()), encoding='utf-8')
        output = self.root / 'restored.db'
        self.assertEqual(database.initialize_database(output, dump), 'restored')
        io.reconcile(state(self.db), state(output))

    def test_existing_database_wins_over_sql_even_when_backup_is_invalid(self):
        dump = self.root / 'invalid.sql'; dump.write_text('not SQL', encoding='utf-8')
        before = state(self.db)
        self.assertEqual(database.initialize_database(self.db, dump), 'existing')
        io.reconcile(before, state(self.db))

    def test_invalid_sql_and_broken_references_never_publish_empty_database(self):
        for label, sql in [('syntax', 'not SQL'), ('foreign-key', self.sql_dump(broken=True)),
                           ('attach', "ATTACH DATABASE 'elsewhere.db' AS other;"),
                           ('future', self.sql_dump() + '\nPRAGMA user_version=999;')]:
            with self.subTest(label=label):
                dump = self.root / f'{label}.sql'; dump.write_text(sql, encoding='utf-8')
                output = self.root / f'{label}.db'
                with self.assertRaises((sqlite3.Error, io.DatabaseValidationError)):
                    database.initialize_database(output, dump)
                self.assertFalse(output.exists())

    def sql_dump(self, broken=False):
        with io.snapshot(self.db) as c:
            if broken:
                c.execute('UPDATE songs SET album_id=999999 WHERE id=10'); c.commit()
            return '\n'.join(c.iterdump())

    def test_export_checksum_and_existing_outputs_are_protected(self):
        export = self.root / 'all.json'
        io.write_export(self.db, export)
        with self.assertRaises(io.DatabaseValidationError):
            io.write_export(self.db, export)
        before = fingerprint(self.db)
        with self.assertRaises(io.DatabaseValidationError):
            io.rebuild(state(self.db), self.db)
        self.assertEqual(fingerprint(self.db), before)
        data = json.loads(export.read_text()); data['state']['user_version'] = 999
        export.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(io.DatabaseValidationError, 'checksum'):
            io.read_export(export)

    def test_restore_prepares_migrated_copy_and_retains_original_backup(self):
        before = fingerprint(self.db)
        output = self.root / 'candidate.db'
        io.prepare_candidate(self.db, output)
        self.assertEqual(fingerprint(self.db), before)
        self.assertEqual(io.audit(output)['schema_version'], SCHEMA_VERSION)
        io.reconcile(state(self.db), state(output))

    def test_live_restore_installs_verified_candidate_and_keeps_pre_restore_state(self):
        live = self.root / 'live.db'; shutil.copy2(self.db, live)
        c = sqlite3.connect(live)
        c.execute("UPDATE artists SET name='New live name' WHERE id=3")
        c.commit(); c.close()
        before = state(live)
        backup = io.restore_live_database(self.db, live)
        io.reconcile(before, state(backup))
        io.reconcile(state(self.db), state(live))
        self.assertEqual(state(live)['user_version'], SCHEMA_VERSION)

    def test_broken_and_corrupt_backups_leave_live_database_unchanged(self):
        broken = self.root / 'broken.db'; shutil.copy2(self.db, broken)
        c = sqlite3.connect(broken)
        c.execute('UPDATE songs SET album_id=999999 WHERE id=10'); c.commit(); c.close()
        corrupt = self.root / 'corrupt.db'; corrupt.write_bytes(b'not a database')
        for candidate in (broken, corrupt):
            before = fingerprint(self.db)
            with self.subTest(candidate=candidate.name):
                with self.assertRaises((io.DatabaseValidationError, sqlite3.Error)):
                    io.restore_live_database(candidate, self.db)
                self.assertEqual(fingerprint(self.db), before)

    def test_post_restore_verification_failure_rolls_back_live_state(self):
        live = self.root / 'live.db'; shutil.copy2(self.db, live)
        c = sqlite3.connect(live)
        c.execute("UPDATE artists SET name='Keep current state on failure' WHERE id=3")
        c.commit(); c.close()
        before = state(live)
        candidate = self.root / 'prepared.db'; io.prepare_candidate(self.db, candidate)
        with patch.object(io, 'prepare_candidate', return_value=candidate), \
             patch.object(io, 'reconcile', side_effect=RuntimeError('post-restore failure')):
            with self.assertRaisesRegex(RuntimeError, 'post-restore failure'):
                io.restore_live_database(self.db, live)
        io.reconcile(before, state(live))

    def test_historical_track_position_conflicts_are_reported_without_renumbering(self):
        c = sqlite3.connect(self.db)
        c.execute('DROP TRIGGER songs_track_position_update')
        c.execute('UPDATE songs SET track_number=1 WHERE id=20'); c.commit(); c.close()
        before = state(self.db)
        database.migrate(self.db)
        io.reconcile(before, state(self.db))
        self.assertEqual(len(io.audit(self.db)['track_position_conflicts']), 2)

    def test_flat_database_is_refused_without_modification(self):
        flat = self.root / 'flat.db'
        c = sqlite3.connect(flat); c.execute('CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT)'); c.close()
        before = fingerprint(flat)
        with self.assertRaises(io.DatabaseValidationError):
            database.migrate(flat)
        self.assertEqual(fingerprint(flat), before)

    def test_dev_restore_and_overview_use_complete_inventory_and_authentication(self):
        from songranker import services
        from songranker.developer import dev
        from songranker.storage.database_access import gate
        backup_dir = self.root / 'database_backups'; backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / 'manual_fixture.db'; shutil.copy2(self.db, backup)
        from songranker.storage.competition import start_competition
        active=self.root/'song_ranker_v3.db';start_competition(active,self.db)
        client = services.app.test_client()
        with patch.object(dev, 'DB_NAME', str(active)), patch.object(services, 'DB_NAME', str(active)):
            self.assertEqual(client.post('/api/dev/restore-backup', json={'filename': backup.name}).status_code, 302)
            with client.session_transaction() as session:
                session['is_admin'] = True
            blocked = client.post('/api/dev/restore-backup', json={'filename': backup.name},
                                  environ_overrides={'wsgi.multiprocess': True})
            self.assertEqual(blocked.status_code, 409)
            response = client.post('/api/dev/restore-backup', json={'filename': backup.name})
            self.assertEqual(response.status_code, 409, response.get_json())
            self.assertIn('V2 archive',response.json['message'])
            overview = client.get('/api/dev/overview')
            self.assertEqual(overview.status_code, 200)
            self.assertEqual(overview.json['schema_version'], SCHEMA_VERSION)
            self.assertIn('trivia_adjustments', overview.json['counts'])
            self.assertEqual(gate.connections, 0)
            connection = services.get_db_connection()
            self.assertEqual(gate.connections, 1)
            connection.close(); connection.close()
            self.assertEqual(gate.connections, 0)

    def test_wal_commits_are_included_in_exports(self):
        c = sqlite3.connect(self.db)
        c.execute('PRAGMA journal_mode=WAL')
        c.execute("UPDATE artists SET name='Committed in WAL' WHERE id=3"); c.commit()
        export = self.root / 'wal.json'; io.write_export(self.db, export)
        output = self.root / 'wal-copy.db'; io.rebuild(io.read_export(export), output)
        with io.readonly(output) as result:
            self.assertEqual(result.execute('SELECT name FROM artists WHERE id=3').fetchone()[0], 'Committed in WAL')
        c.close()

    def test_cli_export_rebuild_compare_restore_and_errors(self):
        export = self.root / 'cli.json'; output = self.root / 'cli.db'; recovery = self.root / 'recovery.db'
        commands = [['audit', '--db', str(self.db)],
            ['export', '--db', str(self.db), '--output', str(export)],
            ['rebuild', '--from-export', str(export), '--output', str(output)],
            ['compare', '--before', str(self.db), '--after', str(output)],
            ['restore', '--backup', str(self.db), '--output', str(recovery)]]
        for args in commands:
            with self.subTest(command=args[0]), redirect_stdout(StringIO()):
                self.assertEqual(db_tools.main(args), 0)
        with redirect_stdout(StringIO()):
            self.assertEqual(db_tools.main(['rebuild', '--from-db', str(self.db), '--output', str(self.db)]), 1)

    def startup_events(self, run_name):
        from songranker import services
        import os
        calls = []
        (self.root / '.git').mkdir(exist_ok=True)
        modules = {name: SimpleNamespace() for name in ('apple_access', 'pages', 'trivia',
            'special_modes', 'overall', 'games', 'metadata_tools', 'dev', 'dev_catalog', 'dev_tags', 'dev_system')}
        modules['git_sync']=SimpleNamespace(GitSync=lambda *args:SimpleNamespace(startup=lambda:(calls.append('pull') or dict(code='unchanged',message='Test startup check')),
            reconcile_database=lambda:(calls.append('database') or dict(code='database_matches',message='Test database check'))))
        paths={'database': 'songranker.storage.database', 'database_schema': 'songranker.storage.database_schema', 'database_io': 'songranker.storage.database_io', 'database_access': 'songranker.storage.database_access', 'competition': 'songranker.storage.competition', 'schema_compat': 'songranker.storage.schema_compat', 'preference_state': 'songranker.storage.preference_state', 'catalog_source_state': 'songranker.storage.catalog_source_state', 'challenge_state': 'songranker.storage.challenge_state', 'global_stats_data': 'songranker.reports.global_stats_data', 'voting_stats_data': 'songranker.reports.voting_stats_data', 'recognition_stats_data': 'songranker.reports.recognition_stats_data', 'tournament_stats_data': 'songranker.reports.tournament_stats_data', 'guesser_stats_data': 'songranker.reports.guesser_stats_data', 'shelves_stats_data': 'songranker.reports.shelves_stats_data', 'stats_activity': 'songranker.reports.stats_activity', 'data_health': 'songranker.reports.data_health', 'selection_health': 'songranker.reports.selection_health', 'games': 'songranker.modes.games', 'trivia': 'songranker.modes.trivia', 'special_modes': 'songranker.modes.special_modes', 'preferences': 'songranker.modes.preferences', 'challenges': 'songranker.modes.challenges', 'challenge_rules': 'songranker.modes.challenge_rules', 'mode_ratings': 'songranker.modes.mode_ratings', 'selection': 'songranker.modes.selection', 'selection_data': 'songranker.modes.selection_data', 'dev': 'songranker.developer.dev', 'dev_catalog': 'songranker.developer.dev_catalog', 'dev_tags': 'songranker.developer.dev_tags', 'dev_system': 'songranker.developer.dev_system', 'metadata_tools': 'songranker.developer.metadata_tools', 'metadata_fill': 'songranker.developer.metadata_fill', 'catalog_sources': 'songranker.developer.catalog_sources', 'catalog_operations': 'songranker.developer.catalog_operations', 'tag_operations': 'songranker.developer.tag_operations', 'git_sync': 'songranker.developer.git_sync', 'db_tools': 'songranker.developer.db_tools', 'track_numbers': 'songranker.developer.track_numbers'}
        modules={paths.get(name,'songranker.'+name):value for name,value in modules.items()}
        with patch.dict(sys.modules, modules), patch.object(services, 'ROOT', self.root), \
             patch.object(services, 'init_db', side_effect=lambda: calls.append('bootstrap')), \
             patch('waitress.create_server', return_value=SimpleNamespace(run=lambda:calls.append('serve'))), \
             patch('songranker.hosting.register_waitress_shutdown'), \
             patch.dict(os.environ, {'SONG_RANKER_PORT': '5000','SONG_RANKER_BOOT_COMMIT':''}):
            runpy.run_path(str(Path(__file__).resolve().parents[1] / 'main.py'), run_name=run_name)
        return calls

    def test_script_startup_pulls_before_bootstrap_and_serving(self):
        self.assertEqual(self.startup_events('__main__'), ['pull', 'bootstrap', 'database', 'serve'])

    def test_wsgi_startup_bootstraps_without_git_or_starting_a_server(self):
        self.assertEqual(self.startup_events('isolated_wsgi_import'), ['bootstrap'])


class MaintenanceGateTests(unittest.TestCase):
    def test_normal_connections_remain_concurrent_and_timeout_reopens_gate(self):
        gate = MaintenanceGate()
        gate.enter_connection(); gate.enter_connection()
        with self.assertRaises(TimeoutError):
            with gate.maintenance(timeout=.01):
                self.fail('Maintenance must wait for open connections')
        gate.leave_connection(); gate.leave_connection()
        with gate.maintenance(timeout=.01):
            self.assertEqual(gate.connections, 0)

    def test_maintenance_drains_connections_and_blocks_new_ones(self):
        gate = MaintenanceGate()
        gate.enter_connection()
        requested = Event(); entered = Event(); release = Event(); new_entered = Event()
        def maintain():
            requested.set()
            with gate.maintenance(timeout=2):
                entered.set(); release.wait(2)
        task = Thread(target=maintain)
        task.start(); self.assertTrue(requested.wait(1))
        self.assertFalse(entered.wait(.02))
        gate.leave_connection(); self.assertTrue(entered.wait(1))
        def connect():
            gate.enter_connection(timeout=2); new_entered.set(); gate.leave_connection()
        newcomer = Thread(target=connect); newcomer.start()
        self.assertFalse(new_entered.wait(.02))
        release.set(); task.join(2); newcomer.join(2)
        self.assertTrue(new_entered.is_set()); self.assertEqual(gate.connections, 0)


if __name__ == '__main__':
    unittest.main()
