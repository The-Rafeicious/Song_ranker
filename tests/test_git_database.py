"""Two local computers and a bare remote; never touches the user's databases/Git."""

from pathlib import Path
from unittest.mock import patch
import shutil
import sqlite3
import subprocess
import os
import sys
import unittest

import test_git_sync as fixture

command = fixture.command
from songranker.developer.git_sync import GitSync
from songranker.storage.competition import bootstrap_sql
from songranker.storage.database_io import capture, readonly
from songranker.storage.git_database import DatabaseSync
from songranker.storage.database_schema import SCHEMA_VERSION


class GitDatabaseTests(unittest.TestCase):
    setUp = fixture.GitSyncTests.setUp
    identity = fixture.GitSyncTests.identity
    head = fixture.GitSyncTests.head
    state = fixture.GitSyncTests.state
    remote_change = fixture.GitSyncTests.remote_change

    def pair(self):
        self.assertTrue(self.sync.upload()["ok"])
        self.desktop = self.folder / "desktop"
        command(self.folder, "clone", str(self.remote), str(self.desktop))
        self.identity(self.desktop)
        self.desktop_db = self.desktop / "live.db"
        bootstrap_sql(self.desktop_db, self.desktop / "database_backup.sql")
        self.other = GitSync(self.desktop, self.desktop_db)
        self.assertEqual(self.other.reconcile_database()["code"], "database_matches")

    def edit(self, path, sql, args=()):
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute(sql, args)
            conn.commit()
        finally:
            conn.close()

    def count(self, path=None):
        with readonly(path or self.db) as conn:
            return conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]

    def publish(self):
        result = self.other.upload()
        self.assertTrue(result["ok"], result)

    def pull(self):
        command(self.work, "pull", "--ff-only")

    def accept_remote(self):
        """Explicitly review and apply a remote copy; automatic adoption is retired."""
        reviewed = self.sync.local_choice_review()
        self.assertTrue(reviewed["ok"], reviewed)
        return self.sync.use_remote(reviewed["choice"])

    def test_manual_pull_then_startup_loads_five_hundred_new_songs(self):
        self.pair()
        before = self.state()
        conn = sqlite3.connect(self.desktop_db)
        conn.executemany(
            "INSERT INTO songs(id,title) VALUES(?,?)",
            [(i, "Desktop " + str(i)) for i in range(2, 502)],
        )
        conn.commit()
        conn.close()
        self.publish()
        self.pull()
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.sync.startup()["code"], "unchanged")
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        self.assertEqual((result["local_songs"], result["remote_songs"]), (1, 501))
        self.assertEqual(self.count(), 501)
        with readonly(
            self.db.parent / "database_backups" / result["backup"]
        ) as archived:
            self.assertEqual(capture(archived), before)
        with readonly(self.desktop_db) as remote:
            self.assertEqual(self.state(), capture(remote))
        backups = list(
            (self.db.parent / "database_backups").glob("pre_git_database_*.db")
        )
        self.assertEqual(self.sync.reconcile_database()["code"], "database_matches")
        self.assertEqual(
            backups,
            list((self.db.parent / "database_backups").glob("pre_git_database_*.db")),
        )

    def test_normal_launcher_reconciles_before_the_server_starts(self):
        self.pair()
        command(self.seed, "pull", "--ff-only")
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(
            source / "songranker",
            self.seed / "songranker",
            ignore=shutil.ignore_patterns("__pycache__"),
            dirs_exist_ok=True,
        )
        (self.seed / "data").mkdir(exist_ok=True)
        shutil.copy2(source / "data/schema.sql", self.seed / "data/schema.sql")
        shutil.copy2(source / "main.py", self.seed / "main.py")
        (self.seed / "waitress.py").write_text(
            "from types import SimpleNamespace\nimport os,sqlite3\ndef report():\n c=sqlite3.connect(os.environ['SONG_RANKER_DB']);print('server songs '+str(c.execute('SELECT COUNT(*) FROM songs').fetchone()[0]));c.close()\ndef create_server(*args,**kwargs):return SimpleNamespace(run=report)\n"
        )
        command(self.seed, "add", ".")
        command(self.seed, "commit", "-m", "Application code")
        command(self.seed, "push")
        self.pull()
        command(self.desktop, "pull", "--ff-only")
        self.edit(
            self.desktop_db,
            "INSERT INTO songs(id,title) VALUES(2,'Desktop before launch')",
        )
        self.publish()
        self.pull()
        env = os.environ.copy()
        env.update(
            SONG_RANKER_DB=str(self.db),
            SONG_RANKER_BOOT_COMMIT="",
            PYTHONPATH=str(Path("../.deps/python").resolve()),
        )
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("server songs 1", result.stdout)
        self.assertIn("changed the remote database", result.stdout)
        self.assertEqual(self.count(), 1)
        self.assertTrue(self.accept_remote()["ok"])
        self.assertEqual(self.count(), 2)

    def test_initial_upgrade_recovers_baseline_from_history_after_pull(self):
        self.pair()
        for receipt in self.sync.state_dir.glob("database_*.json"):
            receipt.unlink()
        (self.sync.state_dir / "history.json").unlink()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New desktop song')"
        )
        self.publish()
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        self.assertEqual(self.count(), 2)

    def test_code_fast_forward_is_followed_by_database_reconciliation(self):
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New song')")
        self.publish()
        result = self.sync.startup()
        self.assertEqual(result["code"], "updated")
        self.assertEqual(result["database_sync"]["code"], "database_conflict")
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.accept_remote()["code"], "database_updated")
        self.assertEqual(self.count(), 2)

    def test_same_row_count_remote_edit_and_deletion_are_not_missed(self):
        self.pair()
        self.edit(self.desktop_db, "DELETE FROM songs WHERE id=1")
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Replacement')"
        )
        self.publish()
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        with readonly(self.db) as conn:
            self.assertEqual(
                [tuple(r) for r in conn.execute("SELECT id,title FROM songs")],
                [(2, "Replacement")],
            )
        self.assertEqual(result["remote_changes"]["songs"]["removed"], 1)

    def test_remote_metadata_edit_without_added_rows_is_applied(self):
        self.pair()
        self.edit(
            self.desktop_db, "UPDATE songs SET title='Desktop correction' WHERE id=1"
        )
        self.publish()
        self.pull()
        self.assertEqual(self.accept_remote()["code"], "database_updated")
        with readonly(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT title FROM songs").fetchone()[0],
                "Desktop correction",
            )

    def test_stale_laptop_cannot_upload_over_new_remote_after_manual_pull(self):
        self.pair()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Keep remote')"
        )
        self.publish()
        self.pull()
        before = self.state()
        sql = self.sync.sql.read_bytes()
        head = self.head()
        result = self.sync.upload()
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.sync.sql.read_bytes(), sql)
        self.assertEqual(self.head(), head)
        self.assertEqual(command(self.remote, "rev-parse", "main"), head)

    def test_local_deletion_and_remote_addition_conflict_without_resurrection(self):
        self.pair()
        self.edit(self.db, "DELETE FROM songs WHERE id=1")
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New remote')")
        self.publish()
        self.pull()
        before = self.state()
        head = self.head()
        sql = self.sync.sql.read_bytes()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        incoming = self.db.parent / "database_backups" / result["incoming_backup"]
        self.assertEqual(self.count(incoming), 2)
        self.assertEqual(result["local_changes"]["songs"]["removed"], 1)
        failed = self.sync.upload()
        self.assertEqual(failed["code"], "database_conflict", failed)
        self.assertEqual(self.head(), head)
        self.assertEqual(self.sync.sql.read_bytes(), sql)
        self.assertEqual(self.state(), before)

    def test_same_id_different_new_songs_remain_separate_conflicting_copies(self):
        self.pair()
        self.edit(self.db, "INSERT INTO songs(id,title) VALUES(2,'Laptop song')")
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Desktop song')"
        )
        self.publish()
        self.pull()
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        with readonly(
            self.db.parent / "database_backups" / result["incoming_backup"]
        ) as conn:
            self.assertEqual(
                conn.execute("SELECT title FROM songs WHERE id=2").fetchone()[0],
                "Desktop song",
            )

    def test_both_devices_editing_one_record_blocks_upload(self):
        self.pair()
        self.edit(self.db, "UPDATE songs SET title='Laptop edit'")
        self.edit(self.desktop_db, "UPDATE songs SET title='Desktop edit'")
        self.publish()
        self.pull()
        self.assertEqual(self.sync.reconcile_database()["code"], "database_conflict")
        self.assertEqual(self.sync.upload()["code"], "database_conflict")

    def test_remote_covering_local_changes_and_additions_is_safe(self):
        self.pair()
        for path in (self.db, self.desktop_db):
            self.edit(path, "UPDATE songs SET title='Same deliberate edit'")
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Additional song')"
        )
        self.publish()
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        self.assertEqual(self.count(), 2)

    def test_matching_deletions_on_both_devices_can_advance_to_remote(self):
        self.pair()
        for path in (self.db, self.desktop_db):
            self.edit(path, "DELETE FROM songs WHERE id=1")
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New remote')")
        self.publish()
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        self.assertEqual(self.count(), 1)

    def test_local_only_changes_stay_local_then_upload_normally(self):
        self.pair()
        self.edit(self.db, "UPDATE songs SET title='Local change'")
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_local_ahead", result)
        self.assertEqual(self.state(), before)
        self.assertTrue(self.sync.upload()["ok"])
        self.assertEqual(self.state(), before)
        choice = self.other.local_choice_review()
        self.assertTrue(self.other.use_remote(choice["choice"])["ok"])

    def test_check_remote_compares_database_without_restoring_or_mutating_sql(self):
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Incoming')")
        self.publish()
        before = self.state()
        head = self.head()
        sql = self.sync.sql.read_bytes()
        result = self.sync.check()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["git"]["database_sync"]["code"], "database_conflict")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.head(), head)
        self.assertEqual(self.sync.sql.read_bytes(), sql)

    def test_unknown_baseline_preserves_both_even_if_remote_has_more_rows(self):
        self.pair()
        for receipt in self.sync.state_dir.glob("database_*.json"):
            receipt.unlink()
        self.edit(self.db, "UPDATE songs SET title='Unpublished local edit'")
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Incoming')")
        self.publish()
        self.pull()
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        self.assertTrue(
            (self.db.parent / "database_backups" / result["incoming_backup"]).exists()
        )

    def test_deleted_link_is_detected_from_device_history_if_receipt_is_missing(self):
        self.edit(self.db, "INSERT INTO genres(id,name) VALUES(1,'Existing tag')")
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO song_genres VALUES(1,1)")
        self.publish()
        self.pull()
        self.assertEqual(self.accept_remote()["code"], "database_updated")
        self.edit(self.db, "DELETE FROM song_genres WHERE song_id=1")
        for receipt in self.sync.state_dir.glob("database_*.json"):
            receipt.unlink()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Remote addition')"
        )
        self.publish()
        self.pull()
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        self.assertEqual(result["local_changes"]["song_genres"]["removed"], 1)

    def cast_vote(self, path, winner):
        from songranker import services
        from songranker.modes.preferences import get_offer, save_vote

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            offer = get_offer(
                conn,
                "sync-fixture",
                "standard",
                lambda: tuple(
                    conn.execute(
                        services.SONG_SELECT + " WHERE s.id=?", (sid,)
                    ).fetchone()
                    for sid in (1, 2)
                ),
            )
            save_vote(
                conn,
                "sync-fixture",
                dict(
                    token=offer["token"],
                    winner_id=winner,
                    loser_id=3 - winner,
                    mode="standard",
                    rules_version=offer["rules_version"],
                ),
            )
        finally:
            conn.close()

    def test_remote_game_results_and_ratings_are_loaded_without_reset(self):
        self.edit(self.db, "INSERT INTO songs(id,title) VALUES(2,'Second song')")
        self.pair()
        self.cast_vote(self.desktop_db, 1)
        self.publish()
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        with readonly(self.db) as local, readonly(self.desktop_db) as remote:
            self.assertEqual(capture(local), capture(remote))
            self.assertEqual(
                local.execute("SELECT COUNT(*) FROM preference_events").fetchone()[0], 1
            )
            self.assertGreater(
                local.execute("SELECT elo_score FROM songs WHERE id=1").fetchone()[0],
                1200,
            )

    def test_local_game_result_is_not_overwritten_by_remote_result(self):
        self.edit(self.db, "INSERT INTO songs(id,title) VALUES(2,'Second song')")
        self.pair()
        self.cast_vote(self.db, 1)
        self.cast_vote(self.desktop_db, 2)
        self.publish()
        self.pull()
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.sync.upload()["code"], "database_conflict")

    def test_corrupt_remote_snapshot_does_not_change_live_or_upload_file(self):
        self.pair()
        self.remote_change({"database_backup.sql": "CREATE TABLE broken ("})
        self.pull()
        before = self.state()
        sql = self.sync.sql.read_bytes()
        self.assertEqual(
            self.sync.reconcile_database()["code"], "database_check_failed"
        )
        self.assertEqual(self.state(), before)
        self.assertFalse(self.sync.upload()["ok"])
        self.assertEqual(self.sync.sql.read_bytes(), sql)

    def test_future_schema_is_not_loaded_over_existing_data(self):
        self.pair()
        sql = self.sync.sql.read_text().replace(
            f"PRAGMA user_version={SCHEMA_VERSION};", "PRAGMA user_version=999;"
        )
        self.remote_change({"database_backup.sql": sql})
        self.pull()
        before = self.state()
        self.assertEqual(
            self.sync.reconcile_database()["code"], "database_check_failed"
        )
        self.assertEqual(self.state(), before)

    def test_row_replacement_failure_rolls_back_and_keeps_archive(self):
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New')")
        self.publish()
        self.pull()
        before = self.state()
        from songranker.storage.git_database import replace_contents

        def fail(conn, state):
            replace_contents(conn, state)
            raise sqlite3.DatabaseError("injected after replacement")

        with patch(
            "songranker.storage.git_database.replace_contents", side_effect=fail
        ):
            result = self.accept_remote()
        self.assertEqual(result["code"], "database_check_failed")
        self.assertEqual(self.state(), before)
        archived = list(
            (self.db.parent / "database_backups").glob("pre_git_database_*.db")
        )
        self.assertEqual(len(archived), 1)
        with readonly(archived[0]) as conn:
            self.assertEqual(capture(conn), before)

    def test_local_write_during_preparation_prevents_replacement(self):
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New')")
        self.publish()
        self.pull()
        from songranker.storage.git_database import create_backup

        def racing(*args, **kwargs):
            backup = create_backup(*args, **kwargs)
            self.edit(self.db, "UPDATE songs SET title='Concurrent local write'")
            return backup

        with patch("songranker.storage.git_database.create_backup", side_effect=racing):
            result = self.accept_remote()
        self.assertEqual(result["code"], "database_check_failed")
        self.assertEqual(self.count(), 1)
        with readonly(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT title FROM songs").fetchone()[0],
                "Concurrent local write",
            )

    def test_new_extension_data_is_preserved_when_adopting_remote(self):
        self.pair()
        self.edit(
            self.desktop_db,
            "CREATE TABLE extra_notes(id INTEGER PRIMARY KEY,note TEXT)",
        )
        self.edit(self.desktop_db, "INSERT INTO extra_notes VALUES(1,'Keep extension')")
        self.publish()
        self.pull()
        self.assertEqual(self.accept_remote()["code"], "database_updated")
        with readonly(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT note FROM extra_notes").fetchone()[0],
                "Keep extension",
            )

    def test_local_extension_changes_are_not_lost(self):
        self.pair()
        self.edit(self.db, "CREATE TABLE extra_notes(id INTEGER PRIMARY KEY,note TEXT)")
        self.edit(self.db, "INSERT INTO extra_notes VALUES(1,'Local extension')")
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New')")
        self.publish()
        self.pull()
        before = self.state()
        self.assertEqual(self.sync.reconcile_database()["code"], "database_conflict")
        self.assertEqual(self.state(), before)

    def test_committed_wal_data_is_compared_and_preserved(self):
        self.pair()
        conn = sqlite3.connect(self.desktop_db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO songs(id,title) VALUES(2,'Committed WAL song')")
        conn.commit()
        try:
            self.publish()
            self.pull()
            self.assertEqual(self.accept_remote()["code"], "database_updated")
            self.assertEqual(self.count(), 2)
        finally:
            conn.close()

    def test_completed_adoption_stays_successful_if_receipt_or_status_writes_fail(self):
        self.pair()
        for sid, target in [(2, "remember"), (3, "database_report"), (4, "record")]:
            with self.subTest(target=target):
                self.edit(
                    self.desktop_db,
                    "INSERT INTO songs(id,title) VALUES(?,?)",
                    (sid, "Remote " + str(sid)),
                )
                self.publish()
                self.pull()
                manager = (
                    patch.object(
                        DatabaseSync,
                        "remember",
                        side_effect=OSError("receipt unavailable"),
                    )
                    if target == "remember"
                    else patch.object(
                        self.sync, target, side_effect=OSError("status unavailable")
                    )
                )
                with manager:
                    result = self.accept_remote()
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["code"], "database_updated")
                self.assertEqual(self.count(), sid)
                self.assertTrue(
                    (self.db.parent / "database_backups" / result["backup"]).exists()
                )

    def test_acknowledged_upload_stays_successful_if_local_history_write_fails(self):
        self.pair()
        self.edit(self.db, "INSERT INTO songs(id,title) VALUES(2,'Local new song')")
        before = self.state()
        with patch.object(
            self.sync, "record", side_effect=OSError("history unavailable")
        ):
            result = self.sync.upload()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], "uploaded")
        self.assertEqual(command(self.remote, "rev-parse", "main"), self.head())
        self.assertEqual(self.state(), before)
        self.assertEqual(self.sync.upload()["code"], "unchanged")

    def test_another_configured_database_cannot_reuse_the_original_receipt(self):
        self.pair()
        from songranker.storage.database import initialize_database

        other_path = self.work / "another.db"
        initialize_database(other_path)
        self.edit(
            other_path,
            "INSERT INTO songs(id,title) VALUES(1,'Different local library')",
        )
        other_sync = GitSync(self.work, other_path)
        before = self.head()
        sql = self.sync.sql.read_bytes()
        result = other_sync.upload()
        self.assertEqual(result["code"], "database_conflict", result)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.sync.sql.read_bytes(), sql)
        with readonly(other_path) as conn:
            self.assertEqual(
                conn.execute("SELECT title FROM songs").fetchone()[0],
                "Different local library",
            )

    def test_ambiguous_extension_identities_do_not_hide_local_work(self):
        self.pair()
        self.edit(
            self.db, "CREATE TABLE extra_nullable(id TEXT PRIMARY KEY,value TEXT)"
        )
        self.edit(self.db, "INSERT INTO extra_nullable VALUES(NULL,'First local fact')")
        self.edit(
            self.db, "INSERT INTO extra_nullable VALUES(NULL,'Second local fact')"
        )
        before = self.state()
        result = self.sync.reconcile_database()
        self.assertEqual(result["code"], "database_check_failed", result)
        self.assertEqual(self.state(), before)
        self.assertFalse(self.sync.upload()["ok"])

    def test_pre_v5_sql_history_can_identify_an_unchanged_transferred_catalogue(self):
        from songranker.storage.database_io import snapshot, sql_dump

        self.edit(self.db, "UPDATE song_details SET added_at=0")
        with snapshot(self.db) as conn:
            conn.execute("DELETE FROM competition_state")
            conn.commit()
            legacy_sql = sql_dump(conn)
        self.remote_change({"database_backup.sql": legacy_sql})
        self.pull()
        # The current remote must still be a complete V3 snapshot.
        self.assertEqual(
            self.sync.reconcile_database()["code"], "database_check_failed"
        )
        with snapshot(self.db) as conn:
            conn.execute("INSERT INTO songs(id,title) VALUES(2,'Desktop addition')")
            conn.commit()
            current_sql = sql_dump(conn)
        self.remote_change({"database_backup.sql": current_sql})
        self.pull()
        result = self.accept_remote()
        self.assertEqual(result["code"], "database_updated", result)
        self.assertEqual(self.count(), 2)

    def test_receipt_corruption_fails_closed_when_data_differs(self):
        self.pair()
        self.edit(self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'New')")
        self.publish()
        self.pull()
        before = self.state()
        receipt = next(
            p
            for p in self.sync.state_dir.glob("database_*.json")
            if p.name != "database_status.json"
        )
        receipt.write_text("{broken")
        self.assertEqual(
            self.sync.reconcile_database()["code"], "database_check_failed"
        )
        self.assertEqual(self.state(), before)

    def test_fresh_check_separates_current_code_from_newer_remote_database(self):
        self.pair()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Remote new song')"
        )
        self.publish()
        self.pull()
        result = self.sync.check()
        self.assertTrue(result["ok"], result)
        state = result["git"]
        self.assertEqual(state["state"], "up_to_date")
        self.assertEqual(state["database_sync"]["code"], "database_conflict")
        self.assertFalse(state["upload_ready"])
        self.assertEqual(state["status_source"], "checked")
        self.assertIn("checked_at", state)
        self.assertEqual(self.sync.status()["status_source"], "cached")

    def test_fresh_check_allows_live_local_additions_with_stale_sql_file(self):
        self.pair()
        self.edit(self.db, "INSERT INTO songs(id,title) VALUES(2,'Local new song')")
        result = self.sync.check()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["git"]["database_sync"]["code"], "database_local_ahead")
        self.assertTrue(result["git"]["upload_ready"])
        self.assertTrue(self.sync.upload()["ok"])

    def test_numbered_devices_are_stable_across_three_installations(self):
        self.pair()
        identity, registry = DatabaseSync(
            self.sync, self.sync.inspect()
        ).remote_identity()
        self.assertEqual(identity["device"], 1)
        self.assertEqual(len(registry), 1)
        self.edit(self.desktop_db, "UPDATE songs SET title='Device two'")
        self.publish()
        third = self.folder / "third"
        command(self.folder, "clone", str(self.remote), str(third))
        self.identity(third)
        third_db = third / "live.db"
        bootstrap_sql(third_db, third / "database_backup.sql")
        three = GitSync(third, third_db)
        self.assertTrue(three.reconcile_database()["ok"])
        self.edit(third_db, "UPDATE songs SET title='Device three'")
        self.assertTrue(three.upload()["ok"])
        three.discover()
        ident, devices = DatabaseSync(three, three.inspect()).remote_identity()
        self.assertEqual(ident["device"], 3)
        self.assertEqual(sorted(devices.values()), [1, 2, 3])
        reviewed = self.sync.local_choice_review()
        self.assertEqual(reviewed["details"]["remote_device"], 3)
        self.assertTrue(self.sync.keep_local(reviewed["choice"])["ok"])
        self.assertTrue(self.sync.upload()["ok"])
        ident, devices = DatabaseSync(self.sync, self.sync.inspect()).remote_identity()
        self.assertEqual(ident["device"], 1)
        self.assertEqual(sorted(devices.values()), [1, 2, 3])
        self.assertIn("device: 1", self.sync.sql.read_text().splitlines()[0])
        self.assertIn(ident["committed_at"], self.sync.sql.read_text().splitlines()[0])

    def test_copied_git_identity_on_another_host_gets_a_new_device_number(self):
        self.assertTrue(self.sync.upload()["ok"])
        policy = DatabaseSync(self.sync, self.sync.inspect())
        first = policy.device_key()
        with patch(
            "songranker.storage.git_database.uuid.getnode", return_value=123456789
        ):
            self.assertNotEqual(policy.device_key(), first)
            self.edit(self.db, "UPDATE songs SET title='Another physical host'")
            self.assertTrue(self.sync.upload()["ok"])
            identity, registry = DatabaseSync(
                self.sync, self.sync.inspect()
            ).remote_identity()
            self.assertEqual(identity["device"], 2)
            self.assertEqual(len(registry), 2)
        self.assertEqual(policy.device_key(), first)
        self.edit(self.db, "UPDATE songs SET title='Original host again'")
        self.assertTrue(self.sync.upload()["ok"])
        self.assertEqual(
            DatabaseSync(self.sync, self.sync.inspect()).remote_identity()[0]["device"],
            1,
        )

    def test_manual_sql_commit_preserves_existing_device_number_allocations(self):
        self.pair()
        self.edit(self.desktop_db, "UPDATE songs SET title='Second device'")
        self.publish()
        # A manual SQL edit has an unknown author device but must not reset numbering.
        sql = command(self.remote, "show", "main:database_backup.sql").replace(
            "Second device", "Manual change"
        )
        self.remote_change({"database_backup.sql": sql})
        reviewed = self.sync.local_choice_review()
        self.assertIsNone(reviewed["details"]["remote_device"])
        self.assertTrue(self.sync.keep_local(reviewed["choice"])["ok"])
        self.assertTrue(self.sync.upload()["ok"])
        identity, registry = DatabaseSync(
            self.sync, self.sync.inspect()
        ).remote_identity()
        self.assertEqual(identity["device"], 1)
        self.assertEqual(sorted(registry.values()), [1, 2])

    def test_same_device_remote_ahead_trusts_local_edits_and_deletions(self):
        self.assertTrue(self.sync.upload()["ok"])
        self.edit(
            self.db, "INSERT INTO songs(id,title) VALUES(2,'Previously uploaded')"
        )
        self.assertTrue(self.sync.upload()["ok"])
        self.edit(self.db, "DELETE FROM songs WHERE id=2")
        # Lose the receipt to prove writer identity is independent of Git ancestry.
        DatabaseSync(self.sync, self.sync.inspect()).receipt_path.unlink()
        (self.sync.state_dir / "history.json").unlink()
        checked = self.sync.check()
        d = checked["git"]["database_sync"]
        self.assertEqual(d["reason"], "same_device")
        self.assertEqual(d["code"], "database_local_ahead")
        self.assertTrue(checked["git"]["upload_ready"])
        self.assertTrue(self.sync.upload()["ok"])
        restored = self.folder / "last.db"
        bootstrap_sql(restored, self.sync.sql)
        self.assertEqual(self.count(restored), 1)

    def test_remote_baseline_hash_allows_local_changes_despite_incoming_code(self):
        self.pair()
        self.remote_change({"app.py": "incoming code only"})
        self.edit(self.db, "UPDATE songs SET title='Local edit'")
        checked = self.sync.check()
        d = checked["git"]["database_sync"]
        self.assertEqual(d["remote_hash"], d["baseline_hash"])
        self.assertNotEqual(d["local_hash"], d["remote_hash"])
        self.assertEqual(d["reason"], "remote_unchanged")
        self.assertTrue(checked["git"]["upload_ready"])
        self.assertTrue(self.sync.upload()["ok"])
        self.assertIn("old", (self.work / "app.py").read_text())
        self.assertEqual(
            command(self.remote, "show", "main:app.py"), "incoming code only"
        )

    def test_different_device_requires_review_even_when_remote_covers_local(self):
        self.pair()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Other device')"
        )
        self.publish()
        before = self.state()
        result = self.sync.startup()
        self.assertEqual(result["code"], "updated")
        self.assertEqual(result["database_sync"]["code"], "database_conflict")
        self.assertEqual(self.state(), before)
        reviewed = self.sync.local_choice_review()
        details = reviewed["details"]
        self.assertEqual(details["reason"], "different_device")
        self.assertEqual(details["remote_device"], 2)
        self.assertEqual(details["different_rows"]["songs"]["removed"], 1)
        self.assertEqual(details["baseline_hash"], details["local_hash"])
        self.assertFalse(self.sync.upload()["ok"])
        self.assertTrue(self.sync.use_remote(reviewed["choice"])["ok"])
        self.assertEqual(self.count(), 2)

    def test_explicit_remote_choice_rejects_stale_local_and_remote(self):
        self.pair()
        self.edit(self.desktop_db, "UPDATE songs SET title='Remote'")
        self.publish()
        reviewed = self.sync.local_choice_review()
        self.edit(self.db, "UPDATE songs SET title='Later local'")
        before = self.state()
        self.assertEqual(
            self.sync.use_remote(reviewed["choice"])["code"], "stale_database"
        )
        self.assertEqual(self.state(), before)
        reviewed = self.sync.local_choice_review()
        self.edit(self.desktop_db, "UPDATE songs SET title='Later remote'")
        self.publish()
        self.assertEqual(
            self.sync.use_remote(reviewed["choice"])["code"], "stale_database"
        )
        self.assertEqual(self.state(), before)

    def test_local_write_while_building_upload_is_rechecked_before_push(self):
        self.pair()
        self.edit(self.db, "UPDATE songs SET title='Reviewed'")
        original = self.sync.run

        def racing(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[0] == "commit-tree":
                self.edit(self.db, "UPDATE songs SET title='Concurrent write'")
            return result

        old = command(self.remote, "rev-parse", "main")
        with patch.object(self.sync, "run", side_effect=racing):
            result = self.sync.upload()
        self.assertEqual(result["code"], "stale_database")
        self.assertEqual(command(self.remote, "rev-parse", "main"), old)
        with readonly(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT title FROM songs").fetchone()[0],
                "Concurrent write",
            )

    def test_remote_move_during_push_is_rejected_then_recompared(self):
        self.pair()
        self.edit(self.db, "UPDATE songs SET title='Pending local'")
        original = self.sync.run
        moved = []

        def racing(*args, **kwargs):
            if args[0] == "push" and not moved:
                self.remote_change({"app.py": "concurrent remote code"})
                moved.append(command(self.remote, "rev-parse", "main"))
            return original(*args, **kwargs)

        with patch.object(self.sync, "run", side_effect=racing):
            result = self.sync.upload()
        self.assertEqual(result["code"], "push_failed")
        self.assertEqual(command(self.remote, "rev-parse", "main"), moved[0])
        self.assertTrue(self.sync.upload()["ok"])
        self.assertEqual(
            command(self.remote, "show", "main:app.py"), "concurrent remote code"
        )

    def test_removed_remote_snapshot_is_a_reviewable_conflict(self):
        self.pair()
        self.remote_change({"database_backup.sql": "-- removed snapshot"})
        before = self.state()
        result = self.sync.check()
        self.assertEqual(result["git"]["database_sync"]["code"], "database_conflict")
        self.assertFalse(result["git"]["upload_ready"])
        self.assertEqual(self.sync.upload()["code"], "database_conflict")
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
