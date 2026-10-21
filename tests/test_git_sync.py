"""Real local repositories/remotes only. Never contacts the user's remote."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import py_compile
import shutil
import sqlite3
import subprocess
import sys
import unittest

from songranker.storage.database import initialize_database
from songranker.storage.database_schema import SCHEMA_VERSION
from songranker.storage.database_io import (capture, readonly)
from songranker.developer.git_sync import (GitSync, SyncError, display_remote)

ROOT=Path(__file__).resolve().parents[1]


def command(root,*args):
    r=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,timeout=15)
    if r.returncode:raise AssertionError(r.stderr)
    return r.stdout.strip()


class GitSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        # Nested fixtures must never discover the enclosing checkout (detached in CI).
        isolation=patch.dict(os.environ, GIT_CEILING_DIRECTORIES=str(self.folder.resolve()))
        isolation.start();self.addCleanup(isolation.stop)
        self.remote=self.folder/'remote.git';self.seed=self.folder/'seed';self.work=self.folder/'app'
        command(self.folder,'init','--bare','--initial-branch=main',str(self.remote))
        self.seed.mkdir();command(self.seed,'init','-b','main');self.identity(self.seed)
        (self.seed/'app.py').write_text("VERSION='old'\n");(self.seed/'database_backup.sql').write_text('-- initial snapshot\n')
        (self.seed/'.gitignore').write_text('*.db\n*.db-*\n__pycache__/\ndatabase_backups/\ninstance/\n')
        command(self.seed,'add','.');command(self.seed,'commit','-m','Initial code');command(self.seed,'remote','add','origin',str(self.remote));command(self.seed,'push','-u','origin','main')
        command(self.folder,'clone',str(self.remote),str(self.work));self.identity(self.work)
        self.db=self.work/'live.db';initialize_database(self.db)
        c=sqlite3.connect(self.db);c.execute("INSERT INTO songs(id,title) VALUES(1,'Fixture song')");c.commit();c.close()
        self.sync=GitSync(self.work,self.db)

    def identity(self,root):
        command(root,'config','user.name','Fixture tester');command(root,'config','user.email','fixture@example.invalid')
        command(root,'config','commit.gpgsign','false')

    def state(self):
        with readonly(self.db) as c:return capture(c)

    def remote_change(self,files):
        command(self.seed,'pull','--ff-only')
        for name,value in files.items():
            p=self.seed/name;p.parent.mkdir(parents=True,exist_ok=True)
            if value is None:
                p.unlink(missing_ok=True);command(self.seed,'add','-u','--',name)
            else:
                p.write_text(value);command(self.seed,'add','-f','--',name)
        command(self.seed,'commit','-m','Remote update');command(self.seed,'push','origin','main')

    def head(self,where=None):return command(where or self.work,'rev-parse','HEAD')

    def test_local_status_and_check_do_not_change_worktree_or_database(self):
        before=self.state();head=self.head();sql=self.sync.sql.read_bytes()
        status=self.sync.status();self.assertEqual(status['state'],'up_to_date');self.assertEqual(status['branch'],'main')
        checked=self.sync.check();self.assertTrue(checked['ok']);self.assertEqual(checked['git']['behind'],0)
        self.assertEqual(self.state(),before);self.assertEqual(self.head(),head);self.assertEqual(self.sync.sql.read_bytes(),sql)

    def test_check_reports_incoming_code_without_installing_it(self):
        self.remote_change({'app.py':"VERSION='new'\n"});before=self.state()
        result=self.sync.check();self.assertEqual(result['git']['state'],'behind');self.assertEqual(result['git']['behind'],1)
        self.assertIn('old',(self.work/'app.py').read_text());self.assertEqual(self.state(),before)

    def test_upload_commits_only_snapshot_preserving_unrelated_staging(self):
        (self.work/'app.py').write_text("VERSION='local edit'\n");command(self.work,'add','app.py')
        staged=command(self.work,'rev-parse',':app.py');before=self.state()
        result=self.sync.upload(self.sync.status()['fingerprint']);self.assertTrue(result['ok'],result);self.assertEqual(result['code'],'uploaded')
        self.assertEqual(command(self.work,'diff-tree','--no-commit-id','--name-only','-r','HEAD'),'database_backup.sql')
        self.assertEqual(command(self.work,'rev-parse',':app.py'),staged)
        self.assertEqual(command(self.work,'diff','--cached','--name-only'),'app.py')
        self.assertEqual(command(self.remote,'rev-parse','main'),self.head());self.assertEqual(self.state(),before)

    def test_sql_is_complete_and_unchanged_upload_creates_no_extra_commit(self):
        first=self.sync.upload();self.assertTrue(first['ok']);head=self.head()
        restored=self.folder/'from_sql.db';c=sqlite3.connect(restored);c.executescript(self.sync.sql.read_text());c.close()
        with readonly(restored) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION);self.assertEqual(c.execute('SELECT title FROM songs').fetchone()[0],'Fixture song')
        again=self.sync.upload();self.assertTrue(again['ok']);self.assertEqual(again['code'],'unchanged');self.assertEqual(self.head(),head)

    def test_failed_push_keeps_commit_and_retry_does_not_duplicate_it(self):
        hook=self.remote/'hooks'/'pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        before=self.state();old=self.head();failed=self.sync.upload();self.assertFalse(failed['ok']);self.assertEqual(failed['code'],'push_failed')
        kept=self.head();self.assertNotEqual(kept,old);self.assertEqual(command(self.remote,'rev-parse','main'),old)
        hook.unlink();done=self.sync.upload();self.assertTrue(done['ok']);self.assertEqual(self.head(),kept);self.assertEqual(self.state(),before)

    def test_sql_round_trip_preserves_sparse_hidden_rowids_and_composite_keys(self):
        c=sqlite3.connect(self.db)
        c.executescript('CREATE TABLE ordered_items(a INTEGER,b INTEGER,PRIMARY KEY(a,b)); INSERT INTO ordered_items(rowid,a,b) VALUES(91,4,2),(12,1,8); CREATE TABLE no_rowid(a TEXT PRIMARY KEY) WITHOUT ROWID; INSERT INTO no_rowid VALUES(\'keep\');')
        c.close();before=self.state();self.assertTrue(self.sync.upload()['ok'])
        restored=sqlite3.connect(':memory:')
        try:restored.executescript(self.sync.sql.read_text());self.assertEqual(capture(restored),before)
        finally:restored.close()

    def test_sql_round_trip_preserves_float_precision_nul_text_blobs_and_quoted_names(self):
        c=sqlite3.connect(self.db);c.execute('CREATE TABLE "extra notes"(n REAL, text_value TEXT, binary_value BLOB)')
        c.execute('INSERT INTO "extra notes" VALUES(?,?,?)',(1200.1234567890124,"O'Brien\0雪\nnext",b'\0\xff'));c.commit();c.close()
        before=self.state();self.assertTrue(self.sync.upload()['ok']);restored=sqlite3.connect(':memory:')
        try:restored.executescript(self.sync.sql.read_text());self.assertEqual(capture(restored),before)
        finally:restored.close()

    def test_sql_round_trip_preserves_deleted_id_high_water_and_does_not_replay_triggers(self):
        c=sqlite3.connect(self.db)
        c.executescript('CREATE TABLE extra_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT,value TEXT); CREATE TABLE extra_audit(value TEXT); CREATE TRIGGER extra_changes AFTER INSERT ON extra_sequence BEGIN INSERT INTO extra_audit VALUES(NEW.value); END; INSERT INTO extra_sequence(id,value) VALUES(80,\'gone\'); DELETE FROM extra_sequence; INSERT INTO extra_sequence(id,value) VALUES(2,\'retained\'); PRAGMA application_id=123456;')
        c.close();before=self.state();self.assertTrue(self.sync.upload()['ok']);restored=sqlite3.connect(':memory:')
        try:
            restored.executescript(self.sync.sql.read_text());self.assertEqual(capture(restored),before)
            restored.execute("INSERT INTO extra_sequence(value) VALUES('next')");self.assertEqual(restored.execute('SELECT MAX(id) FROM extra_sequence').fetchone()[0],81)
        finally:restored.close()

    def test_lost_push_reply_reconciles_remote_without_another_commit(self):
        original=self.sync.run
        def lost(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[0]=='push':raise SyncError('timeout','Lost reply')
            return result
        with patch.object(self.sync,'run',side_effect=lost):failed=self.sync.upload()
        self.assertFalse(failed['ok']);head=self.head();self.assertEqual(command(self.remote,'rev-parse','main'),head)
        again=self.sync.upload();self.assertEqual(again['code'],'unchanged');self.assertEqual(self.head(),head)

    def test_commit_hook_failure_keeps_snapshot_without_pushing(self):
        hook=self.work/'.git/hooks/pre-commit';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        old=self.head();failed=self.sync.upload();self.assertEqual(failed['code'],'commit_failed');self.assertEqual(self.head(),old)
        self.assertIn('CREATE TABLE',self.sync.sql.read_text());hook.unlink();self.assertTrue(self.sync.upload()['ok'])

    def test_unpublished_code_commits_are_not_published_by_backup_button(self):
        (self.work/'app.py').write_text('local code\n');command(self.work,'add','app.py');command(self.work,'commit','-m','Local code')
        remote=command(self.remote,'rev-parse','main');sql=self.sync.sql.read_bytes();failed=self.sync.upload()
        self.assertEqual(failed['code'],'pending_code');self.assertEqual(command(self.remote,'rev-parse','main'),remote);self.assertEqual(self.sync.sql.read_bytes(),sql)

    def test_behind_and_diverged_histories_do_not_merge_or_force_push(self):
        self.remote_change({'app.py':'remote code\n'});before=self.state();old=self.head()
        self.assertEqual(self.sync.upload()['code'],'behind');self.assertEqual(self.head(),old)
        (self.work/'other.py').write_text('local\n');command(self.work,'add','other.py');command(self.work,'commit','-m','Local branch')
        self.assertEqual(self.sync.upload()['code'],'diverged');self.assertEqual(self.sync.startup()['code'],'diverged');self.assertEqual(self.state(),before)

    def test_changed_target_fingerprint_prevents_upload(self):
        expected=self.sync.status()['fingerprint'];command(self.work,'switch','-c','different')
        self.assertEqual(self.sync.upload(expected)['code'],'stale_target')

    def test_detached_or_unconfigured_repository_reports_actionable_status(self):
        command(self.work,'checkout','--detach');self.assertEqual(self.sync.status()['state'],'detached')
        command(self.work,'switch','main');command(self.work,'remote','remove','origin');self.assertEqual(self.sync.status()['state'],'no_remote')
        root=self.folder/'unconfigured';root.mkdir();self.assertEqual(GitSync(root,self.db).status()['state'],'not_repo')

    def test_remote_credentials_and_error_output_are_not_exposed(self):
        url='https://user:super-secret@github.com/owner/repo.git?access_token=hidden#fragment'
        command(self.work,'remote','set-url','origin',url);text=json.dumps(self.sync.status())
        self.assertNotIn('super-secret',text);self.assertNotIn('hidden',text);self.assertNotIn('user:',text)
        self.assertEqual(display_remote(url),'github.com/owner/repo.git')
        error=subprocess.CompletedProcess([],1,'','authentication failed '+url)
        with patch('songranker.developer.git_sync.subprocess.run',return_value=error):
            with self.assertRaises(SyncError) as caught:self.sync.run('fetch',network=True)
        self.assertNotIn('secret',str(caught.exception));self.assertEqual(caught.exception.code,'authentication_failed')

    def test_multiple_or_different_push_targets_are_refused(self):
        command(self.work,'remote','set-url','--push','origin',str(self.folder/'different.git'))
        self.assertEqual(self.sync.status()['state'],'different_targets')
        command(self.work,'remote','set-url','--add','--push','origin',str(self.remote));self.assertEqual(self.sync.status()['state'],'multiple_targets')

    def test_timeout_and_missing_git_have_structured_outcomes(self):
        with patch('songranker.developer.git_sync.subprocess.run',side_effect=subprocess.TimeoutExpired(['git'],25)):
            result=self.sync.check();self.assertFalse(result['ok']);self.assertEqual(result['code'],'timeout')
        with patch('songranker.developer.git_sync.subprocess.run',side_effect=FileNotFoundError()):self.assertEqual(self.sync.status()['state'],'git_missing')

    def test_app_git_lock_serializes_tasks_and_busy_startup_does_not_boot(self):
        self.sync.discover()
        with self.sync.lock():
            other=GitSync(self.work,self.db)
            self.assertEqual(other.upload()['code'],'busy');result=other.startup();self.assertEqual(result['code'],'busy');self.assertTrue(result['stop_startup'])
        self.assertTrue(self.sync.check()['ok'])

    def test_startup_fast_forward_keeps_live_database_and_archives_local_sql(self):
        self.sync.sql.write_text('-- local uncommitted dump\n');before=self.state()
        self.remote_change({'app.py':"VERSION='new'\n",'database_backup.sql':'-- incoming dump\n'})
        result=self.sync.startup();self.assertTrue(result['ok'],result);self.assertEqual(result['code'],'updated')
        self.assertEqual((self.work/'app.py').read_text(),"VERSION='new'\n");self.assertEqual(self.sync.sql.read_text(),'-- incoming dump\n')
        self.assertEqual(self.state(),before);self.assertTrue((self.work/'database_backups'/result['backup']).is_file())
        self.assertTrue(any('-- local uncommitted dump' in p.read_text() for p in self.sync.state_dir.glob('before_update_*.sql')))

    def test_startup_refuses_local_code_edits_and_staged_changes(self):
        self.remote_change({'app.py':'remote\n'});(self.work/'app.py').write_text('local\n');old=self.head()
        self.assertEqual(self.sync.startup()['code'],'local_changes');self.assertEqual(self.head(),old)
        command(self.work,'add','app.py');self.assertEqual(self.sync.startup()['code'],'staged_changes')

    def test_incoming_database_and_private_files_are_never_installed(self):
        before=self.state();self.remote_change({'live.db':'unrelated bytes','instance/session_secret':'private incoming'})
        result=self.sync.startup();self.assertEqual(result['code'],'protected_changes');self.assertEqual(self.state(),before)
        self.assertFalse((self.work/'instance/session_secret').exists())

    def test_merge_state_blocks_checkouts_and_uploads(self):
        (self.work/'.git/MERGE_HEAD').write_text(self.head()+'\n')
        self.assertEqual(self.sync.upload()['code'],'operation_in_progress');self.assertEqual(self.sync.startup()['code'],'operation_in_progress')

    def test_failed_fast_forward_restores_previous_sql_and_stops_startup(self):
        self.sync.sql.write_text('-- my local snapshot\n');self.remote_change({'app.py':'new\n','database_backup.sql':'-- remote\n'})
        original=self.sync.run
        def fail(*args,**kwargs):
            if args[0]=='merge':raise SyncError('git_failed','Injected failure')
            return original(*args,**kwargs)
        with patch.object(self.sync,'run',side_effect=fail):result=self.sync.startup()
        self.assertFalse(result['ok']);self.assertTrue(result['stop_startup']);self.assertEqual(self.sync.sql.read_text(),'-- my local snapshot\n')

    def test_backup_failure_prevents_source_update(self):
        self.remote_change({'app.py':'new\n'});old=self.head()
        with patch('songranker.storage.database_io.create_backup',side_effect=OSError('injected backup failure')):result=self.sync.startup()
        self.assertFalse(result['ok']);self.assertEqual(self.head(),old);self.assertIn('old',(self.work/'app.py').read_text())

    def test_unchanged_startup_and_missing_database_upload_are_explicit(self):
        before=self.state();result=self.sync.startup();self.assertEqual(result['code'],'unchanged');self.assertEqual(self.state(),before)
        self.db.unlink();self.assertEqual(self.sync.upload()['code'],'database_missing');self.assertFalse(self.db.exists())

    def test_new_snapshot_never_follows_a_symlink(self):
        self.sync.sql.unlink();self.sync.sql.symlink_to(self.db);before=self.state()
        self.assertEqual(self.sync.upload()['code'],'linked_snapshot');self.assertEqual(self.state(),before)

    def test_sql_snapshot_includes_committed_wal_data(self):
        c=sqlite3.connect(self.db);c.execute('PRAGMA journal_mode=WAL');c.execute("UPDATE songs SET title='Committed WAL title'");c.commit()
        try:self.assertTrue(self.sync.upload()['ok']);self.assertIn('Committed WAL title',self.sync.sql.read_text())
        finally:c.close()

    def test_new_code_clears_only_its_python_cache(self):
        py_compile.compile(str(self.work/'app.py'));cache=list((self.work/'__pycache__').glob('app.*.pyc'))[0]
        other=cache.parent/'other.cpython-312.pyc';other.write_bytes(b'keep')
        self.remote_change({'app.py':"VERSION='new'\n"});self.assertEqual(self.sync.startup()['code'],'updated')
        self.assertFalse(cache.exists());self.assertTrue(other.exists())

    def test_cli_update_reexecutes_before_importing_new_application_modules(self):
        command(self.seed,'pull','--ff-only')
        shutil.copy2(ROOT/'main.py',self.seed/'main.py')
        pkg=self.seed/'songranker';pkg.mkdir(exist_ok=True)
        (pkg/'__init__.py').write_text('')
        (pkg/'developer').mkdir(exist_ok=True);(pkg/'developer/__init__.py').write_text('')
        (pkg/'storage').mkdir(exist_ok=True);(pkg/'storage/__init__.py').write_text('')
        shutil.copy2(ROOT/'songranker/developer/git_sync.py',pkg/'developer/git_sync.py')
        (pkg/'storage/competition.py').write_text("from pathlib import Path\ndef configured_paths(root):return Path(root)/'unused.db',Path(root)/'old.db'\n")
        (pkg/'services.py').write_text("from types import SimpleNamespace\nfrom app import VERSION\nprint('loaded '+VERSION)\napp=SimpleNamespace(config={'MAX_CONTENT_LENGTH':4194304},extensions={'song_ranker_stop':None})\ndef init_db():print('bootstrap '+VERSION)\n")
        (self.seed/'waitress.py').write_text("from types import SimpleNamespace\ndef create_server(*a,**k):return SimpleNamespace(run=lambda:print('served fixture'))\n")
        (pkg/'hosting.py').write_text("def register_waitress_shutdown(*a):pass\n")
        (pkg/'developer/dev_shutdown.py').write_text('')
        paths={'database': 'songranker.storage.database', 'database_schema': 'songranker.storage.database_schema', 'database_io': 'songranker.storage.database_io', 'database_access': 'songranker.storage.database_access', 'competition': 'songranker.storage.competition', 'schema_compat': 'songranker.storage.schema_compat', 'preference_state': 'songranker.storage.preference_state', 'catalog_source_state': 'songranker.storage.catalog_source_state', 'challenge_state': 'songranker.storage.challenge_state', 'global_stats_data': 'songranker.reports.global_stats_data', 'voting_stats_data': 'songranker.reports.voting_stats_data', 'recognition_stats_data': 'songranker.reports.recognition_stats_data', 'tournament_stats_data': 'songranker.reports.tournament_stats_data', 'guesser_stats_data': 'songranker.reports.guesser_stats_data', 'shelves_stats_data': 'songranker.reports.shelves_stats_data', 'stats_activity': 'songranker.reports.stats_activity', 'data_health': 'songranker.reports.data_health', 'selection_health': 'songranker.reports.selection_health', 'games': 'songranker.modes.games', 'trivia': 'songranker.modes.trivia', 'special_modes': 'songranker.modes.special_modes', 'vibe_map': 'songranker.modes.vibe_map', 'preferences': 'songranker.modes.preferences', 'challenges': 'songranker.modes.challenges', 'challenge_rules': 'songranker.modes.challenge_rules', 'mode_ratings': 'songranker.modes.mode_ratings', 'selection': 'songranker.modes.selection', 'selection_data': 'songranker.modes.selection_data', 'dev': 'songranker.developer.dev', 'dev_catalog': 'songranker.developer.dev_catalog', 'dev_tags': 'songranker.developer.dev_tags', 'dev_system': 'songranker.developer.dev_system', 'metadata_tools': 'songranker.developer.metadata_tools', 'metadata_fill': 'songranker.developer.metadata_fill', 'catalog_sources': 'songranker.developer.catalog_sources', 'catalog_operations': 'songranker.developer.catalog_operations', 'tag_operations': 'songranker.developer.tag_operations', 'git_sync': 'songranker.developer.git_sync', 'db_tools': 'songranker.developer.db_tools', 'track_numbers': 'songranker.developer.track_numbers'}
        for name in ('apple_access','pages','trivia','special_modes','vibe_map','overall','games','metadata_tools','dev','dev_catalog','dev_tags','dev_system'):
            dest=self.seed/(paths.get(name,'songranker.'+name).replace('.','/')+'.py');dest.parent.mkdir(exist_ok=True);(dest.parent/'__init__.py').touch();dest.write_text('')
        command(self.seed,'add','.');command(self.seed,'commit','-m','CLI fixture');command(self.seed,'push')
        command(self.work,'pull','--ff-only');py_compile.compile(str(self.work/'app.py'))
        self.remote_change({'app.py':"VERSION='new'\n"})
        env=os.environ.copy();env.update(SONG_RANKER_DB=str(self.folder/'not_created.db'),SONG_RANKER_BOOT_COMMIT='')
        result=subprocess.run([sys.executable,'main.py'],cwd=self.work,env=env,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('loaded new',result.stdout);self.assertIn('bootstrap new',result.stdout)
        self.assertNotIn('loaded old',result.stdout);self.assertIn('served fixture',result.stdout)


if __name__=='__main__':unittest.main()

