import unittest, sqlite3
import test_app as fixture
import test_modes_v32 as modes
from catalog import collection

class PatchChecks(unittest.TestCase):
 setUp=fixture.AppChecks.setUp
 db=fixture.AppChecks.db
 admin=fixture.AppChecks.admin
 fixture=modes.ModeChecks.fixture
 ready=modes.ModeChecks.ready
 def populate(self):
  token,song=self.ready()
  self.c.post(f'/api/trivia/{token}/finish',json={'guesses':{'title':song['title']}})
  with self.db() as c:c.execute("UPDATE genres SET name='Trivia fixture tag' WHERE name='V32 tag'")
  ids,album,tag=self.fixture(8)
  tour=self.c.get(f'/api/generate_bracket?scope=tag&scope_id={tag}&size=8').json
  match=tour['matches'][0]
  self.c.post('/api/tournament_vote',json={'tournament_id':tour['tournament_id'],'match_id':match['id'],'winner_id':match['song1_id'],'loser_id':match['song2_id']})
  self.c.post('/api/vote',json={'winner_id':ids[0],'loser_id':ids[1]})
  self.admin()
 def snapshot(self):
  with self.db() as c:
   tables=['songs','albums','artists','genres','song_artists','song_genres','history','trivia_rounds','trivia_adjustments','tournaments','tournament_entries','tournament_matches','global_stats']
   return {table:c.execute('SELECT * FROM '+table).fetchall() for table in tables}
 def reset_case(self,scope):
  self.populate();before=self.snapshot()
  response=self.c.post('/api/dev/reset-history/'+scope,json={'confirmation':'RESET '+scope.upper()})
  self.assertEqual(response.status_code,200,response.json)
  after=self.snapshot()
  for table in ('albums','artists','genres','song_artists','song_genres'):self.assertEqual(before[table],after[table],table)
  if scope=='matches':
   for table in ('trivia_rounds','trivia_adjustments','tournaments','tournament_entries','tournament_matches','global_stats'):self.assertEqual(before[table],after[table],table)
   self.assertFalse(after['history'])
   self.assertTrue(all(s['elo_score']==1200 and s['matches_played']==0 and s['highest_elo']==1200 and s['highest_rank']==9999 for s in collection()['songs']))
   with self.db() as c:
    columns=[r[1] for r in c.execute('PRAGMA table_info(songs)')]
    excluded={'elo_score','matches_played','highest_elo','highest_rank'}
    self.assertEqual([[v for k,v in zip(columns,row) if k not in excluded] for row in before['songs']],[[v for k,v in zip(columns,row) if k not in excluded] for row in after['songs']])
  elif scope=='trivia':
   for table in ('songs','history','tournaments','tournament_entries','tournament_matches'):self.assertEqual(before[table],after[table],table)
   self.assertFalse(after['trivia_rounds']);self.assertFalse(after['trivia_adjustments'])
   records=dict(after['global_stats']);self.assertEqual(records['trivia_high_score'],0);self.assertEqual(records['trivia_high_streak'],0);self.assertEqual(records['trivia_scoring_version'],2)
   with self.c.session_transaction() as session:self.assertNotIn('trivia_score',session);self.assertNotIn('trivia_round_token',session)
   new=self.c.get('/api/trivia/round').json;self.assertEqual(new['score'],0);self.assertEqual(new['streak'],0)
  else:
   for table in ('history','trivia_rounds','trivia_adjustments','global_stats'):self.assertEqual(before[table],after[table],table)
   self.assertFalse(after['tournaments']);self.assertFalse(after['tournament_matches']);self.assertFalse(after['tournament_entries'])
   with self.db() as c:columns=[r[1] for r in c.execute('PRAGMA table_info(songs)')]
   keep=[i for i,name in enumerate(columns) if name!='tournament_wins']
   self.assertEqual([[row[i] for i in keep] for row in before['songs']],[[row[i] for i in keep] for row in after['songs']])
   self.assertTrue(all(row[columns.index('tournament_wins')]==0 for row in after['songs']))
  backup=fixture.TMP/'database_backups'/response.json['backup']
  with sqlite3.connect(backup) as c:
   for table in ('history','trivia_rounds','tournaments'):self.assertEqual(c.execute('SELECT * FROM '+table).fetchall(),before[table])
  with self.db() as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
 def test_match_reset_keeps_other_modes(self):self.reset_case('matches')
 def test_trivia_reset_keeps_other_modes(self):self.reset_case('trivia')
 def test_tournament_reset_keeps_other_modes(self):self.reset_case('tournaments')
 def test_reset_requires_admin_and_exact_scope_confirmation(self):
  before=self.snapshot();self.assertNotEqual(self.c.post('/api/dev/reset-history/trivia',json={'confirmation':'RESET TRIVIA'}).status_code,200);self.admin()
  self.assertEqual(self.c.post('/api/dev/reset-history/trivia',json={'confirmation':'RESET MATCHES'}).status_code,400)
  self.assertEqual(self.c.post('/api/dev/reset-history/unknown',json={'confirmation':'RESET UNKNOWN'}).status_code,400)
  self.assertEqual(before,self.snapshot())
 def test_answer_links_only_reveal_checked_fields(self):
  token,song=self.ready()
  state=self.c.get('/api/trivia/round').json;self.assertTrue(all(not f['links'] for f in state['fields'].values()))
  response=self.c.post(f'/api/trivia/{token}/field',json={'field':'artist','guess':'wrongwrongwrong'}).json
  self.assertFalse(response['fields']['artist']['correct']);self.assertTrue(response['fields']['artist']['links']);self.assertFalse(response['fields']['title']['links'])
  for link in response['fields']['artist']['links']:self.assertEqual(self.c.get(link['url']).status_code,200)
 def test_single_round_album_is_null(self):
  token,song=self.ready(True)
  result=self.c.post(f'/api/trivia/{token}/finish',json={'guesses':{'title':song['title'],'artist':song['artist'],'album':'nonsense'}}).json
  self.assertFalse(result['album_available']);self.assertNotIn('album',result['fields'])
  with self.db() as c:
   self.assertEqual(c.execute('SELECT album_correct,album_seconds,album_available FROM trivia_rounds WHERE token=?',(token,)).fetchone(),(None,None,0))
   self.assertEqual(c.execute('SELECT available_points FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone()[0],2)

if __name__=='__main__':unittest.main()
