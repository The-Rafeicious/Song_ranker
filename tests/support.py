"""Reusable assertions and route-module fixtures; never opens an active database."""

from songranker.storage.competition import CATALOGUE
from songranker.storage.database_io import quote

KEEP = {
    **CATALOGUE,
    "song_details": (
        "song_id",
        "added_at",
        "preview_bad",
        "preview_note",
        "flagged_at",
    ),
}


RESULT_TABLES = (
    "preference_events",
    "preference_corrections",
    "preference_rating_projection",
    "preference_offers",
    "preference_rating_overrides",
    "trivia_rounds",
    "trivia_adjustments",
    "challenge_runs",
    "tournaments",
    "tournament_entries",
    "tournament_matches",
    "elo_guess_rounds",
    "album_shelf_rounds",
    "album_shelf_items",
    "vibe_rounds",
)


def catalogue(conn):
    return {
        table: sorted(
            [
                list(r)
                for r in conn.execute(
                    "SELECT " + ",".join(map(quote, cols)) + " FROM " + quote(table)
                )
            ],
            key=repr,
        )
        for table, cols in KEEP.items()
    }


def assert_clean(conn):
    for table in RESULT_TABLES:
        if conn.execute("SELECT 1 FROM " + quote(table) + " LIMIT 1").fetchone():
            raise ValueError("Unexpected reset results in " + table + ". ")
    if conn.execute(
        "SELECT 1 FROM songs WHERE elo_score!=1200 OR matches_played!=0 OR highest_elo!=1200 OR highest_rank!=9999 OR tournament_wins!=0 LIMIT 1"
    ).fetchone():
        raise ValueError("Song ratings are not reset.")
    if conn.execute(
        "SELECT 1 FROM song_vibe_positions WHERE status!='unmapped' OR sample_count!=0 OR not_applicable_count!=0 LIMIT 1"
    ).fetchone():
        raise ValueError("Unexpected Vibe selections after reset. ")
    if conn.execute(
        "SELECT 1 FROM song_vibe_progress WHERE completed_passes!=0 LIMIT 1"
    ).fetchone():
        raise ValueError("Unexpected Vibe passes after reset.")
    if conn.execute(
        "SELECT 1 FROM global_stats WHERE key!='trivia_scoring_version' AND value!=0 LIMIT 1"
    ).fetchone():
        raise ValueError("New global records exist.")
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='legacy_elo_changes' AND type='table'"
        ).fetchone()
        and conn.execute("SELECT 1 FROM legacy_elo_changes LIMIT 1").fetchone()
    ):
        raise ValueError("Legacy Elo results remain.")


def route_modules():
    """Read current launcher registration imports for disposable startup stubs."""
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    return {
        alias.name: node.module + "." + alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("songranker")
        and node.module != "songranker.services"
        for alias in node.names
    }


def pre_disc_layout(conn):
    """Remove schema-21 additions when a test constructs an older database layout."""
    for name in ('songs_track_position_insert', 'songs_track_position_update'):
        conn.execute('DROP TRIGGER IF EXISTS '+name)
    for name in ('songs', 'album_shelf_items'):
        conn.execute('ALTER TABLE '+name+' DROP COLUMN disc_number')
