"""Read-only independent Elo projections and evidence for public comparisons."""


def song_mode_ratings(conn):
    result = {r[0]: {mode: dict(elo=1200.0, matches=0, tournament_matches=0)
                    for mode in ('standard', 'blind')} for r in conn.execute('SELECT id FROM songs')}
    # Compatibility for old report fixtures and the pre-migration snapshot check.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='preference_mode_ratings' AND type='table'").fetchone():
        for row in conn.execute('SELECT * FROM preference_mode_ratings'):
            result[row['song_id']][row['mode']] = {key: row[key] for key in ('elo','matches','tournament_matches')}
    return result


def coverage(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='preference_effective'").fetchone():
        return dict(excluded=0, public_anchored=False)
    excluded = conn.execute('''SELECT COUNT(*) FROM preference_effective e
        LEFT JOIN songs w ON w.id=e.winner_id LEFT JOIN songs l ON l.id=e.loser_id
        WHERE e.active=1 AND (e.mode NOT IN ('standard','blind') OR w.id IS NULL OR l.id IS NULL OR w.id=l.id)''').fetchone()[0]
    state = conn.execute('SELECT baseline_kind FROM preference_replay_state WHERE id=1').fetchone()
    return dict(excluded=excluded, public_anchored=bool(state and state[0] == 'legacy_anchor'))


def comparison_report(conn, songs):
    modes = song_mode_ratings(conn)
    from songranker.catalog import voting_records
    votes = voting_records(conn)
    both, counts = [], {}
    for mode in ('standard', 'blind'):
        values = [row[mode] for row in modes.values()]
        counts[mode] = dict(tested=sum(row['matches'] > 0 for row in values),
                            votes=sum(row['matches'] for row in values) // 2,
                            tournament_votes=sum(row['tournament_matches'] for row in values) // 2,
                            effective_votes=sum(row[mode+'_matches'] for row in votes.values()) / 2)
    for song in songs:
        streams = modes[song['id']]
        if all(votes[song['id']][mode+'_matches'] >= 3 for mode in ('standard', 'blind')):
            both.append({**song, 'mode_ratings': streams,
                         'elo_difference': streams['blind']['elo'] - streams['standard']['elo']})
    return dict(counts=counts, qualifying=len(both), coverage=coverage(conn),
        higher_blind=sorted((s for s in both if s['elo_difference'] > 0), key=lambda s: (-s['elo_difference'], s['id']))[:5],
        higher_standard=sorted((s for s in both if s['elo_difference'] < 0), key=lambda s: (s['elo_difference'], s['id']))[:5])
