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

    def test_diagnostics_match_production_anchor_weights_without_writes(self):
        """Selection health uses the same recency and own-mode balance rules."""
        from songranker.reports.health import build_selection_health
        self.conn.execute('BEGIN')
        record_preference(self.conn, 1, 2, 'standard', {sid:dict(id=sid) for sid in (1, 2)})
        self.conn.commit()
        self.offer(1)
        self.conn.execute("UPDATE preference_offers SET song1_id=3,song2_id=4")
        self.conn.commit()
        before = capture(self.conn)
        report = build_selection_health(self.conn, dict(preference_owner='browser'))
        standard = next(p for p in report['pools'] if p['key'] == 'standard')
        rows = S.with_catalogue_age(self.conn, self.conn.execute('SELECT * FROM songs ORDER BY id'))
        other = {i:0 for i in range(1, 5)}
        weights = S.voting_weights(rows, S.mode_counts(self.conn, 'standard'), other, [(3, 4)])
        weights[2] = weights[3] = 0
        total = sum(weights)
        for row in standard['rows']:
            self.assertAlmostEqual(row['probability'], weights[row['id'] - 1] / total)
        self.assertEqual(capture(self.conn), before)

    def bracket(self, tid, ids, blind=False, status='in_progress', scope='global', scope_id=None):
        """Save a bracket's unique entrants without manufacturing match results."""
        self.conn.execute("INSERT INTO tournaments(id,size,is_blind,status,scope_type,scope_id) VALUES(?,8,?,?,?,?)",
                          (tid, blind, status, scope, scope_id))
        self.conn.executemany('INSERT INTO tournament_entries(tournament_id,song_id,seed) VALUES(?,?,?)',
                              [(tid, sid, seed) for seed, sid in enumerate(ids, 1)])

    def test_tournament_counts_split_visibility_and_count_entries_once(self):
        self.bracket(1, [1, 2, 3, 4], blind=True)
        self.bracket(2, [1, 2, 5, 6], status='completed')
        rows = list(map(dict, self.conn.execute('SELECT * FROM songs ORDER BY id')))
        before = capture(self.conn)
        evidence = S.tournament_selection_evidence(self.conn, rows, True)
        self.assertEqual(evidence['counts'], {1:1, 2:1, 3:1, 4:1})
        self.assertEqual(evidence['other_counts'], {1:1, 2:1, 3:0, 4:0})
        self.assertEqual(evidence['recent'], [(1, 2, 5, 6), (1, 2, 3, 4)])
        self.assertEqual(capture(self.conn), before)
        standard = S.tournament_selection_evidence(self.conn, rows, False)
        self.assertEqual(standard['counts'][5], 1)
        self.assertNotIn(5, standard['other_counts'])

    def test_tournament_history_ignores_unrelated_scopes_and_scales_group_age(self):
        self.bracket(1, [1, 2, 3, 4])
        self.bracket(2, [5, 6, 7, 8])
        rows = list(map(dict, self.conn.execute('SELECT * FROM songs WHERE id<=4')))
        evidence = S.tournament_selection_evidence(self.conn, rows, False)
        self.assertEqual(evidence['recent'], [(1, 2, 3, 4)])
        pool = [dict(id=i, elo_score=1200) for i in range(1000)]
        small_group = S.voting_weights(pool, recent=[tuple(range(8)), (50, 51)])[50]
        large_group = S.voting_weights(pool, recent=[tuple(range(32)), (50, 51)])[50]
        self.assertGreater(large_group, small_group)

    def test_tournament_draw_soft_balance_unique_and_full_pool_fallback(self):
        rows = [dict(id=i, elo_score=1200) for i in range(100)]
        counts, other = {i:20 for i in range(100)}, {i:20 for i in range(100)}
        other[0] = 0
        rng = random.Random(5631)
        for _ in range(100):
            chosen = S.tournament_tracks(rows, 8, rng, counts=counts, other_counts=other,
                                          recent=[tuple(range(1, 9))])
            self.assertEqual(len({s['id'] for s in chosen}), 8)
            self.assertNotIn(0, {s['id'] for s in chosen})
        self.assertEqual(len(S.tournament_tracks(rows[:8], 8, rng, counts=counts,
                                                other_counts=other, recent=[tuple(range(8))])), 8)
        self.assertIsNone(S.tournament_tracks(rows[:7], 8))

    def test_tournament_diagnostics_match_entry_weights(self):
        from songranker.reports.health import build_selection_health
        self.bracket(1, [1, 2, 3, 4], blind=True)
        self.bracket(2, [3, 4, 5, 6])
        rows = S.with_catalogue_age(self.conn, self.conn.execute('SELECT * FROM songs ORDER BY id'))
        evidence = S.tournament_selection_evidence(self.conn, rows, False)
        weights = S.voting_weights(rows, **evidence, fallback='tournament_entries')
        before = capture(self.conn)
        report = build_selection_health(self.conn)
        tournament = next(p for p in report['pools'] if p['key']=='tournament')
        for row in tournament['rows']:
            self.assertAlmostEqual(row['probability'], weights[row['id']-1]/sum(weights))
        self.assertEqual(capture(self.conn), before)

    def test_bracket_route_passes_visibility_evidence_and_preserves_eligibility(self):
        from songranker import services
        from songranker.modes import tournament
        self.bracket(1, [1, 2, 3, 4], blind=True)
        self.conn.commit()
        path = self.conn.execute('PRAGMA database_list').fetchone()[2]
        with patch.object(services, 'DB_NAME', path), \
             patch.object(tournament, 'tournament_tracks', wraps=S.tournament_tracks) as draw:
            client = services.app.test_client()
            result = client.get('/api/generate_bracket?size=8', content_type='application/json')
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(draw.call_args.kwargs['other_counts'][1], 1)
            self.assertNotIn(5, draw.call_args.kwargs['other_counts'])
            self.assertEqual(client.get('/api/generate_bracket?size=8&is_blind=true', content_type='application/json').status_code, 400)
            self.conn.execute("UPDATE songs SET audio_url='preview'")
            self.conn.commit()
            result = client.get('/api/generate_bracket?size=8&is_blind=true', content_type='application/json')
            self.assertEqual(result.status_code, 200, result.json)
            tid = result.json['tournament_id']
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM tournament_entries WHERE tournament_id=?',
                                               (tid,)).fetchone()[0], 8)

    def test_local_entries_and_results_leave_competition_weights_and_draws_unchanged(self):
        self.conn.executemany('INSERT INTO songs(id,title,audio_url) VALUES(?,?,?)',[(i,f'Track {i}','preview') for i in range(9,17)])
        self.conn.execute('UPDATE song_details SET added_at=0')
        self.bracket(1,[5,6],scope='global')
        self.bracket(2,[3,4],blind=True,scope='tag',scope_id=1)
        rows=list(map(dict,self.conn.execute('SELECT * FROM songs ORDER BY id')))
        baseline={}
        for scope in ('global','tag'):
            for blind in (False,True):
                e=S.tournament_selection_evidence(self.conn,rows,blind,scope=scope,scope_id=1 if scope=='tag' else None)
                baseline[scope,blind]=e
                self.assertEqual(e['recent'],[(3,4),(5,6)])
        from songranker.reports.health import build_selection_health
        health=build_selection_health(self.conn)
        probabilities={p['key']:p['rows'] for p in health['pools'] if p['key'] in ('tournament','tournament_blind')}
        self.bracket(3,[1,2,3,4],blind=True,status='completed',scope='artist',scope_id=1)
        self.bracket(4,[1,2,3,4],blind=True,scope='album',scope_id=1)
        self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status) VALUES(3,1,1,1,2,1,2,'completed')")
        self.assertTrue(S.preference_evidence(self.conn)[1],'local results remain available to local seeding')
        before=capture(self.conn)
        for (scope,blind),expected in baseline.items():
            actual=S.tournament_selection_evidence(self.conn,rows,blind,scope=scope,scope_id=1 if scope=='tag' else None)
            self.assertEqual(actual,expected)
            self.assertEqual(S.voting_weights(rows,**actual),S.voting_weights(rows,**expected))
            for seed in range(10):
                a=S.tournament_tracks(rows,8,random.Random(seed),**actual)
                b=S.tournament_tracks(rows,8,random.Random(seed),**expected)
                self.assertEqual([s['id'] for s in a],[s['id'] for s in b])
        after=build_selection_health(self.conn)
        self.assertEqual(probabilities,{p['key']:p['rows'] for p in after['pools'] if p['key'] in probabilities})
        self.assertEqual(capture(self.conn),before)

    def test_local_visibility_and_recency_use_only_the_selected_collection(self):
        self.bracket(1,[1,2],blind=True,scope='artist',scope_id=1)
        self.bracket(2,[3,4],scope='album',scope_id=1)
        self.bracket(3,[1,3],scope='artist',scope_id=2)
        self.bracket(4,[1,2],scope='global')
        self.bracket(5,[1,2],blind=True,scope='tag',scope_id=1)
        rows=list(map(dict,self.conn.execute('SELECT * FROM songs ORDER BY id')))
        a=S.tournament_selection_evidence(self.conn,rows,True,scope='artist',scope_id=1)
        self.assertEqual(a['counts'],{1:1,2:1})
        self.assertEqual(a['other_counts'],{1:0,2:0,3:0,4:0})
        self.assertEqual(a['recent'],[(1,2)])
        b=S.tournament_selection_evidence(self.conn,rows,False,scope='album',scope_id=1)
        self.assertEqual(b['counts'],{3:1,4:1})
        self.assertEqual(b['recent'],[(3,4)])
        c=S.tournament_selection_evidence(self.conn,rows,False,scope='artist',scope_id=2)
        self.assertEqual(c['counts'],{1:1,3:1})
        with self.assertRaises(ValueError):
            S.tournament_selection_evidence(self.conn,rows,False,scope='artist')

    def test_route_never_uses_local_seed_results_for_library_or_tag(self):
        from songranker import services
        from songranker.modes import tournament
        self.conn.execute("INSERT INTO albums(id,title) VALUES(1,'Album')")
        self.conn.execute("INSERT INTO artists(id,name) VALUES(1,'Artist')")
        self.conn.execute("INSERT INTO genres(id,name) VALUES(1,'Tag')")
        self.conn.execute('UPDATE songs SET album_id=1')
        self.conn.execute('INSERT INTO song_artists SELECT id,1 FROM songs')
        self.conn.execute('INSERT INTO song_genres SELECT id,1 FROM songs')
        self.conn.commit()
        path=self.conn.execute('PRAGMA database_list').fetchone()[2]
        local={1:1,2:-1}
        with patch.object(services,'DB_NAME',path),patch.object(S,'preference_evidence',return_value=({},local)) as evidence,patch.object(tournament,'tournament_tracks',wraps=S.tournament_tracks) as draw:
            client=services.app.test_client()
            for scope in ('global','tag'):
                result=client.get('/api/generate_bracket',query_string=dict(size=8,scope=scope,scope_id=1),content_type='application/json')
                self.assertEqual(result.status_code,200,result.json)
                self.assertIsNone(draw.call_args.kwargs['local_strength'])
            evidence.assert_not_called()
            for scope in ('artist','album'):
                result=client.get('/api/generate_bracket',query_string=dict(size=8,scope=scope,scope_id=1),content_type='application/json')
                self.assertEqual(result.status_code,200,result.json)
                self.assertEqual(draw.call_args.kwargs['local_strength'],local)
                self.assertEqual(draw.call_args.kwargs['counts'],{})
            self.assertEqual(evidence.call_count,2)
