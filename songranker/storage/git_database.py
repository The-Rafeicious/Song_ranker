"""Whole-snapshot database sync. No row merge and no network or Flask imports."""

from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
import tempfile
from songranker.storage.database import initialize_database
from songranker.storage.database_io import DatabaseValidationError, capture, create_backup, digest, publish, quote, readonly, replace_contents, snapshot, validate


HISTORY_LIMIT = 32
MAX_SQL_BYTES = 64 * 1024 * 1024


def model(conn):
    """Compare stored facts by primary key; only install metadata is device-local.

    Hidden rowids matter for tables without explicit keys. Junction rowids do not
    turn a re-saved link into a different song/tag relationship.
    """
    state = capture(conn)
    facts = {}
    for name, data in state['tables'].items():
        if name in ('@schema', '@sequences', '@application'):
            raise DatabaseValidationError('An extension uses a reserved sync comparison name; compare backups manually.')
        keys = sorted((r[5], r[1]) for r in conn.execute('PRAGMA table_info('+quote(name)+')') if r[5])
        columns = data['columns']
        values = {}
        rowids = data.get('rowids')
        for i, row in enumerate(data['rows']):
            record = dict(zip(columns, row))
            key = [record[column] for _, column in keys] if keys else [rowids[i] if rowids is not None else i]
            if name == 'competition_state':
                record.pop('started_at', None)
                record.pop('migration_report', None)
            identity = json.dumps(key, sort_keys=True)
            if identity in values:
                raise DatabaseValidationError('A table has ambiguous nullable primary keys; automatic database sync was skipped.')
            values[identity] = digest(record)
        facts[name] = values
    facts['@schema'] = {obj['type']+':'+obj['name']: digest(obj['sql']) for obj in state['objects']}
    facts['@sequences'] = state['sequences']
    facts['@application'] = {'id': state['application_id']}
    return facts


def delta(base, changed):
    """Count added, removed and edited rows for each table between two indexed
    snapshots.
    """
    result = {}
    for table in base.keys() | changed.keys():
        before, after = base.get(table, {}), changed.get(table, {})
        added = len(after.keys() - before.keys())
        removed = len(before.keys() - after.keys())
        edited = sum(before[k] != after[k] for k in before.keys() & after.keys())
        if added or removed or edited:
            result[table] = dict(added=added, removed=removed, edited=edited)
    return result


def covers(base, changed, other):
    """Every local change, including removal, must already be present remotely."""
    for table in base.keys() | changed.keys():
        before, after, target = base.get(table, {}), changed.get(table, {}), other.get(table, {})
        for key in before.keys() | after.keys():
            if before.get(key) == after.get(key):
                continue
            if table == '@sequences' and key in after and target.get(key, -1) >= after[key]:
                continue
            if (key in after) != (key in target) or after.get(key) != target.get(key):
                return False
    return True


def placeholder(sql):
    """Detect an empty or comments-only Git SQL snapshot."""
    return not any(line.strip() and not line.lstrip().startswith('--') for line in sql.splitlines())


def prepare_sql(sql, folder, name, historical=False):
    """Materialise and validate bounded SQL in disposable storage, preserving full
    competition facts.
    """
    if len(sql.encode('utf-8')) > MAX_SQL_BYTES:
        raise DatabaseValidationError('Git SQL snapshot exceeds the supported 64 MiB limit.')
    path = Path(folder) / (name+'.sql')
    path.write_text(sql, encoding='utf-8')
    database = Path(folder) / (name+'.db')
    initialize_database(database, path)
    with readonly(database) as conn:
        validate(conn)
        is_v3 = conn.execute("SELECT 1 FROM competition_state WHERE id=1 AND generation=3").fetchone()
    if not is_v3:
        if not historical:
            raise DatabaseValidationError('Git snapshot is not a V3 competition; it was not installed over local results.')
        # Only an ancestry witness may use the old catalogue-only V5 transfer.
        # The current remote candidate must always retain full V3 game facts.
        from songranker.storage.competition import start_competition
        transferred = Path(folder) / (name+'_v3.db')
        start_competition(transferred, database)
        database = transferred
    with readonly(database) as conn:
        return database, model(conn)


class DatabaseSync:
    def __init__(self, git, state):
        self.git, self.state = git, state
        self.binding = digest(dict(repo=str(git.repo), database=str(git.database),
            branch=state['branch'], remote=state['remote'], target=state['target'],
            destination=digest(git.run('remote','get-url',state['remote']).stdout.strip())))
        self.receipt_path = git.state_dir / ('database_'+self.binding+'.json')

    def blob(self, commit):
        """Resolve the tracked SQL snapshot's blob at a commit, returning no value
        when absent.
        """
        result = self.git.run('rev-parse', '--verify', commit+':'+self.git.sql_rel, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def sql(self, blob):
        """Read the SQL text stored in an already resolved Git blob."""
        return self.git.run('show', blob).stdout

    def remember(self, commit, blob):
        """Atomically persist the accepted Git commit/blob receipt bound to this
        installation.
        """
        self.git.state_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.git.state_dir, mode='w', encoding='utf-8', delete=False) as stream:
            name = stream.name
            json.dump(dict(version=1, commit=commit, blob=blob, binding=self.binding), stream)
            stream.flush(); os.fsync(stream.fileno())
        try: os.replace(name, self.receipt_path)
        finally: Path(name).unlink(missing_ok=True)

    def receipt(self):
        """Read and validate the installation-bound database reconciliation receipt."""
        if not self.receipt_path.exists():
            return None
        value = json.loads(self.receipt_path.read_text(encoding='utf-8'))
        if value.get('version') != 1 or value.get('binding') != self.binding:
            raise DatabaseValidationError('Database sync receipt changed; compare the saved copies before continuing.')
        for key in ('commit', 'blob'):
            if not isinstance(value.get(key), str) or len(value[key]) != 40 or any(c not in '0123456789abcdef' for c in value[key]):
                raise DatabaseValidationError('Database sync receipt is invalid; local data was kept.')
        return value

    @contextmanager
    def review(self):
        """Use the fetched, committed Git snapshot even after a manual pull."""
        remote_commit = self.state.get('tracking_head')
        blob = self.blob(remote_commit) if remote_commit else None
        if not blob:
            yield dict(code='no_remote_snapshot', message='No committed remote database snapshot is available; using local data.')
            return
        sql = self.sql(blob)
        if placeholder(sql):
            yield dict(code='no_remote_snapshot', message='The remote SQL file has no database yet; the first backup can be uploaded.')
            return
        self.git.database.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.git.database.parent, prefix='.git_database_') as folder:
            candidate, remote = prepare_sql(sql, folder, 'remote')
            with snapshot(self.git.database) as conn:
                validate(conn)
                local, live_hash = model(conn), digest(capture(conn))
            common = dict(blob=blob, commit=remote_commit, candidate=candidate, live_hash=live_hash,
                local_songs=len(local.get('songs', {})), remote_songs=len(remote.get('songs', {})))
            if local == remote:
                yield dict(common, code='database_matches', message='Local database matches the committed remote snapshot.')
                return
            receipt = self.receipt()
            if receipt is None:
                # A confirmed device-bound checkpoint can recover a lost receipt.
                # Never reuse another configured database's upload history.
                for event in self.git.history():
                    if not isinstance(event,dict) or event.get('database_binding')!=self.binding:continue
                    commit=event.get('commit')
                    confirmed=event.get('action') in ('upload','keep_local') or (event.get('action')=='database' and event.get('code') in ('database_matches','database_updated'))
                    if event.get('ok') and confirmed and isinstance(commit,str) and len(commit)==40 and all(c in '0123456789abcdef' for c in commit):
                        old_blob=self.blob(commit)
                        if old_blob:
                            receipt=dict(commit=commit,blob=old_blob)
                            break
            base = None
            if receipt:
                if self.git.run('merge-base', '--is-ancestor', receipt['commit'], remote_commit, check=False).returncode:
                    yield dict(common, code='database_conflict', message='Remote snapshot history changed since the last database sync. Both copies were kept.')
                    return
                if self.blob(receipt['commit']) != receipt['blob']:
                    raise DatabaseValidationError('Database sync baseline no longer matches its Git commit.')
                _, base = prepare_sql(self.sql(receipt['blob']), folder, 'baseline')
            else:
                # Upgrade recovery: Git may have been pulled before launching.
                # An exact historical logical snapshot proves the local starting point.
                commits = self.git.run('log', '--format=%H', '-'+str(HISTORY_LIMIT), remote_commit, '--', self.git.sql_rel).stdout.splitlines()
                seen = {blob}
                for i, commit in enumerate(commits):
                    old_blob = self.blob(commit)
                    if not old_blob or old_blob in seen:
                        continue
                    seen.add(old_blob)
                    old_sql = self.sql(old_blob)
                    if placeholder(old_sql):
                        continue
                    try: _, old = prepare_sql(old_sql, folder, 'history_'+str(i), historical=True)
                    except (ValueError, sqlite3.Error): continue
                    if old == local:
                        base = old
                        break
            if base is None:
                yield dict(common, code='database_conflict', message='No shared database baseline could be proved. Compare the incoming Git backup with local data; neither copy was overwritten.')
                return
            changes = dict(local_changes=delta(base, local), remote_changes=delta(base, remote))
            if covers(base, local, remote):
                yield dict(common, **changes, code='database_remote_ahead', message='The remote snapshot includes every local change and newer data; a backed-up startup update is safe.')
            elif covers(base, remote, local):
                yield dict(common, **changes, code='database_local_ahead', message='Local changes extend the shared database snapshot; a backup upload is safe.')
            else:
                yield dict(common, **changes, code='database_conflict', message='Local and remote databases both have changes not present in the other copy, including possible deletions. Both copies were kept; upload is blocked.')

    def incoming_backup(self, review):
        """Preserve the incoming candidate as a verified backup without replacing
        different saved data.
        """
        directory = self.git.database.parent / 'database_backups'
        directory.mkdir(exist_ok=True)
        destination = directory / ('incoming_git_'+review['blob']+'.db')
        if destination.exists():
            with readonly(destination) as saved, readonly(review['candidate']) as source:
                if digest(capture(saved)) != digest(capture(source)):
                    raise DatabaseValidationError('The incoming backup filename already contains different data; it was not replaced.')
        else:
            publish(review['candidate'], destination)
        return destination.name

    def adopt(self, review):
        """Archive, check again under a write lock, replace and validate atomically."""
        from songranker.storage.database_access import gate
        with gate.maintenance():
            backup = create_backup(self.git.database, 'pre_git_database')
            with readonly(review['candidate']) as candidate:
                replacement = capture(candidate)
            conn = sqlite3.connect(self.git.database, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute('PRAGMA foreign_keys=OFF')
                conn.execute('BEGIN IMMEDIATE')
                if digest(capture(conn)) != review['live_hash']:
                    raise DatabaseValidationError('Local data changed during the Git database check; nothing was replaced. Restart to retry.')
                if self.git.inspect()['tracking_head'] != review['commit']:
                    raise DatabaseValidationError('Git changed during the database check; restart to retry.')
                replace_contents(conn, replacement)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally: conn.close()
        return backup.name

    @staticmethod
    def public(review):
        """Remove temporary paths and private comparison witnesses from a
        reconciliation review.
        """
        return {key: value for key, value in review.items() if key not in ('candidate', 'live_hash', 'blob')}
