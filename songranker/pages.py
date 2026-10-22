from flask import render_template, request, jsonify, abort
from songranker.services import app, get_db_connection
from songranker.catalog import collection, ranked, proper_album


@app.route("/")
def home():
    return render_template("app_page.html", page="home")


@app.route("/leaderboard")
def leaderboard():
    return render_template("app_page.html", page="rankings_songs")


@app.route("/artists")
def artists_leaderboard():
    return render_template("app_page.html", page="rankings_artists")


@app.route("/albums")
def albums_leaderboard():
    return render_template("app_page.html", page="rankings_albums")


@app.route("/api/library")
def api_library():
    kind = request.args.get("type", "songs")
    if kind not in ("songs", "artists", "albums", "tags"):
        return jsonify({"error": "Invalid type."}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 60)), 200))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify({"error": "Invalid pagination."}), 400
    data = collection()
    items = ranked(data, kind)
    q = request.args.get("q", "").casefold().strip()
    if q:
        items = [
            r
            for r in items
            if q
            in " ".join(
                str(r.get(k, ""))
                for k in ("title", "name", "artist", "album", "genres")
            ).casefold()
        ]
    if kind == "albums":
        items = [r for r in items if proper_album(r)]
    return jsonify(
        type=kind,
        items=items[offset : offset + limit],
        total=len(items),
        offset=offset,
        limit=limit,
        has_more=offset + limit < len(items),
    )


@app.route("/api/collection")
def api_collection():
    return jsonify(collection())


@app.route("/search")
def search():
    return render_template("app_page.html", page="search")


@app.route("/artist_stats")
def artist_performance():
    mode = (
        "trivia"
        if request.args.get("metric", "recognition") == "recognition"
        else "tournament"
    )
    return render_template(
        "app_page.html", page="mode_rankings_" + mode, ranking_entity="artists"
    )


@app.route("/album_stats")
def album_performance():
    mode = (
        "trivia"
        if request.args.get("metric", "recognition") == "recognition"
        else "tournament"
    )
    return render_template(
        "app_page.html", page="mode_rankings_" + mode, ranking_entity="albums"
    )


@app.route("/global_stats")
def global_stats():
    from songranker.reports.global_stats_data import build_global_stats

    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        data = build_global_stats(conn)
        return render_template("global_stats.html", **data)
    finally:
        conn.close()


@app.route("/song/<int:song_id>")
def song_page(song_id):
    conn = get_db_connection()
    found = conn.execute("SELECT 1 FROM songs WHERE id=?", (song_id,)).fetchone()
    conn.close()
    if not found:
        abort(404)
    return render_template("app_page.html", page="song", entity_id=song_id)


@app.route("/artist/<path:artist_name>")
def artist_page(artist_name):
    """Resolve the collection identity; the shared profile reads its data once."""
    return collection_profile("artist", "artists", "name", artist_name)


@app.route("/album/<path:album_title>")
def album_page(album_title):
    """Resolve the collection identity; the shared profile reads its data once."""
    return collection_profile("album", "albums", "title", album_title)


@app.route("/tags")
def tags_index():
    """Render tag rankings through the shared rankings shell."""
    return render_template("app_page.html", page="rankings_tags")


@app.route("/tag/<path:tag_name>")
def tag_page(tag_name):
    """Resolve the collection identity; the shared profile reads its data once."""
    return collection_profile("tag", "genres", "name", tag_name)


@app.route("/mode_rankings/<mode>")
def special_rankings(mode):
    if mode not in ("trivia", "tournament", "guesser", "shelves", "vibe"):
        return "Unknown mode", 404
    return render_template("app_page.html", page="mode_rankings_" + mode)


def collection_profile(kind, table, column, name):
    """Resolve one named collection for the shared profile template.

    Table and column come only from the fixed route declarations above.
    Catalogue statistics are hydrated by /api/collection, not duplicated here.
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            f"SELECT id,{column} AS name FROM {table} WHERE {column}=? COLLATE NOCASE",
            (name,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        abort(404)
    return render_template(
        "profile.html",
        page=kind,
        profile_kind=kind + "s" if kind != "tag" else "tags",
        profile_name=row["name"],
        entity_id=row["id"],
    )
