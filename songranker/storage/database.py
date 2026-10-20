"""Versioned database bootstrap and backed-up, transactional schema migration."""
from pathlib import Path
from datetime import datetime
import sqlite3
from songranker.storage.database_schema import (SCHEMA_VERSION, create_objects, table_columns, definitions)

LEGACY_SCHEMA_VERSION = 8

def _migrate_legacy(filename):
    path = Path(filename)
    if not path.exists(): return
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        song_columns={r['name'] for r in conn.execute('PRAGMA table_info(songs)')}
        if 'songs' in tables and 'album_id' not in song_columns:
            raise sqlite3.DatabaseError('This is the older flat-schema database. Use song_ranker_v2.db; the older database is kept separately.')
        if 'history' not in tables or conn.execute('PRAGMA user_version').fetchone()[0] >= LEGACY_SCHEMA_VERSION:
            return
        # sqlite backup captures a consistent snapshot, including older schemas.
        directory = path.parent / 'database_backups'
        directory.mkdir(exist_ok=True)
        backup = directory / ('pre_upgrade_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
        destination = sqlite3.connect(backup)
        try: conn.backup(destination)
        finally: destination.close()
        conn.execute('BEGIN IMMEDIATE')
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(history)')}
        for name, declaration in [('created_at','DATETIME'),('mode',"TEXT NOT NULL DEFAULT 'unknown'"),
                                  ('winner_before','REAL'),('winner_after','REAL'),('loser_before','REAL'),('loser_after','REAL')]:
            if name not in columns: conn.execute(f'ALTER TABLE history ADD COLUMN {name} {declaration}')
        if 'elo_history' in tables:
            consumed = set()
            for row in conn.execute('SELECT * FROM elo_history ORDER BY id').fetchall():
                candidates = conn.execute('SELECT * FROM history WHERE winner_id=? AND loser_id=? AND winner_before IS NULL ORDER BY id',
                                          (row['winner_id'], row['loser_id'])).fetchall()
                exact = [h for h in candidates if h['created_at'] and h['created_at'] == row['created_at']]
                target = exact[0] if exact else (candidates[0] if len(candidates)==1 and not candidates[0]['created_at'] else None)
                if target:
                    # Existing history labels are authoritative. Only legacy unknown
                    # rows receive the explicitly recorded Elo entry's mode.
                    conn.execute('UPDATE history SET winner_before=?,winner_after=?,loser_before=?,loser_after=?,created_at=COALESCE(created_at,?), mode=CASE WHEN mode=\'unknown\' THEN ? ELSE mode END WHERE id=?',
                        (row['winner_before'],row['winner_after'],row['loser_before'],row['loser_after'],row['created_at'],row['mode'],target['id']))
                    consumed.add(row['id'])
            unmatched = [dict(r) for r in conn.execute('SELECT * FROM elo_history') if r['id'] not in consumed]
            if unmatched:
                # Do not guess a pairing for ambiguous old votes. Keep only the
                # unmatched legacy values, instead of retaining a duplicate log.
                conn.execute('CREATE TABLE legacy_elo_changes AS SELECT * FROM elo_history WHERE 0')
                for row in unmatched:
                    conn.execute('INSERT INTO legacy_elo_changes VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
        for table in ('admin_audit_log','interaction_events','elo_history'):
            conn.execute(f'DROP TABLE IF EXISTS {table}')
        if 'trivia_stats' in tables:
            conn.execute('DELETE FROM trivia_stats WHERE attempts=0 AND correct=0')
        if 'tournament_matches' in tables:
            columns={r['name']:r for r in conn.execute('PRAGMA table_info(tournament_matches)')}
            if columns['song1_id']['notnull'] or columns['song2_id']['notnull']:
                # Archived brackets keep their structure when a song is deleted.
                # Nullable references avoid dangling IDs or deleting whole brackets.
                schema=conn.execute("SELECT sql FROM sqlite_master WHERE name='tournament_matches'").fetchone()[0]
                indexes=[r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='tournament_matches' AND sql IS NOT NULL")]
                sequence=conn.execute("SELECT seq FROM sqlite_sequence WHERE name='tournament_matches'").fetchone()
                schema=schema.replace('CREATE TABLE tournament_matches','CREATE TABLE tournament_matches_slim',1)
                schema=schema.replace('song1_id INTEGER NOT NULL','song1_id INTEGER').replace('song2_id INTEGER NOT NULL','song2_id INTEGER')
                conn.execute(schema)
                names=','.join('"'+name+'"' for name in columns)
                conn.execute(f'INSERT INTO tournament_matches_slim ({names}) SELECT {names} FROM tournament_matches')
                conn.execute('DROP TABLE tournament_matches')
                conn.execute('ALTER TABLE tournament_matches_slim RENAME TO tournament_matches')
                if sequence:
                    conn.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='tournament_matches'",(sequence[0],))
                for index in indexes:conn.execute(index)
        conn.execute('CREATE INDEX IF NOT EXISTS history_winner ON history(winner_id,id)')
        conn.execute('CREATE INDEX IF NOT EXISTS history_loser ON history(loser_id,id)')
        conn.execute('CREATE INDEX IF NOT EXISTS songs_album ON songs(album_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS song_artists_artist ON song_artists(artist_id,song_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS song_genres_genre ON song_genres(genre_id,song_id)')
        from songranker.storage.schema_compat import ensure_mode_schema
        ensure_mode_schema(conn, legacy=True)
        if 'genres' in tables and 'description' not in {r['name'] for r in conn.execute('PRAGMA table_info(genres)')}:
            conn.execute("ALTER TABLE genres ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        from songranker.storage.schema_compat import ensure_special_schema
        ensure_special_schema(conn, legacy=True)
        conn.execute(f'PRAGMA user_version={LEGACY_SCHEMA_VERSION}')
        conn.commit()
        conn.execute('VACUUM')
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()


def _canonical_columns_present(conn):
    objects = {row[0]: row[1] for row in conn.execute("SELECT name,type FROM sqlite_master")}
    types_ok = all(objects.get(name) == kind for kind, name, _ in definitions() if kind in ('table','view'))
    return types_ok and all(set(expected) == {r[1] for r in conn.execute(f'PRAGMA table_xinfo("{name}")')}
               for name, expected in table_columns().items())


def _complete_old_layout(conn):
    from songranker.storage.preference_state import LEGACY_COLUMNS
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    old_names = {'albums','artists','genres','songs','song_artists','song_genres','tournaments',
        'global_stats','tournament_entries','tournament_matches','trivia_adjustments','trivia_rounds',
        'elo_guess_rounds','album_shelf_rounds','album_shelf_items'}
    return ('history' in tables and set(LEGACY_COLUMNS) == {r[1] for r in conn.execute('PRAGMA table_xinfo(history)')}
        and all(set(table_columns()[name]) == {r[1] for r in conn.execute(f'PRAGMA table_xinfo("{name}")')}
                for name in old_names))


def migrate(filename):
    """Canonicalise to the current schema with rollback and a pre-upgrade SQLite snapshot.

    Rebuild inside one write transaction, rather than replacing an open file.
    A concurrent write during candidate preparation aborts the upgrade safely.
    """
    from songranker.storage.safe_mode import assert_writable
    assert_writable(filename)
    from songranker.storage.database_io import (DatabaseValidationError, capture, create_backup, readonly, replace_contents, validate)
    path = Path(filename)
    if not path.exists():
        return
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            raise DatabaseValidationError('Database needs a newer app; it was left unchanged.')
        validate(conn)
        if version == SCHEMA_VERSION:
            if not _canonical_columns_present(conn):
                raise DatabaseValidationError('Current schema has missing/unsupported objects or columns; restore a verified backup.')
            # Missing indexes/triggers are repaired from the canonical registry.
            create_objects(conn, kinds={'index', 'view', 'trigger'})
            conn.commit()
        # SQL iterdump does not retain PRAGMA user_version. A complete v8 layout
        # can be recognised without repeating old, data-changing migrations.
        complete = _canonical_columns_present(conn) or _complete_old_layout(conn)
    finally:
        conn.close()
    if version==SCHEMA_VERSION:
        from songranker.storage.source_storage import compact_database
        compact_database(path,grow_only=True)
        return
    if not complete and version < LEGACY_SCHEMA_VERSION:
        _migrate_legacy(path)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        generation = conn.execute('PRAGMA data_version').fetchone()[0]
        backup = create_backup(path, 'pre_upgrade')
        with readonly(backup) as source:
            validate(source)
            state = capture(source)
        # Validate the full candidate before taking the live write lock.
        candidate = sqlite3.connect(':memory:')
        candidate.row_factory = sqlite3.Row
        from songranker.storage.database_io import populate
        try:
            populate(candidate, state)
        finally:
            candidate.close()
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute('BEGIN IMMEDIATE')
        if generation != conn.execute('PRAGMA data_version').fetchone()[0]:
            raise DatabaseValidationError('Database changed during upgrade preparation; restart to retry.')
        replace_contents(conn, state)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    from songranker.storage.source_storage import compact_database
    compact_database(path,force=True,backed_up=True)


def initialize_database(filename, sql_backup=None):
    """Existing DB wins. Missing DB restores SQL before any empty schema is made."""
    from songranker.storage.safe_mode import assert_writable
    assert_writable(filename)
    import tempfile
    from songranker.storage.database_io import (DatabaseValidationError, publish, validate)
    path = Path(filename).resolve()
    if path.exists():
        migrate(path)
        return 'existing'
    path.parent.mkdir(parents=True, exist_ok=True)
    source = Path(sql_backup) if sql_backup is not None else None
    with tempfile.TemporaryDirectory(dir=path.parent, prefix='.bootstrap_') as folder:
        candidate = Path(folder) / 'candidate.db'
        conn = sqlite3.connect(candidate)
        conn.execute('PRAGMA page_size=2048')
        conn.row_factory = sqlite3.Row
        try:
            if source is not None and source.exists():
                # Dump files are local backups, not scripts allowed to attach or
                # write other databases. Invalid restores never publish a file.
                def authorize(action, arg1, arg2, db, trigger):
                    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK
                conn.set_authorizer(authorize)
                conn.executescript(source.read_text(encoding='utf-8-sig'))
                conn.commit()
                conn.set_authorizer(None)
                validate(conn)
                restored = True
            else:
                conn.execute('BEGIN IMMEDIATE')
                create_objects(conn)
                conn.execute("INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',1)")
                conn.execute("INSERT INTO competition_state VALUES(1,3,unixepoch(),'{}')")
                conn.executemany('INSERT INTO global_stats(key,value) VALUES(?,?)',
                    [('trivia_high_score', 0), ('trivia_high_streak', 0), ('trivia_scoring_version', 2)])
                conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                conn.commit()
                restored = False
        finally:
            conn.close()
        migrate(candidate)
        check = sqlite3.connect(candidate)
        try:
            validate(check)
        finally:
            check.close()
        try:
            publish(candidate, path)
        except DatabaseValidationError:
            # Another startup won the exclusive publish. Validate that winner;
            # never replace it with this process's potentially older backup.
            if path.exists():
                migrate(path)
                return 'existing'
            raise
    return 'restored' if restored else 'created'
