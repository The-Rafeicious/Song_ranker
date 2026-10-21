"""Read the shared exposure projections and saved recency for game selectors."""
import random

from songranker.modes.selection import choose_match


def mode_counts(conn, mode):
    counts={r['song_id']: r['appearances'] for r in conn.execute(
        'SELECT song_id,appearances FROM mode_exposures WHERE mode=?', (mode,))}
    if mode in ('standard','blind','public'):
        from songranker.elo_history import tournament_appearances
        for sid,values in tournament_appearances(conn).items():counts[sid]=counts.get(sid,0)+values[mode]
    return counts


def preference_pair(conn, mode, owner=None, rng=random):
    from songranker.services import get_song_full
    if mode not in ('standard', 'blind'):
        raise ValueError('Choose standard or blind voting.')
    previous = previous_preference(conn, mode, owner)
    where = " WHERE TRIM(COALESCE(audio_url,''))!=''" if mode == 'blind' else ''
    pool = [dict(s) for s in conn.execute('SELECT id,elo_score FROM songs'+where+' ORDER BY id')]
    pool=with_catalogue_age(conn,pool)
    pair = choose_match(pool, rng, counts=mode_counts(conn, mode), previous=previous)
    if pair[0] is None:
        return pair
    # Hydrate two songs after the draw rather than all catalogue metadata.
    return tuple(dict(get_song_full(s['id'], conn)) for s in pair)


def vibe_song(conn, *, counts=None, previous=None, rng=random):
    """Read-only Vibe Map draw, ready for the later round controller.

    Read saved completed-pass counts, retaining a one-pass lower bound for
    legacy fully mapped songs. Merely drawing or editing a draft never counts.
    Explicit caller counts can override individual entries.
    """
    from songranker.modes.selection import choose_vibe_song
    from songranker.services import get_song_full
    from songranker.storage.vibe_state import MAPS
    pool = with_catalogue_age(conn, conn.execute('SELECT id FROM songs ORDER BY id'))
    completed = {
        song['id']: max(song['vibe_completed_passes'],int(all(song['vibe_maps'][key]['status'] in ('placed', 'not_applicable')
                            for key, *_ in MAPS)))
        for song in pool}
    if counts is not None:
        completed.update(counts)
    chosen = choose_vibe_song(pool, rng, counts=completed, previous=previous)
    return get_song_full(chosen['id'], conn) if chosen is not None else None


def album_vibe_groups(conn, album_ids):
    """All songs belonging to eligible albums, including unnumbered tracks."""
    from songranker.vibe_maps import with_vibe_maps
    groups = {aid:[] for aid in album_ids}
    rows = [dict(row) for row in conn.execute('SELECT id,album_id FROM songs')
            if row['album_id'] in groups]
    for song in with_vibe_maps(conn,rows):
        groups[song['album_id']].append(song)
    return groups


def previous_preference(conn, mode, owner=None):
    from songranker.modes.preferences import owner_hash
    previous = None
    if owner:
        previous = conn.execute('''SELECT song1_id,song2_id FROM preference_offers
            WHERE owner_hash=? AND mode=? AND origin='ordinary' AND status='answered'
            ORDER BY closed_at DESC,rowid DESC LIMIT 1''', (owner_hash(owner), mode)).fetchone()
    if previous is None:
        from songranker.elo_history import source_sql
        previous = conn.execute(f'SELECT winner_id,loser_id FROM {source_sql(conn)} WHERE mode=? ORDER BY id DESC LIMIT 1', (mode,)).fetchone()
    return tuple(previous) if previous else ()


def previous_guess(conn, token=None):
    row = conn.execute('''SELECT song1_id,song2_id FROM elo_guess_rounds
        WHERE token=? AND completed_at IS NOT NULL''', (token,)).fetchone()
    if row is None:
        row = conn.execute('''SELECT song1_id,song2_id FROM elo_guess_rounds
            WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 1''').fetchone()
    return tuple(row) if row else ()


def shelf_history(conn):
    """One ordered set per completed round; frozen album links retain their meaning."""
    result = []; last = None
    for row in conn.execute('''SELECT DISTINCT r.id,r.completed_at,i.album_id
        FROM album_shelf_rounds r JOIN album_shelf_items i ON i.round_id=r.id
        WHERE r.completed_at IS NOT NULL ORDER BY r.completed_at,r.id,i.album_id'''):
        if row['id'] != last:
            result.append(set()); last = row['id']
        if row['album_id'] is not None:
            result[-1].add(row['album_id'])
    return result


def with_catalogue_age(conn,rows):
    """Read age and vibe metadata for shared adaptive selectors."""
    rows=[dict(row) for row in rows]
    exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='song_details'").fetchone()
    ages=dict(conn.execute('SELECT song_id,added_at FROM song_details')) if exists else {}
    from songranker.vibe_maps import with_vibe_maps
    return with_vibe_maps(conn, [dict(row,added_at=ages.get(row['id'],0)) for row in rows])
