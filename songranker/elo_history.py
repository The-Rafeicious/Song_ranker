"""Read-only public Elo feed; ordinary vote/exposure views keep their meaning."""
from math import ceil


def source_sql(conn):
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='preference_effective' AND type='view'").fetchone():
        return """(SELECT e.id,e.winner_id,e.loser_id,e.mode,e.created_at,
            p.winner_before,p.winner_after,p.loser_before,p.loser_after,
            e.origin,e.rating_weight,e.tournament_id,e.tournament_match_id,e.revision,
            CASE WHEN e.revision>0 THEN 'Corrected'
             WHEN p.winner_before IS NOT o.winner_before OR p.winner_after IS NOT o.winner_after
               OR p.loser_before IS NOT o.loser_before OR p.loser_after IS NOT o.loser_after
             THEN 'Recalculated' ELSE '' END history_note
            FROM preference_effective e JOIN preference_events o ON o.id=e.id
            LEFT JOIN preference_rating_projection p ON p.event_id=e.id
            WHERE e.active=1 AND e.mode IN ('standard','blind'))"""
    return "(SELECT h.*,'ordinary' origin,1.0 rating_weight,NULL tournament_id,NULL tournament_match_id,'' history_note FROM history h)"


def filters(mode='all', origin='all'):
    mode = mode if mode in ('standard', 'blind') else 'all'
    origin = origin if origin in ('ordinary', 'tournament') else 'all'
    return mode, origin


def summary(conn):
    row = conn.execute(f"""SELECT COUNT(*) total,
        COALESCE(SUM(h.origin='tournament'),0) tournament,
        COALESCE(SUM(h.mode='blind'),0) blind,
        COALESCE(SUM(h.mode='standard'),0) standard,
        COALESCE(SUM(h.origin='tournament' AND h.mode='standard'),0) tournament_standard,
        COALESCE(SUM(h.origin='tournament' AND h.mode='blind'),0) tournament_blind
        FROM {source_sql(conn)} h JOIN songs w ON w.id=h.winner_id
        JOIN songs l ON l.id=h.loser_id WHERE h.winner_id!=h.loser_id""").fetchone()
    result = dict(row)
    result['ordinary'] = result['total'] - result['tournament']
    result['tournament_share'] = 100 * result['tournament'] / result['total'] if result['total'] else None
    return result


def page(conn, mode='all', origin='all', number=1, size=50, reader=None):
    from songranker.services import fetch_match_history
    reader = reader or fetch_match_history
    mode, origin = filters(mode, origin)
    total = conn.execute(f"""SELECT COUNT(*) FROM {source_sql(conn)} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.winner_id!=h.loser_id AND (?='all' OR h.mode=?)
        AND (?='all' OR (?='tournament')=(h.origin='tournament'))""", (mode, mode, origin, origin)).fetchone()[0]
    pages = max(1, ceil(total / size))
    try:
        number = max(1, min(int(number), pages))
    except (ValueError, TypeError, OverflowError):
        number = 1
    rows = reader(conn, limit=size, offset=(number-1)*size, mode=mode, origin=origin)
    return dict(history=rows, history_mode=mode, history_origin=origin, history_page=number,
                history_pages=pages, history_total=total, history_start=(number-1)*size+1 if total else 0,
                history_end=min(number*size, total), elo_summary=summary(conn))


def tournament_appearances(conn):
    """Effective first-round evidence per participant, using saved Elo influence."""
    source=source_sql(conn)
    query=f"""SELECT song_id,mode,SUM(rating_weight) appearances FROM (
        SELECT h.winner_id song_id,h.mode,h.rating_weight FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.origin='tournament' AND h.winner_id!=h.loser_id
        UNION ALL
        SELECT h.loser_id song_id,h.mode,h.rating_weight FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.origin='tournament' AND h.winner_id!=h.loser_id
    ) GROUP BY song_id,mode"""
    result={}
    for row in conn.execute(query):
        counts=result.setdefault(row['song_id'],dict(standard=0,blind=0,public=0))
        if row['mode'] in ('standard','blind'):
            counts[row['mode']]+=row['appearances'];counts['public']+=row['appearances']
    return result
