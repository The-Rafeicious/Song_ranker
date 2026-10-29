"""Voting recency, per-track visibility balance and saved-history routing."""
import math
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from songranker.modes import selection as S
from songranker.modes.preferences import owner_hash, record_preference
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture


class VotingWeightTests(unittest.TestCase):
    def pool(self, size):
        """Build a uniform finite-rating pool with no freshness or Vibe bias."""
        return [dict(id=i, elo_score=1200, added_at=0) for i in range(size)]

    def test_visibility_gap_overrides_below_average_catchup_and_recovers(self):
        rows = self.pool(100)
        counts = {i: 100 for i in range(100)}
        counts[0] = counts[1] = 20
        other = dict(counts)
        other[0] = 0
        before = S.voting_weights(rows, counts, other)
        self.assertLess(before[0], before[1] / 1000000)
        other[0] = 18
        catching_up = S.voting_weights(rows, counts, other)
        self.assertGreater(catching_up[0], before[0])
        other[0] = 20
        self.assertAlmostEqual(S.voting_weights(rows, counts, other)[0], before[1])
        other[0] = 40
        self.assertGreater(S.voting_weights(rows, counts, other)[0], before[1])

    def test_equal_counts_are_uniform_and_mode_swap_reverses_pressure(self):
        rows = self.pool(8)
        self.assertEqual(S.voting_weights(rows, {i: 10 for i in range(8)},
                                         {i: 10 for i in range(8)}), [.125] * 8)
        a, b = {i: 10 for i in range(8)}, {i: 10 for i in range(8)}
        a[0], b[0] = 30, 2
        self.assertLess(S.voting_weights(rows, a, b)[0], .001)
        self.assertGreater(S.voting_weights(rows, b, a)[0], .125)

    def test_five_match_repeats_are_damped_and_penalty_fades(self):
        rows = self.pool(1000)
        weights = []
        for age in (0, 5, 10, 30, 127):
            recent = [(998, 999)] * age + [(0, 1)]
            weights.append(S.voting_weights(rows, recent=recent)[0])
        self.assertEqual(weights, sorted(weights))
        self.assertLess(weights[1], .001 * .04)
        self.assertGreater(weights[-1], .001 * .99)
        small = S.voting_weights(self.pool(10), recent=[(8, 9)] * 5 + [(0, 1)])[0]
        self.assertGreater(small / .1, weights[1] / .001)

    def test_both_slots_respect_balance_and_small_pools_remain_playable(self):
        rows = self.pool(20)
        counts = {i: 10 for i in range(20)}
        other = dict(counts)
        other[0] = other[1] = 0
        rng = random.Random(563)
        selected = [s['id'] for _ in range(1000) for s in
                    S.choose_match(rows, rng, counts=counts, other_counts=other)]
        self.assertNotIn(0, selected)
        self.assertNotIn(1, selected)
        pair = S.choose_match(rows[:2], rng, counts=counts, other_counts=other,
                              previous=(0, 1), recent=[(0, 1)] * 128)
        self.assertEqual({s['id'] for s in pair}, {0, 1})
        self.assertEqual(S.choose_match(rows[:1]), (None, None))
        for weight in S.voting_weights(rows, {i: 1e12 for i in range(20)},
                                      {i: 0 for i in range(20)}, [(0, 1)]):
            self.assertTrue(math.isfinite(weight) and weight > 0)

    def test_seeded_repeated_play_reduces_short_returns_without_stalling(self):
        rows = self.pool(120)
        def simulate(adaptive):
            """Count short returns while updating the same per-mode exposure facts."""
            rng, history = random.Random(563), []
            counts = {mode: {i: 0 for i in range(120)} for mode in ('blind', 'standard')}
            returns = 0
            for turn in range(800):
                mode = 'blind' if turn % 2 else 'standard'
                other = 'standard' if mode == 'blind' else 'blind'
                kwargs = dict(other_counts=counts[other], recent=history[:128]) if adaptive else {}
                pair = S.choose_match(rows, rng, counts=counts[mode],
                                      previous=history[0] if history else (), **kwargs)
                ids = tuple(s['id'] for s in pair)
                returns += sum(sid in {s for p in history[:6] for s in p} for sid in ids)
                for sid in ids:
                    counts[mode][sid] += 1
                history.insert(0, ids)
            gap = sum(abs(counts['blind'][i] - counts['standard'][i]) for i in range(120))
            return returns, gap
        old, new = simulate(False), simulate(True)
        self.assertLess(new[0], old[0] * .6)
        self.assertLess(new[1], old[1])


class VotingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'selection.db'
        initialize_database(path)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executemany('INSERT INTO songs(id,title,audio_url) VALUES(?,?,?)',
                              [(i, f'Track {i}', 'preview' if i <= 4 else '') for i in range(1, 9)])
        self.conn.commit()

    def offer(self, index, owner='browser', mode='standard', status='answered'):
        """Save presentation history without adding exposure or rating evidence."""
        self.conn.execute('''INSERT INTO preference_offers
            (token,owner_hash,song1_id,song2_id,mode,rules_version,status,
             closed_at,song1_snapshot,song2_snapshot) VALUES(?,?,1,2,?,1,?,?,'{}','{}')''',
            (str(index), owner_hash(owner), mode, status, f'2026-10-01 00:{index // 60:02}:{index % 60:02}'))

    def test_history_spans_modes_is_bounded_and_ignores_other_browsers_and_open_offers(self):
        for index in range(140):
            self.offer(index, mode='blind' if index % 2 else 'standard')
        self.offer(200, owner='another')
        self.offer(201, status='open')
        self.conn.execute("UPDATE preference_offers SET song1_id=3,song2_id=4 WHERE token='139'")
        recent = S.recent_preferences(self.conn, 'browser')
        self.assertEqual(len(recent), 128)
        self.assertEqual(recent[0], (3, 4))
        self.assertEqual(len(S.recent_preferences(self.conn, 'browser', 8)), 8)

    def test_fallback_uses_effective_saved_results_and_both_modes(self):
        for mode, pair in [('standard', (1, 2)), ('blind', (3, 4))]:
            self.conn.execute('BEGIN')
            record_preference(self.conn, *pair, mode, {sid:dict(id=sid) for sid in pair})
            self.conn.commit()
        self.assertEqual(S.recent_preferences(self.conn, 'fresh-browser'), [(3, 4), (1, 2)])

    def test_preview_eligibility_balance_inputs_and_reads_do_not_change_data(self):
        before = capture(self.conn)
        with patch.object(S, 'choose_match', return_value=(None, None)) as choose:
            S.preference_pair(self.conn, 'standard', 'browser')
            self.assertEqual(len(choose.call_args.args[0]), 8)
            self.assertEqual(set(choose.call_args.kwargs['other_counts']), {1, 2, 3, 4})
            S.preference_pair(self.conn, 'blind', 'browser')
            self.assertEqual(len(choose.call_args.args[0]), 4)
        self.assertEqual(capture(self.conn), before)

    def test_production_history_horizon_grows_with_eligible_collection(self):
        """The production reader scales its horizon and respects preview eligibility."""
        self.conn.executemany('INSERT INTO songs(id,title) VALUES(?,?)',
                              [(i, f'Track {i}') for i in range(9, 1025)])
        with patch.object(S, 'choose_match', return_value=(None, None)), \
             patch.object(S, 'recent_preferences', return_value=[]) as history:
            S.preference_pair(self.conn, 'standard', 'browser')
            self.assertEqual(history.call_args.kwargs['limit'], 128)
            S.preference_pair(self.conn, 'blind', 'browser')
            self.assertEqual(history.call_args.kwargs['limit'], 8)
