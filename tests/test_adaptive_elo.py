"""Adaptive ratings, startup archives and deterministic replay on disposable data."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import math
import random
import sqlite3
import tempfile
import unittest

from songranker.storage.database import activate_adaptive_elo, initialize_database
from songranker.storage.database_io import capture, readonly, validate
from songranker.storage.preference_state import (
    EloPopulation, calculate_new_elo, live_elo_scale, rebuild_preference_ratings,
    replay, mode_replay,
)
from songranker.modes.preferences import record_preference, rebuild_ratings


class AdaptiveEloTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ratings.db"
        initialize_database(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(self.conn.close)
        self.conn.executemany("INSERT INTO songs(id,title) VALUES(?,?)",
                              ((i, f"Track {i}") for i in range(1, 21)))
        self.conn.execute("INSERT INTO genres(id,name) VALUES(1,'Scoped')")
        self.conn.execute("INSERT INTO tournaments(id,size,scope_type,scope_id,status,elo_policy_version,elo_weight) VALUES(1,16,'tag',1,'in_progress',1,.5)")
        self.conn.commit()

    def vote(self, winner, loser, mode="standard", half=False):
        self.conn.execute("BEGIN IMMEDIATE")
        extra = {}
        if half:
            match = self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id) VALUES(1,1,?,?,?)",
                (self.conn.execute("SELECT COUNT(*)+1 FROM tournament_matches").fetchone()[0], winner, loser)).lastrowid
            extra = dict(tournament_id=1, tournament_match_id=match, weight=.5)
        event = record_preference(self.conn, winner, loser, mode,
                                 {sid: dict(id=sid, title=f"Track {sid}") for sid in (winner, loser)}, **extra)
        self.conn.commit()
        return event

    def history(self, rounds=80):
        rng = random.Random(540)
        for i in range(rounds):
            a, b = rng.sample(range(1, 21), 2)
            self.vote(a, b, "blind" if i % 3 == 0 else "standard", half=i % 7 == 0)

    def test_scale_is_tested_only_bounded_mature_and_population_relative(self):
        self.assertEqual(EloPopulation().scale(), 400)
        self.assertEqual(EloPopulation([(1, 1200, 100)]).scale(), 400)
        rows = [(i, value, 1) for i, value in enumerate([1184, 1184, 1216, 1216])]
        early = EloPopulation(rows).scale()
        mature = EloPopulation((i, v, 100) for i, v, _ in rows).scale()
        self.assertAlmostEqual(early, 371.2)
        self.assertTrue(256 < mature < early < 400)
        self.assertEqual(EloPopulation(rows + [(99, 5000, 0)]).scale(), early)
        self.assertAlmostEqual(EloPopulation((i, v + 900, n) for i, v, n in rows).scale(), early)
        self.assertEqual(EloPopulation((i, v * 5, 1000) for i, v, _ in rows).scale(), 400)
        self.assertTrue(200 <= EloPopulation((i, 1200, 1000000) for i in range(100)).scale() < 201)

    def test_pair_conservation_equal_split_half_weight_and_extreme_gaps(self):
        for scale in (200, 256, 371.2, 400):
            self.assertEqual(calculate_new_elo(1200, 1200, 32, scale), (1216, 1184))
            self.assertEqual(calculate_new_elo(1200, 1200, 16, scale), (1208, 1192))
            favourite = calculate_new_elo(1264, 1200, 32, scale)
            upset = calculate_new_elo(1200, 1264, 32, scale)
            self.assertAlmostEqual(sum(favourite), 2464)
            self.assertAlmostEqual(sum(upset), 2464)
            self.assertTrue(0 < favourite[0] - 1264 < 16 < upset[0] - 1200 < 32)
        for a, b in ((0, 5000), (-1e300, 1e300), (1e300, -1e300)):
            self.assertTrue(all(math.isfinite(v) for v in calculate_new_elo(a, b, 32, 200)))
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                calculate_new_elo(value, 1200)

    def test_live_and_replay_agree_after_mixed_history_and_manual_override(self):
        self.history()
        self.conn.execute("BEGIN IMMEDIATE")
        end = self.conn.execute("SELECT MAX(id) FROM preference_events").fetchone()[0]
        self.conn.execute("INSERT INTO preference_rating_overrides(request_token,song_id,song_snapshot,after_event_id,previous_elo,new_elo) VALUES('override',1,'{}',?,1200,1380)", (end,))
        self.conn.execute("UPDATE songs SET elo_score=1380 WHERE id=1")
        self.conn.commit()
        self.vote(1, 2)
        self.vote(3, 4, "blind", half=True)
        before = capture(self.conn)
        self.conn.execute("BEGIN IMMEDIATE")
        rebuild_ratings(self.conn)
        self.conn.commit()
        after = capture(self.conn)
        # Peaks also rebuild; an override itself does not count as a match/peak.
        for table in ("songs", "preference_mode_ratings", "preference_rating_projection"):
            self.assertEqual(before["tables"][table], after["tables"][table], table)
        self.assertTrue(200 <= live_elo_scale(self.conn) <= 400)
        self.assertNotEqual(live_elo_scale(self.conn, "standard"), live_elo_scale(self.conn, "blind"))

    def test_startup_archives_old_policy_replays_once_and_preserves_facts(self):
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1")
        self.conn.commit()
        self.history()
        # Exercise effective corrections and voids without rewriting source facts.
        self.conn.execute("INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active) VALUES(1,'void-first','void',1,2,'standard',0)")
        self.conn.execute("INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active) VALUES(2,'correct-second','replace',3,4,'blind',1)")
        self.conn.commit()
        before = capture(self.conn)
        report = activate_adaptive_elo(self.path)
        self.assertTrue(Path(report["backup"]).is_file())
        with readonly(report["backup"]) as archived:
            self.assertEqual(capture(archived), before)
        after = capture(self.conn)
        changed = {"songs", "preference_rating_projection", "preference_mode_ratings", "preference_replay_state", "competition_state"}
        for name in before["tables"]:
            if name not in changed:
                self.assertEqual(before["tables"][name], after["tables"][name], name)
        self.assertNotEqual(before["tables"]["songs"], after["tables"]["songs"])
        self.assertEqual(report["events"], 79)
        self.assertEqual(self.conn.execute("SELECT rules_version FROM preference_replay_state").fetchone()[0], 2)
        self.assertIsNone(activate_adaptive_elo(self.path))
        self.assertEqual(capture(self.conn), after)
        self.assertEqual(len(list(self.path.parent.glob("database_backups/pre_adaptive_elo_*.db"))), 1)
        self.conn.execute("BEGIN IMMEDIATE")
        rebuild_preference_ratings(self.conn)
        self.conn.commit()
        self.assertEqual(capture(self.conn), after)
        self.vote(1, 2)
        latest = capture(self.conn)
        self.conn.execute("BEGIN IMMEDIATE")
        rebuild_ratings(self.conn)
        self.conn.commit()
        self.assertEqual(capture(self.conn), latest)
        validate(self.conn)

    def test_failed_archive_or_replay_leaves_old_database_and_marker_intact(self):
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1")
        self.conn.commit()
        self.history(10)
        before = capture(self.conn)
        with patch("songranker.storage.database_io.create_backup", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                activate_adaptive_elo(self.path)
        self.assertEqual(capture(self.conn), before)

        def fail(conn):
            conn.execute("UPDATE songs SET elo_score=1")
            raise RuntimeError("interrupted replay")

        with patch("songranker.storage.preference_state.rebuild_preference_ratings", side_effect=fail):
            with self.assertRaises(RuntimeError):
                activate_adaptive_elo(self.path)
        self.assertEqual(capture(self.conn), before)
        self.assertIsNotNone(activate_adaptive_elo(self.path))

    def test_concurrent_startups_only_publish_one_replay_and_archive(self):
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1")
        self.conn.commit()
        self.history(10)
        with ThreadPoolExecutor(2) as workers:
            reports = list(workers.map(lambda _: activate_adaptive_elo(self.path), range(2)))
        self.assertEqual(sum(report is not None for report in reports), 1)
        self.assertEqual(len(list(self.path.parent.glob("database_backups/pre_adaptive_elo_*.db"))), 1)

    def test_missing_tested_baseline_stops_instead_of_replaying_from_final_rating(self):
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1")
        self.conn.commit()
        self.vote(1, 2)
        self.conn.execute("DELETE FROM preference_rating_seeds WHERE song_id=1")
        self.conn.commit()
        before = capture(self.conn)
        with self.assertRaisesRegex(ValueError, "missing its rating baseline"):
            activate_adaptive_elo(self.path)
        self.assertEqual(capture(self.conn), before)

    def test_protected_anchor_is_retained_and_unknown_policy_is_rejected(self):
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1,baseline_kind='legacy_anchor',cutoff_event_id=100,legacy_boundary=100")
        self.conn.execute("UPDATE songs SET elo_score=1350,matches_played=8,highest_elo=1400 WHERE id=1")
        self.conn.execute("INSERT INTO preference_rating_seeds VALUES(1,1350,8,1400,9999)")
        self.conn.commit()
        report = activate_adaptive_elo(self.path)
        self.assertTrue(report["anchored"])
        self.assertEqual(tuple(self.conn.execute("SELECT elo_score,matches_played,highest_elo FROM songs WHERE id=1").fetchone()), (1350, 8, 1400))
        self.conn.execute("UPDATE preference_replay_state SET rules_version=99")
        self.conn.commit()
        before = capture(self.conn)
        with self.assertRaises(ValueError):
            activate_adaptive_elo(self.path)
        self.assertEqual(capture(self.conn), before)

    def test_wal_archive_contains_latest_committed_state(self):
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("UPDATE preference_replay_state SET rules_version=1")
        self.conn.execute("UPDATE songs SET title='Latest WAL title' WHERE id=1")
        self.conn.commit()
        report = activate_adaptive_elo(self.path)
        with readonly(report["backup"]) as saved:
            self.assertEqual(saved.execute("SELECT title FROM songs WHERE id=1").fetchone()[0], "Latest WAL title")

    def test_large_mature_history_remains_finite_balanced_and_deterministic(self):
        rng = random.Random(540)
        songs = [dict(id=i) for i in range(1, 1001)]
        seeds = {s["id"]: dict(elo=1200., matches=0, highest_elo=1200., highest_rank=9999) for s in songs}
        events = [dict(id=i, winner_id=rng.randint(1, 500), loser_id=rng.randint(501, 1000),
                       active=1, mode="blind" if i % 2 else "standard",
                       origin="tournament" if i % 7 == 0 else "ordinary",
                       rating_weight=.5 if i % 7 == 0 else 1.) for i in range(1, 12001)]
        ratings, snapshots = replay(songs, seeds, events, [], 0, 0, 2)
        self.assertEqual((ratings, snapshots), replay(songs, seeds, list(reversed(events)), [], 0, 0, 2))
        values = [row["elo"] for row in ratings.values()]
        self.assertTrue(all(math.isfinite(v) for v in values))
        self.assertGreater(max(values) - min(values), 200)
        self.assertAlmostEqual(math.fsum(values), 1200000., places=7)
        self.assertTrue(all(0 < after - before <= 32 for before, after, _, _ in snapshots.values()))
        self.assertEqual(EloPopulation((sid, row["elo"], 24) for sid, row in ratings.items()).scale(), 400)
        modes = mode_replay(songs, events, 2)
        for mode in ("standard", "blind"):
            self.assertAlmostEqual(math.fsum(row["elo"] for (sid, key), row in modes.items() if key == mode), 1200000., places=7)


if __name__ == "__main__":
    unittest.main()
