"""The schema.sql registry. Execute statements without executescript's implicit COMMIT."""

from functools import lru_cache
import re
import sqlite3
from songranker.paths import ROOT

SCHEMA_VERSION = 20
SCHEMA_PATH = ROOT/'data/schema.sql'


@lru_cache(maxsize=1)
def definitions():
    """Parse the canonical schema into complete named CREATE definitions, rejecting
    other or incomplete SQL.
    """
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
    """Execute selected canonical schema definitions inside the caller's transaction."""
    for kind, name, sql in definitions():
        if (names is None or name in names) and (kinds is None or kind in kinds):
            conn.execute(sql)


@lru_cache(maxsize=1)
def table_columns():
    """Read canonical table-column order from a disposable in-memory schema."""
    conn = sqlite3.connect(':memory:')
    try:
        create_objects(conn)
        return {name: tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{name}")'))
                for kind, name, _ in definitions() if kind == 'table'}
    finally:
        conn.close()
