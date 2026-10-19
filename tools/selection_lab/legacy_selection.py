"""Soft selection weights: every eligible track retains a chance."""
import math
import random


def exposure_weight(count):
    return .25 + .75 / math.sqrt(1 + max(0, float(count or 0)))


def choose_match(songs, rng=random):
    if len(songs) < 2:
        return None, None
    first = rng.choices(songs, weights=[exposure_weight(s['matches_played']) for s in songs], k=1)[0]
    pool = [s for s in songs if s['id'] != first['id']]
    weights = []
    for s in pool:
        gap = abs(s['elo_score'] - first['elo_score'])
        # A broad 80-180 Elo shoulder, rather than only near-identical ratings.
        elo = .12 + .88 * math.exp(-((gap - 110) / 145) ** 2)
        counts = 1 / (1 + abs(s['matches_played'] - first['matches_played']) / 12)
        weights.append(exposure_weight(s['matches_played']) * elo * (.35 + .65 * counts))
    second = rng.choices(pool, weights=weights, k=1)[0]
    return (second, first) if rng.random() < .5 else (first, second)


def tournament_tracks(pool, size, rng=random):
    """Weighted draw without replacement, then noisy Elo seeding.

    Prior champions are spread across seed pairs, hence opposite halves, before
    another pair is assigned. Noise keeps the rest of the bracket variable.
    """
    remaining = list(pool)
    chosen = []
    for _ in range(min(size, len(remaining))):
        song = rng.choices(remaining, weights=[exposure_weight(s.get('tournament_matches',0)) for s in remaining], k=1)[0]
        chosen.append(song)
        remaining.remove(song)
    chosen.sort(key=lambda s:s['elo_score'] + rng.uniform(-70,70), reverse=True)
    champions = [s for s in chosen if s.get('championships',0)>0]
    champions.sort(key=lambda s:(s['elo_score']+rng.uniform(-35,35)), reverse=True)
    other = [s for s in chosen if s not in champions]
    # Seeding order places seeds 1/2 in opposite halves, 3/4 in opposite halves,
    # and spreads the top four over quarter-brackets.
    return champions + other
