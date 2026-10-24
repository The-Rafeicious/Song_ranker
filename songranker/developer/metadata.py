"""Conservative, fill-only Apple metadata planning. No library import helpers.

Fill verified blank catalogue fields and Apple source facts; never edit tags.
Keep all nonblank values, album/artist relationships and preferred artwork. Release matching accepts
removed trailing Single/EP labels; saved identities allow preferred local artwork.
Unlinked releases still require exact artist and artwork checks.
"""

from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import re
from copy import deepcopy
import sqlite3
import time
import unicodedata
from songranker.apple_access import apple_lookup, AppleRequestError
from songranker.developer.catalog_sources import parse_track_number
from songranker.developer.catalog_sources import check_track_position
from songranker.developer.catalog_sources import (
    observation,
    current_sources,
    source_conflict,
    save_source,
    source_label,
    identifier,
)
from secrets import token_urlsafe
from threading import Thread, Lock, Event
from flask import jsonify, request, Response
from songranker.services import app, DB_NAME, admin_required


class ScanStopped(Exception):
    pass


def normalized(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-"}))
    return " ".join(text.split())


def release_key(value):
    """Only ignore Apple's format suffix, never Deluxe/Live/remaster editions."""
    return re.sub(r"\s*-\s*(?:single|ep)$", "", normalized(value)).strip()


def missing_source(source):
    """Identify saved Apple sources with missing required identity or metadata
    fields.
    """
    if not source:
        return True
    keys = (
        "track_id",
        "collection_id",
        "artist_id",
        "storefront",
        "title",
        "artist",
        "album",
        "track_url",
        "album_url",
        "release_date",
        "duration_ms",
        "censored_title",
        "collection_explicitness",
    )
    return (
        any(blank(source.get(k)) for k in keys)
        or source.get("explicitness") not in ("explicit", "cleaned", "notExplicit")
        or any(
            blank(source.get("metadata", {}).get(k))
            for k in (
                "source_track_number",
                "disc_number",
                "disc_count",
                "cover_url",
                "audio_url",
            )
        )
    )


def merge_source(previous, fresh):
    """Append enriched observations; never replace an existing known source fact."""
    result = deepcopy(previous or {})
    for key, value in fresh.items():
        if key == "metadata":
            metadata = result.setdefault("metadata", {})
            for field, entry in value.items():
                if blank(metadata.get(field)) and not blank(entry):
                    metadata[field] = entry
        elif key != "explicitness" and blank(result.get(key)) and not blank(value):
            result[key] = value
    flag = result.get("explicitness")
    if flag not in ("explicit", "cleaned", "notExplicit"):
        result["explicitness"] = fresh["explicitness"]
        result["explicitness_assumed"] = fresh["explicitness"] == "unknown"
    return result


def propose_song(plan, song, remote):
    """Add fill-only metadata/source proposals while rejecting changed or duplicate
    Apple track identities.
    """
    if "release_date" not in song:
        return  # Legacy helper databases have only the old fields.
    fresh = observation(remote, plan["country"])
    fresh["metadata"].pop("genres", None)  # Song tags are never part of metadata fill.
    for key, remote_key in [("disc_number", "discNumber"), ("disc_count", "discCount")]:
        fresh["metadata"][key] = remote.get(remote_key)
    previous = song.get("source")
    if previous and previous["track_id"] != fresh["track_id"]:
        raise ValueError(
            "The verified track differs from the saved Apple source; existing link kept."
        )
    if any(
        s["id"] != song["id"]
        and s.get("source", {}).get("track_id") == fresh["track_id"]
        for s in plan["snapshot"]["songs"]
    ):
        raise ValueError("This Apple track is already linked to another local song.")
    if any(
        r["id"] != song["id"] and r["source"]["track_id"] == fresh["track_id"]
        for r in plan["sources"]
    ):
        raise ValueError(
            "More than one local song matches this Apple identity; review needed."
        )
    if blank(song["release_date"]) and not any(
        r["id"] == song["id"] for r in plan["song_dates"]
    ):
        try:
            value = release_date(remote.get("releaseDate"))
        except ValueError as error:
            plan["metadata_failures"].append(
                dict(id=song["id"], title=song["title"], reason=str(error))
            )
        else:
            plan["song_dates"].append(
                dict(id=song["id"], title=song["title"], value=value)
            )
    propose_fields(plan, song, fresh, "Verified Apple track " + fresh["track_id"])
    previous = next(
        (r["source"] for r in plan["sources"] if r["id"] == song["id"]), previous
    )
    merged = merge_source(previous, fresh)
    if merged != previous:
        fields = [
            key for key in merged if not previous or merged[key] != previous.get(key)
        ]
        plan["sources"] = [r for r in plan["sources"] if r["id"] != song["id"]]
        plan["sources"].append(
            dict(id=song["id"], title=song["title"], source=merged, fields=fields)
        )


def artwork_key(url):
    """Require a full Apple artwork asset path; ignore CDN host and size only."""
    try:
        u = urlsplit(url or "")
        if u.scheme != "https" or not (u.hostname or "").endswith(".mzstatic.com"):
            return None
        path = u.path
        if not re.search(r"/[0-9]+x[0-9]+[^/]*\.(?:jpg|png|webp)$", path, re.I):
            return None
        # /image/thumb/Music.../<unique asset>/SIZE.jpg -> same asset at all sizes.
        key = re.sub(r"/[0-9]+x[0-9]+[^/]*\.(?:jpg|png|webp)$", "", path, flags=re.I)
        return key if len(key) > 30 and "/Music" in key else None
    except (ValueError, TypeError):
        return None


def same_art(local, remote):
    """Compare normalised artwork identities independently of image size variants."""
    key = artwork_key(local)
    return bool(key and key == artwork_key(remote))


def release_date(value):
    """Validate an Apple release date and return its plausible ISO calendar day."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T.*)?", value
    ):
        raise ValueError("Missing or invalid Apple release date.")
    day = date.fromisoformat(value[:10])
    if not 1900 <= day.year <= date.today().year + 2:
        raise ValueError("Implausible Apple release date.")
    return day.isoformat()


def blank(value):
    """Treat null and whitespace-only strings as missing metadata without treating
    zero as empty.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def snapshot(conn):
    """Only matching identity/targets: voting and trivia can continue during scans."""
    albums = [
        dict(r)
        for r in conn.execute(
            "SELECT id,title,cover_url,release_date FROM albums ORDER BY id"
        )
    ]
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(songs)")}
    modern = {"release_date", "release_date_origin"} <= columns
    extra = ",release_date,release_date_origin" if modern else ""
    if "disc_number" in columns:
        extra += ",disc_number"
    songs = [
        dict(r)
        for r in conn.execute(
            "SELECT id,title,album_id,audio_url,track_number"
            + extra
            + " FROM songs ORDER BY id"
        )
    ]
    sources = current_sources(conn) if modern else {}
    artist_columns = {r[1] for r in conn.execute("PRAGMA table_info(artists)")}
    artist_rows = [
        dict(r)
        for r in conn.execute(
            "SELECT id,name"
            + (",cover_url" if "cover_url" in artist_columns else "")
            + " FROM artists ORDER BY id"
        )
    ]
    artists = {r["id"]: r["name"] for r in artist_rows}
    links = [
        tuple(r)
        for r in conn.execute(
            "SELECT song_id,artist_id FROM song_artists ORDER BY song_id,artist_id"
        )
    ]
    for song in songs:
        song["artists"] = [
            artists[a] for s, a in links if s == song["id"] and a in artists
        ]
        song["artist_ids"] = [
            a for sid, a in links if sid == song["id"] and a in artists
        ]
        if modern:
            song["source"] = sources.get(song["id"], {}).get("source", {})
    return {"albums": albums, "songs": songs, "artists": artist_rows}


def connection(filename, readonly=False):
    """Open an existing compatible relational database with row objects and foreign
    keys enabled.
    """
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError("Database does not exist; no new database was created.")
    conn = sqlite3.connect(
        path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=30
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    required = {
        "songs": {"id", "title", "album_id", "audio_url", "track_number"},
        "albums": {"id", "title", "cover_url", "release_date"},
    }
    for table, columns in required.items():
        if not columns <= {
            r["name"] for r in conn.execute(f"PRAGMA table_info({table})")
        }:
            conn.close()
            raise ValueError("Use the current relational Song Ranker database.")
    return conn


FIELD_LABELS = {
    "audio_url": "Preview URL",
    "cover_url": "Artwork URL",
    "title": "Title",
    "name": "Artist name",
    "release_date_origin": "Release-date source",
}


def media_url(value):
    """Accept only absolute HTTPS media values, excluding credentials and script URLs."""
    try:
        parsed = urlsplit(value or "")
        return (
            value
            if parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            else None
        )
    except (TypeError, ValueError):
        return None


def queue_field(plan, entity, row, field, value, evidence):
    """Queue one blank-only field; contradictory evidence removes the proposal."""
    if (
        field not in row
        or not blank(row[field])
        or not isinstance(value, str)
        or blank(value)
    ):
        return
    key = (entity, row["id"], field)
    if key in plan["field_conflicts"]:
        return
    previous = next(
        (r for r in plan["fills"] if (r["entity"], r["id"], r["field"]) == key), None
    )
    if previous:
        if previous["value"] != value and not (
            field == "cover_url" and same_art(previous["value"], value)
        ):
            plan["fills"].remove(previous)
            plan["field_conflicts"].add(key)
            plan["field_failures"].append(
                dict(
                    title=row.get("title") or row.get("name") or str(row["id"]),
                    reason="Conflicting "
                    + FIELD_LABELS[field].lower()
                    + " evidence; review manually.",
                )
            )
        return
    plan["fills"].append(
        dict(
            entity=entity,
            id=row["id"],
            title=row.get("title") or row.get("name") or str(row["id"]),
            field=field,
            label=FIELD_LABELS[field],
            value=value,
            evidence=evidence,
        )
    )


def matching_release(album, source):
    """Require an actual release-title match before using source album-level facts."""
    return bool(
        normalized(album["title"])
        and release_key(album["title"]) == release_key(source.get("album"))
    )


def propose_fields(plan, song, source, evidence):
    """Fill missing song media/identity and matching-release artwork without moving links."""
    metadata = source.get("metadata") or {}
    queue_field(
        plan, "songs", song, "audio_url", media_url(metadata.get("audio_url")), evidence
    )
    queue_field(plan, "songs", song, "title", source.get("title"), evidence)
    if not blank(song.get("release_date")) and song.get("release_date") == source.get(
        "release_date"
    ):
        queue_field(plan, "songs", song, "release_date_origin", "apple", evidence)
    album = next(
        (a for a in plan["snapshot"]["albums"] if a["id"] == song["album_id"]), None
    )
    if album and matching_release(effective_row(plan, "albums", album), source):
        queue_field(
            plan,
            "albums",
            album,
            "cover_url",
            media_url(metadata.get("cover_url")),
            evidence,
        )


def inventory(state):
    """Count blank writable catalogue fields and saved-source date recovery opportunities."""
    missing = {}
    for entity, fields in (
        (
            "songs",
            (
                "title",
                "audio_url",
                "track_number",
                "release_date",
                "release_date_origin",
            ),
        ),
        ("albums", ("title", "cover_url", "release_date")),
        ("artists", ("name", "cover_url")),
    ):
        for field in fields:
            missing[entity + "." + field] = sum(
                field in row and blank(row[field]) for row in state[entity]
            )
    return dict(
        totals={key: len(state[key]) for key in ("songs", "albums", "artists")},
        missing=missing,
        saved_dates=sum(
            blank(s.get("release_date"))
            and bool((s.get("source") or {}).get("release_date"))
            for s in state["songs"]
        ),
    )


def saved_facts(plan):
    """Recover exact linked facts offline before spending requests on unknown metadata."""
    state = plan["snapshot"]
    identities = Counter(
        identifier((s.get("source") or {}).get("track_id")) for s in state["songs"]
    )
    occupied = {
        (s["album_id"], s.get("disc_number", 1), s["track_number"])
        for s in state["songs"]
        if not blank(s["track_number"])
    }
    for song in state["songs"]:
        source = song.get("source") or {}
        key = identifier(source.get("track_id"))
        if not key or identities[key] != 1:
            continue
        evidence = "Saved Apple track " + key
        propose_fields(plan, song, source, evidence)
        if "release_date" in song and blank(song["release_date"]):
            try:
                value = release_date(
                    source.get("release_date")
                    or (source.get("metadata") or {}).get("release_date")
                )
            except ValueError:
                pass
            else:
                plan["song_dates"].append(
                    dict(
                        id=song["id"],
                        title=song["title"],
                        value=value,
                        evidence=evidence,
                    )
                )
        enriched = deepcopy(source)
        metadata = enriched.setdefault("metadata", {})
        for field in ("title", "artist", "album", "release_date"):
            if (
                blank(metadata.get(field))
                and isinstance(source.get(field), str)
                and not blank(source[field])
            ):
                metadata[field] = source[field]
            if (
                blank(enriched.get(field))
                and isinstance(metadata.get(field), str)
                and not blank(metadata[field])
            ):
                enriched[field] = metadata[field]
        store = source.get("storefront")
        if isinstance(store, str) and re.fullmatch("[a-z]{2}", store):
            for field, kind, identity in (
                ("track_url", "song", key),
                ("album_url", "album", identifier(source.get("collection_id"))),
            ):
                if identity and blank(enriched.get(field)):
                    enriched[field] = (
                        f"https://music.apple.com/{store}/{kind}/{identity}"
                    )
        if blank(metadata.get("track_number")) and not blank(
            metadata.get("source_track_number")
        ):
            try:
                number = parse_track_number(metadata["source_track_number"])
                disc = parse_track_number(metadata.get("disc_number"))
                count = parse_track_number(metadata.get("disc_count"))
                if not disc or not count or disc > count:
                    raise ValueError("Unverified disc")
            except (ValueError, TypeError):
                pass
            else:
                enriched["metadata"]["track_number"] = number
        if enriched != source:
            plan["sources"].append(
                dict(
                    id=song["id"],
                    title=song["title"],
                    source=enriched,
                    fields=[k for k in enriched if enriched[k] != source.get(k)],
                )
            )
        if blank(song["track_number"]):
            album = next(
                (a for a in state["albums"] if a["id"] == song["album_id"]), None
            )
            if not album or not matching_release(album, source):
                continue
            try:
                number = parse_track_number(
                    metadata.get("source_track_number") or metadata.get("track_number")
                )
                disc = parse_track_number(metadata.get("disc_number"))
                count = parse_track_number(metadata.get("disc_count"))
                if not number or not disc or not count or disc > count:
                    continue
                if song.get("disc_number", 1) > 1 and song["disc_number"] != disc:
                    continue
                position = (album["id"], disc, number)
                if position in occupied:
                    continue
            except (ValueError, TypeError):
                continue
            occupied.add(position)
            plan["tracks"].append(
                dict(
                    id=song["id"],
                    title=song["title"],
                    album_id=album["id"],
                    value=number,
                    disc_number=disc,
                    evidence=evidence,
                )
            )
    # Blank album/artist names require unanimous linked saved identities, never a fuzzy search.
    for entity, rows, field in (
        ("albums", state["albums"], "title"),
        ("artists", state["artists"], "name"),
    ):
        for row in rows:
            linked = (
                [s for s in state["songs"] if s["album_id"] == row["id"]]
                if entity == "albums"
                else [s for s in state["songs"] if row["id"] in s["artist_ids"]]
            )
            if entity == "artists" and any(len(s["artist_ids"]) != 1 for s in linked):
                continue
            sources = [s.get("source") or {} for s in linked]
            name_key, id_key = (
                ("album", "collection_id")
                if entity == "albums"
                else ("artist", "artist_id")
            )
            if not sources or any(
                not identifier(s.get(id_key)) or blank(s.get(name_key)) for s in sources
            ):
                continue
            if len({(s[id_key], normalized(s[name_key])) for s in sources}) != 1:
                continue
            queue_field(
                plan,
                entity,
                row,
                field,
                sources[0][name_key],
                "Unanimous saved Apple identity " + sources[0][id_key],
            )
    for song in state["songs"]:
        source = next(
            (r["source"] for r in plan["sources"] if r["id"] == song["id"]),
            song.get("source") or {},
        )
        key = identifier(source.get("track_id"))
        if key and identities[key] == 1:
            propose_fields(plan, song, source, "Saved Apple track " + key)


def effective_row(plan, entity, row):
    """Use already reviewed blank-name proposals for matching without mutating the snapshot."""
    return {
        **row,
        **{
            r["field"]: r["value"]
            for r in plan["fills"]
            if r["entity"] == entity and r["id"] == row["id"]
        },
    }


def artist_artwork(plan, lookup, cancelled):
    """Fill blank artist pictures only from exact artist responses, never album covers."""
    for original_artist in plan["snapshot"]["artists"]:
        artist = effective_row(plan, "artists", original_artist)
        if (
            "cover_url" not in artist
            or not blank(artist["cover_url"])
            or blank(artist["name"])
        ):
            continue
        linked = [
            s
            for s in plan["snapshot"]["songs"]
            if artist["id"] in s["artist_ids"] and len(s["artist_ids"]) == 1
        ]
        candidates = {
            s.get("source", {}).get("artist_id")
            for s in linked
            if normalized(s.get("source", {}).get("artist"))
            == normalized(artist["name"])
        }
        candidates.discard(None)
        if len(candidates) != 1:
            continue
        if cancelled():
            plan["stopped"] = "Scan cancelled."
            return
        key = next(iter(candidates))
        try:
            results = lookup(
                "https://itunes.apple.com/lookup?"
                + urlencode(dict(id=key, entity="musicArtist", country=plan["country"]))
            ).get("results", [])
            matches = [
                r
                for r in results
                if isinstance(r, dict)
                and r.get("wrapperType") == "artist"
                and str(r.get("artistId")) == key
                and normalized(r.get("artistName")) == normalized(artist["name"])
            ]
            if len(matches) == 1 and media_url(matches[0].get("artworkUrl100")):
                queue_field(
                    plan,
                    "artists",
                    original_artist,
                    "cover_url",
                    media_url(matches[0]["artworkUrl100"]),
                    "Verified Apple artist " + key,
                )
            else:
                plan["field_failures"].append(
                    dict(
                        title=artist["name"],
                        reason="Apple returned no uniquely verified artist artwork; no album cover was substituted.",
                    )
                )
        except (ValueError, ScanStopped) as error:
            plan["field_failures"].append(dict(title=artist["name"], reason=str(error)))
            if isinstance(error, ScanStopped):
                plan["stopped"] = str(error)
                return


def paced_lookup(url, cancelled=lambda: False):
    """Wait through local Apple throttling while honouring cancellation and stopping
    on upstream failures.
    """
    while True:
        if cancelled():
            raise ScanStopped("Scan cancelled.")
        try:
            return apple_lookup(url)
        except AppleRequestError as error:
            # Local spacing/window limits are expected. Remote errors stop the
            # batch; do not repeatedly retry a refusal or Apple's HTTP 429.
            if error.state != "throttled":
                raise ScanStopped(str(error)) from error
            until = time.monotonic() + max(1, error.retry_after)
            while time.monotonic() < until:
                if cancelled():
                    raise ScanStopped("Scan cancelled.")
                time.sleep(min(0.25, max(0, until - time.monotonic())))


def plan_metadata(
    filename,
    country="gb",
    lookup=paced_lookup,
    progress=lambda *a: None,
    cancelled=lambda: False,
):
    """Build a cancellable dry-run plan for missing catalogue metadata against a
    consistent snapshot.
    """
    if not re.fullmatch("[a-zA-Z]{2}", country):
        raise ValueError("Country must be a two-letter store code.")
    conn = connection(filename, True)
    try:
        conn.execute("BEGIN")
        original = snapshot(conn)
    finally:
        conn.close()
    plan = {
        "snapshot": original,
        "dates": [],
        "tracks": [],
        "track_failures": [],
        "country": country.lower(),
        "stopped": "",
        "applied": False,
        "backup": None,
        "song_dates": [],
        "sources": [],
        "metadata_failures": [],
        "fills": [],
        "field_failures": [],
        "field_conflicts": set(),
        "inventory": inventory(original),
    }
    saved_facts(plan)
    occupied = {
        (s["album_id"], s.get("disc_number", 1), s["track_number"])
        for s in original["songs"]
        if s["track_number"] is not None
    } | {(r["album_id"], r.get("disc_number", 1), r["value"]) for r in plan["tracks"]}
    stopped = ""
    for index, original_album in enumerate(original["albums"]):
        album = effective_row(plan, "albums", original_album)
        local = [s for s in original["songs"] if s["album_id"] == album["id"]]
        missing_tracks = [
            s
            for s in local
            if blank(s["track_number"])
            and not any(r["id"] == s["id"] for r in plan["tracks"])
        ]
        need_date = blank(album["release_date"])
        missing_metadata = [
            s
            for s in local
            if "release_date" in s
            and (
                (
                    blank(s["release_date"])
                    and not any(r["id"] == s["id"] for r in plan["song_dates"])
                )
                or missing_source(
                    next(
                        (r["source"] for r in plan["sources"] if r["id"] == s["id"]),
                        s.get("source"),
                    )
                )
                or (
                    blank(s["audio_url"])
                    and not any(
                        r["entity"] == "songs"
                        and r["id"] == s["id"]
                        and r["field"] == "audio_url"
                        for r in plan["fills"]
                    )
                )
            )
        ]
        single = normalized(album["title"]).endswith(" - single")
        date_row = {
            "id": album["id"],
            "title": album["title"],
            "value": album["release_date"],
            "status": "kept",
            "reason": "Existing date preserved.",
        }
        plan["dates"].append(date_row)
        failures = {}
        proposals = []
        if single:
            for song in missing_tracks:
                if len(local) != 1 or (album["id"], 1, 1) in occupied:
                    failures[song["id"]] = (
                        "Single has multiple tracks or track 1 is occupied."
                    )
                else:
                    proposals.append(
                        {
                            "id": song["id"],
                            "title": song["title"],
                            "album_id": album["id"],
                            "value": 1,
                            "disc_number": 1,
                        }
                    )
        try:
            if need_date or (missing_tracks and not single) or missing_metadata:
                if stopped or cancelled():
                    raise ScanStopped(stopped or "Scan cancelled.")
                if not normalized(album["title"]):
                    raise ValueError("Blank local album title; manual review needed.")
                if not local:
                    raise ValueError("No local tracks to verify this release.")
                known_sources = [s.get("source") or {} for s in local]
                known_ids = {
                    q["collection_id"]
                    for q in known_sources
                    if identifier(q.get("collection_id")) and matching_release(album, q)
                }
                known_id = next(iter(known_ids)) if len(known_ids) == 1 else None
                if not known_id and not artwork_key(album["cover_url"]):
                    raise ValueError(
                        "Artwork cannot be verified as an Apple asset; manual review needed."
                    )
                names = {
                    normalized(n)
                    for song in local
                    for n in song["artists"]
                    if normalized(n)
                }
                if known_id:
                    names |= {
                        normalized(q.get("artist"))
                        for q in known_sources
                        if q.get("collection_id") == known_id
                        and normalized(q.get("artist"))
                    }
                if not names:
                    raise ValueError("No local artist available for verification.")
                search_artist = next(
                    (n for song in local for n in song["artists"] if normalized(n)),
                    next(iter(names)),
                )
                term = (
                    (local[0]["title"] if single else release_key(album["title"]))
                    + " "
                    + search_artist
                )
                url = "https://itunes.apple.com/search?" + urlencode(
                    {
                        "term": term,
                        "country": country.lower(),
                        "media": "music",
                        "entity": "song" if single else "album",
                        "explicit": "Yes",
                        "limit": 200,
                    }
                )
                results = [] if known_id else lookup(url).get("results", [])
                candidates = []
                for row in results:
                    if not isinstance(row, dict):
                        continue
                    title = (
                        row.get("trackName") if single else row.get("collectionName")
                    )
                    expected = local[0]["title"] if single else album["title"]
                    if (
                        (
                            normalized(title) == normalized(expected)
                            if single
                            else release_key(title) == release_key(expected)
                        )
                        and normalized(row.get("artistName")) in names
                        and same_art(album["cover_url"], row.get("artworkUrl100"))
                        and isinstance(row.get("collectionId"), int)
                        and not isinstance(row.get("collectionId"), bool)
                        and row["collectionId"] > 0
                    ):
                        candidates.append(row)
                ids = {r["collectionId"] for r in candidates}
                if known_id:
                    ids = {int(known_id)}
                if len(ids) != 1:
                    raise ValueError(
                        "No unique title / artist / artwork match; manual review needed."
                    )
                collection_id = next(iter(ids))
                data = lookup(
                    "https://itunes.apple.com/lookup?"
                    + urlencode(
                        {
                            "id": collection_id,
                            "country": country.lower(),
                            "entity": "song",
                            "limit": 200,
                        }
                    )
                ).get("results", [])
                data = [r for r in data if isinstance(r, dict)]
                releases = [
                    r
                    for r in data
                    if r.get("wrapperType") == "collection"
                    and r.get("collectionId") == collection_id
                    and (
                        bool(known_id)
                        or same_art(album["cover_url"], r.get("artworkUrl100"))
                    )
                    and normalized(r.get("artistName")) in names
                    and (
                        single
                        or release_key(r.get("collectionName"))
                        == release_key(album["title"])
                    )
                ]
                if len(releases) != 1:
                    raise ValueError("Album lookup identity is missing or ambiguous.")
                source = releases[0]
                remote_tracks = [
                    r
                    for r in data
                    if r.get("wrapperType") == "track"
                    and r.get("kind") == "song"
                    and r.get("collectionId") == collection_id
                ]

                def matches(song):
                    """Find remote tracks matching the local song's title, artist,
                    release, artwork and saved identity.
                    """
                    return [
                        r
                        for r in remote_tracks
                        if (
                            str(r.get("trackId"))
                            == song.get("source", {}).get("track_id")
                            if song.get("source", {}).get("track_id")
                            else normalized(song["title"])
                            and normalized(r.get("trackName"))
                            == normalized(song["title"])
                        )
                        and (
                            normalized(r.get("artistName"))
                            in {normalized(n) for n in song["artists"]}
                            or (
                                bool(known_id)
                                and normalized(r.get("artistName"))
                                == normalized(song.get("source", {}).get("artist"))
                            )
                        )
                        and normalized(r.get("collectionName"))
                        == normalized(source.get("collectionName"))
                        and (
                            bool(known_id)
                            or same_art(album["cover_url"], r.get("artworkUrl100"))
                        )
                        and (
                            not song.get("source")
                            or str(r.get("trackId")) == song["source"]["track_id"]
                        )
                    ]

                # The release date is from the verified collection wrapper,
                # never guessed from the first song's original release date.
                if not any(len(matches(s)) == 1 for s in local):
                    raise ValueError(
                        "No uniquely verified local track in the album lookup."
                    )
                if need_date:
                    try:
                        date_row.update(
                            value=release_date(source.get("releaseDate")),
                            status="proposed",
                            reason="Verified Apple collection "
                            + str(collection_id)
                            + ": "
                            + str(source.get("collectionName")),
                        )
                    except ValueError as error:
                        date_row.update(value=None, status="failed", reason=str(error))
                queue_field(
                    plan,
                    "albums",
                    original_album,
                    "cover_url",
                    media_url(source.get("artworkUrl100")),
                    "Verified Apple collection " + str(collection_id),
                )
                for song in missing_metadata:
                    try:
                        matched = matches(song)
                        if len(matched) != 1:
                            raise ValueError(
                                "Track title / artist / artwork / source match is missing or ambiguous."
                            )
                        propose_song(plan, song, matched[0])
                    except ValueError as error:
                        plan["metadata_failures"].append(
                            dict(id=song["id"], title=song["title"], reason=str(error))
                        )
                if not single:
                    for song in missing_tracks:
                        matched = matches(song)
                        try:
                            if len(matched) != 1:
                                raise ValueError(
                                    "Track title / artist / artwork match is missing or ambiguous."
                                )
                            row = matched[0]
                            if (
                                type(row.get("discCount")) is not int
                                or row["discCount"] < 1
                                or type(row.get("discNumber")) is not int
                                or not 1 <= row["discNumber"] <= row["discCount"]
                                or ("disc_number" not in song and row["discCount"] != 1)
                            ):
                                raise ValueError(
                                    "Multi-disc or missing disc metadata; no position guessed."
                                )
                            if (
                                song.get("disc_number", 1) > 1
                                and song["disc_number"] != row["discNumber"]
                            ):
                                raise ValueError(
                                    "Saved disc differs from Apple; review the position manually."
                                )
                            number = parse_track_number(row.get("trackNumber"))
                            count = parse_track_number(row.get("trackCount"))
                            if number is None or count is None or number > count:
                                raise ValueError(
                                    "Invalid or missing Apple track position / count."
                                )
                            proposals.append(
                                {
                                    "id": song["id"],
                                    "title": song["title"],
                                    "album_id": album["id"],
                                    "value": number,
                                    "disc_number": row["discNumber"],
                                }
                            )
                        except ValueError as error:
                            failures[song["id"]] = str(error)
        except (ValueError, ScanStopped) as error:
            if isinstance(error, ScanStopped):
                stopped = str(error)
                plan["stopped"] = stopped
            if need_date:
                date_row.update(value=None, status="failed", reason=str(error))
            for song in missing_metadata:
                plan["metadata_failures"].append(
                    dict(id=song["id"], title=song["title"], reason=str(error))
                )
            if not single:
                for song in missing_tracks:
                    failures[song["id"]] = str(error)
        counts = Counter((p["disc_number"], p["value"]) for p in proposals)
        for proposal in proposals:
            if (
                counts[(proposal["disc_number"], proposal["value"])] > 1
                or (album["id"], proposal["disc_number"], proposal["value"]) in occupied
            ):
                failures[proposal["id"]] = (
                    "Track position is duplicated or already occupied locally."
                )
            else:
                plan["tracks"].append(proposal)
                occupied.add((album["id"], proposal["disc_number"], proposal["value"]))
        for song in missing_tracks:
            if song["id"] in failures:
                plan["track_failures"].append(
                    {
                        "id": song["id"],
                        "title": song["title"],
                        "album": album["title"],
                        "reason": failures[song["id"]],
                    }
                )
        progress(index + 1, len(original["albums"]), album["title"])
    for song in original["songs"]:
        if (
            song["album_id"] not in {a["id"] for a in original["albums"]}
            and "release_date" in song
            and (blank(song["release_date"]) or missing_source(song.get("source")))
        ):
            plan["metadata_failures"].append(
                dict(
                    id=song["id"],
                    title=song["title"],
                    reason="No linked album to verify; local links kept.",
                )
            )
        if song["album_id"] not in {a["id"] for a in original["albums"]} and blank(
            song["track_number"]
        ):
            plan["track_failures"].append(
                {
                    "id": song["id"],
                    "title": song["title"],
                    "album": "No album",
                    "reason": "Missing or unlinked album; track position cannot be verified.",
                }
            )
    if not plan["stopped"]:
        artist_artwork(plan, lookup, cancelled)
    return plan


def apply_plan(filename, plan):
    """Recheck identity and blanks under a write lock. All updates are atomic."""
    if plan["applied"]:
        raise ValueError("This scan has already been applied.")
    conn = connection(filename)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if snapshot(conn) != plan["snapshot"]:
            raise ValueError(
                "Library metadata changed since the scan. Scan again; nothing was written."
            )
        for track in plan["tracks"]:
            number = parse_track_number(track["value"])
            if number is None:
                raise ValueError("A proposed track position is blank.")
            check_track_position(
                conn,
                track["album_id"],
                number,
                track["id"],
                track.get("disc_number", 1),
            )
        for row in plan.get("sources", []):
            conflict = source_conflict(conn, row["id"], row["source"])
            if conflict:
                raise ValueError(
                    "An Apple identity is already linked to another song. Scan again."
                )
        modern_discs = "disc_number" in {
            r[1] for r in conn.execute("PRAGMA table_info(songs)")
        }
        for track in plan["tracks"]:
            if modern_discs:
                conn.execute(
                    "UPDATE songs SET disc_number=?,track_number=? WHERE id=? AND (track_number IS NULL OR TRIM(track_number)='')",
                    (track.get("disc_number", 1), track["value"], track["id"]),
                )
                continue
            conn.execute(
                "UPDATE songs SET track_number=? WHERE id=? AND (track_number IS NULL OR TRIM(track_number)='')",
                (track["value"], track["id"]),
            )
        for row in plan["dates"]:
            if row["status"] == "proposed":
                value = release_date(row["value"])
                conn.execute(
                    "UPDATE albums SET release_date=? WHERE id=? AND (release_date IS NULL OR TRIM(release_date)='')",
                    (value, row["id"]),
                )
        for row in plan.get("song_dates", []):
            value = release_date(row["value"])
            conn.execute(
                "UPDATE songs SET release_date=?,release_date_origin=CASE WHEN release_date_origin IS NULL OR TRIM(release_date_origin)='' THEN 'apple' ELSE release_date_origin END WHERE id=? AND (release_date IS NULL OR TRIM(release_date)='')",
                (value, row["id"]),
            )
        for row in plan.get("sources", []):
            save_source(
                conn, row["id"], dict(source=row["source"], observed_at=time.time())
            )
        allowed = {
            "songs": {"title", "audio_url", "release_date_origin"},
            "albums": {"title", "cover_url"},
            "artists": {"name", "cover_url"},
        }
        for row in plan.get("fills", []):
            entity, field = row["entity"], row["field"]
            if field not in allowed.get(entity, set()):
                raise ValueError("Unsupported metadata field.")
            conn.execute(
                f"UPDATE {entity} SET {field}=? WHERE id=? AND ({field} IS NULL OR TRIM({field})='')",
                (row["value"], row["id"]),
            )
        counts = inventory(snapshot(conn))
        conn.commit()
        plan["applied"] = True
        plan["inventory"] = counts
        plan["backup"] = None  # Routine edits do not create backups.
        for row in plan["dates"]:
            if row["status"] == "proposed":
                row["status"] = "filled"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return plan


def text_report(plan):
    """Format metadata proposals, failures, backup and apply status as a downloadable
    report.
    """
    lines = [
        "SONG RANKER — METADATA FILL",
        "Applied" if plan["applied"] else "Dry run — no metadata written",
        "Track numbers "
        + ("filled: " if plan["applied"] else "proposed: ")
        + str(len(plan["tracks"])),
        "Track failures: " + str(len(plan["track_failures"])),
    ]
    lines += [
        "Song release dates: " + str(len(plan.get("song_dates", []))),
        "Apple source updates: " + str(len(plan.get("sources", []))),
        "Song metadata failures: " + str(len(plan.get("metadata_failures", []))),
    ]
    if plan["backup"]:
        lines.append("Backup: " + plan["backup"])
    if plan["stopped"]:
        lines.append("Search stopped: " + plan["stopped"])
    lines += ["", "OTHER BLANK FIELDS — no song tags"]
    lines += [
        f"{r['entity']} #{r['id']} {r['title']} | {r['label']}: {r['value']} | {r['evidence']}"
        for r in plan.get("fills", [])
    ]
    lines += [
        f"[UNRESOLVED] {r['title']} | {r['reason']}"
        for r in plan.get("field_failures", [])
    ]
    lines += ["", "RELEASE DATES — every album"]
    for row in plan["dates"]:
        lines.append(
            f"[{row['status'].upper()}] Album #{row['id']} {row['title']} | {row['value'] or 'blank'} | {row['reason']}"
        )
    lines += ["", "DISC / TRACK POSITIONS"]
    lines += [
        f"Song #{r['id']} {r['title']} | Disc {r.get('disc_number', 1)} · Track {r['value']}"
        for r in plan["tracks"]
    ]
    lines += ["", "TRACK NUMBER FAILURES ONLY"]
    lines += [
        f"[FAILED] Song #{r['id']} {r['title']} | {r['album']} | {r['reason']}"
        for r in plan["track_failures"]
    ]
    if not plan["track_failures"]:
        lines.append("None.")
    lines += ["", "SONG RELEASE DATES"]
    lines += [
        f"Song #{r['id']} {r['title']} | {r['value']} | Apple track date"
        for r in plan.get("song_dates", [])
    ]
    lines += [
        "",
        "APPLE SOURCE FACTS — local artwork, placement, tags and previews kept",
    ]
    lines += [
        f"Song #{r['id']} {r['title']} | Apple {r['source']['track_id']} | {source_label(r['source'])} | {', '.join(r['fields'])}"
        for r in plan.get("sources", [])
    ]
    lines += ["", "SONG METADATA FAILURES"]
    lines += [
        f"Song #{r['id']} {r['title']} | {r['reason']}"
        for r in plan.get("metadata_failures", [])
    ]
    return "\n".join(lines) + "\n"


# Authenticated, single-job developer metadata scan and report endpoints.


_lock = Lock()
_job = None


def public(job):
    """Expose scan progress and reviewable changes without publishing internal job
    state.
    """
    plan = job.get("plan")
    return {
        "token": job["token"],
        "state": job["state"],
        "done": job["done"],
        "total": job["total"],
        "album": job["album"],
        "error": job.get("error", ""),
        "tracks": len(plan["tracks"]) if plan else 0,
        "dates": sum(d["status"] == "proposed" for d in plan["dates"]) if plan else 0,
        "song_dates": len(plan.get("song_dates", [])) if plan else 0,
        "sources": len(plan.get("sources", [])) if plan else 0,
        "fields": len(plan.get("fills", [])) if plan else 0,
        "field_changes": plan.get("fills", []) if plan else [],
        "field_failures": plan.get("field_failures", []) if plan else [],
        "track_changes": plan.get("tracks", []) if plan else [],
        "inventory": plan.get("inventory", {}) if plan else {},
        "metadata_failures": len(plan.get("metadata_failures", [])) if plan else 0,
        "song_date_changes": plan.get("song_dates", []) if plan else [],
        "source_changes": (
            [
                dict(
                    id=r["id"],
                    title=r["title"],
                    fields=r["fields"],
                    content_label=source_label(r["source"]),
                )
                for r in plan.get("sources", [])
            ]
            if plan
            else []
        ),
        "track_failures": len(plan["track_failures"]) if plan else 0,
        "date_failures": (
            sum(d["status"] == "failed" for d in plan["dates"]) if plan else 0
        ),
        "stopped": plan["stopped"] if plan else "",
        "date_changes": (
            [d for d in plan["dates"] if d["status"] in ("proposed", "filled")]
            if plan
            else []
        ),
        "failures": plan["track_failures"] if plan else [],
    }


def run_scan(job, country):
    """Run a metadata plan in the background and publish its ready or error state
    under the job lock.
    """

    def progress(done, total, album):
        """Update completed-count and album progress safely for the background
        metadata job.
        """
        with _lock:
            job.update(done=done, total=total, album=album)

    try:
        plan = plan_metadata(
            DB_NAME,
            country,
            lookup=lambda url: paced_lookup(url, job["cancel"].is_set),
            progress=progress,
            cancelled=job["cancel"].is_set,
        )
        with _lock:
            job.update(plan=plan, state="ready")
    except Exception as error:
        app.logger.exception("Metadata scan failed")
        with _lock:
            job.update(error=str(error), state="error")


@app.route("/api/dev/metadata", methods=["GET", "POST"])
@admin_required
def metadata_scan():
    global _job
    with _lock:
        if request.method == "POST":
            if _job and _job["state"] in ("scanning", "applying"):
                return jsonify(message="A metadata task is already running."), 409
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify(message="Send a metadata task as an object."), 400
            country = data.get("country", "gb")
            if (
                not isinstance(country, str)
                or len(country) != 2
                or not country.isascii()
                or not country.isalpha()
            ):
                return jsonify(message="Choose a two-letter Apple store code."), 400
            _job = {
                "token": token_urlsafe(24),
                "state": "scanning",
                "done": 0,
                "total": 0,
                "album": "",
                "cancel": Event(),
                "plan": None,
                "error": "",
            }
            Thread(target=run_scan, args=(_job, country.lower()), daemon=True).start()
        if _job:
            return jsonify(public(_job))
        try:
            conn = connection(DB_NAME, True)
            try:
                counts = inventory(snapshot(conn))
            finally:
                conn.close()
        except (ValueError, OSError, sqlite3.Error):
            counts = {}
        return jsonify(state="idle", inventory=counts)


@app.route("/api/dev/metadata/<token>/cancel", methods=["POST"])
@admin_required
def cancel_scan(token):
    with _lock:
        if not _job or token != _job["token"]:
            return jsonify(message="Scan not found."), 404
        if _job["state"] == "scanning":
            _job["cancel"].set()
        return jsonify(public(_job))


@app.route("/api/dev/metadata/<token>/apply", methods=["POST"])
@admin_required
def apply_scan(token):
    with _lock:
        if not _job or token != _job["token"]:
            return jsonify(message="Scan not found."), 404
        if _job["state"] != "ready":
            return (
                jsonify(message="Only a completed, unapplied scan can be applied."),
                409,
            )
        _job["state"] = "applying"
        job = _job
    try:
        apply_plan(DB_NAME, job["plan"])
    except Exception as error:
        with _lock:
            job.update(state="ready", error=str(error))
        return jsonify(message=str(error)), 409
    with _lock:
        job.update(state="applied", error="")
        return jsonify(public(job))


@app.route("/api/dev/metadata/<token>/report")
@admin_required
def scan_report(token):
    with _lock:
        if not _job or token != _job["token"]:
            return jsonify(message="Scan not found."), 404
        if _job["state"] in ("scanning", "applying"):
            return jsonify(message="Wait for the task to finish."), 409
        report = (
            text_report(_job["plan"])
            if _job["plan"]
            else "METADATA SCAN FAILED\n" + _job["error"] + "\nNo metadata written.\n"
        )
        if _job["plan"] and _job["error"]:
            report += "\nAPPLY ERROR: " + _job["error"] + "\n"
    return Response(
        report,
        content_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="metadata_fill_report.txt"',
            "Cache-Control": "no-store",
        },
    )
