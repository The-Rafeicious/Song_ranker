"""Adaptive draws from eligible pools; standard library only, no stored counters."""

import math
import random
import statistics
import sys
import time
from songranker.modes.vibe_similarity import SongVibeBias, AlbumVibeBias

EXPLORATION = 0.08
MATCH_FLOOR = 0.20
MATCH_CLOSENESS = 0.80
GUESS_FLOOR = 0.05
GUESS_TARGET_WEIGHT = 0.95
GUESS_WIDTH = 0.10
GUESS_PREVIOUS = 0.25
VIBE_FIRST_PASS = 0.95
VIBE_LATER_PASS = 0.75
VIBE_PREVIOUS = 0.25


def nonnegative(value):
    """Coerce exposure/evidence input to a finite nonnegative float, defaulting
    invalid values to zero.
    """
    try:
        value = float(value or 0)
        return max(0.0, value) if math.isfinite(value) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def policy(counts):
    """Smooth stage changes relative to this pool's mean, never a hard match quota."""
    values = [nonnegative(c) for c in counts]
    average = statistics.fmean(values) if values else 0
    maturity = average / (average + 4)
    floor = MATCH_FLOOR - 0.05 * maturity
    return dict(
        mean=average,
        maturity=maturity,
        exploration=EXPLORATION,
        strength=1 + 0.12 * maturity,
        match_floor=floor,
        match_close=1 - floor,
        bandwidth=1 - 0.15 * maturity,
    )


def exposure_probabilities(counts, added_at=None, now=None):
    """Bounded below-average support plus an eight-percent uniform floor.

    Newly added tracks receive at most 20% extra support, decaying over seven days
    and with their evidence. Imported V5 catalogue tracks have added_at=0.
    """
    values = [nonnegative(c) for c in counts]
    if not values:
        return []
    state = policy(values)
    average = state["mean"]
    now = time.time() if now is None else now
    ages = list(added_at) if added_at is not None else [0] * len(values)
    if len(ages) != len(values):
        raise ValueError("One added timestamp per pool entry is required.")
    weights = []
    for count, added in zip(values, ages):
        shortfall = (1 + max(0, average - count)) ** state["strength"]
        fresh = (
            0.2
            * math.exp(-max(0, now - nonnegative(added)) / (7 * 86400))
            / (1 + count / (1 + average))
            if nonnegative(added) > 0
            else 0
        )
        weights.append(shortfall * (1 + fresh))
    total = math.fsum(weights)
    return [EXPLORATION / len(values) + (1 - EXPLORATION) * w / total for w in weights]


def pool_probabilities(songs, counts, fallback):
    """Compute exposure-aware draw probabilities using mode counts and catalogue age."""
    return exposure_probabilities(
        counts_for(songs, counts, fallback), [s.get("added_at", 0) for s in songs]
    )


def weighted_index(weights, rng=random):
    """Draw an index from a validated nonnegative weight distribution using the
    supplied random source.
    """
    if not weights or any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError("A finite, nonnegative eligible distribution is required.")
    total = math.fsum(weights)
    if total <= 0:
        raise ValueError("No eligible weighted choice.")
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
    """Linearly interpolate a quantile from the sorted eligible rating distribution."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def rating_spread(ratings):
    """IQR, then 10–90% span, then median adjacent distinct-rating gap."""
    values = list(ratings)
    if not values:
        return 0.0
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("Finite ratings are required.")
    for low, high in ((0.25, 0.75), (0.10, 0.90)):
        span = quantile(values, high) - quantile(values, low)
        if span > 0:
            return span
    distinct = sorted(set(values))
    return (
        statistics.median(b - a for a, b in zip(distinct, distinct[1:]))
        if len(distinct) > 1
        else 0.0
    )


def rated_pool(songs):
    """Keep unique songs with finite numeric Elo ratings for preference and
    tournament draws.
    """
    result = []
    seen = set()
    for song in songs:
        value = song.get("elo_score")
        if (
            song.get("id") is not None
            and song["id"] not in seen
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            result.append(song)
            seen.add(song["id"])
    return result


def counts_for(songs, counts, fallback):
    """Resolve per-song mode exposure counts, using the requested row field only when
    no count map exists.
    """
    return [
        counts.get(s["id"], 0) if counts is not None else s.get(fallback, 0)
        for s in songs
    ]


def voting_weights(songs, counts=None, other_counts=None, recent=()):
    """Apply pool-sized recency and each track's own visibility balance to exposure.

    Recent pairs are newest first. Recency fades over sqrt(pool size)/2 matches;
    the newest occurrence controls a track, and small pools recover sooner.
    Visibility pressure uses the signed count gap in units of sqrt(1+lower count),
    independent of the pool mean. Only entries present in other_counts can play
    both modes. Every weight remains positive: these are preferences, not quotas.
    """
    current = counts_for(songs, counts, "matches_played")
    weights = pool_probabilities(songs, counts, "matches_played")
    recovery = max(1.0, math.sqrt(len(songs)) / 2)
    last_seen = {}
    for age, pair in enumerate(recent):
        for sid in pair:
            last_seen.setdefault(sid, age)
    for i, (song, count) in enumerate(zip(songs, current)):
        sid = song["id"]
        if sid in last_seen:
            weights[i] *= (-math.expm1(-(last_seen[sid] + 1) / recovery)) ** 3
        if other_counts is not None and sid in other_counts:
            count, other = nonnegative(count), nonnegative(other_counts[sid])
            gap = (count - other) / math.sqrt(1 + min(count, other))
            weights[i] *= 2 / (1 + math.exp(max(-50, min(50, gap))))
    return weights


def choose_match(songs, rng=random, *, counts=None, previous=(), pair_counts=None,
                 other_counts=None, recent=()):
    """Exposure-fair Elo neighbours with soft recency and per-track mode balance."""
    songs = rated_pool([dict(s) for s in songs])
    if len(songs) < 2:
        return None, None
    base = voting_weights(songs, counts, other_counts, recent)
    excluded = set(previous) & {s["id"] for s in songs}
    if len(songs) - len(excluded) < 2:
        excluded.clear()
    first_weights = [0 if s["id"] in excluded else w for s, w in zip(songs, base)]
    first = weighted_index(first_weights, rng)
    candidates = [
        i for i, s in enumerate(songs) if i != first and s["id"] not in excluded
    ]
    stage = policy(counts_for(songs, counts, "matches_played"))
    scale = rating_spread(s["elo_score"] for s in songs) * stage["bandwidth"]

    def closeness(i):
        """Weight a candidate by its rating distance from the first song relative to
        the pool scale.
        """
        gap = abs(songs[i]["elo_score"] - songs[first]["elo_score"])
        distance = gap / scale if scale else 0
        return 1 / (1 + distance * distance)

    vibe = SongVibeBias(songs)
    second = candidates[
        weighted_index(
            [
                base[i]
                * (stage["match_floor"] + stage["match_close"] * closeness(i))
                * vibe.multiplier(songs[first]["id"], songs[i]["id"])
                * max(.25, 1 / math.sqrt(1 + nonnegative((pair_counts or {}).get(tuple(sorted((songs[first]["id"], songs[i]["id"]))), 0))))
                for i in candidates
            ],
            rng,
        )
    ]
    pair = songs[first], songs[second]
    return pair[::-1] if rng.random() < 0.5 else pair


def choose_single(songs, rng=random, *, counts=None, previous=None):
    """Draw one exposure-weighted song while avoiding the previous song when
    alternatives exist.
    """
    songs = [dict(s) for s in songs]
    if not songs:
        return None
    base = pool_probabilities(songs, counts, "attempts")
    if len(songs) > 1:
        base = [0 if s["id"] == previous else w for s, w in zip(songs, base)]
    return songs[weighted_index(base, rng)]


def vibe_probabilities(songs, *, counts=None, previous=None, now=None):
    """Adaptive draws with extra mass for the least-completed Vibe Map pass.

    Counts are completed Vibe Map rounds, never Elo/Trivia exposures. A caller
    without saved repeat counts supplies the first-pass 0/1 coverage projection.
    Recency is a soft penalty within both distributions, so a lone unfinished
    song retains its priority even if it was the previous draw.
    """
    values = [nonnegative(c) for c in counts_for(songs, counts, "vibe_attempts")]
    if not values:
        return []
    base = exposure_probabilities(values, [s.get("added_at", 0) for s in songs], now)
    base = [
        w * (VIBE_PREVIOUS if s["id"] == previous else 1) for s, w in zip(songs, base)
    ]
    total = math.fsum(base)
    base = [w / total for w in base]
    least = min(values)
    priority = VIBE_FIRST_PASS if least == 0 else VIBE_LATER_PASS
    cohort_total = math.fsum(w for w, count in zip(base, values) if count == least)
    return [
        (1 - priority) * w + (priority * w / cohort_total if count == least else 0)
        for w, count in zip(base, values)
    ]


def choose_vibe_song(songs, rng=random, *, counts=None, previous=None):
    """One unique eligible song; coverage first, no rating or preview requirement."""
    pool = []
    seen = set()
    for row in songs:
        song = dict(row)
        if song.get("id") is not None and song["id"] not in seen:
            pool.append(song)
            seen.add(song["id"])
    if not pool:
        return None
    weights = vibe_probabilities(pool, counts=counts, previous=previous)
    return pool[weighted_index(weights, rng)]


def gap_positions(values, tolerance=0.0):
    """Assign normalised midpoint ranks, treating values within tolerance as tied."""
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while (
            end < len(order)
            and abs(values[order[end]] - values[order[position]]) <= tolerance
        ):
            end += 1
        rank = (position + end - 1) / 2 / max(1, len(order) - 1)
        for i in order[position:end]:
            result[i] = rank
        position = end
    return result


def choose_guess_pair(songs, rng=random, *, counts=None, previous=(), target=0.60):
    """Relative gap kernel; the caller freezes the versioned run target at offer time."""
    songs = rated_pool([dict(s) for s in songs])
    if len({s["elo_score"] for s in songs}) < 2:
        return None, None
    if not 0 <= target <= 1:
        raise ValueError("Gap target must be between zero and one.")
    base = pool_probabilities(songs, counts, "guess_attempts")
    previous = set(previous)
    first = weighted_index(
        [
            w * (GUESS_PREVIOUS if s["id"] in previous else 1)
            for s, w in zip(songs, base)
        ],
        rng,
    )
    candidates = [
        i for i, s in enumerate(songs) if s["elo_score"] != songs[first]["elo_score"]
    ]
    gaps = [abs(songs[i]["elo_score"] - songs[first]["elo_score"]) for i in candidates]
    tolerance = (
        16 * sys.float_info.epsilon * max(1.0, max(abs(s["elo_score"]) for s in songs))
    )
    positions = gap_positions(gaps, tolerance)
    weights = [
        base[i]
        * (
            GUESS_FLOOR
            + GUESS_TARGET_WEIGHT * math.exp(-0.5 * ((p - target) / GUESS_WIDTH) ** 2)
        )
        * (GUESS_PREVIOUS if songs[i]["id"] in previous else 1)
        for i, p in zip(candidates, positions)
    ]
    vibe = SongVibeBias(songs)
    weights = [
        w * vibe.multiplier(songs[first]["id"], songs[i]["id"])
        for w, i in zip(weights, candidates)
    ]
    second = candidates[weighted_index(weights, rng)]
    return songs[first], songs[second]


def draw_entries(pool, size, rng=random, *, counts=None):
    """Select unique exposure-weighted tournament entries with a bounded Vibe
    affinity after the first draw.
    """
    pool = rated_pool([dict(s) for s in pool])
    if type(size) is not int or size < 1 or len(pool) < size:
        return None
    weights = pool_probabilities(pool, counts, "tournament_entries")
    vibe = SongVibeBias(pool)
    chosen = []
    factors = None
    for _ in range(size):
        adjusted = (
            [w * f for w, f in zip(weights, factors)]
            if factors is not None
            else weights
        )
        index = weighted_index(adjusted, rng)
        chosen.append(pool[index])
        weights[index] = 0
        if factors is None:
            factors = [vibe.multiplier(chosen[0]["id"], song["id"]) for song in pool]
    return chosen


def tournament_tracks(pool, size, rng=random, *, counts=None, local_strength=None):
    """Fair entry draw followed by strength seeding; local evidence is bounded.

    Local opponent-adjusted evidence can shift a seed by at most 10% of the
    eligible pool's rating spread. Two-percent jitter preserves near-tie variety.
    Standard mirrored seed positions separate the top two/four seeds until the
    final/semi-finals. This changes neither eligibility nor public ratings.
    """
    pool = rated_pool([dict(s) for s in pool])
    chosen = draw_entries(pool, size, rng, counts=counts)
    if chosen is None:
        return None
    scale = rating_spread(s['elo_score'] for s in pool) or 1.0
    chosen.sort(key=lambda s: s['elo_score'] + scale * .10 *
                max(-1, min(1, (local_strength or {}).get(s['id'], 0))) +
                rng.uniform(-scale * .02, scale * .02), reverse=True)
    return chosen


def preference_evidence(conn):
    """Read pair exposure and local seed evidence without writing ratings.

    Ordinary effective votes count once; all valid saved tournament rounds count
    once, including local brackets. Local seed evidence shrinks each opponent's
    result towards its current Elo expectation with eight neutral observations;
    opponents then contribute equally, so repeating one rivalry cannot dominate.
    """
    from collections import defaultdict
    from songranker.catalog import source_sql
    ratings={r['id']:r['elo_score'] for r in rated_pool([dict(row) for row in conn.execute('SELECT id,elo_score FROM songs')])}
    spread=rating_spread(ratings.values())
    pairs=defaultdict(int)
    local=defaultdict(lambda: [0,0])
    for row in conn.execute('SELECT winner_id,loser_id FROM '+source_sql(conn)+" WHERE origin='ordinary'"):
        a,b=row
        if a in ratings and b in ratings and a!=b:pairs[tuple(sorted((a,b)))]+=1
    for row in conn.execute("""SELECT m.winner_id,m.loser_id,t.scope_type
        FROM tournament_matches m JOIN tournaments t ON t.id=m.tournament_id
        WHERE m.status='completed' AND m.winner_id!=m.loser_id
        AND ((m.winner_id=m.song1_id AND m.loser_id=m.song2_id)
          OR (m.winner_id=m.song2_id AND m.loser_id=m.song1_id))"""):
        a,b,scope=row
        if a not in ratings or b not in ratings:continue
        pairs[tuple(sorted((a,b)))]+=1
        if scope not in ('artist','album'):continue
        for sid,other,won in ((a,b,1),(b,a,0)):
            expected=1/(1+math.exp(max(-35,min(35,(ratings[other]-ratings[sid])/spread)))) if spread else .5
            bucket=local[sid,other];bucket[0]+=won-expected;bucket[1]+=1
    evidence=defaultdict(list)
    for (sid,other),(residual,n) in local.items():evidence[sid].append(2*residual/(n+8))
    return dict(pairs), {sid:statistics.fmean(values) for sid,values in evidence.items()}


def shelves_feasible(groups, available, count):
    """Check whether a remaining album choice can supply the required album count and
    ten tracks.
    """
    return (
        len(available) >= count
        and sum(sorted((len(groups[i]) for i in available), reverse=True)[:count]) >= 10
    )


def draw_shelves(
    groups,
    album_counts,
    track_counts,
    history,
    count=0,
    rng=random,
    *,
    vibe_groups=None,
):
    """Album-first fairness; frozen ten-track draws with capacity lookahead."""
    if type(count) is not int or count not in (0, 2, 3):
        return None
    groups = {aid: list(tracks) for aid, tracks in groups.items() if len(tracks) >= 2}
    ids = list(groups)
    possible = [
        n
        for n in ([count] if count in (2, 3) else [2, 3])
        if shelves_feasible(groups, ids, n)
    ]
    if not possible:
        return None
    n = rng.choice(possible)
    history = list(history)
    last = set(history[-1]) if history else set()
    fresh = [aid for aid in ids if aid not in last]
    if shelves_feasible(groups, fresh, n):
        ids = fresh
    all_ids = list(groups)
    vibe = AlbumVibeBias(
        {aid: (vibe_groups or groups).get(aid, groups[aid]) for aid in all_ids}
    )
    base = dict(
        zip(
            all_ids,
            exposure_probabilities([album_counts.get(aid, 0) for aid in all_ids]),
        )
    )
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
        largest = sorted(remaining, key=lambda aid: len(groups[aid]), reverse=True)[
            : left + 1
        ]
        eligible = [
            aid
            for aid in remaining
            if capacity
            + len(groups[aid])
            + sum(len(groups[a]) for a in [a for a in largest if a != aid][:left])
            >= 10
        ]
        weights = [
            base[aid]
            * (
                1.0
                if aid not in ages
                else -math.expm1(-(ages[aid] + 1) / expected_cycle)
            )
            for aid in eligible
        ]
        if chosen:
            weights = [
                w * vibe.multiplier(chosen[0], aid) for w, aid in zip(weights, eligible)
            ]
        chosen.append(eligible[weighted_index(weights, rng)])
    allocation = dict.fromkeys(chosen, 2)
    while sum(allocation.values()) < 10:
        available = [aid for aid in chosen if allocation[aid] < len(groups[aid])]
        smallest = min(allocation[aid] for aid in available)
        allocation[
            rng.choice([aid for aid in available if allocation[aid] == smallest])
        ] += 1
    selected = []
    for aid in chosen:
        remaining = list(groups[aid])
        weights = pool_probabilities(remaining, track_counts, "shelf_attempts")
        for _ in range(allocation[aid]):
            index = weighted_index(weights, rng)
            selected.append(remaining.pop(index))
            weights.pop(index)
    rng.shuffle(selected)
    return chosen, selected


# Read the shared exposure projections and saved recency for game selectors.


def mode_counts(conn, mode):
    """Read mode exposures and add effective weighted tournament participation to
    voting modes.
    """
    counts = {
        r["song_id"]: r["appearances"]
        for r in conn.execute(
            "SELECT song_id,appearances FROM mode_exposures WHERE mode=?", (mode,)
        )
    }
    if mode in ("standard", "blind", "public"):
        from songranker.catalog import tournament_appearances

        for sid, values in tournament_appearances(conn).items():
            counts[sid] = counts.get(sid, 0) + values[mode]
    return counts


def preference_pair(conn, mode, owner=None, rng=random):
    """Draw a standard/blind pair from eligible songs, then hydrate only the two
    selected records.
    """
    from songranker.services import get_song_full

    if mode not in ("standard", "blind"):
        raise ValueError("Choose standard or blind voting.")
    where = " WHERE TRIM(COALESCE(audio_url,''))!=''" if mode == "blind" else ""
    pool = [
        dict(s)
        for s in conn.execute("SELECT id,elo_score,audio_url FROM songs" + where + " ORDER BY id")
    ]
    pool = with_catalogue_age(conn, pool)
    # Retain about eight recovery timescales; the read horizon grows with the
    # eligible collection instead of becoming a fixed lifetime tuning limit.
    horizon = max(8, math.ceil(4 * math.sqrt(len(rated_pool(pool)))))
    recent = recent_preferences(conn, owner, limit=horizon)
    previous = recent[0] if recent else previous_preference(conn, mode, owner)
    pair_counts, _ = preference_evidence(conn)
    other = mode_counts(conn, "blind" if mode == "standard" else "standard")
    # A track without a preview cannot catch up in Blind, so its Non-blind
    # selection must not be suppressed by an impossible balance target.
    other = {s["id"]: other.get(s["id"], 0) for s in pool
             if str(s.get("audio_url") or "").strip()}
    pair = choose_match(pool, rng, counts=mode_counts(conn, mode), previous=previous,
                        pair_counts=pair_counts, other_counts=other, recent=recent)
    if pair[0] is None:
        return pair
    # Hydrate two songs after the draw rather than all catalogue metadata.
    return tuple(dict(get_song_full(s["id"], conn)) for s in pair)


def vibe_song(conn, *, counts=None, previous=None, rng=random):
    """Read-only Vibe Map draw, ready for the later round controller.

    Read saved completed-pass counts, retaining a one-pass lower bound for
    legacy fully mapped songs. Merely drawing or editing a draft never counts.
    Explicit caller counts can override individual entries.
    """

    from songranker.services import get_song_full
    from songranker.storage.vibe_state import MAPS

    pool = with_catalogue_age(conn, conn.execute("SELECT id FROM songs ORDER BY id"))
    completed = {
        song["id"]: max(
            song["vibe_completed_passes"],
            int(
                all(
                    song["vibe_maps"][key]["status"] in ("placed", "not_applicable")
                    for key, *_ in MAPS
                )
            ),
        )
        for song in pool
    }
    if counts is not None:
        completed.update(counts)
    chosen = choose_vibe_song(pool, rng, counts=completed, previous=previous)
    return get_song_full(chosen["id"], conn) if chosen is not None else None


def album_vibe_groups(conn, album_ids):
    """All songs belonging to eligible albums, including unnumbered tracks."""
    from songranker.vibe_maps import with_vibe_maps

    groups = {aid: [] for aid in album_ids}
    rows = [
        dict(row)
        for row in conn.execute("SELECT id,album_id FROM songs")
        if row["album_id"] in groups
    ]
    for song in with_vibe_maps(conn, rows):
        groups[song["album_id"]].append(song)
    return groups


def recent_preferences(conn, owner=None, limit=128):
    """Read a bounded newest-first song history across both voting visibilities.

    Use the browser's answered ordinary offers when available, including seen
    identities after corrections. Fall back to effective saved results for old
    sessions/imports. Merely preparing an offer does not create played history.
    """
    from songranker.modes.preferences import owner_hash
    from songranker.catalog import source_sql

    rows = []
    if owner:
        rows = conn.execute(
            """SELECT song1_id,song2_id FROM preference_offers
            WHERE owner_hash=? AND origin='ordinary' AND status='answered'
            ORDER BY closed_at DESC,rowid DESC LIMIT ?""",
            (owner_hash(owner), limit),
        ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT winner_id,loser_id FROM " + source_sql(conn) +
            " ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [tuple(row) for row in rows]


def previous_preference(conn, mode, owner=None):
    """Read the owning browser's last answered pair, falling back to the latest
    effective mode result.
    """
    from songranker.modes.preferences import owner_hash

    previous = None
    if owner:
        previous = conn.execute(
            """SELECT song1_id,song2_id FROM preference_offers
            WHERE owner_hash=? AND mode=? AND origin='ordinary' AND status='answered'
            ORDER BY closed_at DESC,rowid DESC LIMIT 1""",
            (owner_hash(owner), mode),
        ).fetchone()
    if previous is None:
        from songranker.catalog import source_sql

        previous = conn.execute(
            f"SELECT winner_id,loser_id FROM {source_sql(conn)} WHERE mode=? ORDER BY id DESC LIMIT 1",
            (mode,),
        ).fetchone()
    return tuple(previous) if previous else ()


def previous_guess(conn, token=None):
    """Read a completed Guesser pair from the supplied round or latest result to
    avoid an immediate repeat.
    """
    row = conn.execute(
        """SELECT song1_id,song2_id FROM elo_guess_rounds
        WHERE token=? AND completed_at IS NOT NULL""",
        (token,),
    ).fetchone()
    if row is None:
        row = conn.execute(
            """SELECT song1_id,song2_id FROM elo_guess_rounds
            WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 1"""
        ).fetchone()
    return tuple(row) if row else ()


def shelf_history(conn):
    """One ordered set per completed round; frozen album links retain their meaning."""
    result = []
    last = None
    for row in conn.execute("""SELECT DISTINCT r.id,r.completed_at,i.album_id
        FROM album_shelf_rounds r JOIN album_shelf_items i ON i.round_id=r.id
        WHERE r.completed_at IS NOT NULL ORDER BY r.completed_at,r.id,i.album_id"""):
        if row["id"] != last:
            result.append(set())
            last = row["id"]
        if row["album_id"] is not None:
            result[-1].add(row["album_id"])
    return result


def with_catalogue_age(conn, rows):
    """Read age and vibe metadata for shared adaptive selectors."""
    rows = [dict(row) for row in rows]
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='song_details'"
    ).fetchone()
    ages = (
        dict(conn.execute("SELECT song_id,added_at FROM song_details"))
        if exists
        else {}
    )
    from songranker.vibe_maps import with_vibe_maps

    return with_vibe_maps(
        conn, [dict(row, added_at=ages.get(row["id"], 0)) for row in rows]
    )
