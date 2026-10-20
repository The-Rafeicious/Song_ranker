"""Read-only V5.1 projections: raw opportunity denominators and adaptive support.

Every query runs in its caller's read snapshot. There are no materialized song
totals, descriptor grids, pair matrices, cached percentages or scheduled rewrites.
"""
import math
import statistics

from songranker.modes.judgements import MODES, available, mode_key, result, songs_for
from songranker.modes.vibe_map import MAPS
from songranker.modes.judgement_selection import diagnostics


def rate(n, d): return 100*n/d if d else None


def overview(conn, mode):
    mode = mode_key(mode)
    eligible = conn.execute("SELECT COUNT(*) FROM songs WHERE TRIM(COALESCE(audio_url,''))!=''").fetchone()[0]
    if not available(conn):
        return dict(mode=mode,name=MODES[mode].NAME,color=MODES[mode].COLOR,rounds=0,recent_skips=0,
                    offered_songs=0,tested_songs=0,eligible_songs=eligible,coverage=None if not eligible else 0,
                    eligible_tested=0,still_to_try=eligible,active_days=0)
    counts = dict(conn.execute('SELECT status,COUNT(*) FROM judgement_rounds WHERE mode=? GROUP BY status', (mode,)))
    row = conn.execute("""SELECT COUNT(*) offers,COUNT(DISTINCT i.song_id) tested,
        COUNT(DISTINCT CASE WHEN TRIM(COALESCE(s.audio_url,''))!='' THEN s.id END) eligible_tested
        FROM judgement_items i JOIN judgement_rounds r ON r.id=i.round_id
        LEFT JOIN songs s ON s.id=i.song_id WHERE r.mode=? AND r.status='answered'""", (mode,)).fetchone()
    days = conn.execute("SELECT COUNT(DISTINCT date(closed_at,'unixepoch')) FROM judgement_rounds WHERE mode=? AND status='answered'", (mode,)).fetchone()[0]
    return dict(mode=mode,name=MODES[mode].NAME,color=MODES[mode].COLOR,rounds=counts.get('answered',0),
                recent_skips=counts.get('skipped',0),offered_songs=row['offers'],tested_songs=row['tested'],
                eligible_songs=eligible,eligible_tested=row['eligible_tested'],still_to_try=eligible-row['eligible_tested'],
                coverage=rate(row['eligible_tested'],eligible),active_days=days)


def spotlight_records(conn):
    if not available(conn): return {}
    return {r['song_id']:dict(r) for r in conn.execute("""SELECT i.song_id,COUNT(*) offers,
        SUM(a.points) points,AVG(a.points) mean_points,
        SUM(3.0*a.points/(12+2.0*a.points)) support_total,
        AVG(3.0*a.points/(12+2.0*a.points)) mean_support,
        SUM(a.points=0) zero_shares
        FROM spotlight_allocations a JOIN judgement_items i ON i.round_id=a.round_id AND i.slot=a.slot
        JOIN judgement_rounds r ON r.id=a.round_id WHERE r.mode='spotlight'
        AND r.status='answered' AND i.song_id IS NOT NULL GROUP BY i.song_id""")}


def descriptor_records(conn):
    if not available(conn): return dict(vibe={})
    return {mode:dict(conn.execute("""SELECT i.song_id,COUNT(*) FROM judgement_items i
        JOIN judgement_rounds r ON r.id=i.round_id WHERE r.mode=? AND r.status='answered'
        AND i.song_id IS NOT NULL GROUP BY i.song_id""", (mode,))) for mode in ('vibe')}


def overall_sources(conn):
    return dict(spotlight=spotlight_records(conn),descriptors=descriptor_records(conn),
                overview={mode:overview(conn,mode) for mode in MODES})


def reliability(n, values):
    observed = [v for v in values if v>0]
    reference = statistics.fmean(observed) if observed else 0
    return n/(n+reference) if n>0 and reference>0 else 0


def spotlight_stats(conn):
    rows = spotlight_records(conn)
    n = [r['offers'] for r in rows.values()]
    for row in rows.values():
        row['evidence'] = reliability(row['offers'],n)
        row['adjusted_support'] = .5 + (row['mean_support']-.5)*row['evidence']
    ordered = sorted(rows.values(),key=lambda r:(-r['adjusted_support'],-r['offers'],r['song_id']))
    rounds = conn.execute("SELECT COUNT(*) FROM judgement_rounds WHERE mode='spotlight' AND status='answered'").fetchone()[0]
    return dict(points_shared=rounds*12,leaders=ordered[:50],songs=rows,
                neutral_points=3,points_per_round=12,
                interpretation='Shares are relative to the other songs offered; ties are retained. One offer is one observation.')


def vibe_stats(conn):
    grouped = [dict(r) for r in conn.execute("""SELECT v.map_key,i.song_id,COUNT(*) placements,
        AVG(v.x) x,AVG(v.y) y,AVG(v.x*v.x) xx,AVG(v.y*v.y) yy
        FROM vibe_placements v JOIN judgement_rounds r ON r.id=v.round_id
        JOIN judgement_items i ON i.round_id=r.id AND i.slot=0
        WHERE r.status='answered' AND i.song_id IS NOT NULL GROUP BY v.map_key,i.song_id""")]
    maps = []
    for definition in MAPS:
        rows = [r for r in grouped if r['map_key']==definition['key']]
        for row in rows:
            row.update(evidence=reliability(row['placements'],[r['placements'] for r in rows]),
                       spread=math.sqrt(max(0,row['xx']-row['x']**2)+max(0,row['yy']-row['y']**2)))
            row.pop('xx');row.pop('yy')
        heat = [[0]*5 for _ in range(5)]
        for r in conn.execute("""SELECT v.x,v.y,COUNT(*) n FROM vibe_placements v
            JOIN judgement_rounds r ON r.id=v.round_id WHERE r.status='answered' AND v.map_key=?
            GROUP BY v.x,v.y""", (definition['key'],)): heat[r['y']][r['x']] = r['n']
        placements = sum(sum(row) for row in heat)
        maps.append(dict(definition,placements=placements,tested_songs=len(rows),
                         heatmap=heat,songs=sorted(rows,key=lambda r:(-r['placements'],r['song_id']))))
    reviewed = conn.execute("SELECT COUNT(*) FROM judgement_rounds WHERE mode='vibe' AND status='answered' AND themes_reviewed=1").fetchone()[0]
    themes = [dict(r) for r in conn.execute("""SELECT t.tag_key,t.tag_id,t.label,COUNT(*) selections
        FROM vibe_themes t JOIN judgement_rounds r ON r.id=t.round_id WHERE r.status='answered'
        GROUP BY t.tag_key,t.tag_id,t.label ORDER BY selections DESC,t.tag_key""")]
    for row in themes: row['reviewed_round_share'] = rate(row['selections'],reviewed)
    return dict(maps=maps,theme_reviewed_rounds=reviewed,themes=themes,
                interpretation='Independent descriptions of heard previews. Missing maps/themes are unknown, not centre/zero values.')


def build_judgement_stats(conn, mode, *, page=1, page_size=20):
    mode = mode_key(mode)
    if type(page) is not int or page<1 or type(page_size) is not int or not 1<=page_size<=50:
        raise ValueError('Use a positive history page and 1 to 50 records per page.')
    summary = overview(conn,mode)
    if not available(conn): return dict(summary=summary,history=[],history_page=1,history_pages=1)
    details = {'spotlight':spotlight_stats,'vibe':vibe_stats}[mode](conn)
    pages = max(1,math.ceil(summary['rounds']/page_size));page=min(page,pages)
    rows = conn.execute("""SELECT * FROM judgement_rounds WHERE mode=? AND status='answered'
        ORDER BY closed_at DESC,id DESC LIMIT ? OFFSET ?""",(mode,page_size,(page-1)*page_size)).fetchall()
    history = [dict(result(conn,r),songs=songs_for(conn,r['id'])) for r in rows]
    # Tokens authorize browser receipts and do not belong in public history.
    for row in history: row.pop('token')
    weights = diagnostics(conn,mode);weights.pop('probabilities')
    from songranker.reports.stats_activity import attach_reports
    return attach_reports(conn,dict(summary=summary,details=details,history=history,
        history_page=page,history_pages=pages,history_page_size=page_size,selection=weights),mode)
