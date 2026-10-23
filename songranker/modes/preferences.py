"""The ordinary preference write path: offers, receipts, corrections and replay."""

from contextlib import contextmanager
import hashlib
import json
import math
import secrets
from songranker.storage.preference_state import (
    calculate_new_elo,
    compact,
    replay,
    mode_replay,
)

RULES_VERSION = 1
EXPOSURE_MODES = (
    "public",
    "standard",
    "blind",
    "trivia",
    "guesser",
    "tournament",
    "shelves",
)


class PreferenceError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@contextmanager
def transaction(conn):
    """Run atomic preference writes in an immediate transaction or nested savepoint
    with rollback on failure.
    """
    nested = conn.in_transaction
    savepoint = "preference_" + secrets.token_hex(8)
    conn.execute("SAVEPOINT " + savepoint if nested else "BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("RELEASE " + savepoint) if nested else conn.commit()
    except BaseException:
        if nested:
            conn.execute("ROLLBACK TO " + savepoint)
            conn.execute("RELEASE " + savepoint)
        else:
            conn.rollback()
        raise


def owner_hash(owner):
    """Hash a browser-owner identity before persisting preference ownership."""
    return hashlib.sha256(str(owner).encode("utf-8")).hexdigest()


def snapshot_song(conn, song):
    row = dict(song)
    # Freeze identity/preview facts, never expose pre-vote Elo in an offer.
    result = {
        key: row.get(key)
        for key in (
            "id",
            "title",
            "album_id",
            "audio_url",
            "album",
            "album_is_single",
            "cover_url",
            "artist",
            "genres",
        )
    }
    links = [
        dict(r)
        for r in conn.execute(
            """SELECT a.id,a.name FROM song_artists sa
        JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=? ORDER BY a.id""",
            (row["id"],),
        )
    ]
    result.update(
        artist_ids=[a["id"] for a in links],
        artist_links=links,
        tag_ids=[
            r[0]
            for r in conn.execute(
                "SELECT genre_id FROM song_genres WHERE song_id=? ORDER BY genre_id",
                (row["id"],),
            )
        ],
    )
    return result


def ensure_seeds(conn):
    state = conn.execute("SELECT * FROM preference_replay_state WHERE id=1").fetchone()
    if state is None:
        if conn.execute("SELECT 1 FROM preference_events LIMIT 1").fetchone():
            raise PreferenceError(
                "Preference replay state is missing. Restore a verified backup.", 409
            )
        conn.execute(
            "INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',1)"
        )
        state = conn.execute(
            "SELECT * FROM preference_replay_state WHERE id=1"
        ).fetchone()
    conn.execute(
        """INSERT INTO preference_rating_seeds(song_id,elo,matches,highest_elo,highest_rank)
        SELECT id,elo_score,COALESCE(matches_played,0),COALESCE(highest_elo,elo_score),COALESCE(highest_rank,9999)
        FROM songs WHERE id NOT IN (SELECT song_id FROM preference_rating_seeds)"""
    )
    for mode in ("standard", "blind"):
        conn.execute(
            """INSERT OR IGNORE INTO preference_mode_ratings(song_id,mode)
            SELECT id,? FROM songs""",
            (mode,),
        )
    return dict(state)


def get_offer(conn, owner, mode, choose_pair):
    if mode not in ("standard", "blind"):
        raise PreferenceError("Choose non-blind or blind voting.")
    with transaction(conn):
        ensure_seeds(conn)
        offer = conn.execute(
            "SELECT * FROM preference_offers WHERE owner_hash=? AND mode=? AND origin='ordinary' AND status='open'",
            (owner_hash(owner), mode),
        ).fetchone()
        if (
            offer
            and conn.execute(
                "SELECT COUNT(*) FROM songs WHERE id IN (?,?)",
                (offer["song1_id"], offer["song2_id"]),
            ).fetchone()[0]
            != 2
        ):
            conn.execute(
                "UPDATE preference_offers SET status='cancelled',closed_at=CURRENT_TIMESTAMP WHERE token=?",
                (offer["token"],),
            )
            offer = None
        if offer is None:
            first, second = choose_pair()
            if first is None or second is None:
                raise PreferenceError(
                    "Add at least two eligible songs with previews for blind voting."
                )
            first, second = snapshot_song(conn, first), snapshot_song(conn, second)
            token = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO preference_offers(token,owner_hash,song1_id,song2_id,mode,rules_version,song1_snapshot,song2_snapshot)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    token,
                    owner_hash(owner),
                    first["id"],
                    second["id"],
                    mode,
                    RULES_VERSION,
                    compact(first),
                    compact(second),
                ),
            )
            offer = conn.execute(
                "SELECT * FROM preference_offers WHERE token=?", (token,)
            ).fetchone()
        return {
            "token": offer["token"],
            "mode": offer["mode"],
            "rules_version": offer["rules_version"],
            "songs": [
                json.loads(offer["song1_snapshot"]),
                json.loads(offer["song2_snapshot"]),
            ],
        }


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise PreferenceError("Enter a valid " + label + ".")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise PreferenceError("Enter a valid " + label + ".") from None
    if not 0 < result <= 9223372036854775807:
        raise PreferenceError("Enter a valid " + label + ".")
    return result


def token(value):
    """Validate the shape and length of a preference offer token before lookup."""
    if not isinstance(value, str) or not 16 <= len(value) <= 200:
        raise PreferenceError(
            "Reload this round before saving. Its round token is missing or invalid."
        )
    return value


def receipt(event):
    """Build a saved vote receipt from frozen song snapshots and before/after
    ratings.
    """
    def side(prefix):
        """Project one receipt participant with its saved identity and exact Elo
        change.
        """
        song = json.loads(event[prefix + "_snapshot"])
        return {
            **song,
            "elo_before": event[prefix + "_before"],
            "elo_score": event[prefix + "_after"],
            "elo_change": f"{event[prefix + '_after'] - event[prefix + '_before']:+.0f}",
        }

    return {
        "event_id": event["id"],
        "token": event["offer_token"],
        "mode": event["mode"],
        "rules_version": event["rules_version"],
        "winner": side("winner"),
        "loser": side("loser"),
    }


def record_preference(
    conn,
    w,
    l,
    mode,
    snapshots,
    *,
    offer_token=None,
    tournament_id=None,
    tournament_match_id=None,
    weight=1,
):
    """One atomic fact/public/mode update, called inside the owning transaction."""
    if not conn.in_transaction:
        raise RuntimeError("Preference writes require an owning transaction.")
    tournament = tournament_match_id is not None
    if (
        mode not in ("standard", "blind")
        or w == l
        or weight not in (0.5, 1)
        or (not tournament and weight != 1)
    ):
        raise PreferenceError("Invalid preference rules.")
    songs = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM songs WHERE id IN (?,?)", (w, l))
    }
    if len(songs) != 2:
        raise PreferenceError(
            "A song in this round was removed. Load a new round.", 409
        )
    ensure_seeds(conn)
    a, b = songs[w]["elo_score"], songs[l]["elo_score"]
    na, nb = calculate_new_elo(a, b, 32 * weight)
    cursor = conn.execute(
        """INSERT INTO preference_events(winner_id,loser_id,mode,created_at,
        winner_before,winner_after,loser_before,loser_after,offer_token,origin,rules_version,
        winner_snapshot,loser_snapshot,rating_weight,tournament_id,tournament_match_id)
        VALUES(?,?,?,CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            w,
            l,
            mode,
            a,
            na,
            b,
            nb,
            offer_token,
            "tournament" if tournament else "ordinary",
            RULES_VERSION,
            compact(snapshots[w]),
            compact(snapshots[l]),
            weight,
            tournament_id,
            tournament_match_id,
        ),
    )
    event_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO preference_rating_projection VALUES(?,?,?,?,?)",
        (event_id, a, na, b, nb),
    )
    for sid, value in ((w, na), (l, nb)):
        conn.execute(
            """UPDATE songs SET elo_score=?,matches_played=matches_played+?,
            highest_elo=MAX(highest_elo,?) WHERE id=?""",
            (value, int(not tournament), value, sid),
        )
    for sid in (w, l):
        rank = conn.execute(
            "SELECT COUNT(*)+1 FROM songs WHERE elo_score>(SELECT elo_score FROM songs WHERE id=?)",
            (sid,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE songs SET highest_rank=MIN(highest_rank,?) WHERE id=?", (rank, sid)
        )
    current = {
        r["song_id"]: r["elo"]
        for r in conn.execute(
            "SELECT song_id,elo FROM preference_mode_ratings WHERE mode=? AND song_id IN (?,?)",
            (mode, w, l),
        )
    }
    values = calculate_new_elo(current[w], current[l], 32 * weight)
    for sid, value in zip((w, l), values):
        conn.execute(
            """UPDATE preference_mode_ratings SET elo=?,matches=matches+1,
            tournament_matches=tournament_matches+? WHERE song_id=? AND mode=?""",
            (value, int(tournament), sid, mode),
        )
    return event_id


def save_tournament_preference(conn, tournament, match, winner, loser):
    """Only newly created, eligible first rounds enter the shared preference log."""
    if (
        tournament["elo_policy_version"] != 1
        or match["round_number"] != 1
        or match["match_type"] != "bracket"
    ):
        return None
    from songranker.services import SONG_SELECT

    snapshots = {
        sid: snapshot_song(
            conn, conn.execute(SONG_SELECT + " WHERE s.id=?", (sid,)).fetchone()
        )
        for sid in (winner, loser)
    }
    return record_preference(
        conn,
        winner,
        loser,
        "blind" if tournament["is_blind"] else "standard",
        snapshots,
        tournament_id=match["tournament_id"],
        tournament_match_id=match["id"],
        weight=tournament["elo_weight"],
    )


def save_vote(conn, owner, data):
    offered_token = token(data.get("token"))
    w, l = integer(data.get("winner_id"), "winner"), integer(
        data.get("loser_id"), "opponent"
    )
    mode = data.get("mode")
    if mode not in ("standard", "blind") or w == l:
        raise PreferenceError("Choose two different songs in the offered voting mode.")
    with transaction(conn):
        offer = conn.execute(
            "SELECT * FROM preference_offers WHERE token=? AND owner_hash=?",
            (offered_token, owner_hash(owner)),
        ).fetchone()
        if offer is None:
            raise PreferenceError("This round is unavailable. Load a new round.", 404)
        if (
            offer["mode"] != mode
            or offer["origin"] != "ordinary"
            or offer["rules_version"] != RULES_VERSION
        ):
            raise PreferenceError(
                "This submission does not match the offered round.", 409
            )
        if "rules_version" in data and data["rules_version"] != offer["rules_version"]:
            raise PreferenceError("The round rules do not match this submission.", 409)
        existing = conn.execute(
            "SELECT * FROM preference_events WHERE offer_token=?", (offered_token,)
        ).fetchone()
        if existing:
            saved = receipt(existing)
            if saved["winner"]["id"] != w or saved["loser"]["id"] != l:
                error = PreferenceError("This round already has a saved result.", 409)
                error.saved_result = saved
                raise error
            return saved
        if offer["status"] != "open":
            raise PreferenceError("This round was closed. Load a new round.", 409)
        if {w, l} != {offer["song1_id"], offer["song2_id"]}:
            raise PreferenceError("Choose the two songs from the offered round.", 409)
        snapshots = {
            item["id"]: item
            for item in (
                json.loads(offer["song1_snapshot"]),
                json.loads(offer["song2_snapshot"]),
            )
        }
        event_id = record_preference(
            conn, w, l, mode, snapshots, offer_token=offered_token
        )

        conn.execute(
            "UPDATE preference_offers SET status='answered',closed_at=CURRENT_TIMESTAMP,song1_snapshot=NULL,song2_snapshot=NULL WHERE token=?",
            (offered_token,),
        )
        return receipt(
            conn.execute(
                "SELECT * FROM preference_events WHERE id=?", (event_id,)
            ).fetchone()
        )


def rebuild_ratings(conn):
    settings = ensure_seeds(conn)
    songs = [dict(r) for r in conn.execute("SELECT id FROM songs")]
    seeds = {
        r["song_id"]: dict(r)
        for r in conn.execute("SELECT * FROM preference_rating_seeds")
    }
    events = [
        dict(r) for r in conn.execute("SELECT * FROM preference_effective ORDER BY id")
    ]
    overrides = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM preference_rating_overrides ORDER BY after_event_id,id"
        )
    ]
    ratings, projected = replay(
        songs,
        seeds,
        events,
        overrides,
        settings["cutoff_event_id"],
        settings["legacy_boundary"],
    )
    conn.execute(
        "DELETE FROM preference_rating_projection WHERE event_id>?",
        (settings["cutoff_event_id"],),
    )
    conn.executemany(
        "INSERT INTO preference_rating_projection VALUES(?,?,?,?,?)",
        ((event_id, *values) for event_id, values in projected.items()),
    )
    conn.executemany(
        "UPDATE songs SET elo_score=?,matches_played=?,highest_elo=?,highest_rank=? WHERE id=?",
        (
            (row["elo"], row["matches"], row["highest_elo"], row["highest_rank"], sid)
            for sid, row in ratings.items()
        ),
    )
    conn.execute("DELETE FROM preference_mode_ratings")
    conn.executemany(
        "INSERT INTO preference_mode_ratings VALUES(?,?,?,?,?)",
        (
            (sid, mode, row["elo"], row["matches"], row["tournament_matches"])
            for (sid, mode), row in mode_replay(songs, events).items()
        ),
    )


def fingerprint(event):
    """Hash a preference event's compact representation for stale correction checks."""
    return hashlib.sha256(compact(dict(event)).encode("utf-8")).hexdigest()


def event_detail(conn, event_id):
    event_id = integer(event_id, "event ID")
    original = conn.execute(
        "SELECT * FROM preference_events WHERE id=?", (event_id,)
    ).fetchone()
    if original is None:
        raise PreferenceError("Saved vote not found.", 404)
    effective = dict(
        conn.execute(
            "SELECT * FROM preference_effective WHERE id=?", (event_id,)
        ).fetchone()
    )
    source = dict(original)
    snapshots = [
        json.loads(source["winner_snapshot"]),
        json.loads(source["loser_snapshot"]),
    ]
    return {
        "id": event_id,
        "original": source,
        "effective": effective,
        "songs": snapshots,
        "fingerprint": fingerprint(original),
        "correctable": source["origin"] != "tournament"
        and event_id
        > conn.execute(
            "SELECT cutoff_event_id FROM preference_replay_state WHERE id=1"
        ).fetchone()[0],
        "corrections": [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM preference_corrections WHERE event_id=? ORDER BY id",
                (event_id,),
            )
        ],
    }


def correction_response(row):
    """Return the corrected event ID, revision and active state after successful
    replay.
    """
    return {
        "status": "success",
        "message": "Vote correction saved. Ratings and statistics were rebuilt.",
        "event_id": row["event_id"],
        "revision": row["id"],
        "active": bool(row["active"]),
    }


def correct_vote(conn, event_id, data):
    request_token = token(data.get("request_token"))
    action = data.get("action")
    if action not in ("void", "restore", "replace"):
        raise PreferenceError("Choose void, restore or replace.")
    reason = str(data.get("reason") or "").strip()
    if len(reason) > 1000:
        raise PreferenceError("Keep the correction note under 1000 characters.")
    with transaction(conn):
        existing = conn.execute(
            "SELECT * FROM preference_corrections WHERE request_token=?",
            (request_token,),
        ).fetchone()
        if existing:
            expected_w = data.get("winner_id")
            if (
                existing["event_id"] != event_id
                or existing["action"] != action
                or existing["reason"] != reason
                or action == "replace"
                and (
                    existing["winner_id"] != integer(expected_w, "winner")
                    or existing["mode"] != data.get("mode")
                )
            ):
                raise PreferenceError(
                    "That correction token was already used for a different change.",
                    409,
                )
            return correction_response(existing)
        detail = event_detail(conn, event_id)
        current = detail["effective"]
        if detail["original"]["origin"] == "tournament":
            raise PreferenceError(
                "Tournament Elo follows its saved first-round result. Delete/reset that bracket to remove its influence; ordinary-vote corrections cannot change bracket results.",
                409,
            )
        if (
            data.get("expected_revision") != current["revision"]
            or data.get("fingerprint") != detail["fingerprint"]
        ):
            raise PreferenceError(
                "This vote changed since you opened it. Reload the saved vote.", 409
            )
        settings = ensure_seeds(conn)
        if event_id <= settings["cutoff_event_id"]:
            raise PreferenceError(
                "The older history cannot reconstruct its saved Elo. Pre-upgrade votes are protected by a legacy anchor.",
                409,
            )
        ids = {song.get("id") for song in detail["songs"]}
        if (
            len(ids) != 2
            or None in ids
            or conn.execute(
                "SELECT COUNT(*) FROM songs WHERE id IN (?,?)", tuple(ids)
            ).fetchone()[0]
            != 2
        ):
            raise PreferenceError(
                "Restore the missing catalogue song from backup before correcting this vote.",
                409,
            )
        winner, loser, mode = current["winner_id"], current["loser_id"], current["mode"]
        if action == "replace":
            winner = integer(data.get("winner_id"), "winner")
            if winner not in ids or data.get("mode") not in ("standard", "blind"):
                raise PreferenceError("Use the original pair and a valid voting mode.")
            loser = next(sid for sid in ids if sid != winner)
            mode = data["mode"]
        active = int(action != "void")
        cursor = conn.execute(
            """INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active,reason)
            VALUES(?,?,?,?,?,?,?,?)""",
            (event_id, request_token, action, winner, loser, mode, active, reason),
        )
        rebuild_ratings(conn)
        return correction_response(
            conn.execute(
                "SELECT * FROM preference_corrections WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
        )


def override_rating(conn, data):
    request_token = token(data.get("request_token"))
    sid = integer(data.get("song_id"), "song ID")
    reason = str(data.get("reason") or "").strip()
    if len(reason) > 1000 or isinstance(data.get("new_elo"), bool):
        raise PreferenceError(
            "Enter a numeric Elo and keep the note under 1000 characters."
        )
    try:
        value = float(data.get("new_elo"))
    except (TypeError, ValueError):
        raise PreferenceError("Enter a numeric Elo value.") from None
    if not math.isfinite(value) or not 0 <= value <= 5000:
        raise PreferenceError("Elo must be between 0 and 5000.")
    with transaction(conn):
        old = conn.execute(
            "SELECT * FROM preference_rating_overrides WHERE request_token=?",
            (request_token,),
        ).fetchone()
        if old:
            if (
                json.loads(old["song_snapshot"])["id"] != sid
                or old["new_elo"] != value
                or old["reason"] != reason
            ):
                raise PreferenceError(
                    "That rating token was already used for a different change.", 409
                )
            return {
                "status": "success",
                "message": "Saved rating correction.",
                "override_id": old["id"],
            }
        song = conn.execute("SELECT * FROM songs WHERE id=?", (sid,)).fetchone()
        if song is None:
            raise PreferenceError("Song not found.", 404)
        if data.get("expected_elo") != song["elo_score"]:
            raise PreferenceError(
                "The song Elo changed. Reload it before correcting.", 409
            )
        ensure_seeds(conn)
        after = conn.execute(
            "SELECT COALESCE(MAX(id),0) FROM preference_events"
        ).fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO preference_rating_overrides(request_token,song_id,song_snapshot,after_event_id,previous_elo,new_elo,reason)
            VALUES(?,?,?,?,?,?,?)""",
            (
                request_token,
                sid,
                compact({"id": sid, "title": song["title"]}),
                after,
                song["elo_score"],
                value,
                reason,
            ),
        )
        conn.execute("UPDATE songs SET elo_score=? WHERE id=?", (value, sid))
        return {
            "status": "success",
            "message": "Saved rating correction.",
            "override_id": cursor.lastrowid,
        }


def void_song_votes(conn, song_id):
    settings = ensure_seeds(conn)
    rows = conn.execute(
        "SELECT * FROM preference_effective WHERE active=1 AND (winner_id=? OR loser_id=?)",
        (song_id, song_id),
    ).fetchall()
    if any(row["id"] <= settings["cutoff_event_id"] for row in rows):
        raise PreferenceError(
            "This song has protected legacy-anchor votes. Keep it or reset preference history before removing it.",
            409,
        )
    for row in rows:
        conn.execute(
            """INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active,reason)
            VALUES(?,?,'void',?,?,?,0,'Catalogue song removed')""",
            (
                row["id"],
                secrets.token_urlsafe(24),
                row["winner_id"],
                row["loser_id"],
                row["mode"],
            ),
        )
    conn.execute(
        "UPDATE preference_offers SET status='cancelled',closed_at=CURRENT_TIMESTAMP WHERE status='open' AND (song1_id=? OR song2_id=?)",
        (song_id, song_id),
    )


def reset_preferences(conn):
    conn.execute("DELETE FROM preference_events")
    conn.execute("DELETE FROM preference_offers")
    conn.execute("DELETE FROM preference_rating_overrides")
    conn.execute("DELETE FROM preference_rating_seeds")
    conn.execute("DELETE FROM preference_replay_state")
    conn.execute("DELETE FROM preference_mode_ratings")
    conn.execute(
        "UPDATE songs SET elo_score=1200,matches_played=0,highest_elo=1200,highest_rank=9999"
    )
    ensure_seeds(conn)


def void_tournament_preferences(conn, tournament_id=None):
    """Keep original facts after bracket deletion/reset, and remove their influence."""
    query = "SELECT * FROM preference_effective WHERE origin='tournament' AND active=1"
    rows = conn.execute(
        query + (" AND tournament_id=?" if tournament_id is not None else ""),
        (tournament_id,) if tournament_id is not None else (),
    ).fetchall()
    for row in rows:
        conn.execute(
            """INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active,reason)
            VALUES(?,?,'void',?,?,?,0,'Tournament removed/reset')""",
            (
                row["id"],
                secrets.token_urlsafe(24),
                row["winner_id"],
                row["loser_id"],
                row["mode"],
            ),
        )
    if rows:
        rebuild_ratings(conn)


def exposure_totals(conn):
    totals = {
        r[0]: dict.fromkeys(EXPOSURE_MODES, 0)
        for r in conn.execute("SELECT id FROM songs")
    }
    for row in conn.execute("SELECT * FROM mode_exposures"):
        totals[row["song_id"]][row["mode"]] = row["appearances"]
    return totals


# Read-only independent Elo projections and evidence for public comparisons.


def song_mode_ratings(conn):
    result = {
        r[0]: {
            mode: dict(elo=1200.0, matches=0, tournament_matches=0)
            for mode in ("standard", "blind")
        }
        for r in conn.execute("SELECT id FROM songs")
    }
    # Compatibility for old report fixtures and the pre-migration snapshot check.
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='preference_mode_ratings' AND type='table'"
    ).fetchone():
        for row in conn.execute("SELECT * FROM preference_mode_ratings"):
            result[row["song_id"]][row["mode"]] = {
                key: row[key] for key in ("elo", "matches", "tournament_matches")
            }
    return result


def coverage(conn):
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='preference_effective'"
    ).fetchone():
        return dict(excluded=0, public_anchored=False)
    excluded = conn.execute(
        """SELECT COUNT(*) FROM preference_effective e
        LEFT JOIN songs w ON w.id=e.winner_id LEFT JOIN songs l ON l.id=e.loser_id
        WHERE e.active=1 AND (e.mode NOT IN ('standard','blind') OR w.id IS NULL OR l.id IS NULL OR w.id=l.id)"""
    ).fetchone()[0]
    state = conn.execute(
        "SELECT baseline_kind FROM preference_replay_state WHERE id=1"
    ).fetchone()
    return dict(
        excluded=excluded, public_anchored=bool(state and state[0] == "legacy_anchor")
    )


def comparison_report(conn, songs):
    """Compare standard and blind rating projections, tested coverage and song-level
    differences.
    """
    modes = song_mode_ratings(conn)
    from songranker.catalog import voting_records

    votes = voting_records(conn)
    both, counts = [], {}
    for mode in ("standard", "blind"):
        values = [row[mode] for row in modes.values()]
        counts[mode] = dict(
            tested=sum(row["matches"] > 0 for row in values),
            votes=sum(row["matches"] for row in values) // 2,
            tournament_votes=sum(row["tournament_matches"] for row in values) // 2,
            effective_votes=sum(row[mode + "_matches"] for row in votes.values()) / 2,
        )
    for song in songs:
        streams = modes[song["id"]]
        if all(
            votes[song["id"]][mode + "_matches"] >= 3 for mode in ("standard", "blind")
        ):
            both.append(
                {
                    **song,
                    "mode_ratings": streams,
                    "elo_difference": streams["blind"]["elo"]
                    - streams["standard"]["elo"],
                }
            )
    return dict(
        counts=counts,
        qualifying=len(both),
        coverage=coverage(conn),
        higher_blind=sorted(
            (s for s in both if s["elo_difference"] > 0),
            key=lambda s: (-s["elo_difference"], s["id"]),
        )[:5],
        higher_standard=sorted(
            (s for s in both if s["elo_difference"] < 0),
            key=lambda s: (s["elo_difference"], s["id"]),
        )[:5],
    )
