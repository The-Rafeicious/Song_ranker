"""Vibe-Map-v1.0.0 definitions and lossless schema-16 -> 17 transport upgrade."""
from copy import deepcopy

VIBE_MAP_VERSION = 'Vibe-Map-v1.0.1'
VIBE_MAP_COLOUR = '#d94b58'
# Stable keys and endpoint meanings: coordinate -1 is low, +1 is high.
MAPS = (
    ('mood_energy', 'Mood & energy', 'Sad', 'Happy', 'Gentle', 'Intense'),
    ('relationships', 'Relationships', 'Breakup / separation', 'New / early love',
     'Guarded / distant', 'Close / devoted'),
    ('self_social', 'Self & others', 'Vulnerable / self-doubting', 'Confident / defiant',
     'Introspective / private', 'Outward / social'),
    ('reflection_escape', 'Reflection & escape', 'Looking back / nostalgic',
     'Looking ahead / hopeful', 'Grounded / everyday', 'Dreamlike / escapist'),
)
MAP_COLUMNS = ('id', 'title', 'x_low', 'x_high', 'y_low', 'y_high',
               'definition_version', 'colour', 'display_order')
POSITION_COLUMNS = ('song_id', 'map_id', 'x', 'y', 'status', 'updated_at')
TABLES = {'vibe_maps', 'song_vibe_positions'}


def definition_rows():
    return [list(values) + [1, VIBE_MAP_COLOUR, order]
            for order, values in enumerate(MAPS, 1)]


def seed_definitions(conn):
    """Fresh database only; canonical rebuilds seed through upgrade_state instead."""
    conn.executemany('INSERT INTO vibe_maps VALUES(?,?,?,?,?,?,?,?,?)', definition_rows())


def validate_schema(conn):
    """A schema-17 snapshot must contain the definitions and all four song links."""
    from songranker.storage.database_io import DatabaseValidationError
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not TABLES <= tables:
        raise DatabaseValidationError('Vibe Map tables are missing from this schema-17 database.')
    actual = [list(row) for row in conn.execute('SELECT * FROM vibe_maps ORDER BY display_order')]
    if actual != definition_rows():
        raise DatabaseValidationError('Vibe Map definitions do not match Vibe-Map-v1.0.0.')
    if conn.execute('''SELECT s.id FROM songs s LEFT JOIN song_vibe_positions v ON v.song_id=s.id
                       GROUP BY s.id HAVING COUNT(v.map_id)!=4 LIMIT 1''').fetchone():
        raise DatabaseValidationError('Each song must have all four Vibe Map slots.')


def upgrade_state(original):
    if original['user_version'] >= 17:
        return original
    if TABLES & original['tables'].keys():
        raise ValueError('A pre-17 extension uses Vibe Map tables; a dedicated migration is required.')
    from songranker.storage.preference_state import records, table
    state = deepcopy(original)
    state['tables']['vibe_maps'] = table(MAP_COLUMNS, definition_rows())
    state['tables']['song_vibe_positions'] = table(POSITION_COLUMNS, [
        [song['id'], values[0], None, None, 'unmapped', None]
        for song in records(state, 'songs') for values in MAPS])
    state['user_version'] = 17
    return state
