"""The schema.sql registry. Execute statements without executescript's implicit COMMIT."""
from functools import lru_cache
from pathlib import Path
import re
import sqlite3

SCHEMA_VERSION = 17
from songranker.paths import ROOT
SCHEMA_PATH = ROOT/'data/schema.sql'


@lru_cache(maxsize=1)
def definitions():
    result = []
    pending = ''
    for line in SCHEMA_PATH.read_text(encoding='utf-8').splitlines(True):
        pending += line
        if sqlite3.complete_statement(pending):
            match = re.search(r'CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX|VIEW|TRIGGER)\s+'
                              r'IF NOT EXISTS\s+["`\[]?(\w+)', pending, re.I)
            if not match:
                raise ValueError('schema.sql may contain only named CREATE definitions.')
            result.append((match[1].lower(), match[2], pending.strip()))
            pending = ''
    if pending.strip():
        raise ValueError('Incomplete SQL in schema.sql.')
    return tuple(result)


def create_objects(conn, *, names=None, kinds=None):
    for kind, name, sql in definitions():
        if (names is None or name in names) and (kinds is None or kind in kinds):
            conn.execute(sql)


@lru_cache(maxsize=1)
def table_columns():
    conn = sqlite3.connect(':memory:')
    try:
        create_objects(conn)
        return {name: tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{name}")'))
                for kind, name, _ in definitions() if kind == 'table'}
    finally:
        conn.close()


def ensure_tournament_schema(conn):
    """Compatibility adapter for pre-9 databases and isolated report fixtures."""
    create_objects(conn, names={'tournament_entries', 'tournament_matches',
        'idx_tournament_matches_tournament_round', 'idx_tournament_matches_winner',
        'idx_tournament_matches_loser'})
    columns = {r[1] for r in conn.execute('PRAGMA table_info(tournaments)')}
    for name, declaration in {
        'status': "TEXT NOT NULL DEFAULT 'completed'", 'created_at': 'DATETIME',
        'updated_at': 'DATETIME', 'completed_at': 'DATETIME',
        'current_round': 'INTEGER NOT NULL DEFAULT 1',
        'points_version': 'INTEGER NOT NULL DEFAULT 1',
        'is_blind': 'BOOLEAN NOT NULL DEFAULT 0'
    }.items():
        if name not in columns:
            conn.execute(f'ALTER TABLE tournaments ADD COLUMN {name} {declaration}')
    create_objects(conn, names={'idx_tournaments_status'})
    conn.execute("UPDATE tournaments SET status='completed' WHERE champion_id IS NOT NULL AND status IS NULL")
    conn.execute('UPDATE tournaments SET created_at=COALESCE(created_at,timestamp,CURRENT_TIMESTAMP)')
    conn.execute('UPDATE tournaments SET completed_at=COALESCE(completed_at,timestamp) WHERE champion_id IS NOT NULL')
