"""Shelves round operations, results and detailed statistics."""

from collections import defaultdict
import secrets
import time
from flask import jsonify, render_template, request, session
from songranker.services import app, get_db_connection
from songranker.catalog import display_song
from songranker.reports.stats_activity import attach_reports, coverage_milestone
from datetime import datetime, timezone
from math import ceil, isclose
from songranker.catalog import proper_album


# A round is one scored exercise: hide it as a whole when a saved album is
# excluded, rather than manufacturing a smaller round or a new perfect score.
SHELF_REPORT_FILTER = """r.completed_at IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM album_shelf_items excluded_item
    JOIN albums excluded_album ON excluded_album.id=excluded_item.album_id
    WHERE excluded_item.round_id=r.id AND excluded_album.shelves_excluded=1)"""


def shelf_report_filter(conn):
    """Hide excluded saved rounds; pre-22 read-only archives have no exclusions."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(albums)")}
    return SHELF_REPORT_FILTER if "shelves_excluded" in columns else "r.completed_at IS NOT NULL"


def shelf_position(item):
    """Order a saved position by disc, then track; legacy facts default to disc one."""
    return (item.get("disc_number", 1), item["track_number"])


def grade_shelf(items):
    """0.5 membership points + up to 2.5 relative-order points per track."""
    result = []
    for item in items:
        siblings = [
            other
            for other in items
            if other["album_slot"] == item["album_slot"]
            and other["item_slot"] != item["item_slot"]
        ]
        membership = item["answer_slot"] == item["album_slot"]
        comparisons = len(siblings)
        right = sum(
            membership
            and other["answer_slot"] == other["album_slot"]
            and (
                (shelf_position(item) < shelf_position(other))
                == (item["answer_position"] < other["answer_position"])
            )
            for other in siblings
        )
        order_points = 2.5 * right / comparisons if comparisons else 0
        result.append(
            dict(
                item_slot=item["item_slot"],
                song_id=item["song_id"],
                album_id=item["album_id"],
                album_correct=int(membership),
                order_right=right,
                order_pairs=comparisons,
                answer_slot=item["answer_slot"],
                answer_position=item["answer_position"],
                points=0.5 * int(membership) + order_points,
                available=3 if comparisons else 0.5,
            )
        )
    points = sum(row["points"] for row in result)
    available = sum(row["available"] for row in result)
    return dict(
        points=points,
        available=available,
        accuracy=100 * points / available if available else None,
        album_correct=sum(row["album_correct"] for row in result),
        order_right=sum(row["order_right"] for row in result),
        order_pairs=sum(row["order_pairs"] for row in result),
        items=result,
    )


@app.route("/album_shelves")
def album_shelves():
    return render_template("app_page.html", page="shelves")


@app.route("/album_shelves_stats")
def shelf_stats():
    pass
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_shelves_stats(
            conn,
            history_page=request.args.get("history_page", 1, type=int),
            album_page=request.args.get("album_page", 1, type=int),
            selected=request.args.get("round", type=int),
        )
    finally:
        conn.close()
    return render_template(
        "shelves_stats.html", show_albums="album_page" in request.args, **data
    )


def shelf_pool(conn):
    """The existing numbered/proper-album pool, shared by the picker and stats."""
    pool = [
        dict(r)
        for r in conn.execute(
            """SELECT s.id,s.album_id,s.disc_number,s.track_number FROM songs s JOIN albums a ON a.id=s.album_id
        WHERE a.shelves_excluded=0 AND TRIM(a.title)!='' AND LOWER(TRIM(a.title))!='unknown album'
        AND LOWER(TRIM(a.title)) NOT LIKE '% - single' AND typeof(s.track_number)='integer' AND s.track_number>0
        AND NOT EXISTS(SELECT 1 FROM songs other WHERE other.album_id=s.album_id
          AND other.disc_number=s.disc_number AND other.track_number=s.track_number AND other.id!=s.id) ORDER BY s.id"""
        )
    ]
    from songranker.modes.selection import with_catalogue_age

    pool = with_catalogue_age(conn, pool)
    grouped = defaultdict(list)
    for song in pool:
        grouped[song["album_id"]].append(song)
    # A shelf must offer an ordering question, not a singleton album clue.
    return {id: tracks for id, tracks in grouped.items() if len(tracks) >= 2}


def shelf_candidates(conn, count):
    """Draw eligible albums and tracks using production exposure, recency and
    Vibe-aware selection.
    """
    from songranker.modes.selection import draw_shelves
    from songranker.modes.selection import mode_counts
    from songranker.modes.selection import shelf_history
    from songranker.modes.selection import album_vibe_groups

    grouped = shelf_pool(conn)
    exposure = {
        r["album_id"]: r["appearances"]
        for r in conn.execute("SELECT * FROM shelf_album_exposures")
    }
    return draw_shelves(
        grouped,
        exposure,
        mode_counts(conn, "shelves"),
        shelf_history(conn),
        count,
        vibe_groups=album_vibe_groups(conn, grouped),
    )


def shelf_payload(conn, row):
    items = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM album_shelf_items WHERE round_id=? ORDER BY item_slot",
            (row["id"],),
        )
    ]
    albums = []
    for slot in sorted({i["album_slot"] for i in items}):
        id = next(i["album_id"] for i in items if i["album_slot"] == slot)
        a = conn.execute(
            "SELECT a.id,a.title,a.cover_url,(SELECT MAX(s.disc_number) FROM songs s WHERE s.album_id=a.id) AS disc_count FROM albums a WHERE a.id=?", (id,)
        ).fetchone()
        if not a:
            return None
        albums.append(dict(a, slot=slot))
    songs = []
    for item in items:
        s = display_song(conn, item["song_id"], False)
        if not s:
            return None
        s.pop("artists", None)
        songs.append(dict(s, slot=item["item_slot"]))
    return dict(token=row["token"], albums=albums, songs=songs)


@app.route("/api/album-shelves/round", methods=["POST"])
def shelf_round():
    data = request.get_json(silent=True) or {}
    if (
        not isinstance(data, dict)
        or type(data.get("album_count", 0)) is not int
        or data.get("album_count", 0) not in (0, 2, 3)
    ):
        return jsonify(message="Choose automatic, two or three albums."), 400
    count = data.get("album_count", 0)
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM album_shelf_rounds WHERE token=? AND completed_at IS NULL",
            (session.get("shelf_token", ""),),
        ).fetchone()
        if row and data.get("fresh") is True:
            conn.execute("DELETE FROM album_shelf_rounds WHERE id=?", (row["id"],))
            row = None
        if row:
            payload = shelf_payload(conn, row)
            if not payload or (count and len(payload["albums"]) != count):
                conn.execute("DELETE FROM album_shelf_rounds WHERE id=?", (row["id"],))
                row = None
        if not row:
            conn.execute(
                "DELETE FROM album_shelf_rounds WHERE completed_at IS NULL AND started_at<?",
                (time.time() - 86400,),
            )
            candidate = shelf_candidates(conn, count)
            if not candidate:
                return (
                    jsonify(
                        message="Need ten numbered tracks across two or three proper albums, with at least two tracks per album. Gaps are fine."
                    ),
                    400,
                )
            albums, tracks = candidate
            token = secrets.token_urlsafe(24)
            cur = conn.execute(
                "INSERT INTO album_shelf_rounds(token,started_at) VALUES(?,?)",
                (token, time.time()),
            )
            for slot, song in enumerate(tracks, 1):
                conn.execute(
                    "INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,disc_number) VALUES(?,?,?,?,?,?,?)",
                    (
                        cur.lastrowid,
                        slot,
                        song["id"],
                        song["album_id"],
                        albums.index(song["album_id"]) + 1,
                        song["track_number"],
                        song["disc_number"],
                    ),
                )
            session["shelf_token"] = token
            row = conn.execute(
                "SELECT * FROM album_shelf_rounds WHERE id=?", (cur.lastrowid,)
            ).fetchone()
            payload = shelf_payload(conn, row)
        conn.commit()
        return jsonify(**payload)
    finally:
        conn.close()


@app.route("/api/album-shelves/answer", methods=["POST"])
def shelf_answer():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("placements"), dict):
        return jsonify(message="Place every offered track once."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM album_shelf_rounds WHERE token=?",
            (session.get("shelf_token", ""),),
        ).fetchone()
        if not row or data.get("token") != row["token"]:
            return jsonify(message="This shelf round is no longer active."), 409
        if row["completed_at"] is not None:
            return jsonify(message="This answer is already saved."), 409
        items = [
            dict(i)
            for i in conn.execute(
                "SELECT * FROM album_shelf_items WHERE round_id=?", (row["id"],)
            )
        ]
        if any(not i["song_id"] or not i["album_id"] for i in items):
            return (
                jsonify(message="A track or album was deleted. Start a new round."),
                409,
            )
        offered = {i["item_slot"] for i in items}
        slots = {str(i["album_slot"]) for i in items}
        p = data["placements"]
        if set(p) != slots or any(not isinstance(v, list) for v in p.values()):
            return jsonify(message="Use the offered album shelves."), 400
        flat = [x for v in p.values() for x in v]
        if (
            any(type(x) is not int for x in flat)
            or len(flat) != 10
            or len(set(flat)) != 10
            or set(flat) != offered
        ):
            return (
                jsonify(
                    message="Each of the ten offered tracks must appear exactly once."
                ),
                400,
            )
        by_slot = {i["item_slot"]: i for i in items}
        for slot, ids in p.items():
            for position, id in enumerate(ids, 1):
                by_slot[id].update(answer_slot=int(slot), answer_position=position)
                conn.execute(
                    "UPDATE album_shelf_items SET answer_slot=?,answer_position=? WHERE round_id=? AND item_slot=?",
                    (int(slot), position, row["id"], id),
                )
        conn.execute(
            "UPDATE album_shelf_rounds SET completed_at=? WHERE id=?",
            (time.time(), row["id"]),
        )

        conn.commit()
        graded = grade_shelf(items)
        answers = [
            dict(
                slot=i["item_slot"],
                album_slot=i["album_slot"],
                track_number=i["track_number"],
                disc_number=i["disc_number"],
            )
            for i in items
        ]
        return jsonify(**graded, answers=answers)
    finally:
        conn.close()


# Read-only Shelves reporting. Saved shelf slots/numbers remain scoring facts.


PAGE_SIZE = 10


def percentage(right, total):
    return round(100 * right / total, 1) if total else None


def saved_date(value):
    try:
        stamp = float(value)
        return dict(
            seconds=stamp, iso=datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def integer(value, low=1, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def can_grade(items, rules):
    """Validate saved Shelves rules, slots, track positions and unique identities
    before reconstructing a grade.
    """
    if rules != 1 or not 1 <= len(items) <= 10:
        return False
    slots = {i["album_slot"] for i in items}
    if not all(
        integer(i["item_slot"], high=10)
        and integer(i["album_slot"], high=3)
        and integer(i["track_number"])
        and integer(i.get("disc_number", 1))
        and i["answer_slot"] in slots
        and integer(i["answer_slot"], high=3)
        and integer(i["answer_position"], high=10)
        for i in items
    ):
        return False

    def unique(keys):
        """Check that a chosen tuple of saved item fields is unique within the round."""
        return len({tuple(i[k] for k in keys) for i in items}) == len(items)

    living_ids = [i["song_id"] for i in items if i["song_id"] is not None]
    return (
        unique(("item_slot",))
        and len({(i["album_slot"], *shelf_position(i)) for i in items}) == len(items)
        and unique(("answer_slot", "answer_position"))
        and len(set(living_ids)) == len(living_ids)
    )


def empty_counts():
    """Create the zeroed track/order/point counters shared by Shelves report
    aggregates.
    """
    return dict(
        graded_tracks=0,
        album_correct=0,
        order_right=0,
        order_pairs=0,
        points=0.0,
        available=0.0,
        fully_correct=0,
        wrong_album=0,
        order_affected=0,
    )


def add_counts(target, source):
    """Accumulate one Shelves result's known counters into an existing aggregate."""
    for key in empty_counts():
        target[key] += source[key]


def item_counts(item):
    """Project a graded track into album/order/point and error-category report
    counters.
    """
    full = isclose(item["points"], item["available"], rel_tol=0, abs_tol=1e-8)
    return dict(
        graded_tracks=1,
        album_correct=item["album_correct"],
        order_right=item["order_right"],
        order_pairs=item["order_pairs"],
        points=item["points"],
        available=item["available"],
        fully_correct=int(full),
        wrong_album=int(not item["album_correct"]),
        order_affected=int(item["album_correct"] and not full),
    )


def finish_counts(row):
    """Derive album/order accuracy and wrong-order counts from aggregated Shelves
    counters.
    """
    row.update(
        order_accuracy=percentage(row["order_right"], row["order_pairs"]),
        album_accuracy=percentage(row["album_correct"], row["graded_tracks"]),
        order_wrong=row["order_pairs"] - row["order_right"],
    )
    return row


def window_totals(rows):
    """Summarise Shelves rounds in a report window, distinguishing graded results
    from unknown history.
    """
    rows = list(rows)
    result = empty_counts()
    known = [r for r in rows if r["graded"]]
    for row in known:
        add_counts(result, row)
    result.update(
        rounds=len(rows),
        tracks=sum(r["tracks"] for r in rows),
        scored_rounds=len(known),
        unknown=len(rows) - len(known),
        perfect=sum(r["outcome"] == "perfect" for r in known),
        average_points=sum(r["points"] for r in known) / len(known) if known else None,
    )
    return finish_counts(result)


def page_number(value, pages):
    """Clamp a report page number to the available range, defaulting invalid input to
    page one.
    """
    try:
        return max(1, min(int(value), pages))
    except (TypeError, ValueError, OverflowError):
        return 1


def build_shelves_stats(conn, now=None, history_page=1, album_page=1, selected=None):
    """Aggregate all completed rounds in the caller's snapshot; page only lists."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM artists")}
    albums = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM albums")}
    tags = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM genres")}
    artist_links, tag_links = defaultdict(set), defaultdict(set)
    for r in conn.execute("SELECT song_id,artist_id FROM song_artists"):
        if r["artist_id"] in artists:
            artist_links[r["song_id"]].add(r["artist_id"])
    for r in conn.execute("SELECT song_id,genre_id FROM song_genres"):
        if r["genre_id"] in tags:
            tag_links[r["song_id"]].add(r["genre_id"])
    songs = {}
    album_artists = defaultdict(set)
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
            **empty_counts()
        )
        songs[song["id"]] = song
        album_artists[song.get("album_id")].update(artist_links[song["id"]])

    def album_identity(aid, slot=None):
        """Build a report release identity with linked artists and a fallback for
        unavailable albums.
        """
        album = albums.get(aid)
        return dict(
            id=aid if album else None,
            title=album["title"] if album else "Album unavailable",
            cover_url=(album.get("cover_url") or "") if album else "",
            linked=bool(album and proper_album(album)),
            album_link=None,
            artist_links=(
                sorted(
                    (artists[a] for a in album_artists.get(aid, ())),
                    key=lambda a: (a["name"].casefold(), a["id"]),
                )
                if album
                else []
            ),
            slot=slot,
        )

    rounds = {
        r["id"]: dict(r, items=[], groups=[], **empty_counts())
        for r in conn.execute(
            f"SELECT id,completed_at,rules_version FROM album_shelf_rounds r WHERE {shelf_report_filter(conn)}"
        )
    }
    for raw in conn.execute(
        f"""SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r
                               ON r.id=i.round_id WHERE {shelf_report_filter(conn)} ORDER BY i.round_id,i.item_slot"""
    ):
        rounds[raw["round_id"]]["items"].append(dict(raw))
    album_totals = {}
    missing_album_slots = legacy_sizes = 0
    for row in rounds.values():
        items = row["items"]
        row.update(
            date=saved_date(row["completed_at"]),
            tracks=len(items),
            album_count=len({i["album_slot"] for i in items}),
            graded=can_grade(items, row["rules_version"]),
        )
        legacy_sizes += len(items) != 10
        saved_groups = defaultdict(list)
        for item in items:
            saved_groups[item["album_slot"]].append(item)
            aid = item["album_id"]
            if aid in albums:
                target = album_totals.setdefault(
                    aid,
                    dict(
                        album_identity(aid),
                        name=albums[aid]["title"],
                        attempts=0,
                        rounds_set=set(),
                        songs_set=set(),
                        **empty_counts()
                    ),
                )
                target["attempts"] += 1
                target["rounds_set"].add(row["id"])
                if item["song_id"] in songs:
                    target["songs_set"].add(item["song_id"])
        if row["graded"]:
            grade = grade_shelf(items)
            by_slot = {i["item_slot"]: i for i in grade["items"]}
            for item in items:
                graded = by_slot[item["item_slot"]]
                item.update(graded)
                counts = item_counts(graded)
                add_counts(row, counts)
                if item["song_id"] in songs:
                    song = songs[item["song_id"]]
                    song["attempts"] += 1
                    add_counts(song, counts)
                if item["album_id"] in album_totals:
                    add_counts(album_totals[item["album_id"]], counts)
                item["outcome"] = (
                    "correct"
                    if counts["fully_correct"]
                    else "wrong_album" if counts["wrong_album"] else "order_affected"
                )
            row["outcome"] = (
                "perfect"
                if isclose(row["points"], row["available"], rel_tol=0, abs_tol=1e-8)
                else "partial" if row["points"] else "zero"
            )
        else:
            row["outcome"] = "unknown"
            for item in items:
                item.update(
                    points=None,
                    available=None,
                    outcome="unknown",
                    album_correct=None,
                    order_right=None,
                    order_pairs=None,
                )
        finish_counts(row)
        slot_identities = {}
        for slot, saved in sorted(
            saved_groups.items(), key=lambda entry: str(entry[0])
        ):
            ids = {i["album_id"] for i in saved if i["album_id"] is not None}
            identity = album_identity(next(iter(ids)) if len(ids) == 1 else None, slot)
            slot_identities[slot] = identity
            missing_album_slots += identity["id"] is None
            group_counts = empty_counts()
            if row["graded"]:
                for item in saved:
                    add_counts(group_counts, item_counts(item))
            group = dict(
                identity,
                items=sorted(
                    saved,
                    key=lambda i: (
                        i.get("disc_number", 1),
                        (
                            i["track_number"]
                            if integer(i["track_number"])
                            else float("inf")
                        ),
                        str(i["item_slot"]),
                    ),
                ),
                graded=row["graded"],
                tracks=len(saved),
                **finish_counts(group_counts)
            )
            row["groups"].append(group)
        for item in items:
            item.update(
                song=songs.get(item["song_id"]),
                answer_album=slot_identities.get(item["answer_slot"])
                or album_identity(None, item["answer_slot"]),
                saved_track=(
                    item["track_number"] if integer(item["track_number"]) else None
                ),
            )

    ordered = sorted(
        rounds.values(),
        key=lambda r: ((r["date"] or {}).get("seconds", float("-inf")), r["id"]),
    )
    streak = best = 0
    for row in ordered:
        if row["date"]:
            streak = streak + 1 if row["outcome"] == "perfect" else 0
            best = max(best, streak)
    summary = window_totals(ordered)
    summary.update(
        tracks=sum(r["tracks"] for r in ordered),
        albums_played=len(album_totals),
        current_streak=(
            streak
            if all(r["date"] for r in ordered)
            and (not ordered or ordered[-1]["graded"])
            else None
        ),
        best_streak=best,
        active_days=len(
            {
                r["date"]["iso"][:10]
                for r in ordered
                if r["date"] and r["date"]["seconds"] <= now
            }
        ),
        undated=sum(r["date"] is None for r in ordered),
        legacy_sizes=legacy_sizes,
        missing_album_slots=missing_album_slots,
    )
    scored = [r for r in ordered if r["graded"]]
    best_round = max(
        scored,
        key=lambda r: (
            r["points"],
            r["points"] / r["available"],
            (r["date"] or {}).get("seconds", float("-inf")),
            r["id"],
        ),
        default=None,
    )
    latest = list(reversed(ordered))
    windows = [dict(title="Latest 10 rounds", **window_totals(latest[:10]))]
    for days in (7, 30):
        windows.append(
            dict(
                title="Last " + str(days) + " days",
                **window_totals(
                    r
                    for r in ordered
                    if r["date"] and now - days * 86400 <= r["date"]["seconds"] <= now
                )
            )
        )
    outcomes = [
        dict(
            key=key,
            label=label,
            count=sum(r["outcome"] == key for r in ordered),
            share=percentage(sum(r["outcome"] == key for r in ordered), len(ordered)),
        )
        for key, label in (
            ("perfect", "Perfect rounds"),
            ("partial", "Partial credit"),
            ("zero", "No points"),
            ("unknown", "Unavailable"),
        )
        if key != "unknown" or summary["unknown"]
    ]
    formats = [
        dict(
            key=size,
            label=label,
            **window_totals(
                r
                for r in ordered
                if (
                    r["album_count"] == size
                    if size in (2, 3)
                    else r["album_count"] not in (2, 3)
                )
            )
        )
        for size, label in (
            (2, "Two-album rounds"),
            (3, "Three-album rounds"),
            ("other", "Other saved formats"),
        )
        if size != "other" or any(r["album_count"] not in (2, 3) for r in ordered)
    ]

    pool = shelf_pool(conn)
    playable = {
        aid
        for aid, tracks in pool.items()
        if any(
            len(pool) >= n
            and len(tracks)
            + sum(
                sorted(
                    (len(rows) for key, rows in pool.items() if key != aid),
                    reverse=True,
                )[: n - 1]
            )
            >= 10
            for n in (2, 3)
        )
    }
    eligible_tracks = {s["id"] for aid in playable for s in pool[aid]}
    tested_tracks = {s["id"] for s in songs.values() if s["attempts"]}
    album_appearances = defaultdict(set)
    for row in ordered:
        if row["graded"]:
            for item in row["items"]:
                album_appearances[item["album_id"]].add(row["id"])
    tested_albums = {aid for aid, row in album_totals.items() if row["graded_tracks"]}
    coverage = dict(
        album_milestone=coverage_milestone(len(album_appearances[aid]) for aid in playable),
        track_milestone=coverage_milestone(songs[sid]["attempts"] for sid in eligible_tracks),
        albums=len(playable),
        albums_tested=len(playable & tested_albums),
        albums_untested=len(playable - tested_albums),
        album_share=percentage(len(playable & tested_albums), len(playable)),
        tracks=len(eligible_tracks),
        tracks_tested=len(eligible_tracks & tested_tracks),
        tracks_untested=len(eligible_tracks - tested_tracks),
        track_share=percentage(
            len(eligible_tracks & tested_tracks), len(eligible_tracks)
        ),
        other_albums=len(tested_albums - playable),
        other_tracks=len(tested_tracks - eligible_tracks),
    )
    tested = [finish_counts(s) for s in songs.values() if s["order_pairs"]]

    def records(rows):
        """Choose stable best/worst Shelves order-accuracy records from tested report
        rows.
        """
        rows = list(rows)
        return dict(
            best=sorted(
                (r for r in rows if r["order_pairs"]),
                key=lambda r: (
                    -r["order_right"] / r["order_pairs"],
                    -r["order_pairs"],
                    r["name"].casefold(),
                    r["id"],
                ),
            )[:5],
            missed=sorted(
                (r for r in rows if r["order_wrong"]),
                key=lambda r: (
                    -r["order_wrong"],
                    -r["order_pairs"],
                    r["name"].casefold(),
                    r["id"],
                ),
            )[:5],
        )

    for album in album_totals.values():
        album.update(
            rounds=len(album.pop("rounds_set")), tested=len(album.pop("songs_set"))
        )
        finish_counts(album)
    album_rows = sorted(
        album_totals.values(),
        key=lambda r: (-r["rounds"], -r["attempts"], r["name"].casefold(), r["id"]),
    )
    album_pages = max(1, ceil(len(album_rows) / PAGE_SIZE))
    album_page = page_number(album_page, album_pages)
    album_records = dict(
        records(r for r in album_rows if r["linked"]),
        rows=album_rows[(album_page - 1) * PAGE_SIZE : album_page * PAGE_SIZE],
        page=album_page,
        pages=album_pages,
        total=len(album_rows),
    )
    categories = []
    for kind, title, identities, links in (
        ("artist", "Artist records", artists, artist_links),
        ("tag", "Tag records", tags, tag_links),
    ):
        groups = {}
        for song in tested:
            for identity in links[song["id"]]:
                group = groups.setdefault(
                    identity,
                    dict(
                        identities[identity],
                        name=identities[identity]["name"],
                        tested=0,
                        attempts=0,
                        **empty_counts()
                    ),
                )
                group["tested"] += 1
                group["attempts"] += song["attempts"]
                add_counts(group, song)
        rows = [finish_counts(r) for r in groups.values()]
        categories.append(dict(kind=kind, title=title, **records(rows)))
    history_pages = max(1, ceil(len(latest) / PAGE_SIZE))
    history_page = page_number(history_page, history_pages)
    selected_row = next((r for r in latest if r["id"] == selected), None)
    if selected_row:
        history_page = latest.index(selected_row) // PAGE_SIZE + 1
    start = (history_page - 1) * PAGE_SIZE
    return attach_reports(
        conn,
        dict(
            summary=summary,
            outcomes=outcomes,
            best_round=best_round,
            windows=windows,
            formats=formats,
            coverage=coverage,
            top_tracks=sorted(
                tested,
                key=lambda s: (
                    -s["order_right"] / s["order_pairs"],
                    -s["order_pairs"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            practice_tracks=sorted(
                (s for s in tested if s["order_wrong"]),
                key=lambda s: (
                    s["order_right"] / s["order_pairs"],
                    -s["order_pairs"],
                    s["title"].casefold(),
                    s["id"],
                ),
            )[:10],
            album_records=album_records,
            categories=categories,
            history=latest[start : start + PAGE_SIZE],
            history_page=history_page,
            history_pages=history_pages,
            history_start=start + 1 if latest else 0,
            history_end=min(start + PAGE_SIZE, len(latest)),
            selected_round=selected_row["id"] if selected_row else None,
            selection_missing=selected is not None and selected_row is None,
        ),
        "shelves",
        now=now,
    )
