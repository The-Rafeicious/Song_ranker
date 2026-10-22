"""Continuous Vibe Map rounds, resumable drafts and compact aggregate results."""

import json
import math
import secrets
import time
from flask import jsonify, request, session, render_template
from songranker.services import app, get_db_connection, get_song_full
from songranker.modes.preferences import transaction, owner_hash, snapshot_song
from songranker.modes.selection import vibe_song
from songranker.modes.vibe_similarity import compare_profiles
from songranker.storage.vibe_state import (
    MAPS,
    VIBE_MAP_VERSION,
    RADAR_ORDER,
    DISPLAY_MAPS,
)
from songranker.vibe_maps import map_definitions, song_profiles, pass_counts
from collections import defaultdict
from heapq import heappush, heapreplace
from itertools import combinations
from songranker.catalog import proper_album, versus_metadata
from songranker.modes.vibe_similarity import WIDTH, positions, compare_positions

READJUST_SECONDS = 5
SCALE = 5
KEYS = tuple(values[0] for values in MAPS)


class VibeError(ValueError):
    def __init__(self, message, code="invalid", status=400, **details):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


def identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 96:
        raise VibeError("A nonempty request_id of at most 96 characters is required.")
    return value


def revision(value):
    if type(value) is not int or not 0 <= value < 2**63:
        raise VibeError("A valid round revision is required.")
    return value


def placement(data):
    status = data.get("status", "placed")
    if status == "not_applicable":
        if data.get("x") is not None or data.get("y") is not None:
            raise VibeError("Not-applicable maps cannot contain coordinates.")
        return status, None, None
    if status != "placed":
        raise VibeError("Choose a placement or not applicable.")
    values = []
    for key in ("x", "y"):
        value = data.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not -SCALE <= value <= SCALE
            or not math.isfinite(value)
        ):
            raise VibeError("Both coordinates must be finite numbers between -5 and 5.")
        values.append(value / SCALE)
    return status, *values


def public_point(point):
    return dict(
        status=point["status"],
        x=point["x"] * SCALE if point["x"] is not None else None,
        y=point["y"] * SCALE if point["y"] is not None else None,
        display_x=round(point["x"] * SCALE, 2) if point["x"] is not None else None,
        display_y=round(point["y"] * SCALE, 2) if point["y"] is not None else None,
    )


def radar(points):
    """Eight labelled spokes preserve both axes of all four independent maps."""
    # Related positive poles are neighbours; raw bipolar values remain available.
    order = RADAR_ORDER
    definitions = {values[0]: values for values in DISPLAY_MAPS}
    result = []
    for key, axis, label in order:
        _, title, x_low, x_high, y_low, y_high = definitions[key]
        low, high = (x_low, x_high) if axis == "x" else (y_low, y_high)
        point = points.get(key, {})
        value = point.get(axis) if point.get("status") == "placed" else None
        result.append(
            dict(
                key=key + "_" + axis,
                map_id=key,
                map_title=title,
                axis=axis,
                label=label,
                low=low,
                high=high,
                value=round(value * SCALE, 2) if value is not None else None,
                radius=(value + 1) / 2 if value is not None else None,
            )
        )
    return dict(
        spokes=result,
        radius_min=0,
        radius_max=1,
        neutral_radius=0.5,
        description="Descriptive axes, not quality or performance scores.",
    )


def profile(conn, song_id):
    if type(song_id) is not int or not 0 < song_id < 2**63:
        raise VibeError("A positive song ID is required.")
    if not conn.execute("SELECT 1 FROM songs WHERE id=?", (song_id,)).fetchone():
        raise VibeError("Song no longer exists.", "missing_song", 404)
    points = song_profiles(conn, [song_id])[song_id]
    return dict(
        song_id=song_id,
        completed_passes=pass_counts(conn, [song_id])[song_id],
        maps={
            key: dict(
                public_point(p),
                sample_count=p["sample_count"],
                updated_at=p["updated_at"],
                not_applicable_count=p["not_applicable_count"],
            )
            for key, p in points.items()
        },
        radar=radar(points),
    )


def current(conn, owner):
    return conn.execute(
        "SELECT * FROM vibe_rounds WHERE owner_hash=?", (owner_hash(owner),)
    ).fetchone()


def payload(conn, row, now=None):
    if row is None:
        return dict(round=None, version=VIBE_MAP_VERSION)
    now = time.time() if now is None else now
    answers = json.loads(row["answers"])
    definitions = map_definitions(conn)
    for definition in definitions:
        definition.update(min=-SCALE, max=SCALE, step=None, display_decimals=2)
    song = get_song_full(row["song_id"], conn)
    result = dict(
        version=VIBE_MAP_VERSION,
        token=row["token"],
        song=snapshot_song(conn, song),
        status=row["status"],
        revision=row["revision"],
        map_index=row["map_index"],
        maps=definitions,
        current_map=(
            definitions[row["map_index"]] if row["status"] == "active" else None
        ),
        readjust_seconds=READJUST_SECONDS,
        server_time=now,
        draft=None,
        advance_at=None,
        remaining_ms=None,
        saved_maps=[
            dict(map_id=key, **public_point(answers[key]))
            for key in KEYS
            if key in answers
        ],
    )
    if row["draft_status"] is not None:
        result["draft"] = dict(
            map_id=answers.get(
                "_draft_map", KEYS[min(row["map_index"], len(KEYS) - 1)]
            ),
            **public_point(
                dict(status=row["draft_status"], x=row["draft_x"], y=row["draft_y"])
            ),
            request_id=row["draft_key"],
        )
        result["advance_at"] = row["draft_at"] + READJUST_SECONDS
        result["remaining_ms"] = max(0, math.ceil((result["advance_at"] - now) * 1000))
    if row["status"] == "complete":
        result["summary"] = dict(
            selection_radar=radar(answers), aggregate=profile(conn, row["song_id"])
        )
    return dict(round=result, version=VIBE_MAP_VERSION)


def require_round(conn, owner, data):
    row = current(conn, owner)
    if (
        not row
        or not isinstance(data.get("token"), str)
        or not secrets.compare_digest(row["token"].encode(), data["token"].encode())
    ):
        raise VibeError(
            "This round is no longer current in this browser. Reload its state.",
            "stale_round",
            409,
        )
    return row


def require_stage(row, data):
    if row["status"] == "cancelled":
        raise VibeError("This round has ended.", "ended", 409)
    map_id = data.get("map_id")
    answers = json.loads(row["answers"])
    if map_id not in KEYS or (
        map_id not in answers
        and (row["status"] != "active" or map_id != KEYS[row["map_index"]])
    ):
        raise VibeError("Save the current map before advancing.", "wrong_map", 409)
    if revision(data.get("revision")) != row["revision"]:
        raise VibeError(
            "This placement was changed in another request. Reload its state.",
            "stale_revision",
            409,
        )


def start(conn, owner, data):
    with transaction(conn):
        old = current(conn, owner)
        if old and (
            old["status"] == "active"
            or old["draft_status"] is not None
            or data.get("previous_token") is None
        ):
            return payload(conn, old)
        if old and data.get("previous_token") != old["token"]:
            raise VibeError(
                "The previous round changed. Reload its state.", "stale_round", 409
            )
        chosen = vibe_song(conn, previous=old["song_id"] if old else None)
        if chosen is None:
            raise VibeError("Add songs before starting Vibe Map.", "empty_library", 409)
        conn.execute("DELETE FROM vibe_rounds WHERE owner_hash=?", (owner_hash(owner),))
        conn.execute(
            "INSERT INTO vibe_rounds(owner_hash,token,song_id,started_at) VALUES(?,?,?,?)",
            (owner_hash(owner), secrets.token_urlsafe(32), chosen["id"], time.time()),
        )
        return payload(conn, current(conn, owner))


def draft(conn, owner, data):
    with transaction(conn):
        row = require_round(conn, owner, data)
        key = identifier(data.get("request_id"))
        status, x, y = placement(data)
        answers = json.loads(row["answers"])
        map_id = data.get("map_id")
        if (
            map_id in KEYS
            and answers.get("_draft_map") == map_id
            and row["draft_key"] == key
        ):
            if (row["draft_status"], row["draft_x"], row["draft_y"]) == (
                status,
                x,
                y,
            ) and revision(data.get("revision")) in (
                row["revision"] - 1,
                row["revision"],
            ):
                return payload(conn, row)  # Retried draft does not restart its timer.
            raise VibeError(
                "A request_id cannot be reused for a different placement.",
                "request_conflict",
                409,
            )
        require_stage(row, data)
        answers["_draft_map"] = map_id
        conn.execute(
            """UPDATE vibe_rounds SET draft_status=?,draft_x=?,draft_y=?,draft_at=?,draft_key=?,
                        revision=revision+1,answers=? WHERE owner_hash=?""",
            (status, x, y, time.time(), key, json.dumps(answers), owner_hash(owner)),
        )
        return payload(conn, current(conn, owner))


def advance(conn, owner, data):
    with transaction(conn):
        row = require_round(conn, owner, data)
        key = identifier(data.get("request_id"))
        if data.get("map_id") not in KEYS:
            raise VibeError("A valid map_id is required.")
        expected = revision(data.get("revision"))
        answers = json.loads(row["answers"])
        map_id = data["map_id"]
        existing = answers.get(map_id)
        if (
            existing
            and existing["request_id"] == key
            and existing["revision"] == expected
        ):
            result = payload(conn, row)
            result.update(replayed=True, accepted_map=map_id)
            return result
        if any(answers[k]["request_id"] == key for k in KEYS if k in answers):
            raise VibeError(
                "Use a new request_id for each save.", "request_conflict", 409
            )
        require_stage(row, data)
        if (
            row["draft_status"] is None
            or answers.get("_draft_map", KEYS[min(row["map_index"], len(KEYS) - 1)])
            != map_id
        ):
            raise VibeError("Place the song on this map first.", "missing_draft", 409)
        now = time.time()
        remaining = row["draft_at"] + READJUST_SECONDS - now
        if remaining > 0:
            raise VibeError(
                "Allow five seconds after the latest adjustment.",
                "readjusting",
                409,
                remaining_ms=math.ceil(remaining * 1000),
            )
        point = conn.execute(
            "SELECT * FROM song_vibe_positions WHERE song_id=? AND map_id=?",
            (row["song_id"], map_id),
        ).fetchone()
        if point is None:
            raise VibeError(
                "This map slot is missing. Check the database.", "missing_slot", 409
            )
        # Replace only this round's contribution, preserving other browser/pass samples.
        count = max(point["sample_count"], int(point["status"] == "placed"))
        skipped = point["not_applicable_count"]
        sx = (point["x"] or 0) * count
        sy = (point["y"] or 0) * count
        if existing:
            if existing["status"] == "placed":
                count -= 1
                sx -= existing["x"]
                sy -= existing["y"]
            else:
                skipped -= 1
        if count < 0 or skipped < 0:
            raise VibeError(
                "The saved contribution changed. Reload this round.",
                "changed_sample",
                409,
            )
        if row["draft_status"] == "placed":
            count += 1
            sx += row["draft_x"]
            sy += row["draft_y"]
        else:
            skipped += 1
        x = max(-1, min(1, sx / count)) if count else None
        y = max(-1, min(1, sy / count)) if count else None
        status = "placed" if count else "not_applicable" if skipped else "unmapped"
        conn.execute(
            """UPDATE song_vibe_positions SET x=?,y=?,status=?,updated_at=?,sample_count=?,
                        not_applicable_count=? WHERE song_id=? AND map_id=?""",
            (x, y, status, now, count, skipped, row["song_id"], map_id),
        )
        answers[map_id] = dict(
            status=row["draft_status"],
            x=row["draft_x"],
            y=row["draft_y"],
            request_id=key,
            revision=expected,
            submitted_at=now,
        )
        answers.pop("_draft_map", None)
        index = row["map_index"] + (0 if existing else 1)
        done = index == len(MAPS)
        conn.execute(
            """UPDATE vibe_rounds SET map_index=?,status=?,revision=revision+1,
            draft_status=NULL,draft_x=NULL,draft_y=NULL,draft_at=NULL,draft_key=NULL,answers=?,finished_at=?
            WHERE owner_hash=?""",
            (
                index,
                "complete" if done else "active",
                json.dumps(answers, allow_nan=False),
                (row["finished_at"] or now) if done else None,
                owner_hash(owner),
            ),
        )
        if done and not existing:
            saved = conn.execute(
                "UPDATE song_vibe_progress SET completed_passes=completed_passes+1 WHERE song_id=?",
                (row["song_id"],),
            )
            if saved.rowcount != 1:
                raise VibeError(
                    "The pass counter is missing. Check the database.",
                    "missing_counter",
                    409,
                )
        result = payload(conn, current(conn, owner))
        result.update(replayed=False, accepted_map=map_id)
        return result


def cancel(conn, owner, data):
    with transaction(conn):
        row = require_round(conn, owner, data)
        expected = revision(data.get("revision"))
        if row["status"] == "cancelled" and expected in (
            row["revision"],
            row["revision"] - 1,
        ):
            return payload(conn, row)
        if row["status"] != "active" or row["revision"] != expected:
            raise VibeError("This round has changed or ended.", "stale_revision", 409)
        conn.execute(
            """UPDATE vibe_rounds SET status='cancelled',finished_at=?,revision=revision+1,
            draft_status=NULL,draft_x=NULL,draft_y=NULL,draft_at=NULL,draft_key=NULL WHERE owner_hash=?""",
            (time.time(), owner_hash(owner)),
        )
        return payload(conn, current(conn, owner))


def heatmap(conn, kind, entity_id=None):
    scopes = {
        "all": None,
        "artist": ("song_artists", "artist_id"),
        "album": None,
        "tag": ("song_genres", "genre_id"),
    }
    if kind not in scopes:
        raise VibeError("Choose all, artist, album or tag.")
    params = []
    where = ""
    if kind != "all":
        if type(entity_id) is not int or not 0 < entity_id < 2**63:
            raise VibeError("A positive entity ID is required.")
        params = [entity_id]
        if kind == "album":
            where = " WHERE s.album_id=?"
        else:
            table, column = scopes[kind]
            where = f" WHERE EXISTS(SELECT 1 FROM {table} link WHERE link.song_id=s.id AND link.{column}=?)"
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT s.id FROM songs s" + where + " ORDER BY s.id", params
        )
    ]
    profiles = song_profiles(conn, ids)
    result = {key: dict(points=[], unmapped=0, not_applicable=0) for key in KEYS}
    for sid, points in profiles.items():
        for key, p in points.items():
            if p["status"] == "placed":
                result[key]["points"].append(
                    dict(
                        song_id=sid,
                        x=p["x"] * SCALE,
                        y=p["y"] * SCALE,
                        sample_count=p["sample_count"],
                        weight=1,
                    )
                )
            else:
                result[key][p["status"]] += 1
    return dict(
        kind=kind,
        entity_id=entity_id,
        song_count=len(ids),
        maps=result,
        min=-SCALE,
        max=SCALE,
    )


def browser_owner(create=False):
    if create and "vibe_owner" not in session:
        session["vibe_owner"] = secrets.token_urlsafe(32)
    return session.get("vibe_owner")


def respond(action, *, write=False):
    data = request.get_json(silent=True) if write else None
    if write and not isinstance(data, dict):
        return jsonify(message="A JSON object is required.", code="invalid"), 400
    conn = get_db_connection()
    try:
        # Reads return one consistent snapshot and never create a round.
        if not write:
            conn.execute("BEGIN")
        result = action(conn, data)
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response
    except VibeError as error:
        return (
            jsonify(message=str(error), code=error.code, **error.details),
            error.status,
        )
    finally:
        conn.close()


@app.get("/api/vibe-map/state")
def api_vibe_map_state():
    return respond(
        lambda c, d: (
            payload(c, current(c, browser_owner()))
            if browser_owner()
            else dict(round=None, version=VIBE_MAP_VERSION)
        )
    )


@app.post("/api/vibe-map/round")
def api_vibe_map_round():
    return respond(lambda c, d: start(c, browser_owner(True), d), write=True)


@app.post("/api/vibe-map/draft")
def api_vibe_map_draft():
    return respond(lambda c, d: draft(c, browser_owner(), d), write=True)


@app.post("/api/vibe-map/advance")
def api_vibe_map_advance():
    return respond(lambda c, d: advance(c, browser_owner(), d), write=True)


@app.post("/api/vibe-map/cancel")
def api_vibe_map_cancel():
    return respond(lambda c, d: cancel(c, browser_owner(), d), write=True)


@app.get("/api/vibe-map/profile/<int:song_id>")
def api_vibe_map_profile(song_id):
    return respond(lambda c, d: profile(c, song_id))


@app.get("/api/vibe-map/heatmap")
def api_vibe_map_heatmap():
    def read(conn, data):
        value = request.args.get("id")
        try:
            entity_id = int(value) if value is not None else None
        except ValueError:
            raise VibeError("A numeric entity ID is required.")
        return heatmap(conn, request.args.get("kind", "all"), entity_id)

    return respond(read)


@app.get("/vibe-map")
def vibe_map_page():
    return render_template(
        "vibe_map.html", page="vibe_map", vibe_version=VIBE_MAP_VERSION
    )


def similar_songs(conn, song_id, limit=2):
    """Rank shared placed maps by fixed Gaussian RMS closeness."""
    profile(conn, song_id)  # Validate identity, including an entirely unmapped source.
    profiles = song_profiles(
        conn, [r[0] for r in conn.execute("SELECT id FROM songs ORDER BY id")]
    )
    source = profiles[song_id]
    ranked = []
    for sid, points in profiles.items():
        if sid == song_id:
            continue
        comparison = compare_profiles(source, points)
        if comparison["shared_maps"]:
            ranked.append(dict(song_id=sid, **comparison))
    ranked.sort(key=lambda r: (-r["similarity"], -r["shared_maps"], r["song_id"]))
    matches = []
    for match in ranked[:limit]:
        match["similarity"] = round(match["similarity"], 2)
        match["song"] = snapshot_song(conn, get_song_full(match["song_id"], conn))
        matches.append(match)
    return dict(
        song_id=song_id,
        matches=matches,
        total_comparable=len(ranked),
        map_count=len(MAPS),
    )


@app.get("/api/vibe-map/similar/<int:song_id>")
def api_vibe_map_similar(song_id):
    def read(conn, data):
        try:
            limit = int(request.args.get("limit", "2"))
        except ValueError:
            raise VibeError("Use a similarity limit between 1 and 100.")
        if not 1 <= limit <= 100:
            raise VibeError("Use a similarity limit between 1 and 100.")
        return similar_songs(conn, song_id, limit)

    return respond(read)


# Read-only Vibe Map dashboard; one aggregate per song, never per-play histories.


SIGNAL = 0.2  # One unit on the displayed -5..5 axes; neutral points are not poles.
DENSITY_RADIUS = 0.2


def percentage(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def consistency(vectors):
    """Gaussian of mean squared pair distance, equally weighting four maps.

    Centred sums avoid an O(n²) group-pair loop. With two tracks this is exactly
    their public similarity. Repeats and group size do not multiply a song's vote.
    """
    n = len(vectors)
    if n < 2:
        return None
    squared = 0.0
    for key, *_ in MAPS:
        for axis in (0, 1):
            mean = math.fsum(v[key][axis] for v in vectors) / n
            squared += math.fsum((v[key][axis] - mean) ** 2 for v in vectors)
    mean_pair_distance = 2 * squared / ((n - 1) * len(MAPS))
    return 100 * math.exp(-mean_pair_distance / (2 * WIDTH**2))


def density(points):
    """Fixed-radius neighbours on a spatial grid; each point stays at its location."""
    bins = defaultdict(list)
    for i, p in enumerate(points):
        bins[
            (math.floor(p["x"] / DENSITY_RADIUS), math.floor(p["y"] / DENSITY_RADIUS))
        ].append(i)
    for p in points:
        gx, gy = math.floor(p["x"] / DENSITY_RADIUS), math.floor(
            p["y"] / DENSITY_RADIUS
        )
        p["nearby"] = sum(
            (points[i]["x"] - p["x"]) ** 2 + (points[i]["y"] - p["y"]) ** 2
            <= DENSITY_RADIUS**2 + 1e-12
            for x in range(gx - 1, gx + 2)
            for y in range(gy - 1, gy + 2)
            for i in bins.get((x, y), ())
        )
    maximum = max((p["nearby"] for p in points), default=0)
    return maximum


def colour_points(points, maximum):
    for p in points:
        strength = math.sqrt(p["nearby"] / maximum)
        p.update(
            cx=round(28 + (p["x"] + 1) * 242, 4),
            cy=round(388 - (p["y"] + 1) * 180, 4),
            colour="rgb("
            + ",".join(
                str(round(a + (b - a) * strength))
                for a, b in zip((150, 52, 73), (255, 211, 188))
            )
            + ")",
            opacity=round(0.35 + 0.55 * strength, 3),
        )


def paired_highlights(complete, songs, vectors):
    nearest = []
    furthest = []

    def retain(heap, rank, pair):
        item = (rank, pair)
        if len(heap) < 2:
            heappush(heap, item)
        elif rank > heap[0][0]:
            heapreplace(heap, item)

    for i, a in enumerate(complete):
        for b in complete[i + 1 :]:
            value = compare_positions(vectors[a], vectors[b])["similarity"]
            pair = dict(
                first=songs[a],
                second=songs[b],
                similarity=round(value, 1),
                shared_maps=len(MAPS),
            )
            retain(nearest, (value, -a, -b), pair)
            retain(furthest, (-value, -a, -b), pair)
    return (
        [p for _, p in sorted(nearest, reverse=True)],
        [p for _, p in sorted(furthest, reverse=True)],
    )


def common_patterns(vectors):
    axes = [
        dict(id=key + "_" + axis, map_id=key, axis=index, low=low, high=high)
        for key, _, xl, xh, yl, yh in DISPLAY_MAPS
        for axis, index, low, high in (("x", 0, xl, xh), ("y", 1, yl, yh))
    ]
    balances = []
    for a in axes:
        values = [
            v[a["map_id"]][a["axis"]] for v in vectors.values() if a["map_id"] in v
        ]
        low = sum(v < -SIGNAL for v in values)
        high = sum(v > SIGNAL for v in values)
        middle = len(values) - low - high
        balances.append(
            dict(
                a,
                low_count=low,
                high_count=high,
                middle_count=middle,
                total=len(values),
                low_share=percentage(low, len(values)) or 0,
                high_share=percentage(high, len(values)) or 0,
                middle_share=percentage(middle, len(values)) or 0,
                centre="Present" if a["id"] == "perspective_x" else "Balanced",
            )
        )
    patterns = []
    for a, b in combinations(axes, 2):
        common = [v for v in vectors.values() if a["map_id"] in v and b["map_id"] in v]
        for sign_a, label_a in ((-1, a["low"]), (1, a["high"])):
            for sign_b, label_b in ((-1, b["low"]), (1, b["high"])):
                count = sum(
                    v[a["map_id"]][a["axis"]] * sign_a > SIGNAL
                    and v[b["map_id"]][b["axis"]] * sign_b > SIGNAL
                    for v in common
                )
                if count:
                    patterns.append(
                        dict(
                            label=label_a + " + " + label_b,
                            count=count,
                            total=len(common),
                            share=percentage(count, len(common)),
                        )
                    )
    patterns.sort(key=lambda p: (-p["count"], -p["share"], p["label"]))
    return balances, patterns[:8]


def build_vibe_stats(conn):
    albums = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT id,title,cover_url FROM albums ORDER BY id")
    }
    artists = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT id,name,cover_url FROM artists ORDER BY id")
    }
    tags = {
        r["id"]: dict(r) for r in conn.execute("SELECT id,name FROM genres ORDER BY id")
    }
    artist_members = defaultdict(set)
    tag_members = defaultdict(set)
    album_members = defaultdict(set)
    song_artists = defaultdict(set)
    for row in conn.execute("SELECT song_id,artist_id FROM song_artists"):
        if row["artist_id"] in artists:
            artist_members[row["artist_id"]].add(row["song_id"])
            song_artists[row["song_id"]].add(row["artist_id"])
    for row in conn.execute("SELECT song_id,genre_id FROM song_genres"):
        if row["genre_id"] in tags:
            tag_members[row["genre_id"]].add(row["song_id"])
    songs = {}
    for row in conn.execute("SELECT id,title,album_id FROM songs ORDER BY id"):
        song = dict(row)
        aa = [artists[aid] for aid in song_artists[song["id"]]]
        album = albums.get(song["album_id"])
        song.update(versus_metadata(album, aa))
        song["artist"] = ", ".join(a["name"] for a in song["artist_links"])
        songs[song["id"]] = song
        if album:
            album_members[album["id"]].add(song["id"])
    profiles = song_profiles(conn, songs)
    passes = pass_counts(conn, songs)
    vectors = {
        sid: positions({"vibe_maps": profile}) for sid, profile in profiles.items()
    }
    complete = [sid for sid in songs if len(vectors[sid]) == len(MAPS)]
    selected = sum(
        any(p["status"] != "unmapped" for p in profile.values())
        for profile in profiles.values()
    )
    placed = sum(map(len, vectors.values()))
    samples = sum(
        max(p["sample_count"], int(p["status"] == "placed"))
        for profile in profiles.values()
        for p in profile.values()
    )
    overview = dict(
        total=len(songs),
        selected=selected,
        full=len(complete),
        partial=selected - len(complete),
        unselected=len(songs) - selected,
        passes=sum(passes.values()),
        repeated=sum(
            passes[sid] > 1
            or any(p["sample_count"] > 1 for p in profiles[sid].values())
            for sid in songs
        ),
        samples=samples,
        coverage=percentage(selected, len(songs)),
        placed=placed,
        slots=4 * len(songs),
        map_coverage=percentage(placed, 4 * len(songs)),
        consistency=consistency([vectors[s] for s in complete]),
    )
    maps = map_definitions(conn)
    for m in maps:
        points = [
            dict(
                song_id=sid,
                title=songs[sid]["title"],
                artist=songs[sid]["artist"],
                x=v[m["id"]][0],
                y=v[m["id"]][1],
            )
            for sid, v in vectors.items()
            if m["id"] in v
        ]
        m.update(
            points=points,
            count=len(points),
            unmapped=len(songs) - len(points),
            max_nearby=density(points),
            coverage=percentage(len(points), len(songs)),
        )
    maximum = max((m["max_nearby"] for m in maps), default=0)
    for m in maps:
        colour_points(m["points"], maximum)
    balances, patterns = common_patterns(vectors)
    closest, contrasts = paired_highlights(complete, songs, vectors)
    groups = []
    for kind, entities, members in (
        ("album", albums, album_members),
        ("artist", artists, artist_members),
        ("tag", tags, tag_members),
    ):
        rows = []
        for eid, entity in entities.items():
            if kind == "album" and not proper_album(entity):
                continue
            ids = members[eid] & songs.keys()
            mapped = [sid for sid in sorted(ids) if len(vectors[sid]) == len(MAPS)]
            if len(mapped) < 2:
                continue
            value = consistency([vectors[sid] for sid in mapped])
            rows.append(
                dict(
                    id=eid,
                    name=entity.get("name", entity.get("title")),
                    cover_url=entity.get("cover_url") or "",
                    mapped=len(mapped),
                    total=len(ids),
                    coverage=percentage(len(mapped), len(ids)),
                    consistency=round(value, 1),
                    _score=value,
                )
            )
        high = sorted(
            rows, key=lambda r: (-r["_score"], -r["mapped"], -r["coverage"], r["id"])
        )[:5]
        low = sorted(
            rows, key=lambda r: (r["_score"], -r["mapped"], -r["coverage"], r["id"])
        )[:5]
        for row in rows:
            row.pop("_score")
        groups.append(
            dict(
                kind=kind,
                title=dict(album="Albums", artist="Artists", tag="Tags")[kind],
                eligible=len(rows),
                most=high,
                least=low,
            )
        )
    return dict(
        overview=overview,
        maps=maps,
        balances=balances,
        patterns=patterns,
        closest=closest,
        contrasts=contrasts,
        groups=groups,
    )


# Read-only song inspector, reusable by dedicated song profile panels.


def build_song_vibe(conn, song_id, *, show_identity=True):
    saved = profile(
        conn, song_id
    )  # Validate first; missing songs return the mode's 404.
    comparison = similar_songs(conn, song_id, limit=2)
    song = snapshot_song(conn, get_song_full(song_id, conn))
    for item in [song] + [match["song"] for match in comparison["matches"]]:
        item["album_link"] = (
            dict(title=item["album"], id=item["album_id"])
            if proper_album(dict(title=item["album"]))
            else None
        )
    # Public profile coordinates are -5..5; readiness uses the radar's validated slots.
    profile_ready = all(
        spoke["radius"] is not None for spoke in saved["radar"]["spokes"]
    )
    data = dict(
        profile_ready=profile_ready,
        song=song,
        profile=saved,
        matches=comparison["matches"],
        total_comparable=comparison["total_comparable"],
        map_count=comparison["map_count"],
    )
    return dict(
        data,
        html=render_template(
            "vibe_song_stats_panel.html", show_identity=show_identity, **data
        ),
    )


# Compact, scoped Vibe Map cards using the dashboard's existing measures.


def build_entity_vibe(conn, kind, entity_id):
    tables = {
        "album": ("albums", "title"),
        "artist": ("artists", "name"),
        "tag": ("genres", "name"),
    }
    if kind not in tables:
        raise VibeError("Choose album, artist or tag.")
    if type(entity_id) is not int or not 0 < entity_id < 2**63:
        raise VibeError("A positive entity ID is required.")
    table, name_column = tables[kind]
    entity = conn.execute(
        f"SELECT id,{name_column} AS name FROM {table} WHERE id=?", (entity_id,)
    ).fetchone()
    if entity is None:
        raise VibeError("This collection no longer exists.", "missing_entity", 404)
    if kind == "album":
        where = "s.album_id=?"
    else:
        link, column = (
            ("song_artists", "artist_id")
            if kind == "artist"
            else ("song_genres", "genre_id")
        )
        where = f"EXISTS(SELECT 1 FROM {link} link WHERE link.song_id=s.id AND link.{column}=?)"
    songs = {
        r["id"]: dict(r)
        for r in conn.execute(
            f"SELECT s.id,s.title FROM songs s WHERE {where} ORDER BY s.id",
            (entity_id,),
        )
    }
    profiles = song_profiles(conn, songs)
    vectors = {
        sid: positions({"vibe_maps": profile}) for sid, profile in profiles.items()
    }
    full = [v for v in vectors.values() if len(v) == len(MAPS)]
    selected = sum(
        any(p["status"] != "unmapped" for p in profile.values())
        for profile in profiles.values()
    )
    score = consistency(full)
    summary = dict(
        total=len(songs),
        full=len(full),
        partial=selected - len(full),
        consistency=round(score, 1) if score is not None else None,
    )
    maps = map_definitions(conn)
    for definition in maps:
        key = definition["id"]
        points = [
            dict(song_id=sid, title=songs[sid]["title"], x=v[key][0], y=v[key][1])
            for sid, v in vectors.items()
            if key in v
        ]
        definition.update(points=points, count=len(points), max_nearby=density(points))
    maximum = max((m["max_nearby"] for m in maps), default=0)
    for definition in maps:
        colour_points(definition["points"], maximum)
    data = dict(
        profile_ready=len(full) >= 2,
        kind=kind,
        entity=dict(entity),
        summary=summary,
        maps=maps,
    )
    return dict(data, html=render_template("vibe_entity_stats_panel.html", **data))


# Read-only library cards and collection consistency rankings; no pair matrix.


CATEGORIES = {
    "albums": ("albums", "title"),
    "artists": ("artists", "name"),
    "tags": ("genres", "name"),
}


def library_data(conn):
    songs = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT id,title,album_id FROM songs ORDER BY id")
    }
    profiles = song_profiles(conn, songs)
    vectors = {sid: positions({"vibe_maps": p}) for sid, p in profiles.items()}
    full = [v for v in vectors.values() if len(v) == len(MAPS)]
    selected = sum(
        any(p["status"] != "unmapped" for p in profile.values())
        for profile in profiles.values()
    )
    score = consistency(full)
    summary = dict(
        total=len(songs),
        full=len(full),
        partial=selected - len(full),
        selected=selected,
        consistency=round(score, 1) if score is not None else None,
        positions=sum(map(len, vectors.values())),
        passes=sum(pass_counts(conn, songs).values()),
        coverage=percentage(selected, len(songs)),
    )
    rankings = {}
    for category, (table, name) in CATEGORIES.items():
        cover = ",cover_url" if category != "tags" else ",'' AS cover_url"
        entities = {
            r["id"]: dict(r)
            for r in conn.execute(
                f"SELECT id,{name} AS name{cover} FROM {table} ORDER BY id"
            )
        }
        members = defaultdict(set)
        if category == "albums":
            for sid, s in songs.items():
                members[s["album_id"]].add(sid)
        else:
            link, col = (
                ("song_artists", "artist_id")
                if category == "artists"
                else ("song_genres", "genre_id")
            )
            for r in conn.execute(f"SELECT song_id,{col} AS entity_id FROM {link}"):
                if r["song_id"] in songs:
                    members[r["entity_id"]].add(r["song_id"])
        rows = []
        for eid, entity in entities.items():
            if category == "albums" and not proper_album(dict(title=entity["name"])):
                continue
            ids = members[eid]
            mapped = [
                vectors[sid] for sid in sorted(ids) if len(vectors[sid]) == len(MAPS)
            ]
            if len(mapped) < 2:
                continue
            raw = consistency(mapped)
            if category == "albums":
                entity["title"] = entity["name"]
            rows.append(
                dict(
                    entity,
                    mapped=len(mapped),
                    total=len(ids),
                    song_count=len(ids),
                    coverage=percentage(len(mapped), len(ids)),
                    consistency=round(raw, 1),
                    _score=raw,
                )
            )
        rows.sort(key=lambda r: (-r["_score"], -r["mapped"], -r["coverage"], r["id"]))
        for rank, row in enumerate(rows, 1):
            row.pop("_score")
            row["rank"] = rank
        rankings[category] = rows
    return summary, songs, vectors, rankings


def build_library_vibe(conn):
    summary, songs, vectors, rankings = library_data(conn)
    maps = map_definitions(conn)
    for m in maps:
        points = [
            dict(
                song_id=sid, title=songs[sid]["title"], x=v[m["id"]][0], y=v[m["id"]][1]
            )
            for sid, v in vectors.items()
            if m["id"] in v
        ]
        m.update(points=points, count=len(points), max_nearby=density(points))
    maximum = max((m["max_nearby"] for m in maps), default=0)
    for m in maps:
        colour_points(m["points"], maximum)
    data = dict(summary=summary, maps=maps)
    leaders = {
        category: rows[0] if rows else None for category, rows in rankings.items()
    }
    counts = {category: len(rows) for category, rows in rankings.items()}
    return dict(
        profile_ready=summary["full"] >= 2,
        **data,
        html=render_template("vibe_entity_stats_panel.html", **data),
        global_html=render_template(
            "vibe_global_stats_panel.html", **data, leaders=leaders, counts=counts
        ),
        banner={category: rows[:20] for category, rows in rankings.items()},
        counts=counts,
    )


def build_vibe_rankings(conn, category, view):
    pass
    if category not in CATEGORIES:
        raise VibeError("Choose albums, artists or tags.")
    if view not in ("top", "bottom"):
        raise VibeError("Choose top or bottom.")
    _, _, _, rankings = library_data(conn)
    rows = rankings[category]
    return dict(
        entity=category,
        view=view,
        total=len(rows),
        limit=20,
        items=(rows if view == "top" else list(reversed(rows)))[:20],
    )


@app.get("/vibe_map_stats")
def vibe_map_stats():
    pass
    from songranker.storage.vibe_state import VIBE_MAP_VERSION

    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_vibe_stats(conn)
        response = app.make_response(
            render_template(
                "vibe_stats.html",
                page="vibe_stats",
                vibe_version=VIBE_MAP_VERSION,
                **data,
            )
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        conn.close()


@app.get("/api/vibe-map/stats")
def api_vibe_map_stats():
    pass
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        response = jsonify(build_vibe_stats(conn))
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        conn.close()


@app.get("/api/vibe-map/inspect/<int:song_id>")
def api_vibe_map_inspect(song_id):
    pass

    return respond(
        lambda conn, data: build_song_vibe(
            conn, song_id, show_identity=request.args.get("context") != "profile"
        )
    )


@app.get("/api/vibe-map/entity/<kind>/<int:entity_id>")
def api_vibe_map_entity(kind, entity_id):
    pass

    return respond(lambda conn, data: build_entity_vibe(conn, kind, entity_id))


@app.get("/api/vibe-map/library")
def api_vibe_map_library():
    pass

    return respond(lambda conn, data: build_library_vibe(conn))


@app.get("/api/vibe-map/rankings")
def api_vibe_map_rankings():
    pass

    return respond(
        lambda conn, data: build_vibe_rankings(
            conn, request.args.get("entity", "albums"), request.args.get("view", "top")
        )
    )
