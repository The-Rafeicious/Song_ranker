import unittest, random, sqlite3, time, shutil
from collections import Counter
from unittest.mock import patch
import test_app as app_fixture
from test_app import TMP, ROOT, main, services
from selection import choose_match, tournament_tracks
from trivia import round_points
from catalog import collection, song_performance

class ModeChecks(unittest.TestCase):
 setUp=app_fixture.AppChecks.setUp
 db=app_fixture.AppChecks.db
 admin=app_fixture.AppChecks.admin
 def fixture(self, count=10):
  with self.db() as c:
   c.execute("INSERT INTO albums(title) VALUES('V32 Album')");album=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   c.execute("INSERT INTO genres(name) VALUES('V32 tag')");tag=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   ids=[]
   for i in range(count):
    c.execute('INSERT INTO songs(title,album_id,audio_url,elo_score,track_number) VALUES(?,?,?,?,?)',(f'Fixture Song {i}',album,'https://example.test/audio',1200+i*30,i+1));sid=c.execute('SELECT last_insert_rowid()').fetchone()[0];ids.append(sid)
    c.execute('INSERT INTO song_artists(song_id,artist_id) SELECT ?,MIN(id) FROM artists',(sid,));c.execute('INSERT INTO song_genres VALUES(?,?)',(sid,tag))
  return ids,album,tag
 def ready(self, single=False):
  ids,album,_=self.fixture(1)
  with self.db() as c:
   c.execute('UPDATE songs SET audio_url=NULL WHERE id!=?',(ids[0],))
   if single:c.execute("UPDATE albums SET title='V32 - Single' WHERE id=?",(album,))
  state=self.c.get('/api/trivia/round').json;token=state['token'];self.c.post(f'/api/trivia/{token}/start',json={})
  c=services.get_db_connection();song=dict(services.get_song_full(ids[0],c));c.close();return token,song
 def test_blur_grade_typo_lock_and_timeout_credit(self):
  token,song=self.ready();url=f'/api/trivia/{token}'
  self.assertEqual(self.c.post(url+'/field',json={'field':'title','guess':'fixture song 0'}).status_code,200)
  artist=self.c.post(url+'/field',json={'field':'artist','guess':song['artist'][:-1]});self.assertTrue(artist.json['fields']['artist']['correct'])
  wrong=self.c.post(url+'/field',json={'field':'album','guess':'zzzzzzzzzzzzzz'});self.assertFalse(wrong.json['fields']['album']['correct']);self.assertEqual(wrong.json['fields']['album']['actual'],song['album'])
  retry=self.c.post(url+'/field',json={'field':'album','guess':song['album']});self.assertFalse(retry.json['fields']['album']['correct'])
  with self.db() as c:c.execute('UPDATE trivia_rounds SET started_at=? WHERE token=?',(time.time()-31,token))
  result=self.c.post(url+'/finish',json={'guesses':{}}).json;self.assertEqual(result['streak'],1);self.assertLessEqual(result['round_points'],.7)
  again=self.c.post(url+'/finish',json={}).json;self.assertEqual(result['score'],again['score'])
  with self.db() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM trivia_rounds WHERE completed_at IS NOT NULL').fetchone()[0],1)
   self.assertEqual(c.execute('SELECT attempts,correct,available_points FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone(),(1,2,3))
  self.assertEqual(self.c.get('/trivia_stats').status_code,200)
 def test_timeout_marks_filled_unsubmitted_and_best_streak(self):
  token,song=self.ready();url=f'/api/trivia/{token}'
  with self.db() as c:c.execute('UPDATE trivia_rounds SET started_at=? WHERE token=?',(time.time()-40,token))
  result=self.c.post(url+'/finish',json={'guesses':{'title':song['title'],'album':song['album']}}).json
  self.assertTrue(result['fields']['title']['correct']);self.assertFalse(result['fields']['artist']['correct']);self.assertTrue(result['fields']['album']['correct']);self.assertAlmostEqual(result['round_points'],.6,places=3)
  state=self.c.get('/api/trivia/round').json;self.c.post(f"/api/trivia/{state['token']}/start",json={});result=self.c.post(f"/api/trivia/{state['token']}/finish",json={'guesses':{'artist':song['artist']}}).json
  self.assertEqual(result['high_streak'],2);self.assertEqual(result['streak'],2)
  state=self.c.get('/api/trivia/round').json;self.c.post(f"/api/trivia/{state['token']}/start",json={});result=self.c.post(f"/api/trivia/{state['token']}/finish",json={}).json
  self.assertTrue(result['game_over']);self.assertEqual(result['high_streak'],2)
 def test_single_has_two_fields_pause_and_resume(self):
  token,song=self.ready(True);url=f'/api/trivia/{token}';state=self.c.get('/api/trivia/round').json
  self.assertFalse(state['album_available']);self.assertNotIn('album',state['fields']);self.assertEqual(state['token'],token)
  with patch('trivia.time.time',return_value=time.time()+5):pause=self.c.post(url+'/pause',json={'paused':True}).json
  self.assertTrue(pause['paused']);self.assertEqual(self.c.post(url+'/field',json={'field':'artist','guess':song['artist']}).status_code,409)
  with patch('trivia.time.time',return_value=time.time()+20):resume=self.c.post(url+'/pause',json={'paused':False}).json
  self.assertLess(resume['elapsed'],6)
  final=self.c.post(url+'/finish',json={'guesses':{'artist':song['artist'],'title':song['title']}}).json
  self.assertGreater(final['round_points'],.9)
  with self.db() as c:self.assertEqual(c.execute('SELECT available_points FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone()[0],2)
 def test_scoring_weights_and_manual_field_edits(self):
  row={'album_available':1,**{f+'_correct':0 for f in ('title','artist','album')},**{f+'_seconds':10 for f in ('title','artist','album')}}
  values=[]
  for f in ('artist','album','title'):values.append(round_points({**row,f+'_correct':1}))
  self.assertTrue(values[0]<values[1]<values[2]);self.assertLessEqual(round_points({**row,**{f+'_correct':1 for f in ('title','artist','album')}}),1)
  token,song=self.ready();self.c.post(f'/api/trivia/{token}/finish',json={'guesses':{'title':song['title']}});self.admin()
  totals={'new_attempts':4,'title_correct':3,'artist_correct':2,'album_attempts':3,'album_correct':1}
  self.assertEqual(self.c.post(f"/api/dev/trivia/{song['id']}",json=totals).status_code,200)
  with self.db() as c:
   self.assertEqual(c.execute('SELECT attempts,correct,available_points FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone(),(4,6,11))
   self.assertEqual(c.execute('SELECT COUNT(*) FROM trivia_rounds').fetchone()[0],1)
  self.assertEqual(self.c.post(f"/api/dev/trivia/{song['id']}",json={**totals,'album_correct':4}).status_code,400)
  self.assertEqual(self.c.post('/api/dev/trivia-records',json={'high_score':3.5,'high_streak':7}).status_code,200)
  self.assertEqual(self.c.delete(f"/api/dev/trivia/{song['id']}").status_code,200)
  with self.db() as c:self.assertFalse(c.execute('SELECT 1 FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone())
 def test_bulk_atomic_conflicts_clear_positions_and_tags(self):
  ids,album,tag=self.fixture(3);self.admin()
  with self.db() as c:
   c.execute("INSERT INTO albums(title) VALUES('Target')");target=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   c.execute('INSERT INTO songs(title,album_id,track_number) VALUES(?,?,?)',('Occupied',target,1))
  data={'action':'move_album','song_ids':ids,'album_id':target}
  self.assertEqual(self.c.post('/api/dev/bulk_songs',json=data).status_code,400)
  with self.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM songs WHERE album_id=?',(album,)).fetchone()[0],3)
  self.assertEqual(self.c.post('/api/dev/bulk_songs',json={**data,'clear_track_numbers':True}).status_code,200)
  with self.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM songs WHERE album_id=? AND track_number IS NULL',(target,)).fetchone()[0],3)
  for action in ('remove_tags','add_tags','add_tags'):
   self.assertEqual(self.c.post('/api/dev/bulk_songs',json={'action':action,'song_ids':ids,'tag_ids':[tag]}).status_code,200)
  with self.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM song_genres WHERE genre_id=?',(tag,)).fetchone()[0],3)
  self.assertEqual(self.c.post('/api/dev/bulk_songs',json={'action':'add_tags','song_ids':ids+[999999],'tag_ids':[tag]}).status_code,400)
 def test_tag_tournament_bronze_before_final_and_podium_edits(self):
  ids,album,tag=self.fixture(8);original=collection();t=self.c.get(f'/api/generate_bracket?scope=tag&scope_id={tag}&size=8&is_blind=true').json;tid=t['tournament_id']
  self.assertEqual({s['id'] for s in t['tracks']},set(ids))
  vote=lambda m:self.c.post('/api/tournament_vote',json={'tournament_id':tid,'match_id':m['id'],'winner_id':m['song1_id'],'loser_id':m['song2_id']})
  for rnd in (1,2):
   for m in self.c.get(f'/api/tournaments/{tid}').json['matches']:
    if m['round_number']==rnd:self.assertEqual(vote(m).status_code,200)
  detail=self.c.get(f'/api/tournaments/{tid}').json;final=next(m for m in detail['matches'] if m['round_number']==3 and m['match_type']=='bracket');bronze=next(m for m in detail['matches'] if m['match_type']=='third_place')
  self.assertEqual(vote(final).status_code,409);self.assertEqual(vote(bronze).status_code,200);self.assertEqual(vote(final).status_code,200)
  self.assertEqual(self.c.post('/api/tournament_complete',json={'tournament_id':tid,'champion_id':final['song1_id']}).status_code,200)
  now=collection();tour=next(t for t in now['tournaments'] if t['id']==tid);self.assertEqual(tour['third_place_id'],bronze['song1_id']);self.assertEqual(tour['runner_up_id'],final['song2_id']);stats=song_performance(now)
  self.assertEqual(stats[bronze['song1_id']]['third_places'],1);self.assertEqual(stats[bronze['song1_id']]['runner_ups'],0);self.assertEqual(stats[final['song1_id']]['tournament_points'],7)
  self.assertEqual([s['elo_score'] for s in now['songs']],[s['elo_score'] for s in original['songs']]);self.assertEqual(now['history'],original['history'])
  self.admin();self.assertEqual(self.c.post(f'/api/dev/tournaments/{tid}/placements',json={'champion_id':final['song2_id'],'third_place_id':bronze['song2_id']}).status_code,200)
  tour=next(t for t in collection()['tournaments'] if t['id']==tid);self.assertEqual(tour['third_place_id'],bronze['song2_id']);self.assertEqual(tour['champion_id'],final['song2_id'])
 def test_schema_upgrade_backup_and_removed_flag(self):
  with self.db() as c:
   self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],8)
   self.assertNotIn('is_tournament_match',[r[1] for r in c.execute('PRAGMA table_info(history)')]);self.assertEqual(c.execute("SELECT type FROM sqlite_master WHERE name='trivia_stats'").fetchone()[0],'view');self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
  from database import migrate
  old=TMP/'v32_upgrade.db';shutil.copyfile(ROOT/'song_ranker_v2.db',old)
  with sqlite3.connect(old) as c:before=c.execute('SELECT SUM(attempts),SUM(correct) FROM trivia_stats').fetchone()
  migrate(old)
  with sqlite3.connect(old) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM trivia_stats').fetchone()[0],0)
  data=old.read_bytes();migrate(old);self.assertEqual(data,old.read_bytes())
 def test_soft_randomness_and_champions_spread(self):
  rng=random.Random(12);pool=[{'id':i,'elo_score':1200,'matches_played':0 if i<5 else 100} for i in range(10)];counts=Counter()
  for _ in range(5000):
   pair=choose_match(pool,rng);self.assertNotEqual(pair[0]['id'],pair[1]['id']);counts.update(s['id'] for s in pair)
  self.assertEqual(len(counts),10);self.assertGreater(sum(counts[i] for i in range(5)),sum(counts[i] for i in range(5,10))*1.7)
  from games import _tournament_seed_order
  pool=[{'id':i,'elo_score':1000+100*i,'tournament_matches':i,'championships':int(i<2)} for i in range(8)]
  for seed in range(25):
   selected=tournament_tracks(pool,8,random.Random(seed));order=_tournament_seed_order(8);positions=[order.index(next(i for i,s in enumerate(selected) if s['id']==champ)) for champ in (0,1)];self.assertNotEqual(positions[0]//4,positions[1]//4)

if __name__=='__main__':unittest.main()
