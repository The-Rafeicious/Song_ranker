"""Retired mode boundaries and adaptive four-family Overall calibration."""
import copy
import unittest
from unittest.mock import patch
from songranker import services, overall
from songranker.catalog import collection, special_records, profile_details
from songranker.storage.database_io import capture
import test_preferences as fixture
from support import route_modules

for module in route_modules().values():
    __import__(module)


class RetiredGuesserTests(unittest.TestCase):
    setUp = fixture.PreferenceTests.setUp
    connect = fixture.PreferenceTests.connect

    def test_retired_routes_and_active_projections_preserve_archive(self):
        self.conn.execute("INSERT INTO elo_guess_rounds(token,song1_id,song2_id,elo1,elo2,started_at,completed_at,chosen_slot) VALUES('archive',1,2,1300,1200,1,2,1)")
        self.conn.commit()
        before = capture(self.conn)
        with patch.object(services, 'DB_NAME', str(self.path)):
            client = services.app.test_client()
            for path in ['/elo_guesser', '/elo_guesser_stats', '/mode_rankings/guesser', '/api/elo-guesser/round']:
                self.assertEqual(client.get(path).status_code, 404, path)
            self.assertEqual(client.post('/api/elo-guesser/answer', json={}).status_code, 404)
            for path in ['/', '/global_stats', '/song/1', '/artist/Artist,%20One', '/query']:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertNotIn('Elo Guesser', response.get_data(as_text=True), path)
            self.assertEqual(client.get('/game?mode=guesser').status_code, 200)
            data = collection(True)
            self.assertNotIn('guesser', data['special_modes'])
            self.assertNotIn('guesser', profile_details(self.conn, {1}, 'songs', 1))
            clean = overall.evaluate(data, force=True)
            altered = copy.deepcopy(data)
            for song in altered['songs']:
                song.update(guess_attempts=100000, guess_correct=100000)
            changed = overall.evaluate(altered, force=True)
            self.assertEqual(clean['entities'], changed['entities'])
        self.assertNotIn('guesser', special_records(self.conn)[1])
        self.assertEqual(capture(self.conn), before)

    def test_configurable_caps_fill_active_and_eligible_family_sets(self):
        self.assertEqual(len(overall.FAMILIES), 4)
        bases = {name: sum(w for mode, _, w in overall.MODE_SPECS if mode in members)
                 for name, members in overall.FAMILIES.items()}
        self.assertEqual(set(bases.values()), {25})
        self.assertEqual(sum(bases.values()), 100)
        for count in range(1, 5):
            cap = overall.family_cap(count)
            weights = {str(i): 10000 if i == 0 else i + 1 for i in range(count)}
            shares = overall.capped_shares(weights, cap)
            self.assertAlmostEqual(sum(shares.values()), 1)
            self.assertLessEqual(max(shares.values()), cap + 1e-12)
        self.assertAlmostEqual(overall.family_cap(4), .35)
        with patch.object(overall, 'FAMILY_CAP_HEADROOM', .05):
            self.assertAlmostEqual(overall.family_cap(4), .30)
            self.assertAlmostEqual(overall.family_cap(2), .55)
        self.assertNotIn('guesser', {mode for mode, _, _ in overall.MODE_SPECS})

    def test_live_calibration_and_song_caps_keep_voting_one_family(self):
        fact = {key: overall.feature(1200 if kind == 'elo' else .7, 10000 if mode in overall.FAMILIES['voting'] else 2)
                for key, mode, _, _, kind in overall.METRICS}
        fact['mode_appearances'] = {mode: 10000 if mode in overall.FAMILIES['voting'] else 2
                                    for mode, _, _ in overall.MODE_SPECS}
        model = overall.calibrate({1: fact}, {}, force=True)
        self.assertAlmostEqual(sum(f['weight'] for f in model['families']), 100)
        self.assertAlmostEqual(next(f['weight'] for f in model['families'] if f['key'] == 'voting'), 35)
        for missing in [(), ('shelves',), ('shelves', 'trivia')]:
            eligible = copy.deepcopy(fact)
            for key, mode, _, _, _ in overall.METRICS:
                if mode in missing: eligible[key]['applicable'] = False
            result = overall.song_score(eligible, model, details=True)
            weights = {family: sum(c['weight'] for c in result['contributions'] if c['key'] in members)
                       for family, members in overall.FAMILIES.items()}
            self.assertAlmostEqual(sum(weights.values()), 100)
            self.assertLessEqual(max(weights.values()), 100 * overall.family_cap(4-len(missing)) + 1e-9)
