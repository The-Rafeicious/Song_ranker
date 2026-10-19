"""Adaptive draws from eligible pools; standard library only, no stored counters."""
import math
import random
import statistics
import sys
import time

EXPLORATION = 0.08
MATCH_FLOOR = 0.20
MATCH_CLOSENESS = 0.80
GUESS_FLOOR = 0.05
GUESS_TARGET_WEIGHT = 0.95
GUESS_WIDTH = 0.10
GUESS_PREVIOUS = 0.25


def nonnegative(value):
    try:
        value = float(value or 0)
        return max(0.0, value) if math.isfinite(value) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def policy(counts):
    """Smooth stage changes relative to this pool's mean, never a hard match quota."""
    values=[nonnegative(c) for c in counts]
    average=statistics.fmean(values) if values else 0
    maturity=average/(average+4)
    floor=MATCH_FLOOR-.05*maturity
    return dict(mean=average,maturity=maturity,exploration=EXPLORATION,
                strength=1+.12*maturity,match_floor=floor,match_close=1-floor,
                bandwidth=1-.15*maturity)


def exposure_probabilities(counts, added_at=None, now=None):
    """Bounded below-average support plus an eight-percent uniform floor.

    Newly added tracks receive at most 20% extra support, decaying over seven days
    and with their evidence. Imported V5 catalogue tracks have added_at=0.
    """
    values=[nonnegative(c) for c in counts]
    if not values:return []
    state=policy(values);average=state['mean'];now=time.time() if now is None else now
    ages=list(added_at) if added_at is not None else [0]*len(values)
    if len(ages)!=len(values):raise ValueError('One added timestamp per pool entry is required.')
    weights=[]
    for count,added in zip(values,ages):
        shortfall=(1+max(0,average-count))**state['strength']
        fresh=.2*math.exp(-max(0,now-nonnegative(added))/(7*86400))/(1+count/(1+average)) if nonnegative(added)>0 else 0
        weights.append(shortfall*(1+fresh))
    total=math.fsum(weights)
    return [EXPLORATION/len(values)+(1-EXPLORATION)*w/total for w in weights]


def pool_probabilities(songs,counts,fallback):
    return exposure_probabilities(counts_for(songs,counts,fallback),[s.get('added_at',0) for s in songs])


def weighted_index(weights, rng=random):
    if not weights or any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError('A finite, nonnegative eligible distribution is required.')
    total = math.fsum(weights)
    if total <= 0:
        raise ValueError('No eligible weighted choice.')
    target = rng.random() * total
    cumulative = 0.0
    last = None
    for index, weight in enumerate(weights):
        if weight:
            last = index
        cumulative += weight
        if target < cumulative:
            return index
    return last  # Floating-point accumulation can finish just short of total.


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position); upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def rating_spread(ratings):
    """IQR, then 10–90% span, then median adjacent distinct-rating gap."""
    values = list(ratings)
    if not values:
        return 0.0
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError('Finite ratings are required.')
    for low, high in ((0.25, 0.75), (0.10, 0.90)):
        span = quantile(values, high) - quantile(values, low)
        if span > 0:
            return span
    distinct = sorted(set(values))
    return statistics.median(b - a for a, b in zip(distinct, distinct[1:])) if len(distinct) > 1 else 0.0


def rated_pool(songs):
    result = []; seen = set()
    for song in songs:
        value = song.get('elo_score')
        if song.get('id') is not None and song['id'] not in seen and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result.append(song); seen.add(song['id'])
    return result


def counts_for(songs, counts, fallback):
    return [counts.get(s['id'], 0) if counts is not None else s.get(fallback, 0) for s in songs]


def choose_match(songs, rng=random, *, counts=None, previous=()):
    """Public Elo distances, explicit per-mode exposures supplied by app callers."""
    songs = rated_pool([dict(s) for s in songs])
    if len(songs) < 2:
        return None, None
    base = pool_probabilities(songs,counts,'matches_played')
    excluded = set(previous) & {s['id'] for s in songs}
    if len(songs) - len(excluded) < 2:
        excluded.clear()
    first_weights = [0 if s['id'] in excluded else w for s, w in zip(songs, base)]
    first = weighted_index(first_weights, rng)
    candidates = [i for i, s in enumerate(songs) if i != first and s['id'] not in excluded]
    stage=policy(counts_for(songs,counts,'matches_played'))
    scale = rating_spread(s['elo_score'] for s in songs)*stage['bandwidth']
    def closeness(i):
        gap = abs(songs[i]['elo_score'] - songs[first]['elo_score'])
        distance = gap / scale if scale else 0
        return 1 / (1 + distance * distance)
    second = candidates[weighted_index([base[i] * (stage['match_floor'] + stage['match_close'] * closeness(i)) for i in candidates], rng)]
    pair = songs[first], songs[second]
    return pair[::-1] if rng.random() < 0.5 else pair


def choose_single(songs, rng=random, *, counts=None, previous=None):
    songs = [dict(s) for s in songs]
    if not songs:
        return None
    base = pool_probabilities(songs,counts,'attempts')
    if len(songs) > 1:
        base = [0 if s['id'] == previous else w for s, w in zip(songs, base)]
    return songs[weighted_index(base, rng)]


def gap_positions(values, tolerance=0.0):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values); position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and abs(values[order[end]] - values[order[position]]) <= tolerance:
            end += 1
        rank = (position + end - 1) / 2 / max(1, len(order) - 1)
        for i in order[position:end]:
            result[i] = rank
        position = end
    return result


def choose_guess_pair(songs, rng=random, *, counts=None, previous=(), target=0.60):
    """Relative gap kernel; the caller freezes the versioned run target at offer time."""
    songs = rated_pool([dict(s) for s in songs])
    if len({s['elo_score'] for s in songs}) < 2:
        return None, None
    if not 0 <= target <= 1:
        raise ValueError('Gap target must be between zero and one.')
    base = pool_probabilities(songs,counts,'guess_attempts')
    previous = set(previous)
    first = weighted_index([w * (GUESS_PREVIOUS if s['id'] in previous else 1) for s, w in zip(songs, base)], rng)
    candidates = [i for i, s in enumerate(songs) if s['elo_score'] != songs[first]['elo_score']]
    gaps = [abs(songs[i]['elo_score'] - songs[first]['elo_score']) for i in candidates]
    tolerance = 16 * sys.float_info.epsilon * max(1.0, max(abs(s['elo_score']) for s in songs))
    positions = gap_positions(gaps, tolerance)
    weights = [base[i] * (GUESS_FLOOR + GUESS_TARGET_WEIGHT * math.exp(-0.5 * ((p - target) / GUESS_WIDTH) ** 2)) *
               (GUESS_PREVIOUS if songs[i]['id'] in previous else 1) for i, p in zip(candidates, positions)]
    second = candidates[weighted_index(weights, rng)]
    return songs[first], songs[second]


def draw_entries(pool, size, rng=random, *, counts=None):
    pool = rated_pool([dict(s) for s in pool])
    if type(size) is not int or size < 1 or len(pool) < size:
        return None
    weights = pool_probabilities(pool,counts,'tournament_entries')
    chosen = []
    for _ in range(size):
        index = weighted_index(weights, rng)
        chosen.append(pool[index]); weights[index] = 0
    return chosen


def tournament_tracks(pool, size, rng=random, *, counts=None):
    """Entry-fair draw, relative noisy seeding, existing champion-first spread."""
    pool = rated_pool([dict(s) for s in pool])
    chosen = draw_entries(pool, size, rng, counts=counts)
    if chosen is None:
        return None
    scale = rating_spread(s['elo_score'] for s in pool)
    chosen.sort(key=lambda s: s['elo_score'] + rng.uniform(-scale / 2, scale / 2), reverse=True)
    champions = [s for s in chosen if s.get('championships', 0) > 0]
    champions.sort(key=lambda s: s['elo_score'] + rng.uniform(-scale / 4, scale / 4), reverse=True)
    return champions + [s for s in chosen if s not in champions]


def shelves_feasible(groups, available, count):
    return len(available) >= count and sum(sorted((len(groups[i]) for i in available), reverse=True)[:count]) >= 10


def draw_shelves(groups, album_counts, track_counts, history, count=0, rng=random):
    """Album-first fairness; frozen ten-track draws with capacity lookahead."""
    if type(count) is not int or count not in (0, 2, 3):
        return None
    groups = {aid: list(tracks) for aid, tracks in groups.items() if len(tracks) >= 2}
    ids = list(groups)
    possible = [n for n in ([count] if count in (2, 3) else [2, 3]) if shelves_feasible(groups, ids, n)]
    if not possible:
        return None
    n = rng.choice(possible)
    history = list(history)
    last = set(history[-1]) if history else set()
    fresh = [aid for aid in ids if aid not in last]
    if shelves_feasible(groups, fresh, n):
        ids = fresh
    all_ids = list(groups)
    base = dict(zip(all_ids, exposure_probabilities([album_counts.get(aid, 0) for aid in all_ids])))
    ages = {}
    for age, albums in enumerate(reversed(history)):
        for aid in albums:
            ages.setdefault(aid, age)
    expected_cycle = len(all_ids) / n
    chosen = []
    for _ in range(n):
        remaining = [aid for aid in ids if aid not in chosen]
        left = n - len(chosen) - 1
        capacity = sum(len(groups[a]) for a in chosen)
        largest = sorted(remaining, key=lambda aid:len(groups[aid]), reverse=True)[:left + 1]
        eligible = [aid for aid in remaining if capacity + len(groups[aid]) +
                    sum(len(groups[a]) for a in [a for a in largest if a != aid][:left]) >= 10]
        weights = [base[aid] * (1.0 if aid not in ages else -math.expm1(-(ages[aid] + 1) / expected_cycle)) for aid in eligible]
        chosen.append(eligible[weighted_index(weights, rng)])
    allocation = dict.fromkeys(chosen, 2)
    while sum(allocation.values()) < 10:
        available = [aid for aid in chosen if allocation[aid] < len(groups[aid])]
        smallest = min(allocation[aid] for aid in available)
        allocation[rng.choice([aid for aid in available if allocation[aid] == smallest])] += 1
    selected = []
    for aid in chosen:
        remaining = list(groups[aid])
        weights = pool_probabilities(remaining,track_counts,'shelf_attempts')
        for _ in range(allocation[aid]):
            index = weighted_index(weights, rng)
            selected.append(remaining.pop(index)); weights.pop(index)
    rng.shuffle(selected)
    return chosen, selected
