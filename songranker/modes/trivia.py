"""Field-by-field trivia: one persisted round, with summaries derived by a view."""

import time
import uuid
import re
import json
from urllib.parse import quote
from flask import request, session, jsonify, render_template
from songranker.services import app, get_db_connection, get_song_full, is_close_match
from songranker.catalog import proper_album
from songranker.modes.selection import choose_single
from songranker.modes.selection import mode_counts
from songranker.modes import challenges
from songranker.reports.stats_activity import attach_reports
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import isfinite
from songranker.modes.challenges import records as challenge_records

FIELDS = ("title", "artist", "album")
WEIGHTS = {"title": 0.5, "artist": 0.2, "album": 0.3}


def elapsed(row, now=None):
    """Compute bounded active answer time while excluding paused seconds."""
    if row["started_at"] is None:
        return 0
    end = row["paused_at"] or (time.time() if now is None else now)
    return max(0, min(30, end - row["started_at"] - row["paused_seconds"]))


def round_points(row):
    """Calculate weighted recognition points with time bonuses and album-availability
    normalisation.
    """
    denominator = 1 if row["album_available"] else 0.7
    return round(
        sum(
            WEIGHTS[f]
            / denominator
            * (0.75 + 0.25 * (1 - min(30, max(0, row[f + "_seconds"] or 0)) / 30))
            for f in FIELDS
            if row[f + "_correct"] == 1
        ),
        4,
    )


def score_state(conn):
    """Read current legacy-session Trivia score/streak and stored all-time records."""
    keys = dict(
        conn.execute(
            "SELECT key,value FROM global_stats WHERE key IN ('trivia_high_score','trivia_high_streak')"
        )
    )
    if session.get("trivia_scoring_version") != 2:
        session.update(trivia_score=0, trivia_streak=0, trivia_scoring_version=2)
    return {
        "score": session.get("trivia_score", 0),
        "streak": session.get("trivia_streak", 0),
        "high_score": keys.get("trivia_high_score", 0),
        "high_streak": keys.get("trivia_high_streak", 0),
    }


def current(conn, token):
    """Resolve a Trivia token only when its persisted challenge or legacy session
    belongs to this browser.
    """
    row = conn.execute("SELECT * FROM trivia_rounds WHERE token=?", (token,)).fetchone()
    if row and row["run_id"] is not None:
        return row if challenges.owns_round(conn, row, "trivia") else None
    return row if token == session.get("trivia_round_token") else None


def round_song(conn, row):
    """Read the frozen Trivia answer snapshot, falling back to current song metadata
    for older rounds.
    """
    return (
        json.loads(row["answer_snapshot"])
        if row["answer_snapshot"]
        else get_song_full(row["song_id"], conn)
    )


def freeze_song(conn, song):
    facts = {
        key: song[key]
        for key in (
            "id",
            "title",
            "artist",
            "album",
            "album_id",
            "audio_url",
            "cover_url",
        )
    }
    facts["artist_answers"] = [
        dict(r)
        for r in conn.execute(
            """SELECT a.id,a.name FROM artists a
        JOIN song_artists sa ON sa.artist_id=a.id WHERE sa.song_id=? ORDER BY a.id""",
            (song["id"],),
        )
    ]
    return json.dumps(facts, ensure_ascii=False, separators=(",", ":"))


def actual_answers(conn, song):
    artists = (
        [r["name"] for r in song["artist_answers"]]
        if "artist_answers" in song
        else [
            r["name"]
            for r in conn.execute(
                "SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?",
                (song["id"],),
            )
        ]
    )
    return {
        "title": song["title"],
        "artist": song["artist"] or "",
        "album": song["album"] or "",
    }, artists


def trivia_match(guess, actual, field):
    """Bracketed additions are optional; the meaningful base must still match."""
    if field not in ("title", "album"):
        return is_close_match(guess, actual)

    def base(value):
        # Innermost groups first so nested credits/edition notes are safe.
        """Strip nested bracketed credits and edition notes before comparing a Trivia
        answer.
        """
        value = str(value or "")
        for _ in range(8):
            stripped = re.sub(r"\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}", " ", value)
            if stripped == value:
                break
            value = stripped
        return " ".join(value.split())

    canonical = base(actual)
    return (
        is_close_match(base(guess), canonical)
        if canonical
        else is_close_match(guess, actual)
    )


def grade(conn, row, field, guess, song, seconds):
    """Save a single unanswered available Trivia field's correctness and bounded
    response time.
    """
    if (
        row[field + "_correct"] is not None
        or field == "album"
        and not row["album_available"]
    ):
        return
    answers, artists = actual_answers(conn, song)
    correct = trivia_match(str(guess or ""), answers[field], field)
    if field == "artist":
        correct = correct or any(
            is_close_match(str(guess or ""), artist) for artist in artists
        )
    conn.execute(
        f"UPDATE trivia_rounds SET {field}_correct=?,{field}_seconds=? WHERE id=?",
        (int(correct), min(30, max(0, seconds)), row["id"]),
    )


def payload(conn, row, reveal=False):
    song = round_song(conn, row)
    classic = score_state(conn)
    if row["rules_version"] == challenges.RULES_VERSION:
        state = challenges.progress(conn, row["run_id"], "trivia")
        best = challenges.records(conn, "trivia")
        state.update(high_score=best["best_score"], high_streak=best["best_streak"])
        requirement = challenges.TRIVIA_LABELS[row["streak_rule"]]
    else:
        state = classic
        requirement = "Classic round · any correct answer keeps the streak going."
    result = {
        **state,
        "token": row["token"],
        "song_id": row["song_id"],
        "audio_url": song["audio_url"],
        "rules_version": row["rules_version"],
        "streak_before": row["streak_before"],
        "streak_rule": row["streak_rule"],
        "streak_requirement": requirement,
        "classic_records": {
            "best_score": classic["high_score"],
            "best_streak": classic["high_streak"],
        },
        "album_available": bool(row["album_available"]),
        "started": row["started_at"] is not None,
        "paused": row["paused_at"] is not None,
        "elapsed": elapsed(row),
        "completed": row["completed_at"] is not None,
        "round_points": round_points(row),
        "fields": {
            f: {
                "correct": (
                    None if row[f + "_correct"] is None else bool(row[f + "_correct"])
                ),
                "actual": (
                    song[f] if row[f + "_correct"] is not None or reveal else None
                ),
            }
            for f in FIELDS
            if f != "album" or row["album_available"]
        },
    }
    for field, answer in result["fields"].items():
        if answer["actual"] is None:
            answer["links"] = []
        elif field == "title":
            answer["links"] = (
                [{"name": song["title"], "url": f"/song/{song['id']}"}]
                if row["song_id"] is not None
                else []
            )
        elif field == "album":
            album = conn.execute(
                "SELECT title FROM albums WHERE id=?", (song["album_id"],)
            ).fetchone()
            answer["links"] = (
                [
                    {
                        "name": song["album"],
                        "url": "/album/" + quote(album["title"], safe=""),
                    }
                ]
                if album
                else []
            )
        else:
            answer["links"] = []
            if "artist_answers" in song:
                for artist in song["artist_answers"]:
                    live = conn.execute(
                        "SELECT name FROM artists WHERE id=?", (artist["id"],)
                    ).fetchone()
                    if live:
                        answer["links"].append(
                            {
                                "name": artist["name"],
                                "url": "/artist/" + quote(live["name"], safe=""),
                            }
                        )
            else:
                answer["links"] = [
                    {"name": r["name"], "url": "/artist/" + quote(r["name"], safe="")}
                    for r in conn.execute(
                        "SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?",
                        (song["id"],),
                    )
                ]
    if row["completed_at"] is not None:
        result.update(
            score=row["user_score_after"],
            streak=row["streak_after"],
            game_over=row["streak_after"] == 0,
            cover_url=song["cover_url"],
            streak_passed=(
                bool(row["streak_passed"])
                if row["streak_passed"] is not None
                else row["streak_after"] != 0
            ),
            actual_title=song["title"],
            actual_artist=song["artist"],
            actual_album=song["album"],
        )
    return result


@app.route("/trivia")
def trivia_mode():
    return render_template("trivia_mode.html")


@app.route("/api/trivia/round", methods=["GET"])
def api_trivia_round():
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old = current(conn, session.get("trivia_round_token"))
        if (
            old
            and old["rules_version"] == 1
            and old["completed_at"] is None
            and old["song_id"] is not None
        ):
            return jsonify(payload(conn, old))
        run = challenges.active_run(conn, "trivia")
        pending = challenges.pending_round(conn, run, "trivia")
        if pending:
            conn.commit()
            session["trivia_round_token"] = pending["token"]
            return jsonify(payload(conn, pending))
        pool = conn.execute(
            "SELECT s.id FROM songs s WHERE TRIM(COALESCE(s.audio_url,''))!='' ORDER BY s.id"
        ).fetchall()
        if not pool:
            return jsonify(message="Add songs with audio previews to play Trivia."), 400
        last = conn.execute(
            "SELECT song_id FROM trivia_rounds WHERE run_id=? ORDER BY id DESC LIMIT 1",
            (run["id"],),
        ).fetchone()
        previous = last["song_id"] if last else old["song_id"] if old else None
        from songranker.modes.selection import with_catalogue_age

        pool = with_catalogue_age(conn, pool)
        selected = choose_single(
            pool, counts=mode_counts(conn, "trivia"), previous=previous
        )
        song = get_song_full(selected["id"], conn)
        token = uuid.uuid4().hex
        album = conn.execute("SELECT * FROM albums WHERE id=?", (song["album_id"],)).fetchone()
        available = bool(album and proper_album(dict(album)) and not album["shelves_excluded"])
        state = challenges.progress(conn, run["id"], "trivia")
        conn.execute(
            """INSERT INTO trivia_rounds(token,song_id,album_available,run_id,rules_version,
            streak_before,streak_rule,answer_snapshot) VALUES(?,?,?,?,?,?,?,?)""",
            (
                token,
                song["id"],
                int(available),
                run["id"],
                challenges.RULES_VERSION,
                state["streak"],
                challenges.trivia_rule(state["streak"], available),
                freeze_song(conn, song),
            ),
        )
        conn.commit()
        session["trivia_round_token"] = token
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route("/api/trivia/<token>/start", methods=["POST"])
def api_trivia_start(token):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = current(conn, token)
        if not row:
            return jsonify(message="Round not found."), 404
        if row["completed_at"] is not None:
            return jsonify(message="Round already completed."), 409
        conn.execute(
            "UPDATE trivia_rounds SET started_at=COALESCE(started_at,?) WHERE id=?",
            (time.time(), row["id"]),
        )
        conn.commit()
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route("/api/trivia/<token>/pause", methods=["POST"])
def api_trivia_pause(token):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("paused", True), bool):
        return jsonify(message="Choose whether to pause the round."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = current(conn, token)
        if not row or row["started_at"] is None or row["completed_at"] is not None:
            return jsonify(message="No active round."), 409
        pause = data.get("paused", True)
        now = time.time()
        if pause and row["paused_at"] is None:
            conn.execute(
                "UPDATE trivia_rounds SET paused_at=? WHERE id=?", (now, row["id"])
            )
        elif not pause and row["paused_at"] is not None:
            conn.execute(
                "UPDATE trivia_rounds SET paused_seconds=paused_seconds+?,paused_at=NULL WHERE id=?",
                (now - row["paused_at"], row["id"]),
            )
        conn.commit()
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route("/api/trivia/<token>/field", methods=["POST"])
def api_trivia_field(token):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("guess", ""), str):
        return jsonify(message="Enter a text guess."), 400
    field = data.get("field")
    if field not in FIELDS:
        return jsonify(message="Choose a trivia field."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = current(conn, token)
        if not row or row["started_at"] is None:
            return jsonify(message="Start the round first."), 409
        if field == "album" and not row["album_available"]:
            return jsonify(message="This round has no album guess."), 400
        if row["completed_at"] is None and row[field + "_correct"] is None:
            if row["paused_at"] is not None:
                return jsonify(message="Resume the round first."), 409
            if not str(data.get("guess", "")).strip():
                return jsonify(message="Enter a guess first."), 400
            grade(
                conn, row, field, data.get("guess"), round_song(conn, row), elapsed(row)
            )
            conn.commit()
        return jsonify(payload(conn, current(conn, token)))
    finally:
        conn.close()


@app.route("/api/trivia/<token>/finish", methods=["POST"])
def api_trivia_finish(token):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("guesses") or {}, dict):
        return jsonify(message="Send the round guesses as fields."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = current(conn, token)
        if not row or row["started_at"] is None:
            return jsonify(message="No active round."), 409
        if row["completed_at"] is not None:
            return jsonify(payload(conn, row, True))
        if (
            row["rules_version"] == challenges.RULES_VERSION
            and row["paused_at"] is not None
        ):
            return jsonify(message="Resume the round first."), 409
        song = round_song(conn, row)
        for field in FIELDS:
            grade(
                conn,
                row,
                field,
                (data.get("guesses") or {}).get(field, ""),
                song,
                elapsed(row),
            )
        row = current(conn, token)
        points = round_points(row)
        classic = row["rules_version"] == 1
        passed = (
            any(row[f + "_correct"] == 1 for f in FIELDS)
            if classic
            else challenges.trivia_passed(row)
        )
        state = (
            score_state(conn)
            if classic
            else challenges.progress(conn, row["run_id"], "trivia")
        )
        final_score = round(float(state["score"]) + points, 4)
        streak = int(state["streak"]) + 1 if passed else 0
        now = time.time()
        conn.execute(
            "UPDATE trivia_rounds SET completed_at=?,paused_at=NULL,user_score_after=?,streak_after=?,streak_passed=? WHERE id=?",
            (now, final_score, streak, int(passed), row["id"]),
        )
        if classic:
            for key, value in [
                ("trivia_high_score", final_score),
                ("trivia_high_streak", streak),
            ]:
                conn.execute(
                    "INSERT INTO global_stats(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)",
                    (key, value),
                )
        else:
            challenges.close_on_miss(conn, row["run_id"], passed, now)

        conn.commit()
        if classic:
            session["trivia_score"] = final_score if passed else 0
            session["trivia_streak"] = streak
        return jsonify(payload(conn, current(conn, token), True))
    finally:
        conn.close()


def edit_trivia_totals(conn, song_id, data):
    """Sparse manual deltas preserve the detailed history instead of rewriting it."""
    totals = conn.execute(
        "SELECT * FROM trivia_stats WHERE song_id=?", (song_id,)
    ).fetchone()
    totals = dict(totals) if totals else {}
    names = [
        "new_attempts",
        "title_correct",
        "artist_correct",
        "album_attempts",
        "album_correct",
    ]
    if set(data) - set(names):
        raise ValueError(
            "Use song, artist and album field counts; legacy totals are no longer supported."
        )
    values = {name: int(data.get(name, totals.get(name, 0))) for name in names}
    if (
        any(v < 0 for v in values.values())
        or any(
            values[f + "_correct"] > values["new_attempts"] for f in ("title", "artist")
        )
        or values["album_attempts"] > values["new_attempts"]
        or values["album_correct"] > values["album_attempts"]
    ):
        raise ValueError("Correct counts cannot exceed the available field attempts.")
    raw = conn.execute(
        """SELECT COUNT(*) new_attempts,COALESCE(SUM(title_correct),0) title_correct,
        COALESCE(SUM(artist_correct),0) artist_correct,COALESCE(SUM(album_available),0) album_attempts,
        COALESCE(SUM(album_correct),0) album_correct FROM trivia_rounds WHERE song_id=? AND completed_at IS NOT NULL""",
        (song_id,),
    ).fetchone()
    delta_names = [
        "new_attempts",
        "title_correct",
        "artist_correct",
        "album_attempts",
        "album_correct",
    ]
    deltas = [values[n] - raw[n] for n in delta_names]
    if not any(deltas):
        conn.execute("DELETE FROM trivia_adjustments WHERE song_id=?", (song_id,))
        return
    conn.execute(
        """INSERT INTO trivia_adjustments(song_id,new_attempts_delta,title_correct_delta,artist_correct_delta,album_attempts_delta,album_correct_delta)
        VALUES(?,?,?,?,?,?) ON CONFLICT(song_id) DO UPDATE SET
        new_attempts_delta=excluded.new_attempts_delta,title_correct_delta=excluded.title_correct_delta,
        artist_correct_delta=excluded.artist_correct_delta,album_attempts_delta=excluded.album_attempts_delta,album_correct_delta=excluded.album_correct_delta""",
        [song_id] + deltas,
    )


# Read-only Trivia dashboard. Field totals and saved-round records stay distinct.


def percentage(correct, attempts):
    return round(100 * correct / attempts, 1) if attempts else None


def nonnegative(value):
    """Coerce saved recognition counters to nonnegative integers with zero for
    invalid values.
    """
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def finite(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_recognition_stats(conn, now=None):
    """Use one caller-owned read snapshot, with no history LIMIT on aggregates."""
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
    for row in conn.execute("SELECT * FROM songs"):
        song = dict(row)
        album = albums.get(song["album_id"], {})
        song.update(
            cover_url=album.get("cover_url") or "",
            artist_links=sorted(
                (artists[a] for a in artist_links[song["id"]]),
                key=lambda a: (a["name"].casefold(), a["id"]),
            ),
            album_link=album if proper_album(album) else None,
        )
        songs[song["id"]] = song

    fields = [
        dict(key=key, name=label, kind=kind, attempts=0, correct=0)
        for key, label, kind in [
            ("title", "Song", "song"),
            ("artist", "Artist", "artist"),
            ("album", "Album", "album"),
        ]
    ]
    by_artist, by_album, by_tag = {}, {}, {}
    tested = []

    def add_group(target, identity, attempts, correct, sid):
        """Accumulate recognition attempts, correct answers and distinct tested songs
        for a collection.
        """
        if not attempts:
            return
        group = target.setdefault(identity, dict(attempts=0, correct=0, songs=set()))
        group["attempts"] += attempts
        group["correct"] += correct
        group["songs"].add(sid)

    for row in conn.execute("SELECT * FROM trivia_stats"):
        song = songs.get(row["song_id"])
        if not song:
            continue
        attempts = nonnegative(row["new_attempts"])
        if not attempts:
            continue
        opportunities = dict(
            title=attempts,
            artist=attempts,
            album=min(attempts, nonnegative(row["album_attempts"])),
        )
        correct = {
            key: min(opportunities[key], nonnegative(row[key + "_correct"]))
            for key in FIELDS
        }
        available, earned = sum(opportunities.values()), sum(correct.values())
        song.update(
            attempts=attempts,
            correct=earned,
            available=available,
            accuracy=percentage(earned, available),
            title_missed=attempts - correct["title"],
        )
        tested.append(song)
        for field in fields:
            key = field["key"]
            field["attempts"] += opportunities[key]
            field["correct"] += correct[key]
        for aid in artist_links[song["id"]]:
            add_group(
                by_artist, aid, opportunities["artist"], correct["artist"], song["id"]
            )
        if song["album_link"]:
            add_group(
                by_album,
                song["album_id"],
                opportunities["album"],
                correct["album"],
                song["id"],
            )
        for tid in tag_links[song["id"]]:
            add_group(by_tag, tid, available, earned, song["id"])

    timing = {key: dict(seconds=0.0, count=0) for key in FIELDS}
    outcomes = Counter()
    recent = []
    rounds = week = month = scored_rounds = 0
    total_points = 0.0
    # Stream the entire saved history; only the display list is capped at twenty.
    query = "SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC"
    for raw in conn.execute(query):
        row = dict(raw)
        rounds += 1
        completed = finite(row["completed_at"])
        if completed is not None:
            week += now - 7 * 86400 <= completed <= now
            month += now - 30 * 86400 <= completed <= now
        eligible = [key for key in FIELDS if key != "album" or row["album_available"]]
        complete = all(row[key + "_correct"] in (0, 1) for key in eligible)
        correct_count = sum(row[key + "_correct"] == 1 for key in eligible)
        seconds = {key: finite(row[key + "_seconds"]) for key in eligible}
        timed = all(
            seconds[key] is not None and 0 <= seconds[key] <= 30
            for key in eligible
            if row[key + "_correct"] == 1
        )
        if complete:
            outcome = (
                "perfect"
                if correct_count == len(eligible)
                else "partial" if correct_count else "missed"
            )
        else:
            outcome = "unknown"
        points = None
        if complete and timed:
            # Historical eligibility wins over today's album link or stray data.
            scored = dict(
                row,
                album_correct=row["album_correct"] if row["album_available"] else None,
            )
            scored.update({key + "_seconds": seconds[key] for key in eligible})
            points = round_points(scored)
            total_points += points
            scored_rounds += 1
        outcomes[outcome] += 1
        for key in eligible:
            elapsed = seconds[key]
            if (
                row[key + "_correct"] == 1
                and elapsed is not None
                and 0 <= elapsed <= 30
            ):
                timing[key]["seconds"] += elapsed
                timing[key]["count"] += 1
        if len(recent) < 20:
            date = None
            if completed is not None:
                try:
                    date = datetime.fromtimestamp(completed, timezone.utc).isoformat()
                except (OverflowError, OSError, ValueError):
                    pass
            recent.append(
                dict(
                    row,
                    song=songs.get(row["song_id"]),
                    points=points,
                    outcome=outcome,
                    date=date,
                )
            )

    for field in fields:
        samples = timing[field["key"]]
        field.update(
            missed=field["attempts"] - field["correct"],
            accuracy=percentage(field["correct"], field["attempts"]),
            seconds=(
                round(samples["seconds"] / samples["count"], 1)
                if samples["count"]
                else None
            ),
            timed_answers=samples["count"],
        )

    def category(kind, title, note, source, identities):
        """Build stable recognition accuracy/struggle leaders for one collection
        category.
        """
        rows = []
        for identity, totals in source.items():
            row = identities[identity]
            rows.append(
                dict(
                    row,
                    name=row.get("name", row.get("title", "")),
                    attempts=totals["attempts"],
                    correct=totals["correct"],
                    missed=totals["attempts"] - totals["correct"],
                    tested=len(totals["songs"]),
                    accuracy=percentage(totals["correct"], totals["attempts"]),
                )
            )
        return dict(
            kind=kind,
            title=title,
            note=note,
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

    playable = [s for s in songs.values() if str(s.get("audio_url") or "").strip()]
    tested_ids = {s["id"] for s in tested}
    tested_playable = sum(s["id"] in tested_ids for s in playable)
    correct, available = sum(f["correct"] for f in fields), sum(
        f["attempts"] for f in fields
    )
    records = dict(
        conn.execute(
            "SELECT key,value FROM global_stats WHERE key IN ('trivia_high_score','trivia_high_streak')"
        )
    )
    outcomes_list = [
        dict(
            key=key,
            label=label,
            count=outcomes[key],
            share=percentage(outcomes[key], rounds),
        )
        for key, label in [
            ("perfect", "All fields correct"),
            ("partial", "Some fields correct"),
            ("missed", "No fields correct"),
            ("unknown", "Result unavailable"),
        ]
        if key != "unknown" or outcomes[key]
    ]
    return attach_reports(
        conn,
        dict(
            summary=dict(
                rounds=rounds,
                tested=len(tested),
                correct=correct,
                available=available,
                accuracy=percentage(correct, available),
                best_score=round(finite(records.get("trivia_high_score")) or 0, 2),
                best_streak=nonnegative(records.get("trivia_high_streak")),
                challenge=challenge_records(conn, "trivia"),
                week=week,
                month=month,
                points=round(total_points, 2) if scored_rounds else None,
                scored_rounds=scored_rounds,
                average_points=(
                    round(total_points / scored_rounds, 3) if scored_rounds else None
                ),
            ),
            fields=fields,
            outcomes=outcomes_list,
            recent=recent,
            coverage=dict(
                playable=len(playable),
                tested=tested_playable,
                untested=len(playable) - tested_playable,
                accuracy=percentage(tested_playable, len(playable)),
                without_preview=len(tested) - tested_playable,
            ),
            top_stats=sorted(
                tested,
                key=lambda s: (
                    -s["correct"] / s["available"],
                    -s["attempts"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            bottom_stats=sorted(
                tested,
                key=lambda s: (
                    s["correct"] / s["available"],
                    -s["attempts"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            categories=[
                category(
                    "artist",
                    "Artist answers",
                    "Artist-field accuracy",
                    by_artist,
                    artists,
                ),
                category(
                    "album",
                    "Album answers",
                    "Eligible album-field accuracy",
                    by_album,
                    albums,
                ),
                category(
                    "tag", "Recognition by tag", "All eligible fields", by_tag, tags
                ),
            ],
        ),
        "recognition",
        now=now,
    )


@app.route("/trivia_stats")
def trivia_stats():
    pass
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_recognition_stats(conn)
    finally:
        conn.close()
    return render_template("trivia_stats.html", **data)
