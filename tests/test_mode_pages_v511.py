"""Page/data contracts: real templates and real subjective facts in disposable DBs."""
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_mode_updates_v51 import fixture
from songranker.version import APP_VERSION
from songranker import services
from songranker.modes import judgement_pages
from songranker.modes.judgements import get_offer, save_answer
from songranker.reports.judgement_page_data import build_judgement_page
from songranker.reports.global_stats_data import build_global_stats

PATHS = {'spotlight': '/shared_spotlight', 'vibe': '/vibe_map'}


class ModePagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'pages.db'
        fixture(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.addCleanup(self.conn.close)
        patcher = patch.object(services, 'DB_NAME', str(self.db))
        patcher.start(); self.addCleanup(patcher.stop)
        self.client = services.app.test_client()
        self.rng = random.Random(511)

    def answer(self, mode, **fields):
        offer = get_offer(self.conn, 'page-test', mode, self.rng)
        defaults = dict(allocations=[5,4,2,1]) if mode == 'spotlight' else dict(
            maps=[dict(map='mood',x=1,y=4),dict(map='sound',x=2,y=0)], themes=[1])
        receipt = save_answer(self.conn, 'page-test', mode, dict(token=offer['token'], **(fields or defaults)))
        return offer, receipt

    def test_four_empty_pages_are_read_only_and_render(self):
        before = self.db.read_bytes()
        for mode, path in PATHS.items():
            for url in (path, path+'_stats'):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertIn(APP_VERSION.encode(), response.data)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM judgement_rounds').fetchone()[0], 0)

    def test_game_assets_and_navigation_are_complete(self):
        response = self.client.get('/vibe_map')
        for name in ['js/listening.js','js/round_flow.js','js/judgement_game.js']:
            self.assertIn(name.encode(), response.data)
        for path in PATHS.values():
            self.assertIn(('href="'+path+'"').encode(), response.data)
            self.assertIn(('href="'+path+'_stats"').encode(), response.data)
        stats = self.client.get('/vibe_map_stats').data
        self.assertNotIn(b'js/judgement_game.js', stats)
        self.assertNotIn(b'js/listening.js', stats)
        self.assertIn(b'css/stats_visuals.css', stats)

    def test_configuration_advertises_live_pages(self):
        result = self.client.get('/api/mode-updates').json
        self.assertFalse(result['backend_only'])
        self.assertEqual({r['play_url'] for r in result['modes']}, set(PATHS.values()))

    def test_spotlight_loads_relative_controller_without_a_heading_stats_link(self):
        spotlight = self.client.get('/shared_spotlight').get_data(as_text=True)
        vibe = self.client.get('/vibe_map').get_data(as_text=True)
        self.assertIn('js/spotlight.js', spotlight)
        self.assertLess(spotlight.index('js/spotlight.js'), spotlight.index('js/judgement_game.js'))
        self.assertIn('<div class="judgement-heading"><h1>Shared Spotlight</h1></div>', spotlight)
        self.assertNotIn('js/spotlight.js', vibe)
        self.assertIn('Stats ↗', vibe)
        self.assertIn('href="/shared_spotlight_stats"', spotlight)  # Dedicated stats remain in navigation.

    def test_all_saved_modes_render_without_public_tokens(self):
        for mode, path in PATHS.items():
            offer, _ = self.answer(mode)
            response = self.client.get(path+'_stats')
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn(offer['token'].encode(), response.data)
            self.assertNotIn(b'owner_hash', response.data)
            self.assertIn(b'Round history', response.data)

    def test_spotlight_leaders_and_distribution_use_real_facts(self):
        self.answer('spotlight')
        data = build_judgement_page(self.conn, 'spotlight')
        self.assertEqual(data['details']['points_shared'], 12)
        self.assertEqual(sum(r['count'] for r in data['details']['distribution']), 4)
        self.assertEqual(sum(r['points']*r['count'] for r in data['details']['distribution']), 12)
        self.assertEqual(len(data['details']['leaders']), 4)
        self.assertTrue(all(r['song']['id'] == r['song_id'] for r in data['details']['leaders']))

    def test_vibe_independent_maps_search_and_unknown_tables(self):
        offer, _ = self.answer('vibe')
        data = build_judgement_page(self.conn, 'vibe', map_key='sound', query=offer['songs'][0]['title'])
        self.assertEqual(data['details']['placements'], 2)
        self.assertEqual(data['selected_map']['key'], 'sound')
        self.assertEqual(data['track_total'], 1)
        self.assertEqual(data['track_rows'][0]['y'], 0)
        empty = build_judgement_page(self.conn, 'vibe', map_key='craft')
        self.assertEqual(empty['track_total'], 0)
        self.assertEqual(empty['selected_map']['placements'], 0)
        self.assertEqual(build_judgement_page(self.conn, 'vibe', map_key='unknown')['selected_map']['key'], 'mood')

    def test_vibe_history_keeps_unreviewed_and_none_separate(self):
        self.answer('vibe', maps=[dict(map='craft',x=0,y=0)])
        self.answer('vibe', maps=[dict(map='craft',x=1,y=2)], themes=[])
        response = self.client.get('/vibe_map_stats')
        self.assertIn(b'Tags: not reviewed', response.data)
        self.assertIn(b'Tags: reviewed, none selected', response.data)
        self.assertIn(b'1 rounds with tags reviewed', response.data)

    def test_renamed_tags_keep_saved_label_and_current_link(self):
        self.answer('vibe')
        self.conn.execute("UPDATE genres SET name='Renamed tag' WHERE id=1"); self.conn.commit()
        response = self.client.get('/vibe_map_stats')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/tag/Renamed%20tag', response.data)
        self.assertIn(b'>sad-pop</a>', response.data)

    def test_history_is_paged_and_bounds_checked(self):
        for _ in range(12): self.answer('spotlight')
        first = build_judgement_page(self.conn, 'spotlight')
        second = build_judgement_page(self.conn, 'spotlight', history_page=2)
        self.assertEqual(len(first['history']), 10)
        self.assertEqual(len(second['history']), 2)
        self.assertFalse({r['id'] for r in first['history']} & {r['id'] for r in second['history']})
        self.assertEqual(self.client.get('/shared_spotlight_stats?history_page=999').status_code, 200)
        for suffix in ['history_page=-1','history_page=no','track_page=0']:
            self.assertEqual(self.client.get('/vibe_map_stats?'+suffix).status_code, 400)

    def test_untrusted_catalogue_and_search_text_is_escaped(self):
        self.conn.execute('UPDATE songs SET title=?', ('<script>window.bad=1</script>',))
        self.conn.execute('UPDATE genres SET description=?', ('</script><img onerror=bad()>',)); self.conn.commit()
        self.answer('vibe')
        game = self.client.get('/vibe_map').data
        self.assertNotIn(b'</script><img onerror=bad()>', game)
        stats = self.client.get('/vibe_map_stats?q=%22%3E%3Cscript%3E').data
        self.assertNotIn(b'<script>window.bad=1</script>', stats)
        self.assertIn(b'&lt;script&gt;', stats)

    def test_global_feed_and_overview_include_all_new_modes(self):
        for mode in PATHS: self.answer(mode)
        result = build_global_stats(self.conn)
        self.assertTrue(set(PATHS).issubset({r['kind'] for r in result['recent_activity']}))
        self.assertTrue(all(result['mode_updates'][m]['rounds'] == 1 for m in PATHS))
        response = self.client.get('/global_stats')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'class="mode-activity spotlight"', response.data)

    def test_builders_run_under_a_write_denial(self):
        for mode in PATHS: self.answer(mode)
        before = self.conn.total_changes
        def authorize(action, *_):
            return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE) else sqlite3.SQLITE_OK
        self.conn.set_authorizer(authorize)
        for mode in PATHS: build_judgement_page(self.conn, mode)
        self.assertEqual(self.conn.total_changes, before)


if __name__ == '__main__':
    unittest.main()
