"""Voting report cohorts and compact rendering use saved evidence, without writes."""

from pathlib import Path
from statistics import median, pstdev
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from songranker import services, pages
from songranker.modes.voting import build_voting_stats
from songranker.modes.preferences import (
    get_offer,
    save_vote,
    save_tournament_preference,
)
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture


class VotingReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "votes.db"
        initialize_database(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO albums(id,title) VALUES(1,'Album')")
        self.conn.execute("INSERT INTO artists(id,name) VALUES(1,'Artist')")
        self.conn.execute("INSERT INTO genres(id,name) VALUES(1,'Tag')")
        for sid in range(1, 7):
            self.conn.execute(
                "INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,1,?)",
                (sid, "Song " + str(sid), sid),
            )
            self.conn.execute("INSERT INTO song_artists VALUES(?,1)", (sid,))
            self.conn.execute("INSERT INTO song_genres VALUES(?,1)", (sid,))
        self.conn.commit()

    def vote(self, pair=(1, 2), mode="standard"):
        offer = get_offer(
            self.conn,
            "test-owner",
            mode,
            lambda: tuple(
                self.conn.execute(
                    services.SONG_SELECT + " WHERE s.id=?", (sid,)
                ).fetchone()
                for sid in pair
            ),
        )
        return save_vote(
            self.conn,
            "test-owner",
            dict(
                token=offer["token"],
                winner_id=pair[0],
                loser_id=pair[1],
                mode=mode,
                rules_version=offer["rules_version"],
            ),
        )

    def test_distribution_ignores_unplayed_ratings_and_stale_counters(self):
        self.vote()
        self.conn.execute(
            "UPDATE songs SET elo_score=9999,matches_played=50 WHERE id=3"
        )
        self.conn.commit()
        before = capture(self.conn)
        report = build_voting_stats(self.conn)
        expected = [
            r[0]
            for r in self.conn.execute("SELECT elo_score FROM songs WHERE id IN (1,2)")
        ]
        d = report["distribution"]
        self.assertEqual((d["rated"], d["excluded"], d["unavailable"]), (2, 4, 0))
        self.assertEqual(
            (d["highest"], d["lowest"], d["median"], d["spread"]),
            (
                max(expected),
                min(expected),
                round(median(expected), 1),
                round(pstdev(expected), 1),
            ),
        )
        self.assertEqual(sum(row["count"] for row in d["bands"]), 2)
        self.assertAlmostEqual(sum(row["share"] for row in d["bands"]), 100)
        self.assertEqual((d["above_start"], d["at_start"], d["below_start"]), (1, 0, 1))
        self.assertEqual(report["coverage"]["under_two"], 2)
        self.assertEqual(capture(self.conn), before)

    def test_unavailable_ratings_and_empty_cohorts_stay_explicit(self):
        empty = build_voting_stats(self.conn)["distribution"]
        self.assertEqual(
            (empty["rated"], empty["excluded"], empty["unavailable"]), (0, 6, 0)
        )
        self.assertIsNone(empty["median"])
        self.assertIsNone(empty["average"])
        self.assertTrue(
            all(row["count"] == 0 and row["share"] is None for row in empty["bands"])
        )
        self.vote()
        self.conn.execute("UPDATE songs SET elo_score=NULL WHERE id=1")
        self.conn.commit()
        d = build_voting_stats(self.conn)["distribution"]
        self.assertEqual((d["rated"], d["unavailable"], d["excluded"]), (1, 1, 4))
        self.assertEqual(sum(row["count"] for row in d["bands"]), 1)

    def test_evidence_depth_and_history_filters_reconcile(self):
        for _ in range(3):
            self.vote()
        for _ in range(2):
            self.vote((2, 3), "blind")
        report = build_voting_stats(
            self.conn, history_mode="blind", history_origin="ordinary"
        )
        c = report["coverage"]
        self.assertEqual((c["under_two"], c["two_to_four"], c["five_plus"]), (0, 2, 1))
        self.assertAlmostEqual(c["avg_appearances"], round(10 / 3, 2))
        self.assertEqual(report["history_total"], 2)
        self.assertTrue(all(r["mode"] == "blind" for r in report["history"]))

    def test_half_weight_tournament_match_still_qualifies_both_tracks(self):
        self.conn.execute(
            "INSERT INTO tournaments(id,size,scope_type,scope_id,elo_policy_version,elo_weight) VALUES(1,8,'album',1,1,0.5)"
        )
        self.conn.execute(
            "INSERT INTO tournament_matches(id,tournament_id,round_number,match_number,song1_id,song2_id) VALUES(1,1,1,1,3,4)"
        )
        tournament = dict(
            self.conn.execute("SELECT * FROM tournaments WHERE id=1").fetchone()
        )
        match = dict(
            self.conn.execute("SELECT * FROM tournament_matches WHERE id=1").fetchone()
        )
        save_tournament_preference(self.conn, tournament, match, 3, 4)
        self.conn.commit()
        report = build_voting_stats(self.conn, history_origin="tournament")
        self.assertEqual(report["distribution"]["rated"], 2)
        self.assertEqual(report["distribution"]["excluded"], 4)
        self.assertEqual(report["coverage"]["avg_appearances"], 0.5)
        self.assertEqual(report["history_total"], 1)
        self.assertEqual(report["elo_summary"]["half"], 1)

    def test_page_has_new_summaries_and_one_useful_disclosure(self):
        self.vote()
        before = capture(self.conn)
        with patch.object(services, "DB_NAME", str(self.path)):
            response = services.app.test_client().get("/voting_stats")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for text in (
            "Voting evidence depth",
            "Voted-track rating balance",
            "tracks without matches excluded",
            "voting-entity-artist",
            "voting-entity-album",
            "voting-entity-tag",
        ):
            self.assertIn(text, html)
        self.assertNotIn("Recent first-round Elo matches</summary>", html)
        self.assertEqual(html.count('<details class="stats-notes">'), 1)
        self.assertIn("Daily figures", html)
        self.assertNotIn("<h3>Last 7 days</h3>", html)
        self.assertEqual(capture(self.conn), before)
