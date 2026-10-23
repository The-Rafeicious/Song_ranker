"""Offline schema adapters for recovery and historical fixtures; current DDL has one owner."""

from songranker.storage.database_schema import create_objects
from copy import deepcopy
import re


def ensure_mode_schema(conn, *, legacy=False):
    objects = {
        r["name"]: r["type"]
        for r in conn.execute(
            "SELECT name,type FROM sqlite_master WHERE type IN ('table','view')"
        )
    }
    if objects.get("trivia_stats") == "view":
        conn.execute("DROP VIEW trivia_stats")
    # Only detailed V3.2 results and their sparse manual corrections remain.
    from songranker.storage.database_schema import create_objects

    create_objects(conn, names={"trivia_adjustments"})
    missing_rounds = "trivia_rounds" not in objects
    if missing_rounds and not legacy:
        create_objects(conn, names={"challenge_runs", "challenge_active_run"})
    if objects.get("trivia_legacy") == "table":
        old_columns = {
            r["name"] for r in conn.execute("PRAGMA table_info(trivia_legacy)")
        }
        deltas = (
            "new_attempts_delta",
            "title_correct_delta",
            "artist_correct_delta",
            "album_attempts_delta",
            "album_correct_delta",
        )
        if set(deltas) <= old_columns:
            columns = ",".join(deltas)
            conn.execute(
                f"INSERT OR IGNORE INTO trivia_adjustments(song_id,{columns}) "
                f"SELECT song_id,{columns} FROM trivia_legacy WHERE "
                + " OR ".join(f"{name}!=0" for name in deltas)
            )
        conn.execute("DROP TABLE trivia_legacy")
    if objects.get("trivia_stats") == "table":
        conn.execute("DROP TABLE trivia_stats")
    # A pre-8 database without detailed Trivia has no quiz facts to transport.
    # Let the final canonical rebuild create the current empty tables/view.
    if not (legacy and missing_rounds):
        create_objects(
            conn, names={"trivia_rounds", "trivia_rounds_song", "trivia_stats"}
        )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(history)")}
    if "is_tournament_match" in cols:
        conn.execute(
            "UPDATE history SET mode='legacy_tournament' WHERE is_tournament_match=1"
        )
        conn.execute("ALTER TABLE history DROP COLUMN is_tournament_match")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tournament_matches)")}
    if "match_type" not in cols:
        conn.execute(
            "ALTER TABLE tournament_matches ADD COLUMN match_type TEXT NOT NULL DEFAULT 'bracket'"
        )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tournaments)")}
    for name, declaration in [
        ("playoff_enabled", "INTEGER NOT NULL DEFAULT 0"),
        ("runner_up_id", "INTEGER REFERENCES songs(id)"),
        ("third_place_id", "INTEGER REFERENCES songs(id)"),
        ("fourth_place_id", "INTEGER REFERENCES songs(id)"),
    ]:
        if name not in cols:
            conn.execute(f"ALTER TABLE tournaments ADD COLUMN {name} {declaration}")
    if not conn.execute(
        "SELECT 1 FROM global_stats WHERE key='trivia_scoring_version'"
    ).fetchone():
        conn.execute(
            "INSERT INTO global_stats(key,value) VALUES('trivia_high_score',0) ON CONFLICT(key) DO UPDATE SET value=0"
        )
        conn.execute(
            "INSERT INTO global_stats(key,value) VALUES('trivia_scoring_version',2)"
        )
    conn.execute(
        "INSERT OR IGNORE INTO global_stats(key,value) VALUES('trivia_high_streak',0)"
    )

    conn.execute("DELETE FROM global_stats WHERE key='trivia_legacy_high_score'")


def ensure_special_schema(conn, *, legacy=False):
    missing = not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='elo_guess_rounds'"
    ).fetchone()
    if missing and not legacy:
        create_objects(conn, names={"challenge_runs", "challenge_active_run"})
    names = {"album_shelf_rounds", "album_shelf_items", "shelf_completed"}
    if not (legacy and missing):
        names.update({"elo_guess_rounds", "elo_guess_completed"})
    create_objects(conn, names=names)


# Pure schema-12 transport upgrade. Historical quiz rows remain classic facts.

CHALLENGE_ADDITIONS = {
    "trivia_rounds": (
        ("run_id", None),
        ("rules_version", 1),
        ("streak_before", None),
        ("streak_rule", None),
        ("streak_passed", None),
        ("answer_snapshot", None),
    ),
    "elo_guess_rounds": (
        ("run_id", None),
        ("rules_version", 1),
        ("streak_before", None),
        ("target_quantile", None),
        ("streak_after", None),
        ("user_score_after", None),
    ),
}


def upgrade_challenges(original):
    """Adapt captured pre-12 rounds to challenge fields while refusing conflicting
    extension tables.
    """
    if original["user_version"] >= 12:
        return original
    state = deepcopy(original)
    if "challenge_runs" in state["tables"]:
        raise ValueError(
            "A pre-12 extension uses challenge_runs; a dedicated migration is required. No data was discarded."
        )
    for name, additions in CHALLENGE_ADDITIONS.items():
        target = state["tables"].get(name)
        if target:
            for column, default in additions:
                if column in target["columns"]:
                    raise ValueError(
                        f"A pre-12 extension uses {name }.{column }; a dedicated migration is required."
                    )
                target["columns"].append(column)
                for row in target["rows"]:
                    row.append(default)
    state["user_version"] = 12
    return state


# Lossless schema-13 upgrade: unknown legacy source identities/dates stay unknown.

SOURCE_ADDITIONS = (("release_date", None), ("release_date_origin", None))


def upgrade_sources(original):
    """Adapt pre-13 song/source metadata without replacing extensions or existing
    stored values.
    """
    if original["user_version"] >= 13:
        return original
    state = deepcopy(original)
    if "song_sources" in state["tables"]:
        raise ValueError(
            "A pre-13 extension uses song_sources; a dedicated migration is required. No data was discarded."
        )
    songs = state["tables"].get("songs")
    if songs:
        for column, default in SOURCE_ADDITIONS:
            if column in songs["columns"]:
                raise ValueError(
                    f"A pre-13 extension uses songs.{column }; a dedicated migration is required."
                )
            songs["columns"].append(column)
            for row in songs["rows"]:
                row.append(default)
    state["user_version"] = 13
    return state


# Schema-20 retirement only: discard former telemetry, preserve every other fact.

LISTENING_COLUMNS = (
    "id",
    "mode",
    "reference",
    "song_key",
    "song_id",
    "seconds",
    "decision_ms",
    "selected",
    "recorded_at",
)
LISTENING_OBJECTS = {"listening_observations", "listening_song_mode"}


def retire_listening(original):
    """Remove supported retired listening storage at schema 20 while refusing
    dependent custom extensions.
    """
    if original["user_version"] >= 20:
        return original
    # Unknown views/triggers/FKs must not quietly become invalid extensions.
    for obj in original["objects"]:
        if obj["name"] not in LISTENING_OBJECTS and re.search(
            r"\blistening_observations\b", obj["sql"], re.I
        ):
            raise ValueError(
                "An extension depends on retired listening data; review it before upgrading. No data was changed."
            )
    old = original["tables"].get("listening_observations")
    if old and tuple(old["columns"]) != LISTENING_COLUMNS:
        raise ValueError("Unsupported listening table columns; no data was discarded.")
    state = deepcopy(original)
    state["tables"].pop("listening_observations", None)
    state["sequences"].pop("listening_observations", None)
    state["objects"] = [
        o for o in state["objects"] if o["name"] not in LISTENING_OBJECTS
    ]
    state["user_version"] = 20
    return state
