"""Fixed Vibe Map definitions and lossless schema-17/18 transport upgrades."""
from copy import deepcopy

VIBE_MAP_VERSION = 'Vibe-Map-v1.0.4'
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
POSITION_COLUMNS_V17 = ('song_id', 'map_id', 'x', 'y', 'status', 'updated_at')
BASE_TABLES = {'vibe_maps', 'song_vibe_positions'}
TABLES = BASE_TABLES | {'song_vibe_progress', 'vibe_rounds'}


def definition_rows():
    return [list(values) + [1, VIBE_MAP_COLOUR, order]
            for order, values in enumerate(MAPS, 1)]


def seed_definitions(conn):
    """Fresh database only; canonical rebuilds seed through upgrade_state instead."""
    conn.executemany('INSERT INTO vibe_maps VALUES(?,?,?,?,?,?,?,?,?)', definition_rows())


def validate_schema(conn):
    """Validate fixed maps and required per-song coverage for this schema."""
    from songranker.storage.database_io import DatabaseValidationError
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = TABLES if conn.execute('PRAGMA user_version').fetchone()[0]>=18 else BASE_TABLES
    if not required <= tables:
        raise DatabaseValidationError('Vibe Map tables are missing from this database schema.')
    actual = [list(row) for row in conn.execute('SELECT * FROM vibe_maps ORDER BY display_order')]
    if actual != definition_rows():
        raise DatabaseValidationError('Vibe Map definitions do not match Vibe-Map-v1.0.0.')
    if conn.execute('''SELECT s.id FROM songs s LEFT JOIN song_vibe_positions v ON v.song_id=s.id
                       GROUP BY s.id HAVING COUNT(v.map_id)!=4 LIMIT 1''').fetchone():
        raise DatabaseValidationError('Each song must have all four Vibe Map slots.')
    if 'song_vibe_progress' in required and conn.execute('''SELECT s.id FROM songs s
        LEFT JOIN song_vibe_progress v ON v.song_id=s.id WHERE v.song_id IS NULL LIMIT 1''').fetchone():
        raise DatabaseValidationError('Each song must have a Vibe Map pass counter.')


def _upgrade_to_17(original):
    if original['user_version'] >= 17:
        return original
    if BASE_TABLES & original['tables'].keys():
        raise ValueError('A pre-17 extension uses Vibe Map tables; a dedicated migration is required.')
    from songranker.storage.preference_state import records, table
    state = deepcopy(original)
    state['tables']['vibe_maps'] = table(MAP_COLUMNS, definition_rows())
    state['tables']['song_vibe_positions'] = table(POSITION_COLUMNS_V17, [
        [song['id'], values[0], None, None, 'unmapped', None]
        for song in records(state, 'songs') for values in MAPS])
    state['user_version'] = 17
    return state


def upgrade_state(original):
    state = _upgrade_to_17(original)
    if state['user_version'] >= 18:
        return state
    if {'song_vibe_progress','vibe_rounds'} & state['tables'].keys():
        raise ValueError('A pre-18 extension uses Vibe Map runtime tables; a dedicated migration is required.')
    from songranker.storage.preference_state import records, table
    state = deepcopy(state)
    positions = state['tables']['song_vibe_positions']
    status = positions['columns'].index('status')
    for key, target in (('sample_count','placed'),('not_applicable_count','not_applicable')):
        if key in positions['columns']:
            raise ValueError('A pre-18 extension uses Vibe Map sample counters.')
        positions['columns'].append(key)
        for row in positions['rows']:
            row.append(int(row[status]==target))
    completed = {}
    for row in records(state,'song_vibe_positions'):
        completed[row['song_id']] = completed.get(row['song_id'],0)+int(row['status']!='unmapped')
    state['tables']['song_vibe_progress'] = table(('song_id','completed_passes'),[
        [row['id'],int(completed.get(row['id'])==len(MAPS))] for row in records(state,'songs')])
    from songranker.storage.database_schema import table_columns
    state['tables']['vibe_rounds'] = table(table_columns()['vibe_rounds'],[])
    state['user_version'] = 18
    return state
