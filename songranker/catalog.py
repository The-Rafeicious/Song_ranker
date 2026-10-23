"""Shared library projections and aggregation. Each song contributes once."""

from collections import defaultdict
from songranker.services import app, get_db_connection
from flask import jsonify
from songranker.modes import challenges
from math import ceil


def proper_album(album):
    """Distinguish named full releases from unknown-album and Single placeholders."""
    title = str(album.get("title") or "").strip().casefold()
    return bool(title) and title != "unknown album" and not title.endswith(" - single")


def versus_metadata(album, linked_artists):
    """Shared display links for paired song rows; preserve whole artist names."""
    album = album or {}
    return dict(
        cover_url=album.get("cover_url") or "",
        artist_links=[
            dict(id=a["id"], name=a["name"])
            for a in sorted(linked_artists, key=lambda a: (a["name"], a["id"]))
        ],
        album_link=(
            dict(id=album["id"], title=album["title"]) if proper_album(album) else None
        ),
    )


TOURNAMENT_TOTALS = (
    "tournament_wins",
    "tournament_losses",
    "tournament_points",
    "championships",
    "runner_ups",
    "tournament_appearances",
    "third_places",
    "fourth_places",
    "podiums",
)


def song_performance(data):
    """Derive achievements from saved matches; final placements require completion."""
    result = {s["id"]: {key: 0 for key in TOURNAMENT_TOTALS} for s in data["songs"]}
    brackets = {t["id"]: t for t in data.get("tournaments", [])}
    appearances = defaultdict(set)
    placements = {
        key: set()
        for key in ("championships", "runner_ups", "third_places", "fourth_places")
    }
    for entry in data.get("tournament_entries", []):
        if entry["song_id"] in result and entry["tournament_id"] in brackets:
            appearances[entry["song_id"]].add(entry["tournament_id"])
    for t in brackets.values():
        champion = t.get("champion_id")
        if t.get("status") == "completed" and champion in result:
            placements["championships"].add((t["id"], champion))
            appearances[champion].add(t["id"])
        if t.get("status") == "completed":
            for key, column in [
                ("runner_ups", "runner_up_id"),
                ("third_places", "third_place_id"),
                ("fourth_places", "fourth_place_id"),
            ]:
                if t.get(column) in result:
                    placements[key].add((t["id"], t[column]))
    for match in data.get("tournament_matches", []):
        t = brackets.get(match["tournament_id"])
        if not t:
            continue
        for song_id in (match.get("song1_id"), match.get("song2_id")):
            if song_id in result:
                appearances[song_id].add(t["id"])
        winner, loser = match.get("winner_id"), match.get("loser_id")
        if (
            match.get("status") != "completed"
            or winner not in result
            or loser not in result
            or winner == loser
        ):
            continue
        result[winner]["tournament_wins"] += 1
        result[loser]["tournament_losses"] += 1
        result[winner]["tournament_points"] += float(match.get("points_awarded") or 0)
        if t.get("status") == "completed":
            size = int(t.get("size") or 0)
            if size >= 2 and size & (size - 1) == 0:
                final_round = size.bit_length() - 1
                if match.get("match_type", "bracket") != "bracket":
                    continue
                if match.get("round_number") == final_round:
                    placements["runner_ups"].add((t["id"], loser))
    for key, finishes in placements.items():
        for _, song_id in finishes:
            result[song_id][key] += 1
    for _, song_id in (
        placements["championships"]
        | placements["runner_ups"]
        | placements["third_places"]
    ):
        result[song_id]["podiums"] += 1
    for song_id, stats in result.items():
        stats["tournament_appearances"] = len(appearances[song_id])
    return result


def aggregate_performance(songs):
    """Pool recognition attempts and total distinct linked songs' achievements."""
    songs = list({s["id"]: s for s in songs}.values())
    attempts = sum(int(s.get("attempts") or 0) for s in songs)
    correct = sum(int(s.get("correct") or 0) for s in songs)
    available = sum(
        int(s.get("available_points", 2 * int(s.get("attempts") or 0)) or 0)
        for s in songs
    )
    return {
        **{key: sum(s.get(key) or 0 for s in songs) for key in TOURNAMENT_TOTALS},
        "voting": summarize_votes([s.get("voting", {}) for s in songs]),
        "recognition_attempts": attempts,
        "recognition_correct": correct,
        "tested_tracks": sum(int(s.get("attempts") or 0) > 0 for s in songs),
        "recognition_score": 100 * correct / available if available else None,
    }


def voting_records(conn):
    """Combined public preference results, retaining origin and mode breakdowns."""

    keys = ("standard_wins", "standard_losses", "blind_wins", "blind_losses")
    result = {
        r["id"]: dict.fromkeys(keys, 0) for r in conn.execute("SELECT id FROM songs")
    }
    sources = {
        sid: {
            origin: dict.fromkeys(keys, 0)
            for origin in ("ordinary", "tournament", "raw")
        }
        for sid in result
    }
    source = source_sql(conn)
    query = f"""SELECT song_id,mode,origin,SUM(won*rating_weight) wins,SUM((1-won)*rating_weight) losses, SUM(won) raw_wins,COUNT(*)-SUM(won) raw_losses FROM (
        SELECT h.winner_id song_id,h.mode,h.origin,h.rating_weight,1 won FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.mode IN ('standard','blind') AND h.winner_id!=h.loser_id
        UNION ALL
        SELECT h.loser_id song_id,h.mode,h.origin,h.rating_weight,0 won FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.mode IN ('standard','blind') AND h.winner_id!=h.loser_id
    ) GROUP BY song_id,mode,origin"""
    for row in conn.execute(query):
        origin = "tournament" if row["origin"] == "tournament" else "ordinary"
        for name in ("wins", "losses"):
            key = row["mode"] + "_" + name
            result[row["song_id"]][key] += row[name]
            sources[row["song_id"]][origin][key] += row[name]
            sources[row["song_id"]]["raw"][key] += row["raw_" + name]
    return {
        sid: summarize_votes([dict(counts, **sources[sid])])
        for sid, counts in result.items()
    }


def summarize_votes(records):
    """Summarise combined preference records by standard/blind mode and
    ordinary/tournament origin.
    """
    records = list(records)
    keys = ("standard_wins", "standard_losses", "blind_wins", "blind_losses")

    def project(rows):
        """Aggregate wins, losses, match counts and win rates for one subset of
        preference records.
        """
        rows = list(rows)
        totals = {key: sum(record.get(key, 0) for record in rows) for key in keys}
        totals.update(
            wins=totals["standard_wins"] + totals["blind_wins"],
            losses=totals["standard_losses"] + totals["blind_losses"],
        )
        for prefix in ("", "standard_", "blind_"):
            wins, losses = totals[prefix + "wins"], totals[prefix + "losses"]
            totals[prefix + "matches"] = wins + losses
            totals[prefix + "win_rate"] = (
                100 * wins / (wins + losses) if wins + losses else None
            )
        return totals

    totals = project(records)
    totals["ordinary"] = project(r.get("ordinary", r) for r in records)
    totals["tournament"] = project(r.get("tournament", {}) for r in records)
    totals["raw"] = project(r.get("raw", r) for r in records)
    return totals


def collection(include_overall_sources=False):
    conn = get_db_connection()
    try:
        conn.execute(
            "BEGIN"
        )  # Read one consistent snapshot, including optional Overall inputs.
        data = {
            "songs": [
                dict(r)
                for r in conn.execute(
                    "SELECT s.*,COALESCE(ts.attempts,0) AS attempts,COALESCE(ts.correct,0) AS correct,COALESCE(ts.available_points,0) AS available_points,COALESCE(ts.new_attempts,0) AS new_attempts,COALESCE(ts.title_correct,0) AS title_correct,COALESCE(ts.artist_correct,0) AS artist_correct,COALESCE(ts.album_attempts,0) AS album_attempts,COALESCE(ts.album_correct,0) AS album_correct FROM songs s LEFT JOIN trivia_stats ts ON ts.song_id=s.id"
                )
            ]
        }
        for key, table in [
            ("artists", "artists"),
            ("albums", "albums"),
            ("tags", "genres"),
            ("history", "history"),
            ("tournaments", "tournaments"),
            ("tournament_entries", "tournament_entries"),
            ("tournament_matches", "tournament_matches"),
        ]:
            data[key] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
        from songranker.vibe_maps import map_definitions, with_vibe_maps

        data["vibe_map_definitions"] = map_definitions(conn)
        data["songs"] = with_vibe_maps(conn, data["songs"])
        data["trivia_rounds"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 100"
            )
        ]
        data["global_stats"] = dict(conn.execute("SELECT key,value FROM global_stats"))
        from songranker.modes.challenges import records as challenge_records

        data["challenge_records"] = {"trivia": challenge_records(conn, "trivia")}
        artist_links, tag_links = defaultdict(list), defaultdict(list)
        for row in conn.execute("SELECT * FROM song_artists"):
            artist_links[row["song_id"]].append(row["artist_id"])
        for row in conn.execute("SELECT * FROM song_genres ORDER BY rowid"):
            tag_links[row["song_id"]].append(row["genre_id"])
        for song in data["songs"]:
            song.update(
                artist_ids=artist_links[song["id"]], tag_ids=tag_links[song["id"]]
            )
        data["history"].sort(key=lambda r: r["id"], reverse=True)

        data["elo_history"] = [
            dict(row)
            for row in conn.execute(
                f"SELECT * FROM {source_sql(conn)} ORDER BY id DESC"
            )
        ]
        data["tournaments"].sort(key=lambda r: r["id"], reverse=True)

        special, summary, _, _ = special_records(conn)
        data["special_modes"] = summary
        performance = song_performance(data)
        voting = voting_records(conn)
        from songranker.modes.preferences import song_mode_ratings
        from songranker.modes.preferences import coverage

        modes = song_mode_ratings(conn)
        data["rating_coverage"] = coverage(conn)
        added = {
            r["song_id"]: r["added_at"]
            for r in conn.execute("SELECT song_id,added_at FROM song_details")
        }
        for song in data["songs"]:
            song.update(
                added_at=added.get(song["id"], 0),
                **performance[song["id"]],
                voting=voting[song["id"]],
                elo_matches_played=voting[song["id"]]["raw"]["matches"],
                mode_ratings=modes[song["id"]],
                **special[song["id"]],
            )
        if include_overall_sources:
            data["overall_sources"] = {
                "trivia_stats": [
                    dict(r) for r in conn.execute("SELECT * FROM trivia_stats")
                ],
                "trivia_rounds": [
                    dict(r)
                    for r in conn.execute(
                        "SELECT song_id,album_available,title_correct,artist_correct,album_correct FROM trivia_rounds WHERE completed_at IS NOT NULL"
                    )
                ],
            }
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='mode_exposures' AND type='view'"
        ).fetchone():
            from songranker.modes.preferences import exposure_totals

            exposures = exposure_totals(conn)

            for sid, values in tournament_appearances(conn).items():
                for mode, value in values.items():
                    exposures[sid][mode] += value
            for song in data["songs"]:
                song["exposures"] = exposures[song["id"]]
        data["competition"] = dict(
            conn.execute(
                "SELECT generation,started_at FROM competition_state WHERE id=1"
            ).fetchone()
            or {}
        )
        return data
    finally:
        conn.close()


def ranked(data, kind):
    """Build song or grouped collection ranking rows from the shared hydrated
    catalogue.
    """
    artists = {r["id"]: r for r in data["artists"]}
    albums = {r["id"]: r for r in data["albums"]}
    tags = {r["id"]: r for r in data["tags"]}
    songs = []
    for row in data["songs"]:
        album = albums.get(row["album_id"], {})
        songs.append(
            {
                **row,
                "name": row["title"],
                "artist": ", ".join(
                    artists[a]["name"] for a in row["artist_ids"] if a in artists
                ),
                "album": album.get("title", ""),
                "cover_url": album.get("cover_url", ""),
                "album_is_single": str(album.get("title", ""))
                .casefold()
                .endswith(" - single"),
                "genres": ", ".join(
                    tags[t]["name"] for t in row["tag_ids"] if t in tags
                ),
                "impact_score": row["elo_score"],
            }
        )
    if kind == "songs":
        return sorted(songs, key=lambda r: (-r["elo_score"], r["title"].casefold()))
    from songranker.impact import calibrate, measure

    related_groups = [
        (
            [s for s in songs if row["id"] in s["artist_ids"]]
            if kind == "artists"
            else (
                [s for s in songs if s["album_id"] == row["id"]]
                if kind == "albums"
                else [s for s in songs if row["id"] in s["tag_ids"]]
            )
        )
        for row in data[kind]
    ]
    context = calibrate(
        songs,
        [
            group
            for row, group in zip(data[kind], related_groups)
            if kind != "albums" or proper_album(row)
        ],
    )
    result = []
    for row, related in zip(data[kind], related_groups):
        result.append(
            {
                **row,
                **aggregate_performance(related),
                "name": row.get("name", row.get("title")),
                "title": row.get("title", row.get("name")),
                "song_count": len(related),
                "avg_elo": (
                    sum(s["elo_score"] for s in related) / len(related)
                    if related
                    else 0
                ),
                **measure(related, context),
                "artist": ", ".join(
                    dict.fromkeys(s["artist"] for s in related if s["artist"])
                ),
            }
        )
    return sorted(
        result,
        key=lambda r: (
            r["impact_score"] is None,
            -(r["impact_score"] or 0),
            r["name"].casefold(),
        ),
    )


def special_records(conn):
    from songranker.modes.shelves import grade_shelf

    """Derive song figures and global mode records from answered rounds only."""
    keys = (
        "guess_attempts",
        "guess_correct",
        "shelf_attempts",
        "shelf_album_correct",
        "shelf_order_right",
        "shelf_order_pairs",
        "shelf_points",
        "shelf_available",
    )
    songs = {
        r["id"]: {key: 0 for key in keys} for r in conn.execute("SELECT id FROM songs")
    }
    guess_rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM elo_guess_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at,id"
        )
    ]
    streak = best = correct = 0
    for row in guess_rows:
        row["correct"] = int((row["chosen_slot"] == 1) == (row["elo1"] > row["elo2"]))
        correct += row["correct"]
        if row.get("rules_version", 1) == 1:
            streak = streak + 1 if row["correct"] else 0
            best = max(best, streak)
            row["streak"] = streak
            from songranker.storage.schema_compat import (
                CHALLENGE_ADDITIONS as ADDITIONS,
            )

            for column, _ in ADDITIONS["elo_guess_rounds"]:
                row.pop(
                    column, None
                )  # Stable classic reporting before/after a schema rebuild.
        else:
            row["streak"] = row["streak_after"]
        for sid in (row["song1_id"], row["song2_id"]):
            if sid in songs:
                songs[sid]["guess_attempts"] += 1
                songs[sid]["guess_correct"] += row["correct"]
    shelf_items = defaultdict(list)
    for row in conn.execute(
        """SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
                              WHERE r.completed_at IS NOT NULL ORDER BY r.id,i.item_slot"""
    ):
        shelf_items[row["round_id"]].append(dict(row))
    shelf_rows = []
    for round_row in conn.execute(
        "SELECT id,completed_at FROM album_shelf_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at,id"
    ):
        graded = grade_shelf(shelf_items[round_row["id"]])
        shelf_rows.append(
            dict(
                round_row,
                song_ids=[item["song_id"] for item in shelf_items[round_row["id"]]],
                album_ids=list(
                    dict.fromkeys(
                        item["album_id"] for item in shelf_items[round_row["id"]]
                    )
                ),
                **{k: v for k, v in graded.items() if k != "items"},
            )
        )
        for item in graded["items"]:
            if item["song_id"] not in songs:
                continue
            s = songs[item["song_id"]]
            s["shelf_attempts"] += 1
            for key, value in [
                ("shelf_album_correct", item["album_correct"]),
                ("shelf_order_right", item["order_right"]),
                ("shelf_order_pairs", item["order_pairs"]),
                ("shelf_points", item["points"]),
                ("shelf_available", item["available"]),
            ]:
                s[key] += value
    points = sum(r["points"] for r in shelf_rows)
    available = sum(r["available"] for r in shelf_rows)
    summary = dict(
        guesser=dict(
            rounds=len(guess_rows),
            correct=correct,
            points=correct,
            accuracy=100 * correct / len(guess_rows) if guess_rows else None,
            streak=streak,
            best_streak=best,
            classic=dict(streak=streak, best_streak=best),
            challenge=challenges.records(conn, "guesser"),
        ),
        shelves=dict(
            rounds=len(shelf_rows),
            points=points,
            available=available,
            accuracy=100 * points / available if available else None,
            best_points=max((r["points"] for r in shelf_rows), default=0),
            perfect=sum(abs(r["points"] - r["available"]) < 1e-8 for r in shelf_rows),
            tracks=sum(len(shelf_items[r["id"]]) for r in shelf_rows),
            album_correct=sum(r["album_correct"] for r in shelf_rows),
            order_right=sum(r["order_right"] for r in shelf_rows),
            order_pairs=sum(r["order_pairs"] for r in shelf_rows),
            albums_played=conn.execute(
                """SELECT COUNT(DISTINCT i.album_id) FROM album_shelf_items i
                JOIN album_shelf_rounds r ON r.id=i.round_id JOIN albums a ON a.id=i.album_id
                WHERE r.completed_at IS NOT NULL"""
            ).fetchone()[0],
        ),
    )
    return songs, summary, guess_rows[-30:][::-1], shelf_rows[-30:][::-1]


def display_song(conn, sid, include_album=True):
    row = conn.execute(
        """SELECT s.id,s.title,s.audio_url,a.title album,a.cover_url,
        a.id album_id FROM songs s LEFT JOIN albums a ON a.id=s.album_id WHERE s.id=?""",
        (sid,),
    ).fetchone()
    if not row:
        return None
    song = dict(row)
    song["artists"] = [
        dict(r)
        for r in conn.execute(
            """SELECT a.id,a.name FROM song_artists sa
        JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=? ORDER BY a.name""",
            (sid,),
        )
    ]
    if not include_album:
        for key in ("album", "album_id", "cover_url"):
            song.pop(key, None)
    return song


@app.route("/api/special-modes/stats")
def special_stats():
    from songranker.modes.shelves import grade_shelf

    conn = get_db_connection()
    try:
        songs, summary, guesses, shelves = special_records(conn)
        for row in guesses:
            row.pop("token", None)
        albums = [dict(row) for row in conn.execute("""
            SELECT a.id,a.title,a.cover_url,COUNT(DISTINCT r.id) AS rounds,
                COUNT(*) AS attempts,SUM(i.answer_slot=i.album_slot) AS correct
            FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
            JOIN albums a ON a.id=i.album_id WHERE r.completed_at IS NOT NULL
            GROUP BY a.id ORDER BY rounds DESC,a.title COLLATE NOCASE""")]
        by_round = defaultdict(list)
        for row in conn.execute(
            """SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
                WHERE r.completed_at IS NOT NULL"""
        ):
            by_round[row["round_id"]].append(dict(row))
        order = defaultdict(lambda: dict(order_right=0, order_pairs=0))
        for items in by_round.values():
            for item in grade_shelf(items)["items"]:
                for key in ("order_right", "order_pairs"):
                    order[item["album_id"]][key] += item[key]
        for album in albums:
            album.update(order[album["id"]])
        return jsonify(
            summary=summary,
            songs=songs,
            guess_history=guesses,
            shelf_history=shelves,
            participating_albums=albums,
        )
    finally:
        conn.close()


# Read-only public Elo feed; ordinary vote/exposure views keep their meaning.


def source_sql(conn):
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='preference_effective' AND type='view'"
    ).fetchone():
        return """(SELECT e.id,e.winner_id,e.loser_id,e.mode,e.created_at,
            p.winner_before,p.winner_after,p.loser_before,p.loser_after,
            e.origin,e.rating_weight,e.tournament_id,e.tournament_match_id,e.revision,
            CASE WHEN e.revision>0 THEN 'Corrected'
             WHEN p.winner_before IS NOT o.winner_before OR p.winner_after IS NOT o.winner_after
               OR p.loser_before IS NOT o.loser_before OR p.loser_after IS NOT o.loser_after
             THEN 'Recalculated' ELSE '' END history_note
            FROM preference_effective e JOIN preference_events o ON o.id=e.id
            LEFT JOIN preference_rating_projection p ON p.event_id=e.id
            WHERE e.active=1 AND e.mode IN ('standard','blind'))"""
    return "(SELECT h.*,'ordinary' origin,1.0 rating_weight,NULL tournament_id,NULL tournament_match_id,'' history_note FROM history h)"


def filters(mode="all", origin="all"):
    """Normalise history mode and origin filters to supported values or all."""
    mode = mode if mode in ("standard", "blind") else "all"
    origin = origin if origin in ("ordinary", "tournament") else "all"
    return mode, origin


def summary(conn):
    """Count effective preference matches by mode and origin for the history summary."""
    row = conn.execute(f"""SELECT COUNT(*) total,
        COALESCE(SUM(h.origin='tournament'),0) tournament,
        COALESCE(SUM(h.mode='blind'),0) blind,
        COALESCE(SUM(h.mode='standard'),0) standard,
        COALESCE(SUM(h.origin='tournament' AND h.mode='standard'),0) tournament_standard,
        COALESCE(SUM(h.origin='tournament' AND h.mode='blind'),0) tournament_blind
        FROM {source_sql(conn)} h JOIN songs w ON w.id=h.winner_id
        JOIN songs l ON l.id=h.loser_id WHERE h.winner_id!=h.loser_id""").fetchone()
    result = dict(row)
    result["ordinary"] = result["total"] - result["tournament"]
    result["tournament_share"] = (
        100 * result["tournament"] / result["total"] if result["total"] else None
    )
    return result


def page(conn, mode="all", origin="all", number=1, size=50, reader=None):
    """Return a bounded, filtered page of effective preference history with
    pagination metadata.
    """
    from songranker.services import fetch_match_history

    reader = reader or fetch_match_history
    mode, origin = filters(mode, origin)
    total = conn.execute(
        f"""SELECT COUNT(*) FROM {source_sql(conn)} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.winner_id!=h.loser_id AND (?='all' OR h.mode=?)
        AND (?='all' OR (?='tournament')=(h.origin='tournament'))""",
        (mode, mode, origin, origin),
    ).fetchone()[0]
    pages = max(1, ceil(total / size))
    try:
        number = max(1, min(int(number), pages))
    except (ValueError, TypeError, OverflowError):
        number = 1
    rows = reader(
        conn, limit=size, offset=(number - 1) * size, mode=mode, origin=origin
    )
    return dict(
        history=rows,
        history_mode=mode,
        history_origin=origin,
        history_page=number,
        history_pages=pages,
        history_total=total,
        history_start=(number - 1) * size + 1 if total else 0,
        history_end=min(number * size, total),
        elo_summary=summary(conn),
    )


def tournament_appearances(conn):
    """Effective first-round evidence per participant, using saved Elo influence."""
    source = source_sql(conn)
    query = f"""SELECT song_id,mode,SUM(rating_weight) appearances FROM (
        SELECT h.winner_id song_id,h.mode,h.rating_weight FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.origin='tournament' AND h.winner_id!=h.loser_id
        UNION ALL
        SELECT h.loser_id song_id,h.mode,h.rating_weight FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.origin='tournament' AND h.winner_id!=h.loser_id
    ) GROUP BY song_id,mode"""
    result = {}
    for row in conn.execute(query):
        counts = result.setdefault(row["song_id"], dict(standard=0, blind=0, public=0))
        if row["mode"] in ("standard", "blind"):
            counts[row["mode"]] += row["appearances"]
            counts["public"] += row["appearances"]
    return result
