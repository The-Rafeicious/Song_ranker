"""Fill-only schema-13 metadata: mocked Apple, real backup and atomic writes."""

from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import json
import sqlite3
import unittest

import test_preferences as fixture
from songranker import services
from songranker.developer import metadata as fill
from songranker.developer import metadata as metadata_tools
from songranker.developer.catalog_sources import (
    observation,
    save_source,
    current_source,
    public_source,
)
from songranker.storage.source_storage import unpack_source
from songranker.storage.database_io import capture, readonly

ART = "https://is1-ssl.mzstatic.com/image/thumb/Music126/v4/ab/12/long-unique-metadata-asset/100x100bb.jpg"


class MetadataFillTests(unittest.TestCase):
    connect = fixture.PreferenceTests.connect
    scalar = fixture.PreferenceTests.scalar

    def setUp(self):
        fixture.PreferenceTests.setUp(self)
        self.conn.execute("DELETE FROM song_artists WHERE song_id>2")
        self.conn.execute("DELETE FROM song_genres WHERE song_id>2")
        self.conn.execute("DELETE FROM songs WHERE id>2")
        self.conn.execute("DELETE FROM albums WHERE id=2")
        self.conn.execute(
            "UPDATE albums SET cover_url=?,release_date=NULL",
            (ART.replace("100x100bb", "600x600bb"),),
        )
        self.conn.execute("UPDATE songs SET track_number=NULL,release_date=NULL")
        self.conn.commit()
        self.calls = []
        self.remote_title = "Album"
        self.flags = {}

    def tracks(self):
        return [
            {
                **dict(
                    wrapperType="track",
                    kind="song",
                    trackId=9000 + i,
                    artistId=7001,
                    collectionId=8001,
                    trackName="Song " + str(i),
                    artistName="Artist, One",
                    collectionName=self.remote_title,
                    artworkUrl100=ART,
                    previewUrl="different remote preview",
                    trackViewUrl=f"https://music.apple.com/gb/album/8001?i={9000+i}",
                    collectionViewUrl="https://music.apple.com/gb/album/8001",
                    releaseDate=f"201{i}-02-03T00:00:00Z",
                    trackTimeMillis=210000,
                    trackNumber=i,
                    trackCount=2,
                    discCount=1,
                    discNumber=1,
                    primaryGenreName="Remote genre",
                ),
                **self.flags,
            }
            for i in (1, 2)
        ]

    def collection(self):
        return dict(
            wrapperType="collection",
            collectionId=8001,
            collectionName=self.remote_title,
            artistName="Artist, One",
            artworkUrl100=ART,
            releaseDate="2021-04-05T00:00:00Z",
        )

    def lookup(self, url):
        self.calls.append(url)
        params = parse_qs(urlsplit(url).query)
        if "/search" in url:
            return {
                "results": (
                    self.tracks()
                    if params["entity"] == ["song"]
                    else [self.collection()]
                )
            }
        return {"results": [self.collection(), *self.tracks()]}

    def plan(self):
        return fill.plan_metadata(self.path, lookup=self.lookup)

    def seed_saved_facts(self):
        """Seed complete linked observations so offline fills need no remote search."""
        self.conn.execute("UPDATE albums SET release_date='2021-04-05'")
        self.conn.execute(
            "UPDATE artists SET cover_url='https://example.test/preferred-artist.jpg'"
        )
        self.conn.execute(
            "UPDATE songs SET track_number=id,release_date='2000-01-01',release_date_origin='manual'"
        )
        for row in self.tracks():
            row.update(
                previewUrl="https://audio.example.test/" + str(row["trackId"]) + ".m4a",
                trackCensoredName=row["trackName"],
                collectionExplicitness="explicit",
                trackExplicitness="explicit",
            )
            save_source(
                self.conn,
                row["trackNumber"],
                dict(source=observation(row, "gb"), observed_at=1),
            )
        self.conn.commit()

    def test_saved_dates_positions_and_previews_fill_offline_without_touching_tags(
        self,
    ):
        self.seed_saved_facts()
        self.conn.execute(
            "UPDATE songs SET track_number=NULL,release_date=NULL,release_date_origin=NULL,audio_url='' WHERE id=1"
        )
        self.conn.commit()
        before = capture(self.conn)
        p = fill.plan_metadata(
            self.path, lookup=lambda url: self.fail("Unnecessary online lookup " + url)
        )
        self.assertEqual(capture(self.conn), before)
        self.assertEqual(p["song_dates"][0]["value"], "2011-02-03")
        self.assertEqual(p["tracks"][0]["value"], 1)
        self.assertEqual(p["fills"][0]["field"], "audio_url")
        self.assertEqual(p["inventory"]["saved_dates"], 1)
        fill.apply_plan(self.path, p)
        self.assertEqual(
            tuple(
                self.conn.execute(
                    "SELECT audio_url,track_number,release_date FROM songs WHERE id=1"
                ).fetchone()
            ),
            ("https://audio.example.test/9001.m4a", 1, "2011-02-03"),
        )
        self.assertEqual(p["inventory"]["missing"]["songs.release_date"], 0)
        after = capture(self.conn)
        for name in (
            "genres",
            "song_genres",
            "song_artists",
            "preference_events",
            "album_shelf_items",
        ):
            self.assertEqual(before["tables"][name], after["tables"][name], name)
        again = fill.plan_metadata(self.path, lookup=lambda url: self.fail(url))
        self.assertEqual(
            (again["song_dates"], again["tracks"], again["fills"]), ([], [], [])
        )

    def test_filling_a_date_preserves_existing_origin(self):
        self.seed_saved_facts()
        self.conn.execute("UPDATE songs SET release_date=NULL WHERE id=1")
        self.conn.commit()
        p = fill.plan_metadata(self.path, lookup=lambda url: self.fail(url))
        fill.apply_plan(self.path, p)
        self.assertEqual(
            self.conn.execute(
                "SELECT release_date_origin FROM songs WHERE id=1"
            ).fetchone()[0],
            "manual",
        )

    def test_saved_identity_finds_album_date_despite_preferred_artwork(self):
        self.seed_saved_facts()
        self.conn.execute(
            "UPDATE albums SET release_date=NULL,cover_url='https://example.test/preferred-cover.jpg'"
        )
        self.conn.commit()
        p = self.plan()
        self.assertEqual(p["dates"][0]["value"], "2021-04-05")
        self.assertFalse(any("/search?" in url for url in self.calls))
        fill.apply_plan(self.path, p)
        self.assertEqual(
            self.scalar("SELECT cover_url FROM albums"),
            "https://example.test/preferred-cover.jpg",
        )

    def test_blank_names_and_artwork_use_verified_identities_and_artist_images(self):
        self.seed_saved_facts()
        self.conn.execute("UPDATE songs SET title='' WHERE id=1")
        self.conn.execute("UPDATE albums SET title='',cover_url=NULL")
        self.conn.execute("UPDATE artists SET name='',cover_url=NULL")
        self.conn.commit()

        def lookup(url):
            if parse_qs(urlsplit(url).query).get("entity") == ["musicArtist"]:
                return {
                    "results": [
                        dict(
                            wrapperType="artist",
                            artistId=7001,
                            artistName="Artist, One",
                            artworkUrl100="https://example.test/artist-portrait.jpg",
                        )
                    ]
                }
            self.fail("Unnecessary album search " + url)

        p = fill.plan_metadata(self.path, lookup=lookup)
        targets = {(r["entity"], r["field"]) for r in p["fills"]}
        self.assertTrue(
            {
                ("songs", "title"),
                ("albums", "title"),
                ("albums", "cover_url"),
                ("artists", "name"),
                ("artists", "cover_url"),
            }
            <= targets
        )
        fill.apply_plan(self.path, p)
        self.assertEqual(self.scalar("SELECT title FROM albums"), "Album")
        self.assertEqual(
            self.scalar("SELECT cover_url FROM artists"),
            "https://example.test/artist-portrait.jpg",
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM song_genres"), 2)

    def test_new_artwork_target_changes_invalidate_the_whole_plan(self):
        self.seed_saved_facts()
        self.conn.execute("UPDATE albums SET cover_url=NULL")
        self.conn.commit()
        p = fill.plan_metadata(self.path, lookup=lambda url: self.fail(url))
        self.conn.execute(
            "UPDATE artists SET cover_url='https://example.test/new-choice.jpg'"
        )
        self.conn.commit()
        before = capture(self.conn)
        with self.assertRaisesRegex(ValueError, "changed since"):
            fill.apply_plan(self.path, p)
        self.assertEqual(capture(self.conn), before)

    def test_conflicting_artwork_and_unsafe_media_are_not_proposed(self):
        self.seed_saved_facts()
        self.conn.execute("UPDATE albums SET cover_url=NULL")
        self.conn.commit()
        source = current_source(self.conn, 2)["source"]
        source["metadata"]["cover_url"] = "https://example.test/different-cover.jpg"
        save_source(self.conn, 2, dict(source=source, observed_at=2))
        self.conn.commit()
        p = fill.plan_metadata(self.path, lookup=lambda url: self.fail(url))
        self.assertFalse(
            any(
                r["entity"] == "albums" and r["field"] == "cover_url"
                for r in p["fills"]
            )
        )
        self.assertTrue(p["field_failures"])
        for value in (
            "javascript:alert(1)",
            "https://user:secret@example.test/image.jpg",
            "/relative.jpg",
            "http://example.test/image.jpg",
        ):
            self.assertIsNone(fill.media_url(value))

    def test_song_dates_are_exact_track_dates_and_dry_run_is_read_only(self):
        before = capture(self.conn)
        p = self.plan()
        self.assertEqual(capture(self.conn), before)
        self.assertEqual(
            [r["value"] for r in p["song_dates"]], ["2011-02-03", "2012-02-03"]
        )
        self.assertEqual(p["dates"][0]["value"], "2021-04-05")
        self.assertEqual(len(p["sources"]), 2)
        self.assertEqual(len(p["tracks"]), 2)
        self.assertEqual(parse_qs(urlsplit(self.calls[0]).query)["explicit"], ["Yes"])
        self.assertIn("SONG RELEASE DATES", fill.text_report(p))
        self.assertFalse(p["applied"])
        self.assertFalse((self.path.parent / "database_backups").exists())

    def test_fill_does_not_create_backups_and_only_target_fields_change(self):
        before = capture(self.conn)
        p = self.plan()
        fill.apply_plan(self.path, p)
        self.assertIsNone(p["backup"])
        self.assertFalse((self.path.parent / "database_backups").exists())
        after = capture(self.conn)
        for name, data in before["tables"].items():
            if name not in ("songs", "albums", "song_sources"):
                self.assertEqual(after["tables"][name], data, name)
        for table, allowed in [
            ("songs", {"track_number", "release_date", "release_date_origin"}),
            ("albums", {"release_date"}),
        ]:
            columns = before["tables"][table]["columns"]
            for old, new in zip(
                before["tables"][table]["rows"], after["tables"][table]["rows"]
            ):
                for i, column in enumerate(columns):
                    if column not in allowed:
                        self.assertEqual(old[i], new[i], table + "." + column)
        self.assertEqual(
            tuple(
                self.conn.execute(
                    "SELECT release_date,release_date_origin FROM songs WHERE id=1"
                ).fetchone()
            ),
            ("2011-02-03", "apple"),
        )
        source = current_source(self.conn, 1)["source"]
        self.assertEqual(source["duration_ms"], 210000)
        self.assertEqual(source["metadata"]["disc_number"], 1)
        self.assertEqual(public_source(source)["content_label"], "Not explicit")
        self.assertTrue(public_source(source)["content_assumed"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM genres"), 1)
        self.assertTrue(p["applied"])
        self.assertEqual(p["dates"][0]["status"], "filled")
        with self.assertRaisesRegex(ValueError, "already been applied"):
            fill.apply_plan(self.path, p)

    def test_second_scan_is_noop_and_does_not_create_another_backup(self):
        fill.apply_plan(self.path, self.plan())
        before = capture(self.conn)
        p = self.plan()
        self.assertEqual((p["tracks"], p["song_dates"], p["sources"]), ([], [], []))
        fill.apply_plan(self.path, p)
        self.assertIsNone(p["backup"])
        self.assertEqual(capture(self.conn), before)

    def test_known_dates_positions_and_source_facts_are_preserved(self):
        old = observation(self.tracks()[0], "gb")
        old.update(explicitness="cleaned", release_date="", duration_ms=None)
        old["metadata"]["audio_url"] = "saved source preview"
        old["metadata"]["cover_url"] = "saved source art"
        save_source(self.conn, 1, dict(source=old, observed_at=1))
        self.conn.execute(
            "UPDATE songs SET release_date='2000-01-01',release_date_origin='manual',track_number=7 WHERE id=1"
        )
        self.conn.execute("UPDATE albums SET release_date='2001-01-01'")
        self.conn.commit()
        self.flags = {"trackExplicitness": "explicit"}
        p = self.plan()
        fill.apply_plan(self.path, p)
        self.assertEqual(
            tuple(
                self.conn.execute(
                    "SELECT release_date,release_date_origin,track_number FROM songs WHERE id=1"
                ).fetchone()
            ),
            ("2000-01-01", "manual", 7),
        )
        self.assertEqual(self.scalar("SELECT release_date FROM albums"), "2001-01-01")
        new = current_source(self.conn, 1)["source"]
        self.assertEqual(new["explicitness"], "cleaned")
        self.assertEqual(new["metadata"]["audio_url"], "saved source preview")
        self.assertEqual(new["metadata"]["cover_url"], "saved source art")
        original = unpack_source(
            self.conn.execute(
                "SELECT snapshot FROM song_sources WHERE song_id=1"
            ).fetchone()[0]
        )
        self.assertEqual(original, new)
        self.assertEqual(new["duration_ms"], 210000)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM song_sources WHERE song_id=1"), 1
        )

    def test_suffix_matching_both_directions_does_not_strip_editions(self):
        for local, remote in [
            ("Album", "Album - EP"),
            ("Album - EP", "Album"),
            ("Album", "Album - Single"),
            ("Album - Single", "Album"),
        ]:
            self.conn.execute("UPDATE albums SET title=?", (local,))
            self.conn.commit()
            self.remote_title = remote
            p = self.plan()
            self.assertEqual(len(p["song_dates"]), 2, (local, remote))
            self.assertEqual(p["dates"][0]["status"], "proposed")
        self.conn.execute("UPDATE albums SET title='Album'")
        self.conn.commit()
        self.remote_title = "Album (Deluxe)"
        p = self.plan()
        self.assertEqual(p["song_dates"], [])
        self.assertEqual(p["dates"][0]["status"], "failed")

    def test_artist_artwork_and_ambiguous_releases_still_require_review(self):
        for field, value in [
            ("artistName", "Wrong Artist"),
            ("artworkUrl100", ART.replace("long-unique", "other-unique")),
        ]:
            original = self.collection
            with patch.object(
                self, "collection", return_value={**original(), field: value}
            ):
                p = self.plan()
                self.assertEqual(p["song_dates"], [])
                self.assertEqual(p["sources"], [])

        def ambiguous(url):
            return {
                "results": [
                    self.collection(),
                    {**self.collection(), "collectionId": 8002},
                ]
            }

        p = fill.plan_metadata(self.path, lookup=ambiguous)
        self.assertEqual(p["dates"][0]["status"], "failed")
        self.assertEqual(p["song_dates"], [])

    def test_wrong_saved_track_identity_is_never_relinked(self):
        source = observation({**self.tracks()[0], "trackId": 9999}, "gb")
        save_source(self.conn, 1, dict(source=source, observed_at=1))
        self.conn.commit()
        p = self.plan()
        self.assertFalse(
            any(
                r["id"] == 1 and r["source"]["track_id"] != "9999" for r in p["sources"]
            )
        )
        self.assertTrue(
            any(
                r["id"] == 1 and r["evidence"].startswith("Saved Apple track 9999")
                for r in p["song_dates"]
            )
        )
        fill.apply_plan(self.path, p)
        self.assertEqual(current_source(self.conn, 1)["source"]["track_id"], "9999")

    def test_stale_date_or_source_change_rejects_without_backup(self):
        p = self.plan()
        self.conn.execute("UPDATE songs SET release_date='2000-01-01' WHERE id=1")
        self.conn.commit()
        before = capture(self.conn)
        with self.assertRaisesRegex(ValueError, "changed since"):
            fill.apply_plan(self.path, p)
        self.assertEqual(capture(self.conn), before)
        self.assertIsNone(p["backup"])
        p = self.plan()
        save_source(
            self.conn,
            2,
            dict(source=observation(self.tracks()[1], "gb"), observed_at=1),
        )
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, "changed since"):
            fill.apply_plan(self.path, p)

    def test_source_write_failure_rolls_back_all_fills_without_automatic_backup(self):
        before = capture(self.conn)
        p = self.plan()
        real = fill.save_source
        calls = []

        def failing(*args):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("second source failed")
            return real(*args)

        with patch.object(fill, "save_source", side_effect=failing):
            with self.assertRaisesRegex(RuntimeError, "second source failed"):
                fill.apply_plan(self.path, p)
        self.assertEqual(capture(self.conn), before)
        self.assertFalse(p["applied"])
        backups = list((self.path.parent / "database_backups").glob("*.db"))
        self.assertEqual(len(backups), 0)
        self.assertEqual(capture(self.conn), before)

    def test_explicit_cleaned_and_unmarked_defaults(self):
        for flag, label in [
            ("explicit", "Explicit"),
            ("cleaned", "Cleaned"),
            ("notExplicit", "Not explicit"),
            (None, "Not explicit"),
        ]:
            self.flags = {"trackExplicitness": flag}
            p = self.plan()
            self.assertTrue(
                all(
                    public_source(r["source"])["content_label"] == label
                    for r in p["sources"]
                )
            )
            self.assertEqual(
                public_source(p["sources"][0]["source"])["content_assumed"],
                flag is None,
            )

    def test_multidisc_fills_verified_disc_track_pairs_and_source(self):
        self.flags = {"discCount": 2, "discNumber": 2}
        p = self.plan()
        self.assertEqual(len(p["tracks"]), 2)
        self.assertEqual(p["track_failures"], [])
        fill.apply_plan(self.path, p)
        self.assertEqual(
            [
                tuple(r)
                for r in self.conn.execute(
                    "SELECT disc_number,track_number FROM songs ORDER BY id"
                )
            ],
            [(2, 1), (2, 2)],
        )
        self.assertEqual(len(p["song_dates"]), 2)
        self.assertEqual(len(p["sources"]), 2)
        self.assertEqual(p["sources"][0]["source"]["metadata"]["disc_number"], 2)

    def test_completed_scan_endpoint_exposes_new_counts_and_keeps_private_plan_server_side(
        self,
    ):
        p = self.plan()
        job = dict(
            token="metadata-test-token",
            state="ready",
            done=1,
            total=1,
            album="Album",
            plan=p,
        )
        client = services.app.test_client()
        self.assertEqual(client.get("/api/dev/metadata").status_code, 302)
        with client.session_transaction() as session:
            session["is_admin"] = True
        with patch.object(metadata_tools, "_job", job), patch.object(
            metadata_tools, "DB_NAME", str(self.path)
        ):
            r = client.get("/api/dev/metadata")
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json["song_dates"], r.json["sources"]), (2, 2))
            self.assertNotIn("snapshot", r.json)
            self.assertNotIn("source", r.json["source_changes"][0])
            applied = client.post(
                "/api/dev/metadata/metadata-test-token/apply", json={}
            )
            self.assertEqual(applied.status_code, 200, applied.json)
            self.assertEqual(applied.json["state"], "applied")
            report = client.get("/api/dev/metadata/metadata-test-token/report")
            self.assertIn("2011-02-03", report.get_data(as_text=True))
            self.assertIn("Apple source updates: 2", report.get_data(as_text=True))
            self.assertEqual(
                client.post(
                    "/api/dev/metadata/metadata-test-token/apply", json={}
                ).status_code,
                409,
            )


if __name__ == "__main__":
    unittest.main()
