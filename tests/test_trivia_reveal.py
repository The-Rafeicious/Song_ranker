"""Prior field accuracy is frozen and revealed only with completed Trivia results."""
import importlib
import json
import unittest
from unittest.mock import patch
import test_preferences as fixture
from support import route_modules
from songranker import services
from songranker.modes import trivia as T
from songranker.storage.database_io import capture
for module in route_modules().values():
    importlib.import_module(module)


class TriviaRevealTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def offer(self):
        self.client=services.app.test_client()
        with patch.object(T,'choose_single',return_value=dict(id=1)):
            response=self.client.get('/api/trivia/round',headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def finish(self,offered,guesses=None):
        token=offered['token']
        self.assertEqual(self.client.post('/api/trivia/'+token+'/start',json={}).status_code,200)
        response=self.client.post('/api/trivia/'+token+'/finish',json=dict(guesses=guesses or {}))
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def test_prior_accuracy_uses_existing_fields_and_is_hidden_until_completion(self):
        self.conn.execute('INSERT INTO trivia_adjustments VALUES(1,2,1,2,1,1)');self.conn.commit()
        before=capture(self.conn)
        self.assertEqual(T.trivia_accuracy(self.conn,1),dict(accuracy=80,rounds=2))
        self.assertEqual(capture(self.conn),before)
        offered=self.offer();self.assertNotIn('previous_trivia',offered)
        frozen=json.loads(self.conn.execute('SELECT answer_snapshot FROM trivia_rounds WHERE token=?',(offered['token'],)).fetchone()[0])
        self.assertEqual(frozen['previous_trivia'],dict(accuracy=80,rounds=2))
        self.client.post('/api/trivia/'+offered['token']+'/start',json={})
        field=self.client.post('/api/trivia/'+offered['token']+'/field',json=dict(field='title',guess='not the song')).json
        self.assertNotIn('previous_trivia',field)
        result=self.client.post('/api/trivia/'+offered['token']+'/finish',json=dict(guesses={})).json
        self.assertTrue(result['completed']);self.assertEqual(result['previous_trivia'],dict(accuracy=80,rounds=2))
        self.assertEqual(T.trivia_accuracy(self.conn,1),dict(accuracy=50,rounds=3))
        self.assertEqual(self.client.post('/api/trivia/'+offered['token']+'/finish',json=dict(guesses={})).json['previous_trivia'],result['previous_trivia'])

    def test_first_attempt_has_no_previous_percentage_even_when_correct(self):
        offered=self.offer();result=self.finish(offered,dict(title='Song 1',artist='Artist, One',album='Album'))
        self.assertIsNone(result['previous_trivia'])
        self.assertGreater(result['round_points'],0)

    def test_real_zero_percent_history_is_not_treated_as_missing(self):
        self.conn.execute('INSERT INTO trivia_adjustments VALUES(1,1,0,0,1,0)');self.conn.commit()
        result=self.finish(self.offer())
        self.assertEqual(result['previous_trivia'],dict(accuracy=0,rounds=1))

    def test_album_not_applicable_uses_only_available_fields(self):
        self.conn.execute('INSERT INTO trivia_adjustments VALUES(1,1,1,1,0,0)');self.conn.commit()
        self.assertEqual(T.trivia_accuracy(self.conn,1),dict(accuracy=100,rounds=1))

    def test_old_snapshots_exclude_current_and_later_rounds_without_writes(self):
        for token,correct in [('earlier',1),('current',0),('later',1)]:
            self.conn.execute("""INSERT INTO trivia_rounds(token,song_id,album_available,started_at,completed_at,title_correct,artist_correct,album_correct,user_score_after,streak_after)
                VALUES(?,1,1,1,2,?,0,?,1,1)""",(token,correct,correct))
        self.conn.commit()
        row=self.conn.execute("SELECT * FROM trivia_rounds WHERE token='current'").fetchone()
        before=capture(self.conn)
        with services.app.test_request_context():result=T.payload(self.conn,row,True)
        self.assertEqual(result['previous_trivia'],dict(accuracy=66.7,rounds=1))
        self.assertEqual(capture(self.conn),before)
