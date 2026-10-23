"""Authenticated, browser-bound review/apply endpoints for tag-only catalogue work."""

from flask import jsonify, request
from itsdangerous import URLSafeTimedSerializer, BadData
from songranker.services import app, admin_required, get_db_connection
from songranker.developer.catalog_sources import owner
import hashlib
import json
import unicodedata
from songranker.storage.tag_limits import check_count


def signer():
    return URLSafeTimedSerializer(app.secret_key, salt="catalog-tag-review-v1")


@app.route("/api/dev/tags/review", methods=["POST"])
@admin_required
def review_tags():
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        change = canonical_proposal(conn, request.get_json(silent=True))
        review = plan(conn, change)
        token = signer().dumps(
            dict(
                owner=owner(),
                change=change,
                before=review["before_hash"],
                after=review["after_hash"],
            )
        )
        return jsonify(
            **{k: v for k, v in review.items() if not k.endswith("_hash")},
            review_token=token,
        )
    except ValueError as error:
        return jsonify(message=str(error)), 400
    finally:
        conn.close()


@app.route("/api/dev/tags/apply", methods=["POST"])
@admin_required
def apply_tags():
    data = request.get_json(silent=True)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("review_token"), str)
        or len(data["review_token"]) > 250000
    ):
        return jsonify(message="Review the tag changes before saving."), 400
    try:
        verified = signer().loads(data["review_token"], max_age=86400)
    except BadData:
        return jsonify(message="This tag review expired or changed. Review again."), 400
    if verified.get("owner") != owner():
        return jsonify(message="Review tags in this browser before saving."), 400
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            review = plan(conn, verified["change"])
        except ValueError as error:
            return jsonify(message=str(error)), 409
        if review["before_hash"] == verified["after"]:
            return jsonify(
                status="success",
                already_matches=True,
                updated=0,
                added_links=0,
                removed_links=0,
                created_tags=[],
                backup=None,
                message="Tags already match this review. Nothing changed.",
            )
        if review["before_hash"] != verified["before"]:
            return (
                jsonify(
                    message="Songs or tags changed since this review. Review again before saving."
                ),
                409,
            )
        created = apply_memberships(conn, review)
        response = jsonify(
            status="success",
            already_matches=False,
            updated=review["changed_songs"],
            added_links=review["added_links"],
            removed_links=review["removed_links"],
            created_tags=created,
            backup=None,
            message=f"Updated tags on {review['changed_songs']} songs.",
        )
        conn.commit()
        return response
    except Exception:
        conn.rollback()
        app.logger.exception("Reviewed tag save failed")
        return (
            jsonify(
                message="Tags could not be saved. No tag changes were applied. Check database health and try again."
            ),
            500,
        )
    finally:
        conn.close()


# Reviewed tag membership changes. No ratings, identities or game facts are edited.


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def identifiers(value, label, allow_empty=False, maximum=10000):
    """Validate, deduplicate and sort bounded positive song/tag ID lists for a tag
    proposal.
    """
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(type(v) is not int or v <= 0 for v in value)
    ):
        raise ValueError(f"{label} must be a list of positive song/tag IDs.")
    result = sorted(set(value))
    if not result and not allow_empty:
        raise ValueError(f"Choose at least one {label.lower()}.")
    return result


def proposal(data):
    """Validate a tag add/remove/replace request and canonicalise existing IDs and
    new tag names.
    """
    if not isinstance(data, dict):
        raise ValueError("Send a tag change as an object.")
    action = data.get("action")
    if action not in ("add_tags", "remove_tags", "replace_tags"):
        raise ValueError("Choose Add, Remove or Replace tags.")
    names = data.get("new_tags", [])
    if not isinstance(names, list) or len(names) > 25:
        raise ValueError("Use at most 25 new tag names per review.")
    unique = {}
    for name in names:
        if not isinstance(name, str):
            raise ValueError("New tag names must be text.")
        name = unicodedata.normalize("NFKC", name).strip().lstrip("#").strip()
        if (
            not name
            or len(name) > 120
            or "," in name
            or any(unicodedata.category(c).startswith("C") for c in name)
        ):
            raise ValueError(
                "Use nonblank tag names up to 120 characters, without commas or control characters."
            )
        unique.setdefault(normalized(name), name)
    result = dict(
        song_ids=identifiers(data.get("song_ids"), "Songs"),
        action=action,
        tag_ids=identifiers(data.get("tag_ids", []), "Tags", True, 1000),
        new_tags=list(unique.values()),
    )
    if action == "remove_tags" and result["new_tags"]:
        raise ValueError("Choose existing tags to remove.")
    if action != "replace_tags" and not result["tag_ids"] and not result["new_tags"]:
        raise ValueError(
            "Choose at least one tag. Replace can explicitly clear all tags."
        )
    return result


def definitions(conn):
    """Read canonical tag IDs, names and descriptions in stable ID order."""
    return {
        r["id"]: dict(r)
        for r in conn.execute("SELECT id,name,description FROM genres ORDER BY id")
    }


def canonical_proposal(conn, data):
    """Bind existing names to IDs now; only truly new names remain unbound."""
    result = proposal(data)
    tags = definitions(conn)
    by_name = {}
    for tag in tags.values():
        by_name.setdefault(normalized(tag["name"]), []).append(tag)
    if any(t not in tags for t in result["tag_ids"]):
        raise ValueError("A selected tag no longer exists.")
    missing = []
    for name in result["new_tags"]:
        found = by_name.get(normalized(name), [])
        if len(found) > 1:
            raise ValueError(
                "Several existing tags match that name. Choose the intended tag by ID."
            )
        if found:
            result["tag_ids"].append(found[0]["id"])
        else:
            missing.append(name)
    result.update(tag_ids=sorted(set(result["tag_ids"])), new_tags=missing)
    return result


def chunks(values, size=400):
    """Yield bounded ID batches so tag queries stay within SQLite parameter limits."""
    for i in range(0, len(values), size):
        yield values[i : i + size]


def digest(value):
    """Hash deterministic tag-review state so apply can reject changes since review."""
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def plan(conn, change):
    """One consistent snapshot; fingerprint metadata/tags, excluding game activity."""
    tags = definitions(conn)
    by_name = {}
    for tag in tags.values():
        by_name.setdefault(normalized(tag["name"]), []).append(tag)
    aliases = {normalized(name): name for name in change["new_tags"]}

    def public(tag):
        """Assign a stable review key to an existing or proposed tag, including
        canonical aliases.
        """
        key = (
            "new:" + normalized(tag["name"])
            if normalized(tag["name"]) in aliases
            else "id:" + str(tag["id"])
        )
        return dict(
            key=key, id=tag["id"], name=tag["name"], description=tag["description"]
        )

    targets = []
    for tid in change["tag_ids"]:
        if tid not in tags:
            raise ValueError(
                "A reviewed tag no longer exists. Review the change again."
            )
        targets.append(public(tags[tid]))
    for norm, name in aliases.items():
        found = by_name.get(norm, [])
        if len(found) > 1:
            raise ValueError(
                "The new tag name is now ambiguous. Review the change again."
            )
        targets.append(
            public(found[0])
            if found
            else dict(key="new:" + norm, id=None, name=name, description="")
        )
    targets.sort(key=lambda t: t["key"])
    wanted = {t["key"]: t for t in targets}
    songs = {}
    artists = {}
    members = {}
    for ids in chunks(change["song_ids"]):
        where = ",".join("?" for _ in ids)
        for r in conn.execute(
            f"""SELECT s.id,s.title,s.album_id,a.title album FROM songs s
            LEFT JOIN albums a ON a.id=s.album_id WHERE s.id IN ({where}) ORDER BY s.id""",
            ids,
        ):
            songs[r["id"]] = dict(r)
            artists[r["id"]] = []
            members[r["id"]] = {}
        for r in conn.execute(
            f"""SELECT sa.song_id,a.id,a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id
            WHERE sa.song_id IN ({where}) ORDER BY a.id""",
            ids,
        ):
            artists[r["song_id"]].append(dict(id=r["id"], name=r["name"]))
        for r in conn.execute(
            f"SELECT song_id,genre_id FROM song_genres WHERE song_id IN ({where}) ORDER BY genre_id",
            ids,
        ):
            if r["genre_id"] not in tags:
                raise ValueError(
                    "An existing tag link is invalid. Check database integrity first."
                )
            tag = public(tags[r["genre_id"]])
            members[r["song_id"]][tag["key"]] = tag
    if len(songs) != len(change["song_ids"]):
        raise ValueError(
            "A selected song no longer exists. Review the selection again."
        )
    rows = []
    before = []
    after = []

    def image(row, values):
        """Build a song's review image with its linked artists and sorted public tag
        definitions.
        """
        return dict(
            song=row,
            artists=artists[row["id"]],
            tags=[
                {k: t[k] for k in ("key", "name", "description")}
                for t in sorted(values.values(), key=lambda t: t["key"])
            ],
        )

    for sid in change["song_ids"]:
        old = members[sid]
        new = (
            old | wanted
            if change["action"] == "add_tags"
            else (
                {k: v for k, v in old.items() if k not in wanted}
                if change["action"] == "remove_tags"
                else wanted.copy()
            )
        )
        check_count(len(new))
        added = [new[k] for k in new.keys() - old.keys()]
        removed = [old[k] for k in old.keys() - new.keys()]
        order = lambda t: (normalized(t["name"]), t["key"])
        rows.append(
            dict(
                song_id=sid,
                title=songs[sid]["title"],
                artist=", ".join(a["name"] for a in artists[sid]),
                album=songs[sid]["album"],
                before=sorted(old.values(), key=order),
                after=sorted(new.values(), key=order),
                added=sorted(added, key=order),
                removed=sorted(removed, key=order),
            )
        )
        before.append(image(songs[sid], old))
        after.append(image(songs[sid], new))
    target_image = [{k: t[k] for k in ("key", "name", "description")} for t in targets]
    changed = sum(bool(r["added"] or r["removed"]) for r in rows)
    return dict(
        action=change["action"],
        target_tags=targets,
        rows=rows,
        selected_count=len(rows),
        changed_songs=changed,
        unchanged_songs=len(rows) - changed,
        added_links=sum(len(r["added"]) for r in rows),
        removed_links=sum(len(r["removed"]) for r in rows),
        new_tags=[t["name"] for t in targets if t["id"] is None],
        before_hash=digest(dict(songs=before, targets=target_image)),
        after_hash=digest(dict(songs=after, targets=target_image)),
    )


def apply_memberships(conn, review):
    """Caller owns BEGIN IMMEDIATE. Apply only the reviewed membership deltas."""
    ids = {}
    for row in review["rows"]:
        for tag in row["after"]:
            if tag["key"] in ids:
                continue
            if tag["id"] is None:
                ids[tag["key"]] = conn.execute(
                    "INSERT INTO genres(name,description) VALUES(?,?)",
                    (tag["name"], tag["description"]),
                ).lastrowid
            else:
                ids[tag["key"]] = tag["id"]
        for tag in row["removed"]:
            conn.execute(
                "DELETE FROM song_genres WHERE song_id=? AND genre_id=?",
                (row["song_id"], tag["id"]),
            )
        for tag in row["added"]:
            conn.execute(
                "INSERT OR IGNORE INTO song_genres(song_id,genre_id) VALUES(?,?)",
                (row["song_id"], ids[tag["key"]]),
            )
    return [
        dict(id=ids["new:" + normalized(name)], name=name)
        for name in review["new_tags"]
    ]
