"""Read-only tournament shadow check. python tools/validate_v4_elo.py /path/to/backup.db"""
from collections import Counter
from pathlib import Path
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preference_state import calculate_new_elo


def check(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        songs = {r['id']: dict(r) for r in conn.execute('SELECT * FROM songs')}
        artists = {sid: set() for sid in songs}
        for r in conn.execute('SELECT * FROM song_artists'):
            artists[r['song_id']].add(r['artist_id'])
        ordinary = [dict(r) for r in conn.execute('SELECT * FROM history')]
        first = [dict(r) for r in conn.execute('''SELECT m.*,t.scope_type,t.is_blind FROM tournament_matches m
            JOIN tournaments t ON t.id=m.tournament_id WHERE m.status='completed'
            AND m.round_number=1 AND m.match_type='bracket' ''')]
    finally:
        conn.close()
    def usable(r):
        return r['winner_id'] in songs and r['loser_id'] in songs and r['winner_id'] != r['loser_id']
    ordinary = [r for r in ordinary if usable(r)]
    first = [r for r in first if usable(r)]
    events = [(r.get('created_at') or '', 0, r['id'], r) for r in ordinary]
    events += [(r.get('played_at') or '', 1, r['id'], r) for r in first]
    events.sort(key=lambda row: row[:3])
    ratings = {}
    max_transfers = {}
    for policy in ('ordinary_only', 'all_first_full', 'restricted_half'):
        values = dict.fromkeys(songs, 1200.0)
        largest = 0
        for _, tournament, _, r in events:
            if tournament and policy == 'ordinary_only':
                continue
            weight = 0.5 if tournament and policy == 'restricted_half' and r['scope_type'] != 'global' else 1
            w, l = r['winner_id'], r['loser_id']
            before = values[w]
            values[w], values[l] = calculate_new_elo(values[w], values[l], 32 * weight)
            if tournament:
                largest = max(largest, values[w] - before)
            assert abs(sum(values.values()) - 1200 * len(values)) < 1e-7
        ratings[policy] = values
        max_transfers[policy] = largest
    def movement(policy):
        diffs = [abs(ratings[policy][sid] - ratings['ordinary_only'][sid]) for sid in songs]
        return dict(mean_absolute_change=sum(diffs) / len(diffs), max_absolute_change=max(diffs),
                    span=max(ratings[policy].values()) - min(ratings[policy].values()),
                    max_first_round_transfer=max_transfers[policy])
    def concentration(rows):
        return dict(matches=len(rows), shared_artist=sum(bool(artists[r['winner_id']] & artists[r['loser_id']]) for r in rows),
                    shared_album=sum(songs[r['winner_id']]['album_id'] is not None and
                    songs[r['winner_id']]['album_id'] == songs[r['loser_id']]['album_id'] for r in rows))
    # Stress a narrow repeated preference; no placement boost or range-dependent K.
    stress = {}
    for weight in (1, 0.5):
        a = b = 1200.0
        for _ in range(100):
            na, nb = calculate_new_elo(a, b, 32 * weight)
            assert 0 < na - a <= 32 * weight and abs(na + nb - 2400) < 1e-9
            a, b = na, nb
        stress[str(weight)] = dict(winner=a, loser=b, span=a-b)
    assert stress['0.5']['span'] < stress['1']['span']
    restricted = [r for r in first if r['scope_type'] != 'global']
    # First-round-only policy bounds an entrant to one rated comparison per bracket.
    appearances = Counter((r['tournament_id'], sid) for r in first for sid in (r['winner_id'], r['loser_id']))
    assert max(appearances.values(), default=0) <= 1
    return dict(ordinary=concentration(ordinary), first_round=concentration(first), restricted=concentration(restricted),
                full=movement('all_first_full'), half=movement('restricted_half'), repeated_pair_100=stress,
                invariants=dict(zero_sum=True, max_one_rated_vote_per_entrant_per_bracket=True,
                                ordinary_k=32, restricted_event_influence=0.5),
                scope='Shadow replay only; historical tournament votes are never backfilled into live Elo.',
                limitation='Observed changes are sensitivity checks, not proof of preference accuracy or elimination of selection bias.')


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1]), indent=2))
