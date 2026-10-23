"""Disposable served Dev and Chromium integration fixtures; no startup Git sync."""

import argparse
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_dev():
    """Run served Dev DOM checks against a disposable local fixture server."""
    with tempfile.TemporaryDirectory(prefix=".dev_check_", dir=ROOT) as folder:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, SONG_RANKER_QA_URL=f"http://127.0.0.1:{port}")
        server = subprocess.Popen(
            [
                sys.executable,
                __file__,
                "--serve-dev",
                str(Path(folder) / "test.db"),
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Fixture server stopped before validation.")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Fixture server could not start.")
            return subprocess.run(
                ["node", "tests/test_dev_pages.js"], cwd=ROOT, env=env
            ).returncode
        finally:
            server.terminate()
            server.wait(timeout=10)


def serve_dev(database, port):
    import os
    from pathlib import Path

    os.environ["SONG_RANKER_DB"] = str(Path(database))
    os.environ["SONG_RANKER_PIN"] = "qa-test-pin"
    os.environ["SONG_RANKER_SECRET"] = "isolated-local-ui-test-secret-000000000000"
    from songranker.storage.database import initialize_database

    initialize_database(os.environ["SONG_RANKER_DB"])
    from songranker import services

    c = services.get_db_connection()
    if not c.execute("SELECT 1 FROM songs").fetchone():
        for i in range(1, 17):
            c.execute(
                "INSERT INTO albums(id,title,release_date) VALUES(?,?,?)",
                (
                    i,
                    (
                        "An extraordinarily long album title to check wrapping across screens"
                        if i == 1
                        else f"Album {i}"
                    ),
                    "2026-01-01",
                ),
            )
            c.execute(
                "INSERT INTO artists(id,name) VALUES(?,?)",
                (i, f"Artist {i} with a long name" if i == 1 else f"Artist {i}"),
            )
            c.execute(
                "INSERT INTO genres(id,name,description) VALUES(?,?,?)",
                (i, f"Tag {i}", f"Tag {i} description and listening notes"),
            )
        for i in range(1, 81):
            c.execute(
                "INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,?,?)",
                (
                    i,
                    (
                        "A very long song title that should stay readable and bounded on phones"
                        if i == 1
                        else f"Song {i}"
                    ),
                    (i - 1) // 5 + 1,
                    (i - 1) % 5 + 1,
                ),
            )
            c.execute("INSERT INTO song_artists VALUES(?,?)", (i, (i - 1) // 5 + 1))
            if i % 3:
                c.execute("INSERT INTO song_genres VALUES(?,?)", (i, (i - 1) % 16 + 1))
        c.commit()
    c.close()
    import main

    services.ROOT = Path(database).parent
    from songranker.developer import dev

    # Only the Apple lookup transport is mocked; imports still use the real DB route.
    def lookup(url):
        """Return deterministic Apple track offers for served import/review checks."""
        return {
            "results": [
                {
                    "kind": "song",
                    "trackId": 9000 + i,
                    "collectionId": 8001,
                    "artistId": 7001,
                    "trackName": f"New import {i}",
                    "artistName": "Test artist",
                    "collectionName": "Import album - EP",
                    "trackNumber": i,
                    "discNumber": 1,
                    "discCount": 1,
                    "releaseDate": "2026-01-01T00:00:00Z",
                    "trackViewUrl": f"https://music.apple.com/us/album/test/8001?i={9000+i}",
                    "collectionViewUrl": "https://music.apple.com/us/album/test/8001",
                    "trackExplicitness": "notExplicit",
                }
                for i in range(1, 6)
            ]
        }

    dev.apple_lookup = lookup
    main.app.run(host="127.0.0.1", port=int(port), use_reloader=False, threaded=True)


def run_vibe():
    chrome = os.environ.get("SONG_RANKER_TEST_CHROME") or next(
        (
            shutil.which(name)
            for name in (
                "google-chrome",
                "google-chrome-stable",
                "chromium",
                "chromium-browser",
            )
            if shutil.which(name)
        ),
        None,
    )
    if not chrome:
        raise SystemExit("A Chromium browser is required for this integration check.")
    with tempfile.TemporaryDirectory(prefix="vibe-browser-") as temporary:
        os.environ["SONG_RANKER_DB"] = str(Path(temporary) / "vibe.db")
        os.environ["SONG_RANKER_PIN"] = "vibe-test-pin"
        from songranker.storage.database import initialize_database

        initialize_database(os.environ["SONG_RANKER_DB"])
        with sqlite3.connect(os.environ["SONG_RANKER_DB"]) as conn:
            conn.execute(
                "INSERT INTO albums(id,title,cover_url) VALUES(1,'A long album title for responsive testing','/vibe-test-art.svg')"
            )
            conn.execute(
                "INSERT INTO artists(id,name,cover_url) VALUES(1,'Artist with a longer name','/vibe-test-art.svg')"
            )
            conn.execute(
                "INSERT INTO genres(id,name) VALUES(1,'Melancholy'),(2,'Hopeful')"
            )
            conn.execute(
                "INSERT INTO albums(id,title,cover_url) VALUES(2,'Second album','/vibe-test-art.svg')"
            )
            for sid in range(1, 7):
                conn.execute(
                    "INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,?,?)",
                    (
                        sid,
                        "A song with a long title " + str(sid),
                        1 if sid <= 3 else 2,
                        sid,
                    ),
                )
                conn.execute("INSERT INTO song_artists VALUES(?,1)", (sid,))
                conn.execute(
                    "INSERT INTO song_genres VALUES(?,?)", (sid, 1 if sid <= 3 else 2)
                )
                if sid > 1:
                    conn.execute(
                        "UPDATE song_vibe_positions SET x=?,y=?,status='placed',sample_count=1,updated_at=1 WHERE song_id=?",
                        ((sid - 3) / 3, (sid - 4) / 4, sid),
                    )
            conn.execute("INSERT INTO albums(id,title) VALUES(3,'Unmapped album')")
            conn.execute("INSERT INTO artists(id,name) VALUES(2,'Unmapped artist')")
            conn.execute("INSERT INTO genres(id,name) VALUES(3,'Unmapped tag')")
            conn.execute(
                "INSERT INTO songs(id,title,album_id) VALUES(7,'Unmapped song',3)"
            )
            conn.execute("INSERT INTO song_artists VALUES(7,2)")
            conn.execute("INSERT INTO song_genres VALUES(7,3)")
        from songranker import services

        services.ROOT = Path(temporary)
        import main as application  # WSGI import never launches the Git updater.
        from flask import Response
        from werkzeug.serving import make_server
        from songranker.modes import vibe_map

        vibe_map.READJUST_SECONDS = 0.3
        vibe_map.vibe_song = lambda conn, previous=None: dict(
            id=2 if previous == 1 else 1
        )

        @application.app.get("/vibe-test-art.svg")
        def cover():
            """Serve local artwork so browser screenshots do not depend on external images."""
            return Response(
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#8b465c"/><circle cx="200" cy="180" r="100" fill="#352f47"/></svg>',
                mimetype="image/svg+xml",
            )

        # Tag-bench-only transport and music data; never reachable in the real app.
        @application.app.post("/tag-test-enable")
        def tag_audio_enable():
            with sqlite3.connect(os.environ["SONG_RANKER_DB"]) as conn:
                conn.execute(
                    "UPDATE songs SET audio_url='/tag-test-audio.wav' WHERE id IN (1,2)"
                )
            return {"ok": True}

        @application.app.get("/tag-test-audio.wav")
        def tag_audio():
            """Serve a silent WAV fixture for playback controls without Apple transport."""
            import io, wave

            buf = io.BytesIO()
            with wave.open(buf, "wb") as clip:
                clip.setnchannels(1)
                clip.setsampwidth(2)
                clip.setframerate(8000)
                clip.writeframes(bytes(30 * 8000 * 2))
            return Response(buf.getvalue(), mimetype="audio/wav")

        @application.app.post("/shelves-test-enable")
        def enable_discs():
            """Seed repeated track numbers across discs only in this disposable fixture."""
            with sqlite3.connect(os.environ["SONG_RANKER_DB"]) as conn:
                for sid, album, track in [(8,1,1),(9,1,2),(10,2,1),(11,2,2)]:
                    conn.execute("INSERT INTO songs(id,title,album_id,disc_number,track_number) VALUES(?,?,?,2,?)", (sid,"Disc two song "+str(sid),album,track))
                    conn.execute("INSERT INTO song_artists VALUES(?,1)", (sid,))
                conn.row_factory = sqlite3.Row
                songs = [dict(row) for row in conn.execute("SELECT id,album_id,disc_number,track_number FROM songs WHERE album_id IN (1,2)")]
            return {"songs": songs}

        server = make_server("127.0.0.1", 0, application.app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(
                os.environ,
                VIBE_TEST_URL=f"http://127.0.0.1:{server.server_port}",
                VIBE_TEST_CHROME=chrome,
            )
            subprocess.run(
                ["node", "tests/browser_check.cjs"], cwd=ROOT, env=env, check=True
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def main():
    """Run the requested disposable integration fixture."""
    if len(sys.argv) > 1 and sys.argv[1] == "--serve-dev":
        serve_dev(sys.argv[2], sys.argv[3])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("dev", "vibe"), default="vibe")
    args = parser.parse_args()
    return run_dev() if args.suite == "dev" else run_vibe()


if __name__ == "__main__":
    raise SystemExit(main())
