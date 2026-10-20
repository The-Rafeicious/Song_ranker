"""Current-pool adaptive selection for V5.1; no stored weights or pair matrix."""
from collections import Counter, defaultdict
import random

from songranker.modes.selection import (pool_probabilities,
                                       weighted_index, policy)
from songranker.modes.selection_data import with_catalogue_age
from songranker.modes.vibe_map import MAPS

RECENCY = .25


def eligible_pool(conn):
    rows = [dict(r) for r in conn.execute("""SELECT id FROM songs
        WHERE TRIM(COALESCE(audio_url,''))!='' ORDER BY id""")]
    return with_catalogue_age(conn, rows)


def counts(conn, mode):
    if mode == 'vibe':
        # Partial reviews count proportionally: one of three maps is 1/3 depth.
        return dict(conn.execute("""SELECT i.song_id,COUNT(*)*1.0/? FROM vibe_placements v
            JOIN judgement_rounds r ON r.id=v.round_id
            JOIN judgement_items i ON i.round_id=r.id AND i.slot=0
            WHERE r.status='answered' AND i.song_id IS NOT NULL GROUP BY i.song_id""", (len(MAPS),)))
    return dict(conn.execute("""SELECT i.song_id,COUNT(*) FROM judgement_items i
        JOIN judgement_rounds r ON r.id=i.round_id WHERE r.status='answered'
        AND r.mode=? AND i.song_id IS NOT NULL GROUP BY i.song_id""", (mode,)))


def draw(conn, mode, owner_hash, size, rng=random):
    pool = eligible_pool(conn)
    if len(pool) < size:
        raise ValueError(f'This mode needs at least {size} songs with saved previews.')
    exposure = counts(conn, mode)
    base = pool_probabilities(pool, exposure, '')
    previous = {r[0] for r in conn.execute("""SELECT song_id FROM judgement_items
        WHERE round_id=(SELECT id FROM judgement_rounds WHERE owner_hash=? AND mode=?
        AND status='answered' ORDER BY id DESC LIMIT 1) AND song_id IS NOT NULL""", (owner_hash, mode))}
    recent = {sid: RECENCY for sid in previous} if len(pool) > size else {}
    weights = [p * recent.get(s['id'], 1) for s, p in zip(pool, base)]
    chosen = []
    artists = defaultdict(set)
    if mode == 'spotlight':
        for row in conn.execute('SELECT song_id,artist_id FROM song_artists'):
            artists[row[0]].add(row[1])
    while len(chosen) < size:
        seen = Counter(a for i in chosen for a in artists[pool[i]['id']])
        current = [0 if i in chosen else w / (1 + sum(seen[a] for a in artists[s['id']]))
                   for i, (s, w) in enumerate(zip(pool, weights))]
        chosen.append(weighted_index(current, rng))
    return [pool[i]['id'] for i in chosen]


def diagnostics(conn, mode):
    pool = eligible_pool(conn); values = counts(conn, mode)
    weights = pool_probabilities(pool, values, '')
    return dict(eligible=len(pool), **policy([values.get(s['id'], 0) for s in pool]),
                recent_factor=RECENCY,
                probabilities=[dict(song_id=s['id'],exposure=values.get(s['id'],0),base_probability=p)
                               for s, p in zip(pool, weights)])
