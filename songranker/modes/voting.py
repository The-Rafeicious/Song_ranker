"""Standard/blind voting, match history and detailed voting statistics."""

from flask import render_template, request, session, jsonify, redirect
from songranker.services import app, get_db_connection, fetch_match_history
from songranker.reports.stats_activity import attach_reports, coverage_milestone
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from math import ceil, isfinite
from statistics import median, mean, pstdev
from songranker.catalog import proper_album, versus_metadata


@app.route("/game")
def index():
    if request.args.get("mode") == "guesser":
        return redirect("/elo_guesser")
    return render_template("app_page.html", page="standard")


def _preference_error(error):
    """Return a preference failure with its HTTP status and any already-saved
    idempotent result.
    """
    payload = {"message": str(error)}
    if getattr(error, "saved_result", None) is not None:
        payload["saved_result"] = error.saved_result
    return jsonify(payload), error.status


@app.route("/api/vote", methods=["POST"])
def api_vote():
    from songranker.modes.preferences import save_vote, PreferenceError

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message="Submit a valid vote object."), 400
    conn = get_db_connection()
    try:
        return jsonify(save_vote(conn, session.get("preference_owner"), data))
    except PreferenceError as error:
        return _preference_error(error)
    finally:
        conn.close()


@app.route("/api/matchup")
def api_matchup():
    import secrets
    from songranker.modes.preferences import get_offer, PreferenceError
    from songranker.modes.selection import preference_pair

    owner = session.get("preference_owner")
    if not owner:
        owner = secrets.token_urlsafe(32)
        session["preference_owner"] = owner
    mode = request.args.get("mode", "standard")
    conn = get_db_connection()
    try:
        payload = get_offer(
            conn, owner, mode, lambda: preference_pair(conn, mode, owner)
        )
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response
    except PreferenceError as error:
        return _preference_error(error)
    finally:
        conn.close()


@app.route("/history")
def history():
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        from songranker.catalog import page

        history_data = page(
            conn,
            mode=request.args.get("mode"),
            origin=request.args.get("origin"),
            number=request.args.get("page", 1),
            reader=fetch_match_history,
        )
    finally:
        conn.close()
    return render_template("history.html", **history_data)


@app.route("/voting_stats")
def voting_stats():
    pass
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_voting_stats(
            conn,
            history_mode=request.args.get("history_mode", "all"),
            history_page=request.args.get("history_page", 1),
            history_origin=request.args.get("history_origin", "all"),
        )
        return render_template("voting_stats.html", **data)
    finally:
        conn.close()


# Read-only standard/blind voting report. No migrations or counter writes.


HISTORY_SIZE = 10
MODES = ("standard", "blind")


@app.route("/api/voting-replay")
def voting_replay():
    """Return a read-only public-Elo timeline, optionally focused on one track."""
    raw = request.args.get("song_id")
    song_id = request.args.get("song_id", type=int)
    if raw is not None and (song_id is None or song_id < 1):
        return jsonify(error="Choose a valid song."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        if song_id is not None and not conn.execute("SELECT 1 FROM songs WHERE id=?", (song_id,)).fetchone():
            return jsonify(error="Song not found."), 404
        return jsonify(build_elo_replay(conn, song_id))
    finally:
        conn.close()


def build_elo_replay(conn, song_id=None):
    """Build compact visible changes from saved public projections in event order.

    Replay the current collection from persisted seeds/legacy anchors, respecting
    cutoff, effective corrections and manual overrides. Never recalculate ratings
    with today's Elo rules. Missing snapshots are omitted explicitly; an unmatched
    endpoint is labelled as current saved ratings, never an opponent's points.
    The sorted index updates only affected tracks; quiet matches emit no frame.
    """
    from bisect import bisect_left, insort
    from songranker.catalog import source_sql

    songs = {r["id"]: dict(r) for r in conn.execute("SELECT id,title,album_id,elo_score,audio_url FROM songs")}
    albums = {r["id"]: dict(r) for r in conn.execute("SELECT id,title,cover_url FROM albums")}
    artists = defaultdict(list)
    for row in conn.execute("SELECT sa.song_id,a.id,a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id ORDER BY a.name,a.id"):
        artists[row["song_id"]].append(dict(id=row["id"], name=row["name"]))
    metadata = {}
    for sid, song in songs.items():
        album = albums.get(song["album_id"], {})
        metadata[sid] = dict(id=sid, title=song["title"], audio_url=song.get("audio_url") or "", cover_url=album.get("cover_url") or "",
                             artist_links=artists[sid], album_link=dict(title=album["title"]) if proper_album(album) else None)
    settings = conn.execute("SELECT * FROM preference_replay_state WHERE id=1").fetchone()
    cutoff = settings["cutoff_event_id"] if settings else 0
    seeds = {r["song_id"]: finite(r["elo"]) for r in conn.execute("SELECT song_id,elo FROM preference_rating_seeds")}
    events = [dict(row) for row in conn.execute("SELECT * FROM " + source_sql(conn) + " WHERE id>? ORDER BY id", (cutoff,))]
    # Seeds normally cover every track. Old imported records can instead retain
    # their first known before-value; unplayed records retain their saved value.
    first = {}
    for event in events:
        for role in ("winner", "loser"):
            value = finite(event.get(role + "_before"))
            if value is not None:
                first.setdefault(event[role + "_id"], value)
    ratings = {sid: seeds.get(sid) if seeds.get(sid) is not None else first.get(sid, finite(song["elo_score"])) for sid, song in songs.items()}
    ratings = {sid: value for sid, value in ratings.items() if value is not None and finite(songs[sid]["elo_score"]) is not None}
    def key(sid):
        """Deterministic score/title/ID ordering for tied leaderboard positions."""
        return (-ratings[sid], songs[sid]["title"].casefold(), sid)
    ordered = sorted(key(sid) for sid in ratings)
    def change(sid, value):
        """Replace one saved rating without re-sorting the entire collection."""
        if sid in ratings:
            ordered.pop(bisect_left(ordered, key(sid)))
        ratings[sid] = value
        insort(ordered, key(sid))
    def snapshot(kind, event=None, changes=(), ordinal=0):
        """Capture five leaders or two neighbours on each side of the centred song."""
        frame = dict(kind=kind, board=[dict(id=row[2], elo=ratings[row[2]]) for row in ordered[:5]],
                     changes=list(changes), ordinal=ordinal, event_id=event.get("id") if event else None,
                     time=(saved_date(event.get("created_at")) or {}).get("iso") if event else None,
                     mode=event.get("mode") if event else None, origin=event.get("origin") if event else None)
        if song_id in ratings:
            position = bisect_left(ordered, key(song_id))
            frame["focus"] = dict(id=song_id, elo=ratings[song_id],
                                  rank=bisect_left(ordered, (-ratings[song_id], "", -1)) + 1)
            frame["board"] = [dict(id=ordered[i][2], elo=ratings[ordered[i][2]],
                                   rank=bisect_left(ordered, (-ratings[ordered[i][2]], "", -1)) + 1,
                                   slot=2 + i - position)
                              for i in range(max(0, position - 2), min(len(ordered), position + 3))]
        elif song_id is not None:
            frame["board"] = []
        return frame
    def visible(frame):
        """Keep only changes to the leaders or the focused song and its nearby standings."""
        return (frame.get("focus"), frame["board"]) if song_id is not None else [(r["id"], r["elo"]) for r in frame["board"]]
    frames = [snapshot("start")]
    omitted = 0
    overrides = [dict(r) for r in conn.execute("SELECT * FROM preference_rating_overrides WHERE after_event_id>=? ORDER BY after_event_id,id", (cutoff,))]
    steps = [(e["id"], 0, e) for e in events] + [(o["after_event_id"], 1, o) for o in overrides]
    ordinal = 0
    for _, adjustment, event in sorted(steps, key=lambda item: (item[0], item[1], item[2]["id"])):
        changes = []
        if adjustment:
            sid, value = event["song_id"], finite(event["new_elo"])
            if sid not in ratings or value is None:
                continue
            changes = [dict(id=sid, before=ratings[sid], after=value)]
            change(sid, value)
            frame = snapshot("adjustment", event, changes, ordinal)
        else:
            ordinal += 1
            w, l = event["winner_id"], event["loser_id"]
            values = [finite(event.get(k)) for k in ("winner_before", "winner_after", "loser_before", "loser_after")]
            if w == l or w not in ratings or l not in ratings or any(v is None for v in values):
                omitted += 1
                continue
            wb, wa, lb, la = values
            # Surface discontinuities as anchors, without assigning them to a vote.
            if abs(ratings[w] - wb) > 1e-7 or abs(ratings[l] - lb) > 1e-7:
                change(w, wb)
                change(l, lb)
                anchor = snapshot("anchor", event, ordinal=ordinal - 1)
                if visible(anchor) != visible(frames[-1]):
                    frames.append(anchor)
            change(w, wa)
            change(l, la)
            changes = [dict(id=w, before=wb, after=wa, opponent_id=l), dict(id=l, before=lb, after=la, opponent_id=w)]
            frame = snapshot("vote", event, changes, ordinal)
        focus_change = song_id is not None and any(c["id"] == song_id for c in changes)
        if visible(frame) != visible(frames[-1]) or focus_change:
            frames.append(frame)
    reconciled = False
    for sid, song in songs.items():
        value = finite(song["elo_score"])
        if value is not None and (sid not in ratings or abs(ratings[sid] - value) > 1e-7):
            change(sid, value)
            reconciled = True
    final = snapshot("current", events[-1] if events else None, ordinal=ordinal)
    if visible(final) != visible(frames[-1]) or frames[-1]["ordinal"] != ordinal:
        frames.append(final)
    else:
        frames[-1]["current"] = True
    used = {r["id"] for f in frames for r in f["board"]}
    used.update(c["id"] for f in frames for c in f["changes"])
    if song_id in metadata:
        used.add(song_id)
    return dict(frames=frames, songs={sid:metadata[sid] for sid in used}, total_matches=len(events),
                omitted=omitted, focus_id=song_id, focus_available=song_id is None or song_id in ratings, anchored=bool(cutoff or (settings and settings["baseline_kind"] == "legacy_anchor")), reconciled=reconciled)


def finite(value):
    try:
        value = float(value)
        return value if isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def percent(n, total):
    return round(100 * n / total, 1) if total else None


def average(values):
    """Return a rounded mean for report values, preserving unavailable for an empty
    sample.
    """
    values = list(values)
    return round(mean(values), 2) if values else None


def saved_date(value):
    try:
        if isinstance(value, (float, int)):
            date = datetime.fromtimestamp(value, timezone.utc)
        else:
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            date = (
                date.replace(tzinfo=timezone.utc)
                if date.tzinfo is None
                else date.astimezone(timezone.utc)
            )
        return dict(seconds=date.timestamp(), iso=date.isoformat())
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def build_voting_stats(
    conn, now=None, history_mode="all", history_page=1, history_origin="all"
):
    """Caller supplies a SELECT snapshot. Rates pool outcomes, never percentages."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM artists")}
    albums = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM albums")}
    tags = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM genres")}
    artist_ids, tag_ids = defaultdict(set), defaultdict(set)
    for r in conn.execute("SELECT song_id,artist_id FROM song_artists"):
        if r["artist_id"] in artists:
            artist_ids[r["song_id"]].add(r["artist_id"])
    for r in conn.execute("SELECT song_id,genre_id FROM song_genres"):
        if r["genre_id"] in tags:
            tag_ids[r["song_id"]].add(r["genre_id"])
    songs = {}
    for raw in conn.execute("SELECT * FROM songs"):
        s = dict(raw)
        s.update(
            versus_metadata(
                albums.get(s.get("album_id")), [artists[a] for a in artist_ids[s["id"]]]
            )
        )
        s.update(
            elo_score=finite(s.get("elo_score")),
            highest_elo=finite(s.get("highest_elo")),
            appearances=0,
            wins=0,
            losses=0,
            standard_wins=0,
            standard_losses=0,
            blind_wins=0,
            blind_losses=0,
            net=0,
            snapshots=0,
            best_run=0,
            current_run=0,
            run_complete=True,
        )
        songs[s["id"]] = s

    def identity(sid):
        """Resolve a report participant or retain a safe removed-track identity."""
        return songs.get(sid) or dict(
            id=None,
            title="Removed track",
            cover_url="",
            artist_links=[],
            album_link=None,
            elo_score=None,
        )

    from songranker.catalog import source_sql

    matches, tournament_matches, skipped = [], [], 0
    for raw in conn.execute(
        f"SELECT * FROM {source_sql(conn)} WHERE mode IN ('standard','blind')"
    ):
        r = dict(raw)
        if (
            r.get("winner_id") is None
            or r.get("loser_id") is None
            or r["winner_id"] == r["loser_id"]
        ):
            skipped += 1
            continue
        wb, wa, lb, la = [
            finite(r.get(k))
            for k in ("winner_before", "winner_after", "loser_before", "loser_after")
        ]
        before = wb is not None and lb is not None and isfinite(wb - lb)
        snapshot = (
            before
            and wa is not None
            and la is not None
            and isfinite(wa - wb)
            and isfinite(la - lb)
            and wa >= wb
            and la <= lb
        )
        r.update(
            winner_before=wb,
            winner_after=wa,
            loser_before=lb,
            loser_after=la,
            winner=identity(r["winner_id"]),
            loser=identity(r["loser_id"]),
            date=saved_date(r.get("created_at")),
            gap=abs(wb - lb) if before else None,
            upset=wb < lb if before else None,
            level=wb == lb if before else False,
            gain=wa - wb if snapshot else None,
            loss=lb - la if snapshot else None,
            snapshot=snapshot,
        )
        (tournament_matches if r.get("origin") == "tournament" else matches).append(r)
    ordinary_matches = list(matches)
    matches += tournament_matches
    matches.sort(
        key=lambda r: ((r["date"] or {}).get("seconds", float("-inf")), r["id"])
    )
    for r in matches:
        for sid, won, delta in [
            (r["winner_id"], True, r["gain"]),
            (r["loser_id"], False, -r["loss"] if r["loss"] is not None else None),
        ]:
            if sid not in songs:
                continue
            s = songs[sid]
            s["appearances"] += 1
            s["wins" if won else "losses"] += r.get("rating_weight", 1)
            s[r["mode"] + ("_wins" if won else "_losses")] += r.get("rating_weight", 1)
            if delta is not None:
                s["net"] += delta
                s["snapshots"] += 1
            if not r["date"] or r["date"]["seconds"] > now:
                s["run_complete"] = False
            else:
                s["current_run"] = s["current_run"] + 1 if won else 0
                s["best_run"] = max(s["best_run"], s["current_run"])
    for s in songs.values():
        s["matches"] = s["wins"] + s["losses"]
        s["win_rate"] = percent(s["wins"], s["matches"])
        s["net"] = round(s["net"], 2)
        for mode in MODES:
            s[mode + "_matches"] = s[mode + "_wins"] + s[mode + "_losses"]
            s[mode + "_rate"] = percent(s[mode + "_wins"], s[mode + "_matches"])
        if not s["run_complete"]:
            s["best_run"] = None

    def result_totals(rows):
        """Aggregate effective voting evidence, rating gaps, saved changes and dated
        participation.
        """
        rated = [r for r in rows if r["gap"] is not None]
        unequal = [r for r in rated if not r["level"]]
        changes = [r for r in rows if r["snapshot"]]
        days = {
            r["date"]["iso"][:10]
            for r in rows
            if r["date"] and r["date"]["seconds"] <= now
        }
        live = {
            sid for r in rows for sid in (r["winner_id"], r["loser_id"]) if sid in songs
        }
        weight = lambda group: sum(r.get("rating_weight", 1) for r in group)
        upsets = weight([r for r in unequal if r["upset"]])
        unequal_weight = weight(unequal)
        return dict(
            matches=len(rows),
            effective_matches=weight(rows),
            rated=len(rated),
            unequal=unequal_weight,
            upsets=upsets,
            upset_rate=percent(upsets, unequal_weight),
            level=len(rated) - len(unequal),
            snapshots=len(changes),
            active_days=len(days),
            tracks=len(live),
            avg_gain=average(r["gain"] for r in changes),
            avg_gap=(
                round(
                    sum(r["gap"] * r.get("rating_weight", 1) for r in rated)
                    / weight(rated),
                    2,
                )
                if weight(rated)
                else None
            ),
        )

    summary = result_totals(matches)
    summary.update(
        undated=sum(not r["date"] for r in matches),
        skipped=skipped,
        removed=sum(
            r["winner_id"] not in songs or r["loser_id"] not in songs for r in matches
        ),
    )
    modes = [
        dict(
            mode=m,
            title="Non-blind" if m == "standard" else "Blind",
            **result_totals([r for r in matches if r["mode"] == m]),
        )
        for m in MODES
    ]
    for m in modes:
        m["share"] = percent(m["matches"], len(matches))
    tested = [s for s in songs.values() if s["matches"]]
    coverage = dict(
        milestone=coverage_milestone(s["appearances"] for s in songs.values()),
        total=len(songs),
        voted=len(tested),
        unplayed=len(songs) - len(tested),
        share=percent(len(tested), len(songs)),
        under_two=sum(s["matches"] < 2 for s in tested),
        two_to_four=sum(2 <= s["matches"] < 5 for s in tested),
        five_plus=sum(s["matches"] >= 5 for s in tested),
        avg_appearances=average(s["matches"] for s in tested),
        both=sum(
            bool(s["standard_matches"] and s["blind_matches"]) for s in songs.values()
        ),
        standard_only=sum(
            bool(s["standard_matches"] and not s["blind_matches"])
            for s in songs.values()
        ),
        blind_only=sum(
            bool(s["blind_matches"] and not s["standard_matches"])
            for s in songs.values()
        ),
    )
    windows = []
    for n in (7, 30):
        group = [
            r
            for r in matches
            if r["date"] and now - n * 86400 <= r["date"]["seconds"] <= now
        ]
        windows.append(
            dict(
                days=n,
                standard=sum(r["mode"] == "standard" for r in group),
                blind=sum(r["mode"] == "blind" for r in group),
                **result_totals(group),
            )
        )
    calendar = Counter(
        (r["date"]["iso"][:10], r["mode"])
        for r in matches
        if r["date"] and r["date"]["seconds"] <= now
    )
    today = datetime.fromtimestamp(now, timezone.utc).date()
    activity = [
        dict(
            date=(today - timedelta(days=n)).isoformat(),
            standard=calendar[((today - timedelta(days=n)).isoformat(), "standard")],
            blind=calendar[((today - timedelta(days=n)).isoformat(), "blind")],
        )
        for n in reversed(range(14))
    ]
    day_totals = Counter()
    for (day, mode), n in calendar.items():
        day_totals[day] += n
    busiest = (
        sorted(day_totals.items(), key=lambda p: (-p[1], p[0]))[0]
        if day_totals
        else None
    )
    valid_dates = [
        r["date"] for r in matches if r["date"] and r["date"]["seconds"] <= now
    ]
    activity_summary = dict(
        avg_day=(
            round(sum(day_totals.values()) / len(day_totals), 1) if day_totals else None
        ),
        first=min(valid_dates, key=lambda d: d["seconds"]) if valid_dates else None,
        latest=max(valid_dates, key=lambda d: d["seconds"]) if valid_dates else None,
        busiest_day=busiest[0] if busiest else "—",
        busiest_votes=busiest[1] if busiest else 0,
        max_day=max((d["standard"] + d["blind"] for d in activity), default=0),
    )
    # A starting/manual Elo is not voting evidence. All summaries and bands use
    # the same current-track cohort reconstructed from valid saved matches.
    rated_tracks = [s for s in tested if s["elo_score"] is not None]
    ratings = [s["elo_score"] for s in rated_tracks]
    distribution = dict(
        median=round(median(ratings), 1) if ratings else None,
        highest=max(ratings) if ratings else None,
        lowest=min(ratings) if ratings else None,
        spread=round(pstdev(ratings), 1) if ratings else None,
        rated=len(ratings),
        unavailable=len(tested) - len(ratings),
        excluded=len(songs) - len(tested),
        average=average(ratings),
        above_start=sum(value > 1200 for value in ratings),
        at_start=sum(value == 1200 for value in ratings),
        below_start=sum(value < 1200 for value in ratings),
        bands=[],
    )
    for low, high, label in (
        [(None, 1000, "Below 1000")]
        + [(n, n + 50, f"{n}–<{n+50}") for n in range(1000, 1400, 50)]
        + [(1400, None, "1400+")]
    ):
        group = [
            s
            for s in rated_tracks
            if s["elo_score"] is not None
            and (low is None or s["elo_score"] >= low)
            and (high is None or s["elo_score"] < high)
        ]
        distribution["bands"].append(
            dict(
                label=label,
                count=len(group),
                share=percent(len(group), len(ratings)),
                voted=sum(bool(s["matches"]) for s in group),
            )
        )
    unequal = [r for r in matches if r["gap"] is not None and not r["level"]]
    snapshots = [r for r in matches if r["snapshot"]]
    movement = dict(
        avg_gain=average(r["gain"] for r in snapshots),
        avg_loss=average(r["loss"] for r in snapshots),
        total=round(sum(r["gain"] for r in snapshots), 2),
        largest_gain=max((r["gain"] for r in snapshots), default=None),
        largest_upset=max((r["gap"] for r in unequal if r["upset"]), default=None),
        missing=len(matches) - len(snapshots),
        drift=round(sum(r["gain"] - r["loss"] for r in snapshots), 6),
    )
    gaps = []
    for low, high, label in [
        (0, 50, "Under 50"),
        (50, 100, "50–<100"),
        (100, 200, "100–<200"),
        (200, 400, "200–<400"),
        (400, None, "400+"),
    ]:
        group = [
            r
            for r in matches
            if r["gap"] is not None
            and low <= r["gap"]
            and (high is None or r["gap"] < high)
        ]
        gaps.append(dict(label=label, **result_totals(group)))
    by_pair = defaultdict(list)
    for r in matches:
        by_pair[tuple(sorted((r["winner_id"], r["loser_id"])))].append(r)
    pairs = []
    for (a, b), rows in by_pair.items():
        if len(rows) < 2:
            continue
        a_wins = sum(r.get("rating_weight", 1) for r in rows if r["winner_id"] == a)
        vote_weight = sum(r.get("rating_weight", 1) for r in rows)
        pairs.append(
            dict(
                first=identity(a),
                second=identity(b),
                first_wins=a_wins,
                second_wins=vote_weight - a_wins,
                vote_weight=vote_weight,
                standard=sum(r["mode"] == "standard" for r in rows),
                blind=sum(r["mode"] == "blind" for r in rows),
                matches=len(rows),
            )
        )
    pairs.sort(
        key=lambda p: (
            -p["matches"],
            p["first"]["title"].casefold(),
            p["second"]["title"].casefold(),
        )
    )
    both = [s for s in tested if s["standard_matches"] >= 3 and s["blind_matches"] >= 3]
    for s in both:
        s["blind_lift"] = round(
            100 * s["blind_wins"] / s["blind_matches"]
            - 100 * s["standard_wins"] / s["standard_matches"],
            1,
        )

    def top(rows, metric, reverse=True):
        """Select five report leaders with deterministic metric, exposure, title and
        ID ordering.
        """
        return sorted(
            rows,
            key=lambda s: (
                -s[metric] if reverse else s[metric],
                -s["matches"],
                s["title"].casefold(),
                s["id"],
            ),
        )[:5]

    def category(kind, title, entities, links):
        """Aggregate tested song preference records into artist, full-album or tag
        leaders.
        """
        rows = []
        for eid, entity in entities.items():
            if kind == "album" and not proper_album(entity):
                continue
            tracks = [s for s in songs.values() if eid in links(s)]
            appearances = sum(s["matches"] for s in tracks)
            if not appearances:
                continue
            wins = sum(s["wins"] for s in tracks)
            rows.append(
                dict(
                    id=eid,
                    name=entity.get("name", entity.get("title", "")),
                    cover_url=entity.get("cover_url") or "",
                    wins=wins,
                    losses=appearances - wins,
                    matches=appearances,
                    tested=sum(bool(s["matches"]) for s in tracks),
                    win_rate=percent(wins, appearances),
                    standard=sum(s["standard_matches"] for s in tracks),
                    blind=sum(s["blind_matches"] for s in tracks),
                )
            )
        return dict(
            kind=kind,
            title=title,
            most=sorted(
                rows, key=lambda r: (-r["matches"], r["name"].casefold(), r["id"])
            )[:5],
            best=sorted(
                (r for r in rows if r["matches"] >= 5),
                key=lambda r: (
                    -r["wins"] / r["matches"],
                    -r["matches"],
                    r["name"].casefold(),
                    r["id"],
                ),
            )[:5],
        )

    history_mode = history_mode if history_mode in MODES else "all"
    history_origin = (
        history_origin if history_origin in ("ordinary", "tournament") else "all"
    )
    elo_matches = sorted(
        matches,
        key=lambda r: ((r["date"] or {}).get("seconds", float("-inf")), r["id"]),
    )
    latest = list(reversed(elo_matches))
    filtered = [
        r
        for r in latest
        if (history_mode == "all" or r["mode"] == history_mode)
        and (
            history_origin == "all"
            or (r.get("origin") == "tournament") == (history_origin == "tournament")
        )
    ]
    elo_summary = dict(
        total=len(elo_matches),
        ordinary=len(ordinary_matches),
        tournament=len(tournament_matches),
        full=sum(r.get("rating_weight") == 1 for r in tournament_matches),
        half=sum(r.get("rating_weight") == 0.5 for r in tournament_matches),
        gain=sum(r["gain"] or 0 for r in tournament_matches),
    )
    source_modes = [
        dict(
            origin=origin,
            mode=mode,
            **result_totals(
                [
                    r
                    for r in matches
                    if (r.get("origin") == "tournament") == (origin == "tournament")
                    and r["mode"] == mode
                ]
            ),
        )
        for origin in ("ordinary", "tournament")
        for mode in MODES
    ]
    pages = max(1, ceil(len(filtered) / HISTORY_SIZE))
    try:
        history_page = max(1, min(int(history_page), pages))
    except (ValueError, TypeError, OverflowError):
        history_page = 1
    start = (history_page - 1) * HISTORY_SIZE
    from songranker.modes.preferences import comparison_report

    return attach_reports(
        conn,
        dict(
            source_modes=source_modes,
            elo_summary=elo_summary,
            history_origin=history_origin,
            split_elo=comparison_report(conn, songs.values()),
            summary=summary,
            modes=modes,
            coverage=coverage,
            windows=windows,
            activity=activity,
            activity_summary=activity_summary,
            distribution=distribution,
            movement=movement,
            gaps=gaps,
            pairs=pairs[:5],
            unique_pairs=len(by_pair),
            repeated_pairs=len(pairs),
            upsets=sorted(
                (r for r in unequal if r["upset"]), key=lambda r: (-r["gap"], -r["id"])
            )[:5],
            gains=sorted(snapshots, key=lambda r: (-r["gain"], -r["id"]))[:5],
            leaders=top([s for s in tested if s["elo_score"] is not None], "elo_score"),
            most_played=top(tested, "matches"),
            most_wins=top(tested, "wins"),
            best_rates=sorted(
                (s for s in tested if s["matches"] >= 5),
                key=lambda s: (
                    -s["wins"] / s["matches"],
                    -s["matches"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:5],
            gain_tracks=top(
                [s for s in tested if s["snapshots"] and s["net"] > 0], "net"
            ),
            loss_tracks=top(
                [s for s in tested if s["snapshots"] and s["net"] < 0], "net", False
            ),
            runs=top(
                [s for s in tested if s["best_run"] is not None and s["best_run"] > 0],
                "best_run",
            ),
            blind_lift=top([s for s in both if s["blind_lift"] > 0], "blind_lift"),
            standard_lift=top(
                [s for s in both if s["blind_lift"] < 0], "blind_lift", False
            ),
            categories=[
                category(
                    "artist", "Artist records", artists, lambda s: artist_ids[s["id"]]
                ),
                category(
                    "album", "Album records", albums, lambda s: [s.get("album_id")]
                ),
                category("tag", "Tag records", tags, lambda s: tag_ids[s["id"]]),
            ],
            history=filtered[start : start + HISTORY_SIZE],
            history_mode=history_mode,
            history_page=history_page,
            history_pages=pages,
            history_total=len(filtered),
            history_start=start + 1 if filtered else 0,
            history_end=min(start + HISTORY_SIZE, len(filtered)),
        ),
        "voting",
        now=now,
    )
