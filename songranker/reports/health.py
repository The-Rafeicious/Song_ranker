"""Stage-relative diagnostics, not a target that rewrites or normalises Elo."""

import math
from statistics import fmean, pstdev
from songranker.modes import selection as S
from songranker.modes.selection import with_catalogue_age
from songranker.modes.selection import mode_counts
from songranker.modes.selection import previous_guess
from songranker.modes.selection import shelf_history
from songranker.modes.challenge_rules import guess_target


def label(text, level):
    """Represent a short health label with its semantic display level."""
    return dict(label=text, level=level)


def exposure_health(values, spread=None):
    """Describe exposure balance, evidence stage and population-relative reference
    bands.
    """
    values = list(values)
    n = len(values)
    mean = fmean(values) if n else 0
    relative = pstdev(values) / (1 + mean) if n else 0
    if not n:
        balance = label("Unavailable", "new")
    elif not mean:
        balance = label("New competition", "new")
    elif mean < 1:
        balance = label("Building evidence", "new")
    elif relative > 1:
        balance = label("Poor balance", "bad")
    elif relative > 0.6:
        balance = label("Uneven", "medium")
    elif relative > 0.35:
        balance = label("Fair", "medium")
    elif relative > 0.15:
        balance = label("Good", "good")
    else:
        balance = label("Excellent", "good")
    # Approximate K32, equal-rating random-result IQR. Diagnostic reference only:
    # a consistent preference signal can legitimately produce a wider range.
    expected = 1.349 * 16 * math.sqrt(mean)
    low, high = 0.5 * expected, 2 * expected
    if spread is None:
        rating = label("Not applicable", "new")
    elif mean < 2:
        rating = label("Still settling", "new")
    elif spread < low:
        rating = label("Compact", "medium")
    elif spread > high:
        rating = label("Wide preference spread", "medium")
    else:
        rating = label("Within reference", "good")
    return dict(
        balance=balance,
        elo=rating,
        mean=round(mean, 3),
        dispersion=round(relative, 3),
        reference_low=round(low, 1),
        reference_high=round(high, 1),
        stage="Starting" if mean < 1 else "Developing" if mean < 8 else "Established",
    )


def coverage_health(right, total):
    """Classify a covered-versus-eligible ratio into a shared health label."""
    if not total:
        return label("Unavailable", "new")
    part = right / total
    return (
        label("Excellent", "good")
        if part >= 0.95
        else (
            label("Good", "good")
            if part >= 0.8
            else (
                label("Fair", "medium")
                if part >= 0.6
                else label("Limited", "medium") if part >= 0.3 else label("Poor", "bad")
            )
        )
    )


# Read-only selector diagnostics using the production pools, counts and kernels.


def normalize(weights):
    """Normalise diagnostic weights to probabilities, returning zeros for an
    empty-weight distribution.
    """
    total = math.fsum(weights)
    return [w / total if total else 0.0 for w in weights]


def build_selection_health(conn, context=None):
    context = context or {}
    songs = [
        dict(r)
        for r in conn.execute(
            "SELECT id,title,album_id,elo_score,audio_url FROM songs ORDER BY id"
        )
    ]
    songs = with_catalogue_age(conn, songs)
    albums = {r["id"]: dict(r) for r in conn.execute("SELECT id,title FROM albums")}
    valid = S.rated_pool(songs)
    previews = [s for s in songs if str(s.get("audio_url") or "").strip(" ")]
    preview_ids = {s["id"] for s in previews}
    tagged = conn.execute(
        "SELECT COUNT(DISTINCT sg.song_id) FROM song_genres sg JOIN genres g ON g.id=sg.genre_id JOIN songs s ON s.id=sg.song_id"
    ).fetchone()[0]
    from songranker.modes.shelves import shelf_pool

    groups = shelf_pool(conn)
    shelf_ids = {s["id"] for tracks in groups.values() for s in tracks}
    history = shelf_history(conn)
    album_counts = {
        r["album_id"]: r["appearances"]
        for r in conn.execute("SELECT * FROM shelf_album_exposures")
    }
    run = None
    if context.get("challenge_owner"):
        run = conn.execute(
            "SELECT * FROM challenge_runs WHERE owner=? AND mode='guesser' AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
            (context["challenge_owner"],),
        ).fetchone()
    streak = 0
    if run:
        from songranker.modes.challenges import progress

        streak = progress(conn, run["id"], "guesser")["streak"]
    last_trivia = None
    if context.get("challenge_owner"):
        active = conn.execute(
            "SELECT id FROM challenge_runs WHERE owner=? AND mode='trivia' AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
            (context["challenge_owner"],),
        ).fetchone()
        if active:
            last_trivia = conn.execute(
                "SELECT song_id FROM trivia_rounds WHERE run_id=? ORDER BY id DESC LIMIT 1",
                (active["id"],),
            ).fetchone()
    if last_trivia is None and context.get("trivia_round_token"):
        last_trivia = conn.execute(
            "SELECT song_id FROM trivia_rounds WHERE token=?",
            (context["trivia_round_token"],),
        ).fetchone()
    last_guess = set(previous_guess(conn, context.get("guess_token")))
    from songranker.catalog import tournament_appearances

    first_rounds = tournament_appearances(conn)
    pools = []

    def pool(
        key,
        label,
        rows,
        counts,
        *,
        previous=(),
        rule="base",
        recent=(),
        other_counts=None,
        unit="tracks",
        kind="song",
        ready=True
    ):
        """Project an eligible draw pool into production-rule probabilities and
        exposure diagnostics.
        """
        rows = list(rows)
        n = len(rows)
        values = [S.nonnegative(counts.get(s["id"], 0)) for s in rows]
        base = S.exposure_probabilities(values, [s.get("added_at", 0) for s in rows])
        weights = list(base)
        excluded = set(previous)
        if rule == "pair":
            if n - len(excluded & {s["id"] for s in rows}) < 2:
                excluded.clear()
            adjusted = S.voting_weights(rows, counts, other_counts, recent)
            weights = [0 if s["id"] in excluded else w for s, w in zip(rows, adjusted)]
        elif rule == "entries":
            weights = S.voting_weights(rows, counts, other_counts, recent, fallback="tournament_entries")
        elif rule == "single" and n > 1:
            weights = [0 if s["id"] in excluded else w for s, w in zip(rows, base)]
        elif rule == "guess":
            weights = [
                w * (S.GUESS_PREVIOUS if s["id"] in excluded else 1)
                for s, w in zip(rows, base)
            ]
        probabilities = normalize(weights) if ready else [0.0] * n
        mean = fmean(values) if n else None
        entries = [
            dict(
                id=s["id"],
                name=s.get("title", ""),
                album=albums.get(s.get("album_id"), {}).get("title", ""),
                exposure=c,
                base_probability=b,
                probability=p,
                cooling=s["id"] in excluded and p == 0,
            )
            for s, c, b, p in zip(rows, values, base, probabilities)
        ]
        eligible = sum(p > 0 for p in probabilities)

        spread = (
            S.rating_spread(s["elo_score"] for s in rows)
            if rows and "elo_score" in rows[0]
            else None
        )
        health = exposure_health(values, spread)
        pools.append(
            dict(
                health=health,
                policy=S.policy(values),
                first_round_exposures=(
                    sum(first_rounds.get(s["id"], {}).get(key, 0) for s in rows)
                    if key in ("standard", "blind")
                    else None
                ),
                key=key,
                label=label,
                kind=kind,
                unit=unit,
                ready=ready,
                eligible=n,
                available=eligible,
                tested=sum(c > 0 for c in values),
                untested=sum(c == 0 for c in values),
                coverage=100 * sum(c > 0 for c in values) / n if n else None,
                total=sum(values),
                mean=mean,
                below=sum(c < mean for c in values) if n else 0,
                spread=(
                    S.rating_spread(s["elo_score"] for s in rows)
                    if rows and "elo_score" in rows[0]
                    else None
                ),
                min_share=min((p for p in probabilities if p > 0), default=None),
                max_share=max(probabilities, default=None),
                effective=(
                    1 / math.fsum(p * p for p in probabilities)
                    if any(probabilities)
                    else None
                ),
                rows=sorted(
                    entries,
                    key=lambda r: (-r["probability"], r["name"].casefold(), r["id"]),
                ),
            )
        )

    for key, label in [("standard", "Non-blind voting"), ("blind", "Blind voting")]:
        rows = [s for s in valid if key == "standard" or s["id"] in preview_ids]
        recent = S.recent_preferences(conn, context.get("preference_owner"),
                                      limit=max(8, math.ceil(4 * math.sqrt(len(rows)))))
        other = mode_counts(conn, "blind" if key == "standard" else "standard")
        pool(
            key,
            label,
            rows,
            mode_counts(conn, key),
            previous=recent[0] if recent else (),
            recent=recent,
            other_counts={s["id"]: other.get(s["id"], 0) for s in rows if s["id"] in preview_ids},
            rule="pair",
            ready=len(rows) >= 2,
        )
    pool(
        "trivia",
        "Trivia",
        previews,
        mode_counts(conn, "trivia"),
        previous=tuple(last_trivia) if last_trivia else (),
        rule="single",
        ready=bool(previews),
    )
    for key, label, blind in [("tournament", "Tournament · non-blind", False),
                              ("tournament_blind", "Tournament · blind", True)]:
        rows = [s for s in valid if not blind or s["id"] in preview_ids]
        evidence = S.tournament_selection_evidence(conn, rows, blind, scope="global")
        pool(key, label, rows, rule="entries", ready=len(rows) >= 8, **evidence)
    pool(
        "guesser",
        "Elo Guesser",
        valid,
        mode_counts(conn, "guesser"),
        previous=last_guess,
        rule="guess",
        ready=len({s["elo_score"] for s in valid}) >= 2,
    )
    pool(
        "shelves",
        "Album Shelves · albums",
        [dict(id=aid, title=albums[aid]["title"]) for aid in groups],
        album_counts,
        kind="album",
        unit="albums",
        ready=bool(groups),
    )
    possible = [n for n in (2, 3) if S.shelves_feasible(groups, list(groups), n)]
    if not possible:
        pools[-1]["ready"] = False
        for row in pools[-1]["rows"]:
            row["probability"] = 0
        pools[-1].update(available=0, min_share=None, max_share=None, effective=None)

    def coverage(label, count):
        """Describe one eligibility count relative to the full catalogue with
        coverage health.
        """
        return dict(
            label=label,
            count=count,
            total=len(songs),
            percent=100 * count / len(songs) if songs else None,
            health=coverage_health(count, len(songs)),
        )

    has_details = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='song_details'"
    ).fetchone()
    bad = (
        conn.execute(
            "SELECT COUNT(*) FROM song_details WHERE preview_bad=1"
        ).fetchone()[0]
        if has_details
        else 0
    )
    return dict(
        preview_flags=bad,
        total=len(songs),
        quality=[
            coverage("Preview URLs present", len(previews)),
            coverage("Tagged tracks", tagged),
            coverage("Finite Elo", len(valid)),
            coverage("Shelves-eligible tracks", len(shelf_ids)),
        ],
        pools=pools,
        weights=dict(
            exploration=S.EXPLORATION,
            shortfall=1 - S.EXPLORATION,
            match_floor=S.MATCH_FLOOR,
            match_close=S.MATCH_CLOSENESS,
            guess_floor=S.GUESS_FLOOR,
            guess_target=S.GUESS_TARGET_WEIGHT,
            guess_width=S.GUESS_WIDTH,
            previous=S.GUESS_PREVIOUS,
        ),
        challenge=dict(
            current_run=bool(run),
            streak=streak,
            target=guess_target(streak),
            samples=[
                dict(streak=n, target=guess_target(n)) for n in (0, 10, 25, 50, 100)
            ],
        ),
        shelves=dict(
            albums=len(groups),
            tracks=len(shelf_ids),
            formats=possible,
            formats_share=100 / len(possible) if possible else None,
            last_albums=len(history[-1]) if history else 0,
            cycles=[dict(size=n, cycle=len(groups) / n) for n in possible],
        ),
    )
