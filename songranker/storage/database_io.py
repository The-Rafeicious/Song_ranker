"""Lossless SQLite transport, reconciliation and canonical rebuilding (stdlib only).

No catalogue cleanup is guessed here: ambiguous metadata and historical answers
are facts. Rebuilding standardises structure, preserves IDs/high-water marks and
keeps extension objects. All destructive replacement is owned by the caller.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import base64
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from threading import Lock

from songranker.storage.database_schema import (SCHEMA_VERSION, create_objects, definitions, table_columns)

EXPORT_FORMAT = 'song-ranker-database/1'


class DatabaseValidationError(ValueError):
    pass


def quote(name):
    return '"' + name.replace('"', '""') + '"'


@contextmanager
def readonly(filename):
    path = Path(filename).resolve(strict=True)
    if not path.is_file():
        raise DatabaseValidationError('Choose a regular database file.')
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def encode(value):
    return {'blob_base64': base64.b64encode(value).decode('ascii')} if isinstance(value, bytes) else value


def decode(value):
    if isinstance(value, dict):
        if set(value) != {'blob_base64'}:
            raise DatabaseValidationError('Unsupported value in export.')
        return base64.b64decode(value['blob_base64'], validate=True)
    if value is None or isinstance(value, (str, int, float)):
        return value
    raise DatabaseValidationError('Unsupported value in export.')


def capture(conn):
    """Call inside a read transaction or on a private SQLite backup snapshot."""
    objects = [dict(zip(('type', 'name', 'table', 'sql'), row)) for row in conn.execute('''
        SELECT type,name,tbl_name,sql FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
        ORDER BY type,name''')]
    tables = {}
    for obj in objects:
        if obj['type'] != 'table':
            continue
        name = obj['name']
        if any(row[6] for row in conn.execute(f'PRAGMA table_xinfo({quote(name)})')):
            raise DatabaseValidationError(f'Generated/hidden columns in {name} require a dedicated migration; no data was discarded.')
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info({quote(name)})')]
        rowid_alias = next((alias for alias in ('rowid', '_rowid_', 'oid')
                            if alias.lower() not in {c.lower() for c in columns}), None)
        has_rowid = rowid_alias is not None and not re.search(r'\bWITHOUT\s+ROWID\b', obj['sql'], re.I)
        selection = ','.join(map(quote, columns))
        if has_rowid:
            records = [(row[0], [encode(v) for v in row[1:]]) for row in conn.execute(
                'SELECT ' + quote(rowid_alias) + ',' + selection + ' FROM ' + quote(name))]
            records.sort(key=lambda item: (json_bytes(item[1]), item[0]))
            tables[name] = {'columns': columns, 'rows': [row for _, row in records],
                            'rowids': [rid for rid, _ in records], 'rowid_alias': rowid_alias}
        else:
            rows = [[encode(v) for v in row] for row in conn.execute('SELECT ' + selection + ' FROM ' + quote(name))]
            rows.sort(key=json_bytes)
            tables[name] = {'columns': columns, 'rows': rows}
    names = {o['name'] for o in objects if o['type'] == 'table'}
    sequence_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone()
    sequences = dict(conn.execute('SELECT name,seq FROM sqlite_sequence')) if sequence_exists else {}
    views = {}
    for obj in objects:
        if obj['type'] == 'view':
            rows = [[encode(v) for v in row] for row in conn.execute('SELECT * FROM ' + quote(obj['name']))]
            rows.sort(key=json_bytes)
            views[obj['name']] = digest(rows)
    return {'user_version': conn.execute('PRAGMA user_version').fetchone()[0],
            'application_id': conn.execute('PRAGMA application_id').fetchone()[0],
            'objects': objects, 'tables': tables,
            'sequences': {name: value for name, value in sequences.items() if name in names},
            'view_hashes': views}


def sql_dump(conn):
    """Verified SQL transport retaining implicit row IDs and exact SQLite values.

    SQLite's iterdump omits implicit row IDs and quote() truncates NUL text /
    rounds some floats. Use the same complete capture as JSON recovery, then
    reconcile a real SQL round trip before the caller can publish this dump.
    """
    state=capture(conn)
    def literal(value):
        value=decode(value)
        if value is None:return 'NULL'
        if isinstance(value,bytes):return "X'"+value.hex()+"'"
        if isinstance(value,str):
            if '\0' in value:return "CAST(X'"+value.encode('utf-8').hex()+"' AS TEXT)"
            return "'"+value.replace("'","''")+"'"
        if isinstance(value,float) and not math.isfinite(value):
            raise DatabaseValidationError('Non-finite values need dedicated recovery; no SQL snapshot was published.')
        return repr(value)
    statements=['PRAGMA foreign_keys=OFF;','BEGIN TRANSACTION;']
    objects=state['objects']
    statements.extend(o['sql'].rstrip(';')+';' for o in objects if o['type']=='table')
    for name,data in state['tables'].items():
        columns=list(data['columns'])
        if 'rowids' in data:columns.insert(0,data['rowid_alias'])
        prefix='INSERT INTO '+quote(name)+'('+','.join(map(quote,columns))+') VALUES('
        for i,row in enumerate(data['rows']):
            values=[data['rowids'][i],*row] if 'rowids' in data else row
            statements.append(prefix+','.join(map(literal,values))+');')
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
        statements.append('DELETE FROM sqlite_sequence;')
        statements.extend('INSERT INTO sqlite_sequence(name,seq) VALUES('+literal(name)+','+str(seq)+');' for name,seq in sorted(state['sequences'].items()))
    statements.extend(o['sql'].rstrip(';')+';' for o in objects if o['type']!='table')
    statements.extend([f'PRAGMA user_version={state["user_version"]};',f'PRAGMA application_id={state["application_id"]};','COMMIT;'])
    result='\n'.join(statements)+'\n'
    check=sqlite3.connect(':memory:')
    try:
        check.executescript(result);validate(check);reconcile(state,capture(check))
    finally:check.close()
    return result


def validate(conn):
    integrity = [row[0] for row in conn.execute('PRAGMA integrity_check')]
    if integrity != ['ok']:
        raise DatabaseValidationError('SQLite integrity check failed: ' + '; '.join(integrity))
    errors = [tuple(row) for row in conn.execute('PRAGMA foreign_key_check')]
    if errors:
        raise DatabaseValidationError(f'Database has {len(errors)} broken references: {errors[:5]}')
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'songs', 'albums', 'artists', 'genres', 'song_artists', 'song_genres'} <= tables:
        raise DatabaseValidationError('Not a complete relational Song Ranker database.')
    if conn.execute('PRAGMA user_version').fetchone()[0] >= 16:
        if conn.execute('SELECT 1 FROM song_genres GROUP BY song_id HAVING COUNT(*)>8 LIMIT 1').fetchone():
            raise DatabaseValidationError('A song exceeds the eight-tag limit in this schema-16 database.')
    if 'album_id' not in {row[1] for row in conn.execute('PRAGMA table_info(songs)')}:
        raise DatabaseValidationError('The older flat-schema database is not supported. Keep it separately.')
    if conn.execute('PRAGMA user_version').fetchone()[0] >= 17:
        from songranker.storage.vibe_state import validate_schema
        validate_schema(conn)


def reconcile(before, after):
    """Compare every stored value, view result and deleted-ID high-water mark."""
    from songranker.storage.preference_state import upgrade_state
    before = upgrade_state(before)
    after = upgrade_state(after)
    for name, data in after['tables'].items():
        if name not in before['tables'] and data['rows']:
            raise DatabaseValidationError(f'Rebuild introduced unexpected data in {name}.')
    for name, data in before['tables'].items():
        actual = after['tables'].get(name)
        if actual is None:
            raise DatabaseValidationError(f'Rebuild lost table {name}.')
        if set(data['columns']) != set(actual['columns']):
            raise DatabaseValidationError(f'Rebuild changed stored columns in {name}.')
        # A rebuild can put columns into canonical order; compare by name.
        order = [actual['columns'].index(column) for column in data['columns']]
        records = [([row[i] for i in order], actual.get('rowids', [None] * len(actual['rows']))[j])
                   for j, row in enumerate(actual['rows'])]
        records.sort(key=lambda item: (json_bytes(item[0]), item[1] or 0))
        rows = [row for row, _ in records]
        if data['rows'] != rows:
            raise DatabaseValidationError(f'Rebuild changed stored values in {name}.')
        if 'rowids' in data and data['rowids'] != [rid for _, rid in records]:
            raise DatabaseValidationError(f'Rebuild changed row IDs in {name}.')
    for name, seq in before['sequences'].items():
        if after['sequences'].get(name, -1) < seq:
            raise DatabaseValidationError(f'Rebuild lowered the ID high-water mark for {name}.')
    for name, view_hash in before['view_hashes'].items():
        if after['view_hashes'].get(name) != view_hash:
            raise DatabaseValidationError(f'Rebuild changed derived view {name}.')
    if before['application_id'] != after['application_id']:
        raise DatabaseValidationError('Rebuild changed the SQLite application ID.')
    managed = {name for _, name, _ in definitions()}
    actual_objects = {(obj['type'], obj['name']): obj for obj in after['objects']}
    for obj in before['objects']:
        if obj['name'] not in managed and actual_objects.get((obj['type'], obj['name'])) != obj:
            raise DatabaseValidationError(f'Rebuild changed extension schema {obj["name"]}.')


def populate(conn, state):
    """Populate an EMPTY database from a validated state, then verify it exactly."""
    if state['user_version'] > SCHEMA_VERSION:
        raise DatabaseValidationError('This database is newer than this app; upgrade the app first.')
    from songranker.storage.preference_state import upgrade_state
    state = upgrade_state(state)
    known = table_columns()
    for name, data in state['tables'].items():
        if name in known and set(data['columns']) != set(known[name]):
            raise DatabaseValidationError(f'Unsupported columns in {name}; no data was discarded.')
    managed = {name for _, name, _ in definitions()}
    extras = [obj for obj in state['objects'] if obj['name'] not in managed]
    if any(re.search(r'CREATE\s+VIRTUAL\s+TABLE', obj['sql'], re.I) for obj in extras):
        raise DatabaseValidationError('Virtual extension tables require a dedicated migration.')
    create_objects(conn, kinds={'table'})
    for obj in extras:
        if obj['type'] == 'table':
            conn.execute(obj['sql'])
    for name, data in state['tables'].items():
        columns = list(data['columns'])
        rows = [[decode(v) for v in row] for row in data['rows']]
        if 'rowids' in data:
            columns.insert(0, data['rowid_alias'])
            rows = [[rid, *row] for rid, row in zip(data['rowids'], rows)]
        statement = ('INSERT INTO ' + quote(name) + '(' + ','.join(map(quote, columns)) +
                     ') VALUES (' + ','.join('?' for _ in columns) + ')')
        conn.executemany(statement, rows)
    for name, seq in state['sequences'].items():
        current = conn.execute('SELECT seq FROM sqlite_sequence WHERE name=?', (name,)).fetchone()
        if current:
            conn.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?', (seq, name))
        else:
            conn.execute('INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)', (name, seq))
    create_objects(conn, kinds={'index', 'view', 'trigger'})
    for obj in extras:
        if obj['type'] != 'table':
            conn.execute(obj['sql'])
    conn.execute(f'PRAGMA application_id={int(state["application_id"])}')
    conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
    validate(conn)
    reconcile(state, capture(conn))


def replace_contents(conn, state):
    """Caller holds BEGIN IMMEDIATE with foreign_keys OFF; rollback stays possible."""
    # Drop triggers/views first, then tables. No unknown extension is discarded:
    # populate recreates every non-managed object from the captured schema.
    for kind in ('trigger', 'view', 'table'):
        for name, in conn.execute('SELECT name FROM sqlite_master WHERE type=? '
                                 "AND name NOT LIKE 'sqlite_%'", (kind,)).fetchall():
            conn.execute('DROP ' + kind.upper() + ' ' + quote(name))
    # sqlite_sequence survives DROP TABLE, but stale rows must not be retained.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
        conn.execute('DELETE FROM sqlite_sequence')
    populate(conn, state)


def create_backup(filename, prefix='manual'):
    if not re.fullmatch(r'[a-z_]+', prefix):
        raise ValueError('Invalid backup prefix.')
    path = Path(filename).resolve(strict=True)
    directory = path.parent / 'database_backups'
    directory.mkdir(exist_ok=True)
    backup = directory / f'{prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.db'
    with readonly(path) as source:
        destination = sqlite3.connect(backup)
        try:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise DatabaseValidationError('Safety backup failed its integrity check.')
        finally:
            destination.close()
    return backup


_rolling_lock = Lock()


def create_rolling_backup(filename):
    """Verified, atomic replacement of the oldest of three requested backup slots.

    Historical/update archives are never pruned or renamed by this policy.
    """
    path=Path(filename).resolve(strict=True)
    directory=path.parent/'database_backups'
    with _rolling_lock:
        if directory.is_symlink():raise DatabaseValidationError('Backup folder must not be a symbolic link.')
        directory.mkdir(exist_ok=True)
        slots=[directory/f'rolling_{i}.db' for i in (1,2,3)]
        if any(p.is_symlink() or (p.exists() and not p.is_file()) for p in slots):
            raise DatabaseValidationError('Rotating backups must be regular files.')
        target=next((p for p in slots if not p.exists()),None)
        if target is None:target=min(slots,key=lambda p:p.stat().st_mtime_ns)
        fd,name=tempfile.mkstemp(dir=directory,prefix='.rolling_',suffix='.db');os.close(fd)
        try:
            with readonly(path) as source:
                destination=sqlite3.connect(name)
                try:
                    source.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or destination.execute('PRAGMA foreign_key_check').fetchall():
                        raise DatabaseValidationError('Rotating backup failed validation; previous slots were kept.')
                finally:destination.close()
            with open(name,'rb+') as stream:os.fsync(stream.fileno())
            os.replace(name,target)
        finally:Path(name).unlink(missing_ok=True)
        return target


@contextmanager
def snapshot(filename):
    """SQLite's backup API includes committed WAL data and concurrent-writer safety."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    try:
        with readonly(filename) as source:
            source.backup(conn)
        yield conn
    finally:
        conn.close()


def audit(filename):
    with snapshot(filename) as conn:
        validate(conn)
        state = capture(conn)
        known = {name for _, name, _ in definitions()}
        from songranker.developer.track_numbers import track_position_conflicts
        return {'schema_version': state['user_version'], 'integrity': 'ok',
                'foreign_key_errors': 0,
                'counts': {name: len(data['rows']) for name, data in state['tables'].items()},
                'data_hashes': {name: digest(data) for name, data in state['tables'].items()},
                'view_hashes': state['view_hashes'], 'sequences': state['sequences'],
                'preserved_extensions': [obj['name'] for obj in state['objects'] if obj['name'] not in known],
                'track_position_conflicts': track_position_conflicts(conn)}


def publish(candidate, output):
    """Atomically publish a new file; never overwrite an existing destination."""
    output = Path(output)
    try:
        os.link(candidate, output)
    except FileExistsError as error:
        raise DatabaseValidationError(f'Output already exists: {output}; choose a new filename.') from error


def write_export(filename, output):
    with snapshot(filename) as conn:
        validate(conn)
        state = capture(conn)
    payload = {'format': EXPORT_FORMAT, 'exported_at': datetime.now(timezone.utc).isoformat(),
               'state': state, 'state_sha256': digest(state)}
    output = Path(output).resolve()
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.export_') as folder:
        candidate = Path(folder) / 'export.json'
        with candidate.open('wb') as f:
            f.write(json_bytes(payload) + b'\n')
            f.flush()
            os.fsync(f.fileno())
        publish(candidate, output)
    return output


def read_export(filename):
    payload = json.loads(Path(filename).read_text(encoding='utf-8'))
    if payload.get('format') != EXPORT_FORMAT or payload.get('state_sha256') != digest(payload.get('state')):
        raise DatabaseValidationError('Export format or checksum is invalid.')
    return payload['state']


def rebuild(state, output):
    """Build/compact a new database, never the active file or a supplied backup."""
    output = Path(output).resolve()
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.rebuild_') as folder:
        candidate = Path(folder) / 'candidate.db'
        conn = sqlite3.connect(candidate)
        conn.execute('PRAGMA page_size=2048')
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('BEGIN IMMEDIATE')
            populate(conn, state)
            conn.commit()
            conn.execute('VACUUM')
            validate(conn)
        finally:
            conn.close()
        from songranker.storage.source_storage import compact_database
        compact_database(candidate,force=True,backed_up=True)
        publish(candidate, output)
    return output


def prepare_candidate(source, output):
    """Copy, migrate and validate a backup without touching source or live files."""
    output = Path(output)
    if output.exists():
        raise DatabaseValidationError('Candidate output must be a new file.')
    with readonly(source) as original:
        validate(original)
        before_version = original.execute('PRAGMA user_version').fetchone()[0]
        if before_version > SCHEMA_VERSION:
            raise DatabaseValidationError('Backup needs a newer app version.')
        target = sqlite3.connect(output)
        try:
            original.backup(target)
        finally:
            target.close()
    from songranker.storage.database import migrate
    migrate(output)
    with readonly(output) as candidate:
        validate(candidate)
    return output


def restore_live_database(source, filename, *, expected_live=None, expected_backup=None):
    """Dev-only replacement: validate candidate, drain app connections, keep rollback.

    The gate covers the local Waitress process. For multi-process WSGI hosting,
    stop other workers before manual recovery (see docs/DATABASE.md).
    """
    from songranker.storage.database_access import gate
    filename = Path(filename).resolve(strict=True)
    with gate.maintenance():
        with tempfile.TemporaryDirectory(dir=filename.parent, prefix='.restore_') as folder:
            candidate = prepare_candidate(source, Path(folder) / 'candidate.db')
            if expected_backup:
                with readonly(candidate) as prepared:
                    if digest(capture(prepared)) != expected_backup:
                        raise DatabaseValidationError('This backup changed since review. Review it again.')
            if expected_live:
                with snapshot(filename) as live:
                    if digest(capture(live)) != expected_live:
                        raise DatabaseValidationError('The live database changed since review. Review the restore again.')
            backup = create_rolling_backup(filename)
            try:
                with readonly(candidate) as prepared:
                    target = sqlite3.connect(filename, timeout=30)
                    try:
                        prepared.backup(target)
                        validate(target)
                        reconcile(capture(prepared), capture(target))
                    finally:
                        target.close()
            except BaseException:
                with readonly(backup) as recovery:
                    target = sqlite3.connect(filename, timeout=30)
                    try:
                        recovery.backup(target)
                        validate(target)
                    finally:
                        target.close()
                raise
    return backup

