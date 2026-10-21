"""Read-only Vibe Map projections; no scoring or selection weights here."""
from songranker.storage.vibe_state import MAPS, CENTER_LABELS, LABEL_OVERRIDES


def empty_profile():
    return {values[0]: dict(x=None, y=None, status='unmapped', updated_at=None,
                           sample_count=0, not_applicable_count=0)
            for values in MAPS}


def map_definitions(conn):
    return [dict(dict(row),**CENTER_LABELS.get(row['id'],{}),**LABEL_OVERRIDES.get(row['id'],{})) for row in conn.execute('SELECT * FROM vibe_maps ORDER BY display_order')]


def song_profiles(conn, song_ids):
    """Read only requested songs in bounded batches; every profile has four slots.

    Old offline selection fixtures can have no Vibe Map schema. They receive
    explicit unmapped slots; live schema validation requires the tables.
    """
    ids = list(dict.fromkeys(song_ids))
    result = {sid: empty_profile() for sid in ids}
    if not ids or not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='song_vibe_positions'").fetchone():
        return result
    for start in range(0, len(ids), 500):
        batch = ids[start:start + 500]
        query = ('SELECT * FROM song_vibe_positions '
                 'WHERE song_id IN (' + ','.join('?' for _ in batch) + ')')
        for row in conn.execute(query, batch):
            result[row['song_id']][row['map_id']] = {
                key: row[key] for key in ('x', 'y', 'status', 'updated_at',
                                         'sample_count', 'not_applicable_count')}
    return result


def pass_counts(conn, song_ids):
    ids = list(dict.fromkeys(song_ids));result = dict.fromkeys(ids,0)
    if not ids or not conn.execute("SELECT 1 FROM sqlite_master WHERE name='song_vibe_progress'").fetchone():
        return result
    for start in range(0,len(ids),500):
        batch=ids[start:start+500]
        result.update(conn.execute('SELECT song_id,completed_passes FROM song_vibe_progress WHERE song_id IN ('+
                                   ','.join('?' for _ in batch)+')',batch))
    return result


def with_vibe_maps(conn, rows):
    rows = [dict(row) for row in rows]
    profiles = song_profiles(conn, (row['id'] for row in rows))
    passes = pass_counts(conn, (row['id'] for row in rows))
    for row in rows:
        row['vibe_maps'] = profiles[row['id']]
        row['vibe_completed_passes'] = passes[row['id']]
    return rows
