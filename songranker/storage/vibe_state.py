"""Fixed Vibe Map definitions and versioned schema-17/18 transport and one-time schema-19 test reset."""
from copy import deepcopy

VIBE_MAP_VERSION = 'Vibe-Map-v1.0.7.1'
VIBE_MAP_COLOUR = '#d94b58'
# Stable keys and endpoint meanings: coordinate -1 is low, +1 is high.
LEGACY_MAPS = (
    ('mood_energy', 'Mood & energy', 'Sad', 'Happy', 'Gentle', 'Intense'),
    ('relationships', 'Relationships', 'Breakup / separation', 'New / early love',
     'Guarded / distant', 'Close / devoted'),
    ('self_social', 'Self & others', 'Vulnerable / self-doubting', 'Confident / defiant',
     'Introspective / private', 'Outward / social'),
    ('reflection_escape', 'Reflection & escape', 'Looking back / nostalgic',
     'Looking ahead / hopeful', 'Grounded / everyday', 'Dreamlike / escapist'),
)
# New keys deliberately prevent old coordinates being relabelled as new meanings.
MAPS = (
    ('pace_mood', 'Pace & mood', 'Slow', 'Upbeat', 'Sad', 'Happy'),
    ('sound_impact', 'Sound & impact', 'Acoustic', 'Electronic', 'Soft', 'Powerful'),
    ('connection', 'Connection', 'Fractured', 'Secure', 'Casual', 'Devoted'),
    ('perspective', 'Perspective', 'Past', 'Future', 'Regretful', 'Hopeful'),
)
# Presentation only: retain stored definitions and schema-19 validation unchanged.
LABEL_OVERRIDES = {'connection': {'y_low': 'Budding'}}
DISPLAY_MAPS = tuple((*values[:4], LABEL_OVERRIDES.get(values[0], {}).get('y_low', values[4]), values[5]) for values in MAPS)
CENTER_LABELS = {'perspective': {'x_center': 'Present'}}
RADAR_ORDER = (('pace_mood','y','Happy'),('perspective','y','Hopeful'),
               ('perspective','x','Future'),('connection','x','Secure'),
               ('connection','y','Devoted'),('sound_impact','y','Powerful'),
               ('sound_impact','x','Electronic'),('pace_mood','x','Upbeat'))
MAP_COLUMNS = ('id', 'title', 'x_low', 'x_high', 'y_low', 'y_high',
               'definition_version', 'colour', 'display_order')
POSITION_COLUMNS_V17 = ('song_id', 'map_id', 'x', 'y', 'status', 'updated_at')
BASE_TABLES = {'vibe_maps', 'song_vibe_positions'}
TABLES = BASE_TABLES | {'song_vibe_progress', 'vibe_rounds'}


def definition_rows(*, legacy=False):
    maps=LEGACY_MAPS if legacy else MAPS
    return [list(values) + [1 if legacy else 2, VIBE_MAP_COLOUR, order]
            for order, values in enumerate(maps, 1)]


def seed_definitions(conn, *, legacy=False):
    """Fresh database only; canonical rebuilds seed through upgrade_state instead."""
    conn.executemany('INSERT INTO vibe_maps VALUES(?,?,?,?,?,?,?,?,?)', definition_rows(legacy=legacy))


def validate_schema(conn):
    """Validate fixed maps and required per-song coverage for this schema."""
    from songranker.storage.database_io import DatabaseValidationError
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = TABLES if conn.execute('PRAGMA user_version').fetchone()[0]>=18 else BASE_TABLES
    if not required <= tables:
        raise DatabaseValidationError('Vibe Map tables are missing from this database schema.')
    actual = [list(row) for row in conn.execute('SELECT * FROM vibe_maps ORDER BY display_order')]
    if actual != definition_rows(legacy=conn.execute('PRAGMA user_version').fetchone()[0]<19):
        raise DatabaseValidationError('Vibe Map definitions do not match this database version.')
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
    state['tables']['vibe_maps'] = table(MAP_COLUMNS, definition_rows(legacy=True))
    state['tables']['song_vibe_positions'] = table(POSITION_COLUMNS_V17, [
        [song['id'], values[0], None, None, 'unmapped', None]
        for song in records(state, 'songs') for values in LEGACY_MAPS])
    state['user_version'] = 17
    return state


def _upgrade_to_18(original):
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


def upgrade_state(original):
    """One-time definition replacement. Only old Vibe Map test facts are cleared.

    Canonical migration creates a pre-upgrade backup and publishes atomically.
    Schema 19 is the durable marker: reruns/exports/rebuilds keep new placements.
    """
    state=_upgrade_to_18(original)
    if state['user_version']>=19:return state
    from songranker.storage.preference_state import records, table
    if state['tables']['vibe_maps']['rows']!=definition_rows(legacy=True):
        # capture sorts rows by primary key, so compare order-independent values.
        if sorted(state['tables']['vibe_maps']['rows'])!=sorted(definition_rows(legacy=True)):
            raise ValueError('Unknown old Vibe Map definitions; refusing to reinterpret/reset them.')
    state=deepcopy(state)
    songs=list(records(state,'songs'))
    state['tables']['vibe_maps']=table(MAP_COLUMNS,definition_rows())
    state['tables']['song_vibe_positions']=table(POSITION_COLUMNS_V17+('sample_count','not_applicable_count'),[
        [song['id'],values[0],None,None,'unmapped',None,0,0] for song in songs for values in MAPS])
    state['tables']['song_vibe_progress']=table(('song_id','completed_passes'),[[song['id'],0] for song in songs])
    from songranker.storage.database_schema import table_columns
    state['tables']['vibe_rounds']=table(table_columns()['vibe_rounds'],[])
    state['user_version']=19
    return state
