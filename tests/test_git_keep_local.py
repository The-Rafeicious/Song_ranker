"""Explicit database choice, backed up and bound to exact local/remote revisions."""

from unittest.mock import patch
import unittest
import test_git_database as fixture
from songranker.storage.database_io import readonly, capture
from songranker.storage.git_database import DatabaseSync


class KeepLocalTests(unittest.TestCase):
    setUp = fixture.GitDatabaseTests.setUp
    identity = fixture.GitDatabaseTests.identity
    head = fixture.GitDatabaseTests.head
    state = fixture.GitDatabaseTests.state
    remote_change = fixture.GitDatabaseTests.remote_change
    pair = fixture.GitDatabaseTests.pair
    edit = fixture.GitDatabaseTests.edit
    publish = fixture.GitDatabaseTests.publish
    pull = fixture.GitDatabaseTests.pull
    count = fixture.GitDatabaseTests.count
    accept_remote = fixture.GitDatabaseTests.accept_remote

    def changed_remote(self):
        self.pair()
        self.edit(
            self.desktop_db, "INSERT INTO songs(id,title) VALUES(2,'Remote-only')"
        )
        self.edit(
            self.desktop_db,
            "UPDATE song_vibe_positions SET status='placed',x=.7,y=-.7,updated_at=1,sample_count=1 WHERE song_id=1",
        )
        self.publish()

    def test_keep_wiped_local_before_restart_then_upload_without_importing_vibes(self):
        self.changed_remote()
        before = self.state()
        reviewed = self.sync.local_choice_review(self.sync.status()["fingerprint"])
        self.assertTrue(reviewed["ok"], reviewed)
        self.assertEqual(reviewed["remote"]["Vibe positions"], 4)
        self.assertEqual(reviewed["local"]["Vibe positions"], 0)
        self.assertEqual(self.state(), before)
        chosen = self.sync.keep_local(reviewed["choice"])
        self.assertTrue(chosen["ok"], chosen)
        self.assertEqual(self.state(), before)
        with readonly(self.db.parent / "database_backups" / chosen["backup"]) as saved:
            self.assertEqual(capture(saved), before)
        with readonly(
            self.db.parent / "database_backups" / chosen["incoming_backup"]
        ) as saved:
            self.assertEqual(
                saved.execute("SELECT COUNT(*) FROM songs").fetchone()[0], 2
            )
        self.assertTrue(self.sync.startup()["ok"])
        self.assertEqual(self.sync.reconcile_database()["code"], "database_local_ahead")
        self.assertEqual(self.state(), before)
        self.assertTrue(self.sync.upload()["ok"])
        review = self.other.local_choice_review()
        self.assertTrue(self.other.use_remote(review["choice"])["ok"])
        self.assertEqual(self.count(self.desktop_db), 1)
        with readonly(self.desktop_db) as c:
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) FROM song_vibe_positions WHERE status='placed'"
                ).fetchone()[0],
                0,
            )

    def test_local_or_remote_change_invalidates_choice(self):
        self.changed_remote()
        r = self.sync.local_choice_review()
        self.edit(self.db, "UPDATE songs SET title='New local edit' WHERE id=1")
        before = self.state()
        result = self.sync.keep_local(r["choice"])
        self.assertFalse(result["ok"])
        self.assertEqual(self.state(), before)
        r = self.sync.local_choice_review()
        self.edit(
            self.desktop_db, "UPDATE songs SET title='New remote edit' WHERE id=1"
        )
        self.publish()
        result = self.sync.keep_local(r["choice"])
        self.assertFalse(result["ok"])
        self.assertEqual(self.state(), before)
        self.assertFalse(self.sync.upload()["ok"])

    def test_missing_choice_receipt_recovers_acknowledgement_from_bound_history(self):
        self.changed_remote()
        r = self.sync.local_choice_review()
        self.assertTrue(self.sync.keep_local(r["choice"])["ok"])
        state = self.sync.inspect()
        DatabaseSync(self.sync, state).receipt_path.unlink()
        self.sync.startup()
        self.assertEqual(self.sync.reconcile_database()["code"], "database_local_ahead")

    def test_failed_backup_cannot_accept_choice(self):
        self.changed_remote()
        r = self.sync.local_choice_review()
        before = self.state()
        with patch(
            "songranker.storage.database_io.create_backup",
            side_effect=OSError("Disk full"),
        ):
            self.assertFalse(self.sync.keep_local(r["choice"])["ok"])
        self.sync.startup()
        self.assertEqual(self.sync.reconcile_database()["code"], "database_conflict")
        self.assertEqual(self.state(), before)
