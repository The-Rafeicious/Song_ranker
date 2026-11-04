"""Query opponent evidence survives retirement of the network UI."""
import unittest
from unittest.mock import patch
import test_elo_replay as fixture
from songranker import services
from songranker.modes.preferences import record_preference
from songranker.reports.query import match_records
from songranker.storage.database_io import capture


class QueryMatchEvidenceTests(unittest.TestCase):
    setUp = fixture.EloReplayTests.setUp
    vote = fixture.EloReplayTests.vote

    def bracket(self, tid, scope='global', status='completed', blind=False):
        """Store a finished or private bracket with explicit scope/visibility."""
        self.conn.execute('INSERT INTO tournaments(id,size,scope_type,status,is_blind) VALUES(?,8,?,?,?)',(tid,scope,status,blind))

    def match(self, tid, winner, loser, round_no=1):
        """Store a decided match; Elo can be attached separately for first-round dedup."""
        index=self.conn.execute('SELECT COUNT(*) FROM tournament_matches WHERE tournament_id=?',(tid,)).fetchone()[0]+1
        return self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status,points_awarded,played_at) VALUES(?,?,?,?,?,?,?,'completed',1.5,'2026-11-01 12:00:00')",(tid,round_no,index,winner,loser,winner,loser)).lastrowid

    def raw_votes(self, pairs):
        """Seed large legacy-style effective history without recalculating Elo."""
        self.conn.executemany("INSERT INTO preference_events(winner_id,loser_id,mode,origin,created_at) VALUES(?,?,'standard','ordinary','2026-11-01 11:00:00')",pairs)

    def test_first_round_is_once_later_round_has_no_invented_elo_and_local_is_explicit(self):
        self.vote(7,8)
        self.bracket(1,blind=True);mid=self.match(1,7,6)
        record_preference(self.conn,7,6,'blind',{7:dict(id=7),6:dict(id=6)},tournament_id=1,tournament_match_id=mid)
        self.match(1,6,7,2)
        self.bracket(2,'artist');self.match(2,7,5)
        self.bracket(3,status='in_progress',blind=True);pending=self.match(3,7,4)
        record_preference(self.conn,7,4,'blind',{7:dict(id=7),4:dict(id=4)},tournament_id=3,tournament_match_id=pending)
        self.conn.commit()
        before=capture(self.conn)
        rows, omitted = match_records(self.conn, {i: {} for i in range(1,9)})
        self.assertEqual(len(rows), 3)
        self.assertEqual(omitted, 0)
        self.assertEqual(len(match_records(self.conn, {i: {} for i in range(1,9)}, include_local=True)[0]), 4)
        first=next(r for r in rows if r['source']=='first_round')
        self.assertIsNotNone(first['winner_after'])
        later=next(r for r in rows if r['source']=='tournament')
        self.assertIsNone(later['winner_after'])
        self.assertEqual(later['points'], 2)
        self.assertEqual(capture(self.conn), before)
