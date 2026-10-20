"""Process-wide launch isolation, configured before Git, Flask or migrations.

Safe mode snapshots the source through SQLite's read-only backup API. Every app
write then targets one persistent test database per source. A shared advisory launcher lock keeps
another V5.1 launcher from opening the same main database at the same time. It
does not change the source's permissions or claim to lock unrelated programs.
"""
import argparse
import atexit
import json
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time

_runtime = None
_runtime_lock = threading.RLock()
FORMAT = 'song-ranker-safe-mode/1'


class SafeModeError(ValueError):
    pass


def enabled():
    value = os.environ.get('SONG_RANKER_SAFE_MODE', '0').strip().lower()
    if value not in ('0','1','false','true','no','yes','off','on'):
        raise SafeModeError('SONG_RANKER_SAFE_MODE must be 1 or 0.')
    return value in ('1','true','yes','on')


def launch_arguments(argv=None):
    parser = argparse.ArgumentParser(description='Song Ranker. Use --safe-mode to test on an isolated copy.')
    parser.add_argument('--safe-mode',action='store_true',help='Protect the main database and resume the isolated test database; Git is disabled.')
    parser.add_argument('--refresh-safe-mode',action='store_true',help='Replace the same test database with a fresh main snapshot; previous test results are cleared.')
    args = parser.parse_args(argv)
    if args.safe_mode or args.refresh_safe_mode:os.environ['SONG_RANKER_SAFE_MODE']='1'
    if args.refresh_safe_mode:os.environ['SONG_RANKER_REFRESH_SAFE_MODE']='1'
    return args


class Runtime:
    def __init__(self, root, *, safe=None, refresh=False):
        from songranker.storage.competition import configured_paths
        self.root = Path(root).resolve()
        self.main_db, self.legacy_db = (p.resolve() for p in configured_paths(self.root))
        self.safe = enabled() if safe is None else safe
        self.refresh = refresh or os.environ.get('SONG_RANKER_REFRESH_SAFE_MODE') == '1'
        self.reused = False
        self.active_db = self.main_db
        self.run_dir = None
        self.session_root = self.root
        self.prepared = False
        self.lock_file = None
        self._mutex = threading.RLock()

    def acquire(self):
        if self.lock_file is not None:return
        self.main_db.parent.mkdir(parents=True,exist_ok=True)
        path = self.main_db.with_name(self.main_db.name+'.app.lock')
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise SafeModeError('The app lock must be a regular local file.')
        stream = path.open('a+b')
        if path.stat().st_size==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            stream.close()
            raise SafeModeError('Another Song Ranker launcher is using this main database. Stop it before choosing live or safe mode.') from error
        self.lock_file = stream
        atexit.register(self.release)

    def release(self):
        with self._mutex:
            if self.lock_file is not None:
                self.lock_file.close();self.lock_file=None

    def _marked_runs(self, base):
        runs = []
        for path in base.glob('run_*'):
            if path.is_symlink() or not path.is_dir():continue
            try:
                marker = path/'safe_run.json'
                if marker.is_symlink():continue
                manifest = json.loads(marker.read_text(encoding='utf-8'))
                if (manifest.get('format') == FORMAT and manifest.get('source') == str(self.main_db)
                        and manifest.get('active_database') == 'song_ranker_v3.db'):
                    runs.append((float(manifest['created_at']), path))
            except (OSError, ValueError, KeyError, TypeError):continue
        return sorted(runs, reverse=True)

    def _snapshot(self):
        # Build separately: a failed refresh must preserve the existing test DB.
        handle, name = tempfile.mkstemp(prefix='.refresh_', suffix='.db', dir=self.run_dir)
        os.close(handle)
        candidate = Path(name)
        try:
            destination = sqlite3.connect(candidate)
            try:
                if self.main_db.exists():
                    if not self.main_db.is_file():raise SafeModeError('Main database is not a regular file.')
                    # mode=ro includes committed WAL without migrating the source.
                    source = sqlite3.connect(self.main_db.as_uri()+'?mode=ro', uri=True, timeout=30)
                    try:source.backup(destination)
                    finally:source.close()
                if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise SafeModeError('Main database could not be copied safely.')
            finally:destination.close()
            for suffix in ('-wal', '-shm', '-journal'):
                self.active_db.with_name(self.active_db.name+suffix).unlink(missing_ok=True)
            if self.main_db.exists():os.replace(candidate, self.active_db)
            else:self.active_db.unlink(missing_ok=True)  # Normal empty-catalogue bootstrap.
        finally:candidate.unlink(missing_ok=True)

    def prepare(self):
        with self._mutex:
            if self.prepared:return self
            self.acquire()
            created = False
            try:
                if self.safe:
                    base = Path(os.environ.get('SONG_RANKER_SAFE_DIR', self.root/'data'/'safe_mode')).resolve()
                    if base == self.main_db or (base.exists() and not base.is_dir()):
                        raise SafeModeError('Choose a directory for the safe database.')
                    base.mkdir(parents=True, exist_ok=True)
                    runs = self._marked_runs(base)
                    self.run_dir = base/('run_'+hashlib.sha256(str(self.main_db).encode()).hexdigest()[:24])
                    if self.run_dir.is_symlink():raise SafeModeError('The safe directory cannot be a symbolic link.')
                    if self.run_dir.exists():
                        if self.run_dir not in [path for _,path in runs]:
                            raise SafeModeError('The safe directory is unmarked or belongs to another source; it was left unchanged.')
                    elif runs:
                        # Adopt the latest old V5.1 test run without copying it.
                        runs[0][1].rename(self.run_dir)
                    else:
                        self.run_dir.mkdir();created = True
                    self.active_db = self.run_dir/'song_ranker_v3.db'
                    self.session_root = self.run_dir
                    self.assert_writable(self.active_db)
                    if self.active_db.exists() and not self.active_db.is_file():
                        raise SafeModeError('Safe database must be a regular file.')
                    self.reused = self.active_db.exists() and not self.refresh
                    if self.reused:
                        check = sqlite3.connect(self.active_db.as_uri()+'?mode=ro', uri=True)
                        try:
                            if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                                raise SafeModeError('Safe database needs recovery or an explicit refresh.')
                        finally:check.close()
                    else:self._snapshot()
                    manifest = dict(format=FORMAT, source=str(self.main_db), created_at=time.time(),
                                    active_database=self.active_db.name, persistent=True)
                    (self.run_dir/'safe_run.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
                    # Prune only marked disposable runs for this exact source.
                    for _,path in runs:
                        if path != self.run_dir and path.exists():
                            try:shutil.rmtree(path)
                            except OSError:pass
                self.prepared = True
                return self
            except BaseException:
                if created and self.run_dir is not None:
                    try:shutil.rmtree(self.run_dir)
                    except OSError:pass
                self.run_dir = None;self.active_db = self.main_db;self.session_root = self.root
                self.release()
                raise

    def assert_writable(self, filename):
        if not self.safe:return
        path=Path(filename).resolve()
        same=path==self.main_db
        if path.exists() and self.main_db.exists():
            same = same or path.samefile(self.main_db)
        if same:raise SafeModeError('Safe mode protects the main database. Use the active test copy.')
        if self.run_dir is None or not path.is_relative_to(self.run_dir):
            raise SafeModeError('Safe mode writes are restricted to the current test run.')

    def status(self, *, paths=False):
        result=dict(safe_mode=self.safe,mode='safe' if self.safe else 'live',
                    main_database_protected=self.safe,git_enabled=not self.safe,
                    active_database=self.active_db.name,
                    test_run=self.run_dir.name if self.run_dir else None,
                    safe_run_retention=1 if self.safe else None,
                    safe_database_reused=self.reused, safe_database_persistent=self.safe)
        if paths:result.update(main_path=str(self.main_db),active_path=str(self.active_db))
        return result


def runtime_for(root=None):
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            if root is None:
                from songranker.paths import ROOT
                root=ROOT
            _runtime=Runtime(root)
        return _runtime


def assert_writable(filename):
    # Offline tools honour the environment too, before Flask is ever imported.
    if _runtime is not None:
        _runtime.assert_writable(filename)
    elif enabled():
        runtime_for().assert_writable(filename)


def assert_git_allowed():
    if (_runtime is not None and _runtime.safe) or enabled():
        raise SafeModeError('Git tasks are disabled in safe mode so test results cannot replace the main snapshot.')
