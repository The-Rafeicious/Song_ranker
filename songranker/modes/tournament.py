from flask import render_template, request, jsonify, abort, redirect, url_for
from songranker.modes.selection import tournament_tracks
from songranker.services import app, get_db_connection
from songranker.reports.stats_activity import attach_reports
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import ceil, isfinite
from songranker.catalog import proper_album, song_performance, tournament_weights
from songranker.reports.global_stats_data import percent, timestamp


@app.route("/tournament")
def tournament():
    """Use the shared application shell; catalogue scopes load with the collection."""
    return render_template(
        "app_page.html", page="tournament_play", page_title="Tournament"
    )


@app.route("/api/generate_bracket")
def api_generate_bracket():
    size = request.args.get("size", 8, type=int)
    scope = request.args.get("scope", "global")
    scope_id = request.args.get("scope_id", type=int)
    is_blind = request.args.get("is_blind", "false").lower() == "true"
    if size not in (8, 16, 32):
        return jsonify({"error": "Tournament size must be 8, 16, or 32."}), 400
    if scope not in ("global", "artist", "album", "tag"):
        return jsonify({"error": "Invalid tournament scope."}), 400
    if scope != "global" and not scope_id:
        return jsonify({"error": "Select an artist, album or tag."}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conditions = []
        params = []
        if scope == "artist":
            conditions.append(
                "EXISTS(SELECT 1 FROM song_artists sa WHERE sa.song_id=s.id AND sa.artist_id=?)"
            )
            params.append(scope_id)
        elif scope == "album":
            conditions.append("s.album_id=?")
            params.append(scope_id)
        elif scope == "tag":
            conditions.append(
                "EXISTS(SELECT 1 FROM song_genres sg WHERE sg.song_id=s.id AND sg.genre_id=?)"
            )
            params.append(scope_id)
        if is_blind:
            conditions.append("TRIM(COALESCE(s.audio_url,''))!=''")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        pool = [
            dict(r)
            for r in conn.execute(
                """SELECT s.id,s.title,s.audio_url,s.elo_score,al.cover_url,
            (SELECT GROUP_CONCAT(a.name,', ') FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=s.id) artist,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.status='completed' AND (tm.winner_id=s.id OR tm.loser_id=s.id)) tournament_matches,
            (SELECT COUNT(*) FROM tournaments t WHERE t.status='completed' AND t.champion_id=s.id) championships
            FROM songs s LEFT JOIN albums al ON al.id=s.album_id"""
                + where
                + " ORDER BY s.id",
                params,
            )
        ]
        if len(pool) < size:
            return (
                jsonify(
                    error=f"Not enough eligible tracks. Needed {size}, found {len(pool)}."
                ),
                400,
            )
        from songranker.modes.selection import mode_counts
        from songranker.modes.selection import with_catalogue_age

        pool = with_catalogue_age(conn, pool)
        songs = tournament_tracks(pool, size, counts=mode_counts(conn, "tournament"))
        if songs is None:
            return (
                jsonify(error="Not enough tracks with valid Elo for this bracket."),
                400,
            )

        cursor = conn.execute(
            """INSERT INTO tournaments
                    (size, scope_type, scope_id, status, created_at, updated_at, current_round, points_version, is_blind, playoff_enabled,
                     elo_policy_version,elo_weight)
                    VALUES (?, ?, ?, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 1, ?, 1, ?, ?)""",
            (size, scope, scope_id, is_blind, 0 if scope in ("artist", "album") else 1, 1 if scope == "global" else 0.5 if scope == "tag" else 0),
        )
        tournament_id = cursor.lastrowid
        for seed, song in enumerate(songs, start=1):
            conn.execute(
                "INSERT INTO tournament_entries (tournament_id, song_id, seed) VALUES (?, ?, ?)",
                (tournament_id, song["id"], seed),
            )
        # Mirror tournament.html's standard seeding order so persisted matches match the UI.
        seed_order = _tournament_seed_order(size)
        for i in range(0, size, 2):
            song1 = songs[seed_order[i]]
            song2 = songs[seed_order[i + 1]]
            conn.execute(
                """INSERT INTO tournament_matches
                (tournament_id, round_number, match_number, song1_id, song2_id)
                VALUES (?, 1, ?, ?, ?)""",
                (tournament_id, (i // 2) + 1, song1["id"], song2["id"]),
            )
        conn.commit()
        return jsonify(
            {
                "tournament_id": tournament_id,
                "tracks": songs,
                "matches": _tournament_matches(conn, tournament_id),
                "elo_policy_version": 0 if scope in ("artist", "album") else 1,
                "elo_weight": 1 if scope == "global" else 0.5 if scope == "tag" else 0,
            }
        )
    except Exception:
        conn.rollback()
        app.logger.exception("Could not create tournament")
        return jsonify({"error": "Could not create tournament."}), 500
    finally:
        conn.close()


def _tournament_seed_order(size):
    """Return zero-based track indexes in the same bracket seeding order as tournament.html."""
    bracket = [1]
    rounds = size.bit_length() - 1
    for r in range(rounds):
        seed_sum = (2 ** (r + 1)) + 1
        next_bracket = []
        for seed in bracket:
            next_bracket.extend((seed, seed_sum - seed))
        bracket = next_bracket
    return [seed - 1 for seed in bracket]


def _tournament_matches(conn, tournament_id):
    """Read one bracket's saved matches in round and match order."""
    rows = conn.execute(
        """SELECT id, tournament_id, round_number, match_number,
        song1_id, song2_id, winner_id, loser_id, status, points_awarded, played_at, match_type
        FROM tournament_matches WHERE tournament_id = ?
        ORDER BY round_number, match_number""",
        (tournament_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _round_points(size, round_number):
    # Normalize the maximum points for a champion to 7 across bracket sizes.
    """Scale round points so a champion's maximum totals seven across supported
    bracket sizes.
    """
    return round(7 * (2 ** (round_number - 1)) / (size - 1), 4)


@app.route("/api/tournament_vote", methods=["POST"])
def api_tournament_vote():
    data = request.get_json(silent=True) or {}
    from songranker.modes.preferences import integer, PreferenceError

    if not isinstance(data, dict):
        return jsonify(error="Submit a tournament vote object."), 400
    try:
        tournament_id, match_id, winner_id, loser_id = (
            integer(data.get(key), key.replace("_", " "))
            for key in ("tournament_id", "match_id", "winner_id", "loser_id")
        )
    except PreferenceError as error:
        return jsonify(error=str(error)), error.status
    if not all((tournament_id, match_id, winner_id, loser_id)) or winner_id == loser_id:
        return (
            jsonify(
                {
                    "error": "tournament_id, match_id, distinct winner_id and loser_id are required."
                }
            ),
            400,
        )

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        match = conn.execute(
            "SELECT * FROM tournament_matches WHERE id = ? AND tournament_id = ?",
            (match_id, tournament_id),
        ).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({"error": "Tournament not found."}), 404
        if (
            match
            and match["status"] == "completed"
        ):
            conn.rollback()
            if (winner_id, loser_id) != (match["winner_id"], match["loser_id"]):
                return (
                    jsonify(error="This match already has a different saved result."),
                    409,
                )
            event = conn.execute(
                "SELECT p.* FROM preference_events p JOIN preference_effective e ON e.id=p.id WHERE p.tournament_match_id=? AND e.active=1",
                (match_id,),
            ).fetchone()
            from songranker.modes.preferences import receipt

            return jsonify(
                success=True,
                points_awarded=match["points_awarded"],
                preference_event_id=event["id"] if event else None,
                elo_result=receipt(event) if event else None,
                matches=_tournament_matches(conn, tournament_id),
            )
        if tournament["status"] != "in_progress":
            conn.rollback()
            return jsonify({"error": "Tournament is not in progress."}), 409
        if not match:
            conn.rollback()
            return jsonify({"error": "Match does not belong to this tournament."}), 404
        if match["status"] != "pending":
            conn.rollback()
            return jsonify({"error": "This match has already been recorded."}), 409
        if {winner_id, loser_id} != {match["song1_id"], match["song2_id"]}:
            conn.rollback()
            return (
                jsonify(
                    {"error": "Winner and loser must be the two songs in this match."}
                ),
                400,
            )

        final_round = tournament["size"].bit_length() - 1
        if (
            tournament["playoff_enabled"]
            and match["match_type"] == "bracket"
            and match["round_number"] == final_round
        ):
            bronze = conn.execute(
                "SELECT status FROM tournament_matches WHERE tournament_id=? AND match_type='third_place'",
                (tournament_id,),
            ).fetchone()
            if not bronze or bronze["status"] != "completed":
                return (
                    jsonify(error="Play the third-place playoff before the final."),
                    409,
                )
        points = (
            _round_points(tournament["size"], final_round - 1) * 0.5
            if match["match_type"] == "third_place"
            else _round_points(tournament["size"], match["round_number"])
        )
        conn.execute(
            """UPDATE tournament_matches SET winner_id = ?, loser_id = ?, status = 'completed',
            points_awarded = ?, played_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (winner_id, loser_id, points, match_id),
        )
        from songranker.modes.preferences import save_tournament_preference, receipt

        event_id = save_tournament_preference(
            conn, tournament, match, winner_id, loser_id
        )
        elo_result = (
            receipt(
                conn.execute(
                    "SELECT * FROM preference_events WHERE id=?", (event_id,)
                ).fetchone()
            )
            if event_id
            else None
        )

        round_rows = conn.execute(
            """SELECT * FROM tournament_matches
            WHERE tournament_id = ? AND round_number = ? AND match_type='bracket' ORDER BY match_number""",
            (tournament_id, match["round_number"]),
        ).fetchall()
        if match["match_type"] == "bracket" and all(
            row["status"] == "completed" or row["id"] == match_id for row in round_rows
        ):
            winners = [
                winner_id if row["id"] == match_id else row["winner_id"]
                for row in round_rows
            ]
            if len(winners) > 1:
                next_round = match["round_number"] + 1
                for i in range(0, len(winners), 2):
                    conn.execute(
                        """INSERT OR IGNORE INTO tournament_matches
                        (tournament_id, round_number, match_number, song1_id, song2_id)
                        VALUES (?, ?, ?, ?, ?)""",
                        (
                            tournament_id,
                            next_round,
                            (i // 2) + 1,
                            winners[i],
                            winners[i + 1],
                        ),
                    )
                if tournament["playoff_enabled"] and next_round == final_round:
                    losers = [
                        row["loser_id"]
                        for row in conn.execute(
                            "SELECT loser_id FROM tournament_matches WHERE tournament_id=? AND round_number=? AND match_type='bracket' ORDER BY match_number",
                            (tournament_id, match["round_number"]),
                        )
                    ]
                    conn.execute(
                        "INSERT OR IGNORE INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,match_type) VALUES(?,?,0,?,?,'third_place')",
                        (tournament_id, final_round, losers[0], losers[1]),
                    )
                conn.execute(
                    "UPDATE tournaments SET current_round = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (next_round, tournament_id),
                )
            else:
                conn.execute(
                    "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (tournament_id,),
                )

        conn.commit()
        return jsonify(
            {
                "success": True,
                "points_awarded": points,
                "preference_event_id": event_id,
                "elo_result": elo_result,
                "matches": _tournament_matches(conn, tournament_id),
            }
        )
    except Exception:
        conn.rollback()
        app.logger.exception("Could not record tournament vote")
        return jsonify({"error": "Could not save this vote."}), 500
    finally:
        conn.close()


@app.route("/api/tournaments", methods=["GET"])
def api_tournaments_list():
    conn = get_db_connection()
    try:
        rows = conn.execute("""SELECT t.id, t.size, t.scope_type, t.scope_id, t.status,
                    t.champion_id, t.created_at, t.updated_at, t.completed_at, t.is_blind, t.playoff_enabled,t.runner_up_id,t.third_place_id,t.fourth_place_id,
                    (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id AND tm.status = 'completed') AS matches_completed,
                    (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id) AS matches_created
                    FROM tournaments t ORDER BY CASE t.status WHEN 'in_progress' THEN 0 ELSE 1 END,
                    COALESCE(t.updated_at, t.timestamp) DESC""").fetchall()
        return jsonify({"tournaments": [dict(row) for row in rows]})
    finally:
        conn.close()


@app.route("/api/tournaments/<int:tournament_id>", methods=["GET"])
def api_tournament_detail(tournament_id):
    conn = get_db_connection()
    try:
        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        if not tournament:
            return jsonify({"error": "Tournament not found."}), 404
        entries = conn.execute(
            """SELECT e.seed, s.id, s.title, s.audio_url, s.elo_score,
            al.cover_url, (SELECT GROUP_CONCAT(a.name, ', ') FROM song_artists sa
            JOIN artists a ON a.id = sa.artist_id WHERE sa.song_id = s.id) AS artist
            FROM tournament_entries e JOIN songs s ON s.id = e.song_id
            LEFT JOIN albums al ON al.id = s.album_id
            WHERE e.tournament_id = ? ORDER BY e.seed""",
            (tournament_id,),
        ).fetchall()
        return jsonify(
            {
                "tournament": dict(tournament),
                "entries": [dict(row) for row in entries],
                "matches": _tournament_matches(conn, tournament_id),
            }
        )
    finally:
        conn.close()


@app.route("/tournament_stats")
def tournament_stats_page():
    """Read-only tournament dashboard; ranking APIs and game actions stay separate."""

    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        selected=request.args.get("tournament",type=int)
        row=conn.execute("SELECT scope_type,scope_id FROM tournaments WHERE id=?",(selected,)).fetchone()
        if row and row['scope_type'] in ('artist','album'):
            return redirect(url_for('local_tournament_stats_page',scope=row['scope_type'],scope_id=row['scope_id'])+'#local-bracket-'+str(selected))
        data = build_tournament_stats(
            conn,
            selected=request.args.get("tournament", type=int),
            archive_page=request.args.get("archive_page", 1, type=int),
            competition_only=True,
        )
        data["local_summary"] = build_local_tournament_stats(conn)
    finally:
        conn.close()
    return render_template("tournament_stats.html", **data)


@app.route("/tournament/<int:tournament_id>/bracket")
def tournament_bracket_page(tournament_id):
    """A shareable, read-only bracket workspace with saved match inspection."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_tournament_stats(conn, selected=tournament_id)
        bracket = next((t for t in data["archive"] if t["id"] == tournament_id), None)
        if bracket is None:
            abort(404)
    finally:
        conn.close()
    return render_template("tournament_bracket.html", bracket=bracket)


@app.route("/api/tournament_stats", methods=["GET"])
def api_tournament_stats():
    """Tournament-only leaderboard; regular Elo and history are not involved."""
    from songranker.catalog import collection, ranked

    rows = []
    for song in ranked(collection(), "songs"):
        played = song["tournament_wins"] + song["tournament_losses"]
        rows.append(
            {
                **{
                    key: song[key]
                    for key in (
                        "id",
                        "title",
                        "artist",
                        "cover_url",
                        "championships",
                        "runner_ups",
                        "third_places",
                        "fourth_places",
                        "podiums",
                        "tournament_points",
                    )
                },
                "tournaments_entered": song["tournament_appearances"],
                "matches_won": song["tournament_wins"],
                "matches_lost": song["tournament_losses"],
                "matches_played": played,
                "win_rate": (
                    round(100 * song["tournament_wins"] / played, 2) if played else None
                ),
            }
        )
    rows.sort(key=lambda r: (-r["championships"], -r["tournament_points"], r["title"]))
    return jsonify(songs=rows)


@app.route("/api/tournament_complete", methods=["POST"])
def api_tournament_complete():
    data = request.get_json(silent=True) or {}
    tournament_id = data.get("tournament_id")
    champion_id = data.get("champion_id")
    if not tournament_id or not champion_id:
        return jsonify({"error": "tournament_id and champion_id are required."}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({"error": "Tournament not found."}), 404
        if tournament["status"] == "completed":
            conn.rollback()
            if tournament["champion_id"] == champion_id:
                return jsonify({"success": True, "already_completed": True})
            return jsonify({"error": "Tournament has already been completed."}), 409
        if tournament["status"] != "in_progress":
            conn.rollback()
            return jsonify({"error": "Tournament is not in progress."}), 409
        pending = conn.execute(
            """SELECT COUNT(*) FROM tournament_matches
            WHERE tournament_id = ? AND status != 'completed' """,
            (tournament_id,),
        ).fetchone()[0]
        final_match = conn.execute(
            """SELECT winner_id,loser_id FROM tournament_matches
            WHERE tournament_id = ? AND match_type='bracket' ORDER BY round_number DESC, match_number ASC LIMIT 1""",
            (tournament_id,),
        ).fetchone()
        if pending or not final_match or final_match["winner_id"] != champion_id:
            conn.rollback()
            return (
                jsonify(
                    {
                        "error": "All matches must be complete and champion must be the final winner."
                    }
                ),
                409,
            )
        bronze = conn.execute(
            "SELECT winner_id,loser_id FROM tournament_matches WHERE tournament_id=? AND match_type='third_place' AND status='completed'",
            (tournament_id,),
        ).fetchone()
        conn.execute(
            """UPDATE tournaments SET runner_up_id=?,third_place_id=?,fourth_place_id=?,champion_id = ?, status = 'completed',
            completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (
                final_match["loser_id"],
                bronze["winner_id"] if bronze else None,
                bronze["loser_id"] if bronze else None,
                champion_id,
                tournament_id,
            ),
        )
        conn.execute(
            "UPDATE songs SET tournament_wins = tournament_wins + 1 WHERE id = ?",
            (champion_id,),
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception:
        conn.rollback()
        app.logger.exception("Could not complete tournament")
        return jsonify({"error": "Could not complete tournament."}), 500
    finally:
        conn.close()


# Read-only tournament dashboard, derived from saved brackets, entries and matches.


ARCHIVE_SIZE = 10


def number(value):
    """Read a finite nonnegative saved tournament number, returning unknown for
    invalid values.
    """
    try:
        value = float(value)
        return value if isfinite(value) and value >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def saved_time(value):
    if value is None or str(value).strip() == "":
        return None
    stamp = timestamp(value)
    if stamp == 0:
        # The shared parser uses zero for invalid dates; preserve a real epoch.
        numeric = number(value)
        if numeric is not None:
            stamp = numeric
        else:
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError, OverflowError):
                return None
    if not isfinite(stamp):
        return None
    try:
        return dict(
            seconds=stamp, iso=datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        )
    except (ValueError, OverflowError, OSError):
        return None


def stage_name(size, round_number, match_type="bracket"):
    """Label a saved bracket stage, third-place playoff or unsupported historical
    round.
    """
    if match_type == "third_place":
        return "Third-place playoff"
    if match_type != "bracket":
        return "Other saved matches"
    if (
        not isinstance(size, int)
        or size < 2
        or size & (size - 1)
        or not isinstance(round_number, int)
        or round_number < 1
    ):
        return "Round " + str(round_number or "?")
    remaining = size // 2 ** (round_number - 1)
    return {2: "Final", 4: "Semi-finals", 8: "Quarter-finals"}.get(
        remaining,
        (
            "Round of " + str(remaining)
            if remaining >= 2
            else "Round " + str(round_number)
        ),
    )


def recorded_result(match):
    """Accept only completed matches with distinct winner/loser identities consistent
    with saved participants.
    """
    winner, loser = match.get("winner_id"), match.get("loser_id")
    if (
        match["status"] != "completed"
        or winner is None
        or loser is None
        or winner == loser
    ):
        return False
    pair = (match.get("song1_id"), match.get("song2_id"))
    return None in pair or {winner, loser} == set(pair)


def podium_points(sid, matches):
    """Sum a participant's recorded win points, preserving unknown points or absent
    participation.
    """
    played = [
        m
        for m in matches
        if m["status"] == "completed"
        and sid is not None
        and sid
        in (m.get("song1_id"), m.get("song2_id"), m.get("winner_id"), m.get("loser_id"))
    ]
    if not played:
        return None
    won = [number(m.get("points_awarded")) for m in played if m.get("winner_id") == sid]
    return round(sum(won), 2) if all(p is not None for p in won) else None


def build_tournament_stats(conn, now=None, selected=None, archive_page=1, competition_only=False):
    """A caller-owned snapshot; no writes, API calls, history cap or Elo inference."""
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
        )
        songs[song["id"]] = song
    brackets = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM tournaments")}
    if competition_only:
        brackets={tid:t for tid,t in brackets.items() if t.get('scope_type') in ('global','tag')}
    entries = [
        dict(r)
        for r in conn.execute("SELECT * FROM tournament_entries")
        if r["tournament_id"] in brackets
    ]
    matches = [
        dict(r)
        for r in conn.execute("SELECT * FROM tournament_matches")
        if r["tournament_id"] in brackets
    ]
    entries_by, matches_by, appearances = (
        defaultdict(list),
        defaultdict(list),
        defaultdict(set),
    )
    seed = {}
    for entry in entries:
        entries_by[entry["tournament_id"]].append(entry)
        seed[entry["tournament_id"], entry["song_id"]] = entry["seed"]
        if entry["song_id"] in songs:
            appearances[entry["song_id"]].add(entry["tournament_id"])
    for match in matches:
        matches_by[match["tournament_id"]].append(match)
        for key in ("song1_id", "song2_id", "winner_id", "loser_id"):
            if match.get(key) in songs:
                appearances[match[key]].add(match["tournament_id"])
    for t in brackets.values():
        if t["status"] == "completed":
            size = t.get("size")
            final = (
                size.bit_length() - 1
                if isinstance(size, int) and size >= 2 and not size & (size - 1)
                else None
            )
            for m in matches_by[t["id"]]:
                if not recorded_result(m):
                    continue
                if (
                    m.get("match_type", "bracket") == "bracket"
                    and final
                    and m["round_number"] == final
                    and m["match_number"] == 1
                    and (
                        t.get("champion_id") is None
                        or t["champion_id"] == m["winner_id"]
                    )
                ):
                    if t.get("champion_id") is None:
                        t["champion_id"] = m["winner_id"]
                    if t.get("runner_up_id") is None:
                        t["runner_up_id"] = m["loser_id"]
                if m.get("match_type") == "third_place":
                    if t.get("third_place_id") is None:
                        t["third_place_id"] = m["winner_id"]
                    if t.get("fourth_place_id") is None:
                        t["fourth_place_id"] = m["loser_id"]
            for key in (
                "champion_id",
                "runner_up_id",
                "third_place_id",
                "fourth_place_id",
            ):
                if t.get(key) in songs:
                    appearances[t[key]].add(t["id"])

    weights=tournament_weights(dict(tournaments=list(brackets.values()),tournament_entries=entries,tournament_matches=matches))
    # Reuse the existing achievement owner, with invalid point values excluded.
    performance = song_performance(
        dict(
            songs=list(songs.values()),
            tournaments=list(brackets.values()),
            tournament_entries=entries,
            tournament_matches=[
                dict(m, points_awarded=number(m.get("points_awarded")) or 0)
                for m in matches
            ],
        )
    )
    for sid, song in songs.items():
        song.update(performance[sid], entries=len(appearances[sid]), entry_credit=performance[sid]["tournament_appearances"])
        song["played"] = song["tournament_wins"] + song["tournament_losses"]
        song["win_rate"] = percent(song["tournament_wins"], song["played"])

    def identity(sid, absent="Not recorded"):
        """Resolve a saved participant with a safe unavailable/not-recorded report
        identity.
        """
        return songs.get(sid) or dict(
            id=None,
            title="Track unavailable" if sid is not None else absent,
            cover_url="",
            artist_links=[],
            album_link=None,
        )

    def scope(t):
        """Resolve a bracket's saved scope to its current collection identity or a
        historical fallback.
        """
        kind = t.get("scope_type")
        row = (
            {"artist": artists, "album": albums, "tag": tags}
            .get(kind, {})
            .get(t.get("scope_id"))
        )
        if kind == "global":
            return dict(kind="tournament", name="Whole collection", row=None)
        if row and (kind != "album" or proper_album(row)):
            return dict(kind=kind, name=row.get("name", row.get("title")), row=row)
        return dict(
            kind="tournament",
            name={
                "artist": "Artist scope",
                "album": "Album scope",
                "tag": "Tag scope",
            }.get(kind, "Scope unavailable"),
            row=None,
        )

    finished, sizes, scopes, visibility = [], Counter(), Counter(), Counter()
    entry_total = missing_entries = week = month = top_half = seeded_champions = (
        first_seed
    ) = 0
    champion_seeds = []
    for t in brackets.values():
        t["finished"] = t["status"] == "completed"
        t["scope"] = scope(t)
        t["visibility"] = (
            "Blind"
            if t.get("is_blind") == 1
            else "Non-blind" if t.get("is_blind") == 0 else "Not recorded"
        )
        t["date"] = (
            saved_time(t.get("completed_at"))
            if t["finished"]
            else saved_time(t.get("updated_at"))
        )
        t["date"] = (
            t["date"]
            or saved_time(t.get("created_at"))
            or saved_time(t.get("timestamp"))
        )
        t["completion_date"] = saved_time(t.get("completed_at"))
        declared = t.get("size")
        t["entry_count"] = (
            declared
            if isinstance(declared, int) and declared > 0
            else len(entries_by[t["id"]]) or None
        )
        if t["entry_count"] is None:
            missing_entries += 1
        else:
            entry_total += t["entry_count"]
        sizes[declared if declared in (32, 16, 8) else "other"] += 1
        scopes[
            (
                t["scope_type"]
                if t["scope_type"] in ("global", "artist", "album", "tag")
                else "other"
            )
        ] += 1
        visibility[t["visibility"]] += 1
        saved = matches_by[t["id"]]
        t["decided"] = sum(m["status"] == "completed" for m in saved)
        t["created_matches"] = len(saved)
        expected = (
            declared - 1 + int(bool(t.get("playoff_enabled")))
            if isinstance(declared, int)
            and declared >= 2
            and not declared & (declared - 1)
            else None
        )
        t["expected_matches"] = expected
        t["progress"] = (
            percent(min(t["decided"], expected), expected) if expected else None
        )
        t["points"] = round(
            sum(
                number(m.get("points_awarded")) or 0
                for m in saved
                if m["status"] == "completed"
            ),
            2,
        )
        placements = {
            key: t.get(key) for key in ("champion_id", "runner_up_id", "third_place_id")
        }
        if t["finished"]:
            finished.append(t)
            completed = t["completion_date"]
            if completed:
                week += now - 7 * 86400 <= completed["seconds"] <= now
                month += now - 30 * 86400 <= completed["seconds"] <= now
            position = seed.get((t["id"], t.get("champion_id")))
            if (
                isinstance(position, int)
                and isinstance(declared, int)
                and 1 <= position <= declared
            ):
                seeded_champions += 1
                first_seed += position == 1
                top_half += position <= declared / 2
                champion_seeds.append(
                    dict(song=identity(t["champion_id"]), seed=position, bracket=t)
                )
        t["podium"] = [
            dict(
                place=i,
                song=identity(placements[key]),
                points=podium_points(placements[key], saved),
            )
            for i, key in enumerate(
                ("champion_id", "runner_up_id", "third_place_id"), 1
            )
        ]
        t["champion"] = identity(
            t.get("champion_id"),
            "Champion not recorded" if t["finished"] else "In progress",
        )

    finished.sort(
        key=lambda t: ((t["date"] or {}).get("seconds", float("-inf")), t["id"]),
        reverse=True,
    )
    decided = [m for m in matches if m["status"] == "completed"]
    known_points = [number(m.get("points_awarded")) for m in decided]
    stages = Counter()
    higher_seed_wins = seeded_matches = match_week = 0
    for m in decided:
        t = brackets[m["tournament_id"]]
        stages[
            stage_name(t.get("size"), m["round_number"], m.get("match_type", "bracket"))
        ] += 1
        a, b = seed.get((t["id"], m.get("winner_id"))), seed.get(
            (t["id"], m.get("loser_id"))
        )
        size = t.get("size")
        if (
            recorded_result(m)
            and isinstance(a, int)
            and isinstance(b, int)
            and isinstance(size, int)
            and 1 <= a <= size
            and 1 <= b <= size
            and a != b
            and m.get("winner_id") != m.get("loser_id")
        ):
            seeded_matches += 1
            higher_seed_wins += a > b
        date = saved_time(m.get("played_at"))
        if date:
            match_week += now - 7 * 86400 <= date["seconds"] <= now

    def breakdown(counter, keys):
        """Convert bracket counters into labelled counts and shares for the current
        report set.
        """
        return [
            dict(
                key=k,
                label=label,
                count=counter[k],
                share=percent(counter[k], len(brackets)),
            )
            for k, label in keys
        ]

    size_rows = breakdown(
        sizes, [(32, "32 tracks"), (16, "16 tracks"), (8, "8 tracks")]
    )
    if sizes["other"]:
        size_rows += breakdown(sizes, [("other", "Other / unknown")])
    scope_rows = breakdown(
        scopes,
        [
            ("global", "Whole collection"),
            ("artist", "Artist"),
            ("album", "Album"),
            ("tag", "Tag"),
        ],
    )
    if scopes["other"]:
        scope_rows += breakdown(scopes, [("other", "Not recorded")])
    visibility_rows = breakdown(
        visibility, [("Blind", "Blind"), ("Non-blind", "Non-blind")]
    )
    if visibility["Not recorded"]:
        visibility_rows += breakdown(visibility, [("Not recorded", "Not recorded")])
    entered_songs = [s for s in songs.values() if s["entries"]]
    records = []
    for label, key, unit, pool in [
        ("Most titles", "championships", "titles", entered_songs),
        ("Most podiums", "podiums", "podiums", entered_songs),
        ("Most tournament points", "tournament_points", "points", entered_songs),
        ("Most entry credit", "entry_credit", "entry credit", entered_songs),
        ("Most match wins", "tournament_wins", "wins", entered_songs),
        (
            "Best win rate · 3+ matches",
            "win_rate",
            "%",
            [s for s in entered_songs if s["played"] >= 3],
        ),
    ]:
        candidates = [s for s in pool if s[key] is not None and s[key] > 0]
        best = min(
            candidates,
            key=lambda s: (
                -(s["tournament_wins"] / s["played"] if key == "win_rate" else s[key]),
                -s["played"],
                s["title"].casefold(),
                s["id"],
            ),
            default=None,
        )
        records.append(
            dict(
                label=label,
                song=best,
                value=(
                    round(best[key], 2)
                    if best and key == "tournament_points"
                    else best[key] if best else None
                ),
                unit=unit,
            )
        )

    def category(kind, identities, links):
        """Aggregate entered-song tournament evidence into collection leaders."""
        grouped = defaultdict(list)
        for song in entered_songs:
            for key in links(song):
                if key in identities:
                    grouped[key].append(song)
        rows = []
        for key, related in grouped.items():
            row = identities[key]
            rows.append(
                dict(
                    row,
                    name=row.get("name", row.get("title", "")),
                    titles=sum(s["championships"] for s in related),
                    podiums=sum(s["podiums"] for s in related),
                    points=round(sum(s["tournament_points"] for s in related), 2),
                    tracks=len(related),
                    brackets=round(sum(max(weights.get((s["id"],tid),0) for s in related) for tid in set().union(*(appearances[s["id"]] for s in related))),2),
                )
            )
        rows.sort(
            key=lambda r: (
                -r["titles"],
                -r["podiums"],
                -r["points"],
                -r["brackets"],
                r["name"].casefold(),
                r["id"],
            )
        )
        return dict(kind=kind, rows=rows[:5])

    archive = sorted(
        brackets.values(),
        key=lambda t: (
            t["status"] == "in_progress",
            (t["date"] or {}).get("seconds", float("-inf")),
            t["id"],
        ),
        reverse=True,
    )
    pages = max(1, ceil(len(archive) / ARCHIVE_SIZE))
    archive_page = max(1, min(archive_page or 1, pages))
    if selected in brackets:
        archive_page = (
            next(i for i, t in enumerate(archive) if t["id"] == selected)
            // ARCHIVE_SIZE
            + 1
        )
    shown = archive[(archive_page - 1) * ARCHIVE_SIZE : archive_page * ARCHIVE_SIZE]
    for t in shown:
        groups = defaultdict(list)
        for m in sorted(
            matches_by[t["id"]],
            key=lambda m: (
                m["round_number"],
                m.get("match_type") == "third_place",
                m["match_number"],
                m["id"],
            ),
        ):
            label = stage_name(
                t.get("size"), m["round_number"], m.get("match_type", "bracket")
            )
            groups[label].append(
                dict(
                    m,
                    left=identity(
                        m.get("song1_id"),
                        (
                            "Track unavailable"
                            if m["status"] == "completed"
                            else "Awaiting qualifier"
                        ),
                    ),
                    right=identity(
                        m.get("song2_id"),
                        (
                            "Track unavailable"
                            if m["status"] == "completed"
                            else "Awaiting qualifier"
                        ),
                    ),
                    points=number(m.get("points_awarded")),
                    date=saved_time(m.get("played_at")),
                )
            )
        t["rounds"] = [dict(label=k, matches=v) for k, v in groups.items()]
        t["map_data"] = dict(
            tournament={key: t[key] for key in ("id", "size", "status", "is_blind")},
            entries=[dict(identity(e["song_id"]), artist=", ".join(a["name"] for a in identity(e["song_id"])["artist_links"])) for e in entries_by[t["id"]]],
            matches=matches_by[t["id"]],
        )
        t["selected"] = t["id"] == selected
    return attach_reports(
        conn,
        dict(
            summary=dict(
                brackets=len(brackets),
                unfinished=len(brackets) - len(finished),
                finished=len(finished),
                completion=percent(len(finished), len(brackets)),
                matches=len(decided),
                entries=entry_total,
                missing_entries=missing_entries,
                week=week,
                month=month,
                match_week=match_week,
                main_matches=sum(
                    m.get("match_type", "bracket") == "bracket" for m in decided
                ),
                bronze_matches=sum(
                    m.get("match_type") == "third_place" for m in decided
                ),
                other_matches=sum(
                    m.get("match_type", "bracket") not in ("bracket", "third_place")
                    for m in decided
                ),
                points=(
                    round(sum(p for p in known_points if p is not None), 2)
                    if any(p is not None for p in known_points)
                    else None
                ),
                missing_points=sum(p is None for p in known_points),
            ),
            latest=finished[0] if finished else None,
            recent_champions=finished[1:6],
            sizes=size_rows,
            scopes=scope_rows,
            visibility=visibility_rows,
            coverage=dict(
                entered=len(entered_songs),
                unentered=len(songs) - len(entered_songs),
                total=len(songs),
                champions=sum(s["championships"] > 0 for s in songs.values()),
                share=percent(len(entered_songs), len(songs)),
                single=sum(s["entries"] == 1 for s in entered_songs),
                repeat=sum(s["entries"] >= 2 for s in entered_songs),
                five_plus=sum(s["entries"] >= 5 for s in entered_songs),
                average=round(sum(s["entries"] for s in entered_songs) / len(entered_songs), 2) if entered_songs else None,
            ),
            stages=[
                dict(label=k, count=v, share=percent(v, len(decided)))
                for k, v in sorted(
                    stages.items(),
                    key=lambda item: (
                        {
                            "Round of 32": 0,
                            "Round of 16": 1,
                            "Quarter-finals": 2,
                            "Semi-finals": 3,
                            "Final": 4,
                            "Third-place playoff": 5,
                        }.get(item[0], 6),
                        item[0],
                    ),
                )
            ],
            records=records,
            categories=[
                category("artist", artists, lambda s: artist_links[s["id"]]),
                category(
                    "album",
                    {i: a for i, a in albums.items() if proper_album(a)},
                    lambda s: {s.get("album_id")},
                ),
                category("tag", tags, lambda s: tag_links[s["id"]]),
            ],
            seeds=dict(
                known=seeded_champions,
                first=first_seed,
                top_half=top_half,
                bottom_half=seeded_champions - top_half,
                top_share=percent(top_half, seeded_champions),
                matches=seeded_matches,
                upsets=higher_seed_wins,
                upset_share=percent(higher_seed_wins, seeded_matches),
                largest=min(
                    champion_seeds,
                    key=lambda r: (-r["seed"], -r["bracket"]["id"]),
                    default=None,
                ),
            ),
            archive=shown,
            archive_page=archive_page,
            archive_pages=pages,
            archive_total=len(archive),
            selected_missing=selected is not None and selected not in brackets,
        ),
        "tournament",
        now=now,
        tournament_ids=set(brackets) if competition_only else None,
    )


@app.route('/tournament_local_stats')
def local_tournament_stats_page():
    """Compare artist/album-only brackets without contributing to competition."""
    scope=request.args.get('scope','all')
    scope_id=request.args.get('scope_id',type=int)
    view=request.args.get('view')
    if view:
        parts=view.split(':',1)
        scope=parts[0]
        try:scope_id=int(parts[1]) if len(parts)==2 else None
        except ValueError:abort(400)
    if scope not in ('all','artist','album') or (scope=='all' and scope_id is not None):abort(400)
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        data=build_local_tournament_stats(conn,scope,scope_id,request.args.get('page',1,type=int))
    finally:conn.close()
    return render_template('tournament_local_stats.html',**data)


def build_local_tournament_stats(conn, scope='all', scope_id=None, page=1):
    """Raw local results: only finished brackets reveal participant comparisons.
    Scope filters apply before every aggregate; archived unfinished Blind identities
    stay hidden. Counts are observed results, not a new cross-library rating.
    """
    artists={r['id']:dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums={r['id']:dict(r) for r in conn.execute('SELECT * FROM albums')}
    songs={r['id']:dict(r) for r in conn.execute('SELECT * FROM songs')}
    links=defaultdict(set)
    for r in conn.execute('SELECT song_id,artist_id FROM song_artists'):links[r['song_id']].add(r['artist_id'])
    brackets=[dict(r) for r in conn.execute("SELECT * FROM tournaments WHERE scope_type IN ('artist','album') ORDER BY id DESC")]
    choices=[]
    for kind,rows in [('artist',artists),('album',albums)]:
        for key in sorted({t['scope_id'] for t in brackets if t['scope_type']==kind},key=lambda key: str(rows.get(key,{}).get('name',rows.get(key,{}).get('title',''))).casefold()):
            row=rows.get(key,{})
            choices.append(dict(value=f'{kind}:{key}',name=row.get('name',row.get('title',f'Removed {kind} #{key}')),kind=kind))
    if scope_id is not None and scope_id not in (artists if scope=='artist' else albums) and not any(t['scope_type']==scope and t['scope_id']==scope_id for t in brackets):abort(404)
    brackets=[t for t in brackets if (scope=='all' or t['scope_type']==scope) and (scope_id is None or t['scope_id']==scope_id)]
    by_id={t['id']:t for t in brackets}
    matches=[dict(r) for r in conn.execute('SELECT * FROM tournament_matches') if r['tournament_id'] in by_id]
    entries=[dict(r) for r in conn.execute('SELECT * FROM tournament_entries') if r['tournament_id'] in by_id]
    finished={t['id'] for t in brackets if t['status']=='completed'}
    decided=[m for m in matches if m['tournament_id'] in finished and recorded_result(m)]
    for t in brackets:
        if t['id'] not in finished:continue
        size=t.get('size');final=size.bit_length()-1 if isinstance(size,int) and size>=2 else None
        for m in decided:
            if m['tournament_id']!=t['id']:continue
            keys=('third_place_id','fourth_place_id') if m.get('match_type')=='third_place' else ('champion_id','runner_up_id') if m['round_number']==final else None
            if keys:
                for key,sid in zip(keys,(m['winner_id'],m['loser_id'])):
                    if t.get(key) is None:t[key]=sid
    complete_data=dict(songs=list(songs.values()),tournaments=[t for t in brackets if t['id'] in finished],tournament_entries=[e for e in entries if e['tournament_id'] in finished],tournament_matches=decided)
    performance=song_performance(complete_data,competitive=False)
    track_rows=[]
    for sid,stats in performance.items():
        played=stats['tournament_wins']+stats['tournament_losses']
        if not played:continue
        song=songs[sid];album=albums.get(song.get('album_id'),{})
        track_rows.append(dict(song,**stats,name=song['title'],cover_url=album.get('cover_url',''),played=played,win_rate=percent(stats['tournament_wins'],played),title_rate=percent(stats['championships'],stats['tournament_appearances']),artist=', '.join(artists[a]['name'] for a in sorted(links[sid]) if a in artists)))
    def rank(rows):
        """Order observed titles, then win rate and match evidence; names break ties."""
        return sorted(rows,key=lambda r:(-r['championships'],-(r['win_rate'] or 0),-r['played'],r['name'].casefold()))
    track_rows=rank(track_rows)
    groups=[]
    for kind,rows in [('artist',artists),('album',albums)]:
        grouped=[]
        for key,identity in rows.items():
            related=[s for s in track_rows if (key in links[s['id']] if kind=='artist' else s.get('album_id')==key)]
            if not related:continue
            wins=sum(s['tournament_wins'] for s in related);losses=sum(s['tournament_losses'] for s in related)
            grouped.append(dict(id=key,name=identity.get('name',identity.get('title')),tracks=len(related),championships=sum(s['championships'] for s in related),podiums=sum(s['podiums'] for s in related),entries=sum(s['tournament_appearances'] for s in related),played=wins+losses,wins=wins,win_rate=percent(wins,wins+losses),points=sum(s['tournament_points'] for s in related),favourite=rank(related)[0]))
        groups.append(dict(kind=kind,rows=rank(grouped)[:25]))
    pairs={}
    for m in decided:
        a,b=sorted((m['winner_id'],m['loser_id']))
        if a not in songs or b not in songs:continue
        pair=pairs.setdefault((a,b),dict(a=songs[a],b=songs[b],a_wins=0,b_wins=0,total=0))
        pair['a_wins' if m['winner_id']==a else 'b_wins']+=1;pair['total']+=1
    head_to_head=sorted(pairs.values(),key=lambda r:(-r['total'],r['a']['title'].casefold(),r['b']['title'].casefold()))[:20]
    decided_counts=Counter(m['tournament_id'] for m in matches if recorded_result(m))
    for t in brackets:
        identity=(artists if t['scope_type']=='artist' else albums).get(t['scope_id'],{})
        t['name']=identity.get('name',identity.get('title','Removed collection'))
        t['decided']=decided_counts[t['id']]
        t['winner']=songs.get(t.get('champion_id')) if t['status']=='completed' else None
    pages=max(1,ceil(len(brackets)/20));page=min(pages,max(1,page or 1))
    return dict(scope=scope,scope_id=scope_id,view=f'{scope}:{scope_id}' if scope_id is not None else scope,choices=choices,
                summary=dict(brackets=len(brackets),completed=len(finished),matches=len(decided),tracks=len(track_rows),points=sum(number(m.get('points_awarded')) or 0 for m in decided)),
                tracks=track_rows[:50],groups=groups,pairs=head_to_head,archive=brackets[(page-1)*20:page*20],page=page,pages=pages)
