"""Connecting receipts, database invariants, legacy retention and transport."""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_mode_updates_v51 import fixture
from songranker.modes.shared_spotlight import allocate
from songranker.modes.judgements import get_offer, save_answer, JudgementError
from songranker.reports.judgement_stats_data import spotlight_stats
from songranker.storage.database import migrate
from songranker.storage.database_schema import SCHEMA_VERSION
from songranker.storage.database_io import capture, populate, reconcile


class ConnectingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'connecting.db'
        fixture(self.path)
        self.c = sqlite3.connect(self.path)
        self.c.row_factory = sqlite3.Row
        self.c.execute('PRAGMA foreign_keys=ON')
        self.addCleanup(self.c.close)

    def offer(self, owner='connecting'):
        return get_offer(self.c, owner, 'spotlight', random.Random(12))

    def test_reference_examples_and_strict_input(self):
        for positions, points in [
            ([0]*4,[0]*4),([20]*4,[1]*4),([50]*4,[3]*4),
            ([80]*4,[5]*4),([100]*4,[6]*4),
            ([100,0,0,0],[12,0,0,0]),([80,60,40,20],[7,4,2,0])]:
            self.assertEqual(allocate(positions),points)
        for invalid in [None,[],[True,0,0,0],[0.0]*4,[101]*4,[-1]*4]:
            with self.assertRaises(ValueError): allocate(invalid)

    def test_positions_are_facts_scores_are_server_owned_and_retries_are_exact(self):
        offer = self.offer()
        self.assertEqual(offer['rules_version'],2)
        payload = dict(token=offer['token'],rules_version=2,positions=[80,60,40,20])
        receipt = save_answer(self.c,'connecting','spotlight',payload)
        self.assertEqual(receipt['allocations'],[7,4,2,0])
        self.assertEqual(receipt['positions'],payload['positions'])
        self.assertEqual(receipt['points_awarded'],13)
        self.assertTrue(save_answer(self.c,'connecting','spotlight',payload)['replayed'])
        with self.assertRaises(JudgementError):
            save_answer(self.c,'connecting','spotlight',dict(payload,positions=[81,60,40,20]))
        self.assertEqual(spotlight_stats(self.c)['points_awarded'],13)
        from songranker.reports.global_stats_data import build_global_stats
        feed = build_global_stats(self.c)['recent_activity']
        self.assertEqual(next(r['details'] for r in feed if r['kind']=='spotlight'),
                         '13 points awarded')
        before = capture(self.c)
        target = sqlite3.connect(':memory:')
        try:
            populate(target,before)
            reconcile(before,capture(target))
        finally: target.close()

    def test_client_cannot_supply_points_or_downgrade_a_new_offer(self):
        offer = self.offer()
        for fields in [dict(rules_version=2,positions=[50]*4,allocations=[12]*4),
                       dict(rules_version=1,allocations=[3]*4),
                       dict(rules_version=2,positions=[50,50,None,50])]:
            with self.assertRaises(JudgementError):
                save_answer(self.c,'connecting','spotlight',dict(token=offer['token'],**fields))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM spotlight_allocations').fetchone()[0],0)

    def test_database_rejects_scores_that_disagree_with_positions(self):
        offer = self.offer()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.c:
                self.c.executemany('INSERT INTO spotlight_positions VALUES(?,?,?)',
                    [(offer['id'],i,0) for i in range(4)])
                self.c.executemany('INSERT INTO spotlight_allocations VALUES(?,?,?)',
                    [(offer['id'],i,3) for i in range(4)])
                self.c.execute("""UPDATE judgement_rounds SET status='answered',
                    closed_at=created_at,answer_hash=? WHERE id=?""",('a'*64,offer['id']))
        self.assertEqual(self.offer()['status'],'open')

    def test_zero_and_maximum_rounds_are_valid_and_totals_are_actual(self):
        for x in [0,100]:
            offer=self.offer()
            receipt=save_answer(self.c,'connecting','spotlight',
                dict(token=offer['token'],rules_version=2,positions=[x]*4))
            self.assertEqual(receipt['points_awarded'],24 if x else 0)
        self.assertEqual(spotlight_stats(self.c)['points_awarded'],24)

    def test_schema17_upgrade_preserves_legacy_receipts_and_pending_offers(self):
        # Build the previous registry in a disposable file, then run real migration.
        from songranker.storage.database_schema import SCHEMA_PATH
        schema=SCHEMA_PATH.read_text()
        schema=schema[:schema.index('-- Coordinates are original')] + schema[schema.index('CREATE TABLE IF NOT EXISTS vibe_placements'):]
        schema=schema.replace("CHECK(rules_version IN (1,2) AND (mode='spotlight' OR rules_version=1))",
                              "CHECK(rules_version=1)")
        # New close trigger is not needed while constructing historical facts.
        schema=schema[:schema.index('-- A closed receipt must')]
        old=Path(self.tmp.name)/'old.db'
        conn=sqlite3.connect(old);conn.row_factory=sqlite3.Row
        conn.executescript(schema)
        for sid in range(1,5):
            conn.execute('INSERT INTO songs(id,title,audio_url) VALUES(?,?,?)',(sid,str(sid),'preview'))
        for rid in (1,2):
            conn.execute('INSERT INTO judgement_rounds(id,token,owner_hash,mode,created_at) VALUES(?,?,?,?,?)',
                (rid,str(rid)*32,'a'*64 if rid==1 else 'b'*64,'spotlight',1))
            for slot in range(4):
                conn.execute('INSERT INTO judgement_items VALUES(?,?,?,?,?)',
                    (rid,slot,slot+1,slot+1,'{"title":"old","artist":"old"}'))
        for slot in range(4):conn.execute('INSERT INTO spotlight_allocations VALUES(?,?,?)',(1,slot,3))
        conn.execute("UPDATE judgement_rounds SET status='answered',closed_at=2,answer_hash=? WHERE id=1",('c'*64,))
        conn.execute('PRAGMA user_version=17');conn.commit()
        before=capture(conn);conn.close()
        migrate(old)
        conn=sqlite3.connect(old)
        try:
            reconcile(before,capture(conn))
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM spotlight_positions').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT SUM(points) FROM spotlight_allocations').fetchone()[0],12)
        finally:conn.close()
        self.assertTrue(list((old.parent/'database_backups').glob('pre_upgrade_*.db')))


if __name__=='__main__':unittest.main()
