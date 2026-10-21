"""Read-only Vibe Map projections; no scoring or selection weights here."""
from songranker.storage.vibe_state import MAPS


def empty_profile():
    return {values[0]: dict(x=None, y=None, status='unmapped', updated_at=None)
            for values in MAPS}


def map_definitions(conn):
    return [dict(row) for row in conn.execute('SELECT * FROM vibe_maps ORDER BY display_order')]


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
        query = ('SELECT song_id,map_id,x,y,status,updated_at FROM song_vibe_positions '
                 'WHERE song_id IN (' + ','.join('?' for _ in batch) + ')')
        for row in conn.execute(query, batch):
            result[row['song_id']][row['map_id']] = {
                key: row[key] for key in ('x', 'y', 'status', 'updated_at')}
    return result


def with_vibe_maps(conn, rows):
    rows = [dict(row) for row in rows]
    profiles = song_profiles(conn, (row['id'] for row in rows))
    for row in rows:
        row['vibe_maps'] = profiles[row['id']]
    return rows
