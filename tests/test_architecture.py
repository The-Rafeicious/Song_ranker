"""Preserve public routes, asset order and profile reads across module consolidation."""

from html.parser import HTMLParser
import importlib
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import unittest

import test_preferences as fixture
from support import route_modules
from songranker import services
from songranker.storage.database_io import capture
from songranker.version import APP_VERSION

# Register all production route owners before any test sends its first request.
for module in route_modules().values():
    importlib.import_module(module)


class Assets(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.styles = []
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.styles.append(attrs["href"])
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])


class ArchitectureTests(unittest.TestCase):
    setUp = fixture.PreferenceTests.setUp
    connect = fixture.PreferenceTests.connect

    def register(self):
        """Register the launcher's actual feature owners without running startup sync."""
        for module in route_modules().values():
            importlib.import_module(module)

    def test_all_previous_urls_methods_and_endpoint_names_are_preserved(self):
        self.register()
        expected = json.loads(
            (Path(__file__).parent / "fixtures/routes.json").read_text()
        )
        actual = sorted(
            [
                dict(
                    path=r.rule,
                    endpoint=r.endpoint,
                    methods=sorted(r.methods - {"HEAD", "OPTIONS"}),
                )
                for r in services.app.url_map.iter_rules()
            ],
            key=lambda r: r["path"],
        )
        added = [
            r
            for r in actual
            if r["endpoint"]
            in ("dev_area", "dev_task", "use_remote_database", "compact_git_storage", "tournament_bracket_page")
        ]
        self.assertEqual(5, len(added))
        added.append(dict(path='/tournament_local_stats',endpoint='local_tournament_stats_page',methods=['GET']))
        self.assertEqual(expected, [r for r in actual if r not in added])

    def test_pages_use_one_asset_registry_and_last_shared_baseline(self):
        self.register()
        client = services.app.test_client()
        with client.session_transaction() as session:
            session["is_admin"] = True
        paths = [
            "/",
            "/leaderboard",
            "/artists",
            "/albums",
            "/tags",
            "/search",
            "/game",
            "/trivia",
            "/tournament",
            "/elo_guesser",
            "/album_shelves",
            "/vibe-map",
            "/global_stats",
            "/voting_stats",
            "/history",
            "/trivia_stats",
            "/tournament_stats",
            "/elo_guesser_stats",
            "/album_shelves_stats",
            "/vibe_map_stats",
            "/song/1",
            "/artist/Artist,%20One",
            "/album/Album",
            "/tag/Tag",
            "/dev/dashboard",
        ]
        root = Path(__file__).resolve().parents[1]
        for path in paths:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                assets = Assets(response.get_data(as_text=True))
                self.assertTrue(
                    assets.styles[-1].startswith("/static/css/site_baseline.css?")
                )
                self.assertEqual(len(assets.styles), len(set(assets.styles)))
                self.assertEqual(len(assets.scripts), len(set(assets.scripts)))
                self.assertTrue(assets.scripts[0].startswith("/static/js/ui.js?"))
                for url in assets.styles + assets.scripts:
                    parsed = urlsplit(url)
                    self.assertEqual(parse_qs(parsed.query).get("v"), [APP_VERSION])
                    self.assertTrue((root / parsed.path.lstrip("/")).is_file(), url)
                if path != "/dev/dashboard":
                    self.assertFalse(any("/dev_" in url for url in assets.scripts))

    def test_collection_profiles_share_identity_payloads_and_are_read_only(self):
        self.register()
        client = services.app.test_client()
        before = capture(self.conn)
        for path, kind, name in [
            ("/artist/Artist,%20One", "artists", "Artist, One"),
            ("/album/Album", "albums", "Album"),
            ("/tag/Tag", "tags", "Tag"),
        ]:
            with self.subTest(path=path):
                html = client.get(path).get_data(as_text=True)
                marker = '<script id="profile-data" type="application/json">'
                data = json.loads(html.split(marker)[1].split("</script>")[0])
                self.assertEqual(data, dict(kind=kind, name=name))
        for path in ["/artist/Missing", "/album/Missing", "/tag/Missing"]:
            self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(capture(self.conn), before)


if __name__ == "__main__":
    unittest.main()
