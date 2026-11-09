from contextlib import closing
from flask import session, render_template, request, jsonify, abort
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
    if mode not in ("trivia", "tournament", "shelves", "vibe"):
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


@app.route('/query')
def mode_query_page():
    """Cross-mode query workspace without eager client catalogue hydration."""
    return render_template('query.html', page='mode_query')


@app.route('/api/query')
def mode_query_api():
    """Validate public filters and return bounded results from a single read snapshot."""
    import json
    from songranker.reports.query import METRICS, KINDS, validate, execute, identities, search_identities
    if request.args.get('schema') == '1':
        return jsonify(metrics=list(METRICS.values()), entities=KINDS)
    try:
        if request.args.get('lookup'):
            kind=request.args['lookup']
            if kind not in KINDS: raise ValueError('Invalid lookup.')
            data=collection()
            q=request.args.get('q','')[:200].strip()
            candidates=identities(data)[kind].values()
            if kind=='albums': candidates=[r for r in candidates if r['proper_album']]
            rows=search_identities(candidates,q) if q else []
            return jsonify(items=rows[:25],total=len(rows))
        raw=request.args.get('spec','{}')
        if len(raw)>12000: raise ValueError('Query is too large.')
        spec=validate(json.loads(raw))
        relationships=any(f['field'] in ('won_against','lost_to') for f in spec['filters'])
        return jsonify(execute(collection(include_overall_sources=True, include_query_sources=relationships),spec))
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return jsonify(error=str(error) or 'Invalid query.'),400


@app.route('/api/query/presets', methods=['GET', 'POST'])
def query_presets_api():
    """List personal presets or save a new one from the current Query builder."""
    import json
    import sqlite3
    from uuid import uuid4

    with closing(get_db_connection()) as conn, conn:
        if request.method == 'GET':
            rows = conn.execute(
                'SELECT id, name, spec, revision FROM query_presets ORDER BY name, id'
            )
            return jsonify(presets=[dict(row, spec=json.loads(row['spec'])) for row in rows])
        try:
            name, spec = query_preset_fields(request.get_json(silent=True))
            preset_id = uuid4().hex
            conn.execute('INSERT INTO query_presets(id, name, spec) VALUES(?,?,?)',
                         (preset_id, name, json.dumps(spec)))
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            return jsonify(error=str(error) or 'Invalid preset.'), 400
        except sqlite3.IntegrityError:
            return jsonify(error='A preset already uses that name.'), 409
        return jsonify(id=preset_id, name=name, spec=spec, revision=1), 201


def query_preset_fields(data):
    """Validate a bounded name and normalize the current builder options for reuse."""
    import json
    from songranker.reports.query import validate

    if not isinstance(data, dict) or not isinstance(data.get('name'), str):
        raise ValueError('Enter a preset name.')
    name = data['name'].strip()
    name.encode('utf-8')
    if not 1 <= len(name) <= 80 or any(ord(ch) < 32 for ch in name):
        raise ValueError('Enter a preset name of 1 to 80 characters.')
    raw = data.get('spec')
    if not isinstance(raw, dict) or len(json.dumps(raw)) > 12000:
        raise ValueError('Invalid or oversized query.')
    spec = validate(dict(raw, page=1))
    spec['sort'] = [{key: sort[key] for key in ('field', 'direction')} for sort in spec['sort']]
    return name, spec


@app.route('/api/dev/query/presets/<preset_id>', methods=['PUT', 'DELETE'])
def edit_query_preset_api(preset_id):
    """Update or delete a preset with the Dev session and the editor's revision."""
    import json
    import sqlite3

    if not session.get('is_admin'):
        return jsonify(error='Unlock Dev to edit saved presets.'), 403
    data = request.get_json(silent=True)
    revision = data.get('revision') if isinstance(data, dict) else None
    if type(revision) is not int or not 1 <= revision < 2**63 - 1:
        return jsonify(error='Reload the preset before making changes.'), 400
    with closing(get_db_connection()) as conn, conn:
        try:
            if request.method == 'DELETE':
                cursor = conn.execute('DELETE FROM query_presets WHERE id=? AND revision=?',
                                      (preset_id, revision))
            else:
                name, spec = query_preset_fields(data)
                cursor = conn.execute(
                    'UPDATE query_presets SET name=?, spec=?, revision=revision+1 '
                    'WHERE id=? AND revision=?',
                    (name, json.dumps(spec), preset_id, revision))
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            return jsonify(error=str(error) or 'Invalid preset.'), 400
        except sqlite3.IntegrityError:
            return jsonify(error='A preset already uses that name.'), 409
        if not cursor.rowcount:
            return jsonify(error='This preset changed or was deleted. Reload before editing.'), 409
        if request.method == 'DELETE':
            return jsonify(deleted=True)
        return jsonify(id=preset_id, name=name, spec=spec, revision=revision + 1)
