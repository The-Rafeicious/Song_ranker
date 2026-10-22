"""Guesser round operations, results and detailed statistics."""

from collections import defaultdict
import math
import random
import secrets
import time
from flask import jsonify, render_template, request, session
from songranker.services import app, get_db_connection
from songranker.modes import challenges
from songranker.catalog import special_records, display_song
from songranker.reports.stats_activity import attach_reports
from datetime import datetime, timezone
from math import ceil, isfinite
from songranker.catalog import proper_album
from songranker.modes.challenges import records as challenge_records


@app.route("/elo_guesser")
def elo_guesser():
    return render_template("app_page.html", page="guesser")


@app.route("/elo_guesser_stats")
def guesser_stats():
    pass
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_guesser_stats(
            conn, history_page=request.args.get("history_page", 1, type=int)
        )
    finally:
        conn.close()
    return render_template("guesser_stats.html", **data)


@app.route("/api/elo-guesser/round", methods=["POST"])
def guess_round():
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM elo_guess_rounds WHERE token=? AND completed_at IS NULL",
            (session.get("guess_token", ""),),
        ).fetchone()
        if row and row["run_id"] is not None:
            row = None  # Modern pending rounds are recovered by server-owned run below.
        run = None
        if not row:
            run = challenges.active_run(conn, "guesser")
            row = challenges.pending_round(conn, run, "guesser")
        if row and (
            not display_song(conn, row["song1_id"])
            or not display_song(conn, row["song2_id"])
        ):
            conn.execute("DELETE FROM elo_guess_rounds WHERE id=?", (row["id"],))
            row = None
        if not row:
            run = run or challenges.active_run(conn, "guesser")
            from songranker.modes.selection import choose_guess_pair
            from songranker.modes.selection import mode_counts
            from songranker.modes.selection import previous_guess

            counts = mode_counts(conn, "guesser")
            pool = [
                dict(r)
                for r in conn.execute("SELECT id,elo_score FROM songs ORDER BY id")
                if isinstance(r["elo_score"], (int, float))
                and math.isfinite(r["elo_score"])
            ]
            if len(pool) < 2 or len({s["elo_score"] for s in pool}) < 2:
                return (
                    jsonify(
                        message="Play Standard Vote or Tournament first to build different Elo ratings."
                    ),
                    400,
                )
            state = challenges.progress(conn, run["id"], "guesser")
            target = challenges.guess_target(state["streak"])
            from songranker.modes.selection import with_catalogue_age

            pool = with_catalogue_age(conn, pool)
            first, second = choose_guess_pair(
                pool,
                counts=counts,
                previous=previous_guess(conn, session.get("guess_token")),
                target=target,
            )
            pair = [first, second]
            random.shuffle(pair)
            token = secrets.token_urlsafe(24)
            cur = conn.execute(
                """INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,
                run_id,rules_version,streak_before,target_quantile) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    token,
                    pair[0]["id"],
                    pair[1]["id"],
                    pair[0]["elo_score"],
                    pair[1]["elo_score"],
                    time.time(),
                    run["id"],
                    challenges.RULES_VERSION,
                    state["streak"],
                    target,
                ),
            )
            row = conn.execute(
                "SELECT * FROM elo_guess_rounds WHERE id=?", (cur.lastrowid,)
            ).fetchone()
        conn.commit()
        session["guess_token"] = row["token"]
        return jsonify(
            token=row["token"],
            rules_version=row["rules_version"],
            streak_before=row["streak_before"],
            songs=[
                display_song(conn, row["song1_id"]),
                display_song(conn, row["song2_id"]),
            ],
            records=guess_game_records(conn, row),
        )
    finally:
        conn.close()


def guess_game_records(conn, row):
    result = special_records(conn)[1]["guesser"]
    if row["rules_version"] == challenges.RULES_VERSION:
        state = (
            challenges.progress(conn, row["run_id"], "guesser")
            if row["completed_at"] is None
            else dict(streak=row["streak_after"], score=row["user_score_after"])
        )
        result.update(
            streak=state["streak"],
            score=state["score"],
            best_streak=result["challenge"]["best_streak"],
        )
    result["rules_version"] = row["rules_version"]
    return result


def guess_result(conn, row):
    correct = int((row["chosen_slot"] == 1) == (row["elo1"] > row["elo2"]))
    return dict(
        correct=bool(correct),
        points=correct,
        ratings=[row["elo1"], row["elo2"]],
        rules_version=row["rules_version"],
        records=guess_game_records(conn, row),
    )


@app.route("/api/elo-guesser/answer", methods=["POST"])
def guess_answer():
    data = request.get_json(silent=True)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("token"), str)
        or not isinstance(data.get("song_id"), int)
        or isinstance(data["song_id"], bool)
    ):
        return jsonify(message="Choose one of the offered songs."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM elo_guess_rounds WHERE token=?", (data["token"],)
        ).fetchone()
        if (
            not row
            or (
                row["run_id"] is not None
                and not challenges.owns_round(conn, row, "guesser")
            )
            or (row["run_id"] is None and row["token"] != session.get("guess_token"))
        ):
            return (
                jsonify(message="This question is no longer active. Load a new pair."),
                409,
            )
        if row["completed_at"] is not None:
            if row["rules_version"] == 1:
                return jsonify(message="This answer is already saved."), 409
            saved_id = row["song1_id"] if row["chosen_slot"] == 1 else row["song2_id"]
            if data["song_id"] != saved_id:
                return (
                    jsonify(
                        message="A different answer is already saved for this pair."
                    ),
                    409,
                )
            return jsonify(guess_result(conn, row))
        if not row["song1_id"] or not row["song2_id"]:
            return jsonify(message="A track was deleted. Load a new pair."), 409
        if data["song_id"] not in (row["song1_id"], row["song2_id"]):
            return jsonify(message="Choose an offered track."), 400
        slot = 1 if data["song_id"] == row["song1_id"] else 2
        now = time.time()
        correct = int((slot == 1) == (row["elo1"] > row["elo2"]))
        if row["rules_version"] == challenges.RULES_VERSION:
            state = challenges.progress(conn, row["run_id"], "guesser")
            conn.execute(
                "UPDATE elo_guess_rounds SET chosen_slot=?,completed_at=?,streak_after=?,user_score_after=? WHERE id=?",
                (
                    slot,
                    now,
                    state["streak"] + 1 if correct else 0,
                    state["score"] + correct,
                    row["id"],
                ),
            )
            challenges.close_on_miss(conn, row["run_id"], correct, now)
        else:
            conn.execute(
                "UPDATE elo_guess_rounds SET chosen_slot=?,completed_at=? WHERE id=?",
                (slot, now, row["id"]),
            )

        conn.commit()
        return jsonify(
            guess_result(
                conn,
                conn.execute(
                    "SELECT * FROM elo_guess_rounds WHERE id=?", (row["id"],)
                ).fetchone(),
            )
        )
    finally:
        conn.close()


# Read-only Elo Guesser dashboard, using saved comparisons rather than today's Elo.


HISTORY_SIZE = 10
GAP_BANDS = (
    (0, 25, "Under 25"),
    (25, 50, "25–<50"),
    (50, 100, "50–<100"),
    (100, 200, "100–<200"),
    (200, None, "200+"),
)


def finite(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def percentage(right, total):
    return round(100 * right / total, 1) if total else None


def saved_date(value):
    stamp = finite(value)
    if stamp is None:
        return None
    try:
        return dict(
            seconds=stamp, iso=datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        )
    except (ValueError, OverflowError, OSError):
        return None


def totals(rows):
    rows = list(rows)
    graded = [r for r in rows if r["correct"] is not None]
    right = sum(r["correct"] for r in graded)
    return dict(
        rounds=len(rows),
        graded=len(graded),
        correct=right,
        wrong=len(graded) - right,
        unknown=len(rows) - len(graded),
        accuracy=percentage(right, len(graded)),
    )


def build_guesser_stats(conn, now=None, history_page=1):
    """One caller-owned SELECT snapshot; aggregate all history, page only its display."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM artists")}
    albums = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM albums")}
    tags = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM genres")}
    artist_links, tag_links = defaultdict(set), defaultdict(set)
    for row in conn.execute("SELECT song_id,artist_id FROM song_artists"):
        if row["artist_id"] in artists:
            artist_links[row["song_id"]].add(row["artist_id"])
    for row in conn.execute("SELECT song_id,genre_id FROM song_genres"):
        if row["genre_id"] in tags:
            tag_links[row["song_id"]].add(row["genre_id"])
    songs = {}
    for raw in conn.execute("SELECT * FROM songs"):
        song = dict(raw)
        album = albums.get(song.get("album_id"), {})
        song.update(
            cover_url=album.get("cover_url") or "",
            artist_links=sorted(
                (artists[a] for a in artist_links[song["id"]]),
                key=lambda a: (a["name"].casefold(), a["id"]),
            ),
            album_link=album if proper_album(album) else None,
            attempts=0,
            correct=0,
            missed=0,
        )
        songs[song["id"]] = song

    def identity(sid):
        return songs.get(sid) or dict(
            id=None,
            title="Removed track" if sid is None else "Track unavailable",
            cover_url="",
            artist_links=[],
            album_link=None,
        )

    rounds = []
    # No tokens, pending answers or LIMIT: the public report contains finished comparisons only.
    for raw in conn.execute(
        """SELECT id,song1_id,song2_id,elo1,elo2,chosen_slot,completed_at,rules_version,streak_after
                               FROM elo_guess_rounds WHERE completed_at IS NOT NULL"""
    ):
        row = dict(raw)
        elo1, elo2 = finite(row["elo1"]), finite(row["elo2"])
        gap = abs(elo1 - elo2) if elo1 is not None and elo2 is not None else None
        valid = (
            elo1 is not None
            and elo2 is not None
            and gap is not None
            and isfinite(gap)
            and gap > 0
            and row["chosen_slot"] in (1, 2)
            and not (row["song1_id"] is not None and row["song1_id"] == row["song2_id"])
        )
        row.update(
            elo1=elo1,
            elo2=elo2,
            gap=gap if valid else None,
            correct=int((row["chosen_slot"] == 1) == (elo1 > elo2)) if valid else None,
            date=saved_date(row["completed_at"]),
            streak=None,
            first=identity(row["song1_id"]),
            second=identity(row["song2_id"]),
        )
        row["chosen"] = (
            row["first"]
            if row["chosen_slot"] == 1
            else row["second"] if row["chosen_slot"] == 2 else None
        )
        rounds.append(row)
    rounds.sort(
        key=lambda r: ((r["date"] or {}).get("seconds", float("-inf")), r["id"])
    )

    streak = best = miss_run = longest_miss = 0
    days = set()
    for row in rounds:
        if row["date"] is not None:
            if row["rules_version"] == 2:
                row["streak"] = row["streak_after"]
                miss_run = 0 if row["correct"] else miss_run + 1
                longest_miss = max(longest_miss, miss_run)
            elif row["correct"] is None:
                streak = miss_run = 0
            else:
                streak = streak + 1 if row["correct"] else 0
                miss_run = 0 if row["correct"] else miss_run + 1
                best, longest_miss = max(best, streak), max(longest_miss, miss_run)
                row["streak"] = streak
            if row["date"]["seconds"] <= now:
                days.add(row["date"]["iso"][:10])
        if row["correct"] is not None:
            for sid in set((row["song1_id"], row["song2_id"])):
                if sid in songs:
                    songs[sid]["attempts"] += 1
                    songs[sid]["correct"] += row["correct"]
                    songs[sid]["missed"] += 1 - row["correct"]

    summary = totals(rounds)
    undated = sum(r["date"] is None for r in rounds)
    summary.update(
        best_streak=best,
        current_streak=(
            streak
            if not undated and (not rounds or rounds[-1]["correct"] is not None)
            else None
        ),
        longest_miss=longest_miss,
        active_days=len(days),
        undated=undated,
        challenge=challenge_records(conn, "guesser"),
    )
    latest = list(reversed(rounds))
    windows = [dict(title="Latest 10 guesses", **totals(latest[:10]))]
    for days_back in (7, 30):
        window = [
            r
            for r in rounds
            if r["date"] and now - days_back * 86400 <= r["date"]["seconds"] <= now
        ]
        windows.append(dict(title="Last " + str(days_back) + " days", **totals(window)))

    scored = [r for r in rounds if r["correct"] is not None]
    gaps = []
    for low, high, label in GAP_BANDS:
        group = [
            r for r in scored if low <= r["gap"] and (high is None or r["gap"] < high)
        ]
        gaps.append(dict(label=label, low=low, high=high, **totals(group)))
    correct_gaps = [r["gap"] for r in scored if r["correct"]]
    wrong_gaps = [r["gap"] for r in scored if not r["correct"]]
    gap_summary = dict(
        correct_average=(
            round(sum(correct_gaps) / len(correct_gaps), 1) if correct_gaps else None
        ),
        wrong_average=(
            round(sum(wrong_gaps) / len(wrong_gaps), 1) if wrong_gaps else None
        ),
        closest_correct=round(min(correct_gaps), 1) if correct_gaps else None,
        widest_wrong=round(max(wrong_gaps), 1) if wrong_gaps else None,
    )
    choices = [
        dict(
            slot=slot,
            label=label,
            share=percentage(
                sum(r["chosen_slot"] == slot for r in scored), len(scored)
            ),
            **totals(r for r in scored if r["chosen_slot"] == slot)
        )
        for slot, label in ((1, "First card"), (2, "Second card"))
    ]

    tested = [s for s in songs.values() if s["attempts"]]
    for song in tested:
        song["accuracy"] = percentage(song["correct"], song["attempts"])
    eligible = {
        s["id"]
        for s in songs.values()
        if isinstance(s.get("elo_score"), (int, float))
        and finite(s["elo_score"]) is not None
    }
    if len({songs[sid]["elo_score"] for sid in eligible}) < 2:
        eligible.clear()
    tested_ids = {s["id"] for s in tested}
    covered = len(eligible & tested_ids)
    coverage = dict(
        eligible=len(eligible),
        tested=covered,
        untested=len(eligible) - covered,
        share=percentage(covered, len(eligible)),
        other_tested=len(tested_ids - eligible),
    )

    def category(kind, title, identities, links):
        groups = defaultdict(lambda: dict(attempts=0, correct=0, tested=0))
        for song in tested:
            for identity_id in links(song):
                group = groups[identity_id]
                group["attempts"] += song["attempts"]
                group["correct"] += song["correct"]
                group["tested"] += 1
        rows = [
            dict(
                identities[sid],
                name=identities[sid].get("name", identities[sid].get("title", "")),
                missed=g["attempts"] - g["correct"],
                accuracy=percentage(g["correct"], g["attempts"]),
                **g
            )
            for sid, g in groups.items()
        ]
        return dict(
            kind=kind,
            title=title,
            best=sorted(
                rows,
                key=lambda r: (
                    -r["correct"] / r["attempts"],
                    -r["attempts"],
                    r["name"].casefold(),
                    r["id"],
                ),
            )[:5],
            missed=sorted(
                (r for r in rows if r["missed"]),
                key=lambda r: (
                    -r["missed"],
                    -r["attempts"],
                    r["name"].casefold(),
                    r["id"],
                ),
            )[:5],
        )

    pair_groups = defaultdict(list)
    for row in scored:
        if row["song1_id"] in songs and row["song2_id"] in songs:
            pair_groups[tuple(sorted((row["song1_id"], row["song2_id"])))].append(row)
    pairs = []
    for (first, second), rows in pair_groups.items():
        if len(rows) < 2:
            continue
        # Catalogue order is stable; it does not claim to be a saved card position or winner.
        pair = sorted(
            (songs[first], songs[second]),
            key=lambda s: (s["title"].casefold(), s["id"]),
        )
        pairs.append(
            dict(
                first=pair[0],
                second=pair[1],
                average_gap=round(sum(r["gap"] for r in rows) / len(rows), 1),
                **totals(rows)
            )
        )
    pairs.sort(
        key=lambda r: (
            -r["rounds"],
            -r["wrong"],
            r["first"]["title"].casefold(),
            r["second"]["title"].casefold(),
            r["first"]["id"],
            r["second"]["id"],
        )
    )
    pages = max(1, ceil(len(rounds) / HISTORY_SIZE))
    try:
        history_page = max(1, min(int(history_page), pages))
    except (TypeError, ValueError, OverflowError):
        history_page = 1
    start = (history_page - 1) * HISTORY_SIZE
    return attach_reports(
        conn,
        dict(
            summary=summary,
            windows=windows,
            gaps=gaps,
            gap_summary=gap_summary,
            choices=choices,
            coverage=coverage,
            top_tracks=sorted(
                tested,
                key=lambda s: (
                    -s["correct"] / s["attempts"],
                    -s["attempts"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            practice_tracks=sorted(
                (s for s in tested if s["missed"]),
                key=lambda s: (
                    s["correct"] / s["attempts"],
                    -s["attempts"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            categories=[
                category(
                    "artist", "Artist records", artists, lambda s: artist_links[s["id"]]
                ),
                category(
                    "album",
                    "Album records",
                    albums,
                    lambda s: [s["album_id"]] if s["album_link"] else [],
                ),
                category("tag", "Tag records", tags, lambda s: tag_links[s["id"]]),
            ],
            pairs=pairs[:5],
            history=latest[start : start + HISTORY_SIZE],
            history_page=history_page,
            history_pages=pages,
            history_start=start + 1 if rounds else 0,
            history_end=min(start + HISTORY_SIZE, len(rounds)),
        ),
        "guesser",
        now=now,
    )
