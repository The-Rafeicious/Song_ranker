"""Real file copies, WAL, process locks and full app boot; all sources disposable."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from songranker.storage import safe_mode
from songranker.storage.safe_mode import Runtime, SafeModeError
from songranker.storage.database import initialize_database,migrate
from songranker.storage.database_io import readonly,create_backup,publish,prepare_candidate,audit
from songranker.storage.source_storage import compact_database
from songranker.developer.git_sync import GitSync
from songranker import services
from test_mode_updates_v51 import fixture

ROOT=Path(__file__).resolve().parents[1]


def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class SafeModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.main=self.root/'live.db';fixture(self.main,schema15=True)
        self.environ=patch.dict(os.environ,{'SONG_RANKER_DB':str(self.main),'SONG_RANKER_SAFE_DIR':str(self.root/'safe'),'SONG_RANKER_SAFE_MODE':'0','SONG_RANKER_REFRESH_SAFE_MODE':'0'})
        self.environ.start();self.addCleanup(self.environ.stop)

    def runtime(self):
        runtime=Runtime(ROOT,safe=True).prepare();self.addCleanup(runtime.release);return runtime

    def child(self,code,**extra):
        env=dict(os.environ,**extra)
        return subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True,timeout=40)

    def test_safe_copy_upgrades_and_writes_while_source_bytes_and_schema_stay_exact(self):
        before=fingerprint(self.main);runtime=self.runtime()
        with patch.object(safe_mode,'_runtime',runtime):
            initialize_database(runtime.active_db)
            c=sqlite3.connect(runtime.active_db);c.execute("UPDATE songs SET title='Synthetic edit' WHERE id=1");c.commit();c.close()
            self.assertTrue(create_backup(runtime.active_db).is_relative_to(runtime.run_dir))
        self.assertEqual(fingerprint(self.main),before)
        with readonly(self.main) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],15)
        with readonly(runtime.active_db) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],17)
        self.assertEqual(runtime.session_root,runtime.run_dir)

    def test_safe_managed_helpers_refuse_main_and_hardlink_aliases(self):
        runtime=self.runtime();alias=self.root/'alias.db';os.link(self.main,alias);before=fingerprint(self.main)
        with patch.object(safe_mode,'_runtime',runtime):
            for path in (self.main,alias):
                for action in (migrate,initialize_database,compact_database,create_backup):
                    with self.subTest(action=action.__name__,path=path),self.assertRaises(SafeModeError):action(path)
            with self.assertRaises(SafeModeError):prepare_candidate(runtime.active_db,self.main)
            with self.assertRaises(SafeModeError):publish(runtime.active_db,self.root/'unapproved-output.db')
            self.assertEqual(audit(self.main)['schema_version'],15)  # Reads remain available.
        self.assertEqual(fingerprint(self.main),before)

    def test_all_app_connections_target_copy_and_cannot_attach_source(self):
        runtime=self.runtime();before=fingerprint(self.main)
        with patch.object(safe_mode,'_runtime',runtime),patch.object(services,'runtime',runtime):
            initialize_database(runtime.active_db)
            with patch.object(services,'DB_NAME',str(self.main)),self.assertRaises(SafeModeError):services.get_db_connection()
            with patch.object(services,'DB_NAME',str(runtime.active_db)):
                c=services.get_db_connection()
                with self.assertRaises(sqlite3.DatabaseError):c.execute('ATTACH DATABASE ? AS main_source',(str(self.main),))
                c.execute("UPDATE songs SET title='Test only' WHERE id=1");c.commit();c.close()
        self.assertEqual(fingerprint(self.main),before)

    def test_readonly_snapshot_includes_committed_wal_without_changing_it(self):
        c=sqlite3.connect(self.main);c.execute('PRAGMA journal_mode=WAL');c.execute("UPDATE artists SET name='Committed WAL artist' WHERE id=1");c.commit()
        self.addCleanup(c.close)
        wal=Path(str(self.main)+'-wal');before=(self.main.read_bytes(),wal.read_bytes())
        runtime=self.runtime()
        with readonly(runtime.active_db) as copied:self.assertEqual(copied.execute('SELECT name FROM artists WHERE id=1').fetchone()[0],'Committed WAL artist')
        self.assertEqual((self.main.read_bytes(),wal.read_bytes()),before)

    def test_live_launcher_cannot_enter_while_safe_launcher_holds_main_lock(self):
        runtime=self.runtime();before=fingerprint(self.main)
        code="from songranker.storage.safe_mode import Runtime,SafeModeError\nfrom songranker.paths import ROOT\ntry:Runtime(ROOT,safe=False).prepare()\nexcept SafeModeError:print('locked');raise SystemExit(2)\n"
        result=self.child(code);self.assertEqual(result.returncode,2,result.stderr);self.assertIn('locked',result.stdout)
        runtime.release();result=self.child(code);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(fingerprint(self.main),before)

    def test_git_reads_and_tasks_are_explicitly_disabled_without_invoking_git(self):
        runtime=self.runtime();git=GitSync(ROOT,runtime.active_db)
        with patch.object(safe_mode,'_runtime',runtime),patch.object(git,'run') as run:
            for task in (git.status,git.check,git.startup,git.upload):self.assertEqual(task()['code'],'safe_mode')
            with self.assertRaises(SafeModeError):git.write_snapshot()
            run.assert_not_called()

    def test_restarts_reuse_one_database_and_keep_test_progress(self):
        before=fingerprint(self.main)
        runtime=self.runtime();path=runtime.active_db
        with sqlite3.connect(path) as c:c.execute("UPDATE songs SET title='Persistent safe edit' WHERE id=1")
        runtime.release()
        for _ in range(4):
            runtime=self.runtime()
            self.assertEqual(runtime.active_db,path);self.assertTrue(runtime.status()['safe_database_reused'])
            with readonly(path) as c:self.assertEqual(c.execute('SELECT title FROM songs WHERE id=1').fetchone()[0],'Persistent safe edit')
            runtime.release()
        self.assertEqual(len(list((self.root/'safe').glob('run_*'))),1)
        self.assertEqual(fingerprint(self.main),before)

    def test_explicit_refresh_replaces_same_copy_with_latest_main(self):
        runtime=self.runtime();path=runtime.active_db
        with sqlite3.connect(path) as c:c.execute("UPDATE songs SET title='Test edit' WHERE id=1")
        runtime.release()
        with sqlite3.connect(self.main) as c:c.execute("UPDATE songs SET title='New real song' WHERE id=1")
        before=fingerprint(self.main)
        runtime=Runtime(ROOT,safe=True,refresh=True).prepare();self.addCleanup(runtime.release)
        self.assertEqual(runtime.active_db,path);self.assertFalse(runtime.reused)
        with readonly(path) as c:self.assertEqual(c.execute('SELECT title FROM songs WHERE id=1').fetchone()[0],'New real song')
        self.assertEqual(fingerprint(self.main),before)
        self.assertFalse(list(path.parent.glob('.refresh_*')))

    def test_adopts_latest_legacy_run_and_only_prunes_marked_same_source(self):
        base=self.root/'safe';base.mkdir()
        paths=[]
        for n in range(3):
            folder=base/f'run_old{n}';folder.mkdir();paths.append(folder)
            folder.joinpath('song_ranker_v3.db').write_bytes(self.main.read_bytes())
            folder.joinpath('safe_run.json').write_text(json.dumps(dict(format=safe_mode.FORMAT,source=str(self.main),created_at=n,active_database='song_ranker_v3.db')))
        unrelated=base/'run_unrelated';unrelated.mkdir();(unrelated/'keep.txt').write_text('keep')
        with sqlite3.connect(paths[-1]/'song_ranker_v3.db') as c:c.execute("UPDATE songs SET title='Latest test progress' WHERE id=1")
        runtime=self.runtime()
        with readonly(runtime.active_db) as c:self.assertEqual(c.execute('SELECT title FROM songs WHERE id=1').fetchone()[0],'Latest test progress')
        self.assertTrue(runtime.reused);self.assertTrue(unrelated.exists())
        self.assertTrue(all(not p.exists() for p in paths))

    def test_failed_refresh_preserves_test_copy_and_releases_lock(self):
        runtime=self.runtime();path=runtime.active_db;before=path.read_bytes();runtime.release()
        self.main.write_bytes(b'corrupt source')
        runtime=Runtime(ROOT,safe=True,refresh=True)
        with self.assertRaises(sqlite3.DatabaseError):runtime.prepare()
        self.assertEqual(path.read_bytes(),before);self.assertIsNone(runtime.lock_file)
        self.assertFalse(list(path.parent.glob('.refresh_*')))
        resumed=self.runtime();self.assertEqual(resumed.active_db,path)

    def test_unmarked_persistent_directory_is_preserved_and_rejected(self):
        runtime=self.runtime();folder=runtime.run_dir;runtime.release()
        (folder/'safe_run.json').unlink();before=(folder/'song_ranker_v3.db').read_bytes()
        with self.assertRaises(SafeModeError):Runtime(ROOT,safe=True).prepare()
        self.assertEqual((folder/'song_ranker_v3.db').read_bytes(),before)

    def test_missing_main_is_not_created_when_bootstrapping_empty_safe_run(self):
        self.main.unlink();runtime=self.runtime()
        with patch.object(safe_mode,'_runtime',runtime):initialize_database(runtime.active_db)
        self.assertFalse(self.main.exists());self.assertTrue(runtime.active_db.exists())

    def test_corrupt_source_fails_closed_without_changing_source(self):
        self.main.write_bytes(b'not a sqlite database');before=self.main.read_bytes()
        runtime=Runtime(ROOT,safe=True)
        with self.assertRaises(sqlite3.DatabaseError):runtime.prepare()
        self.assertIsNone(runtime.lock_file);self.assertEqual(self.main.read_bytes(),before)

    def test_environment_and_cli_flag_cannot_silently_fall_back_to_live_mode(self):
        with patch.dict(os.environ,SONG_RANKER_SAFE_MODE='perhaps'),self.assertRaises(SafeModeError):safe_mode.enabled()
        with patch.dict(os.environ,SONG_RANKER_SAFE_MODE='0'):
            safe_mode.launch_arguments(['--safe-mode']);self.assertTrue(safe_mode.enabled())
        with patch.dict(os.environ,SONG_RANKER_SAFE_MODE='0',SONG_RANKER_REFRESH_SAFE_MODE='0'):
            safe_mode.launch_arguments(['--refresh-safe-mode']);self.assertTrue(safe_mode.enabled())
            self.assertEqual(os.environ['SONG_RANKER_REFRESH_SAFE_MODE'],'1')

    def test_full_safe_backend_smoke_keeps_source_exact_and_shows_banner(self):
        before=fingerprint(self.main)
        code="""import main,json
from songranker import services
from tools.test_v51_backend import run
from songranker.storage.database_io import capture,readonly
with readonly(services.runtime.active_db) as db:safe_before=capture(db)
report=run()
with readonly(services.runtime.active_db) as db:assert capture(db)==safe_before
assert all(r['status']=='passed' for r in report['modes'])
c=main.app.test_client()
assert b'SAFE MODE' in c.get('/').data
assert c.get('/api/runtime-mode').json['main_database_protected']
assert c.get('/api/runtime-mode').headers['X-Song-Ranker-Mode']=='safe'
with c.session_transaction() as s:s['is_admin']=True
assert c.post('/api/dev/git/upload',json={}).status_code==409
print(json.dumps(report['runtime']))
"""
        result=self.child(code,SONG_RANKER_SAFE_MODE='1');self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(fingerprint(self.main),before)
        with readonly(self.main) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],15)


if __name__=='__main__':unittest.main()
