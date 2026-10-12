import unittest,sqlite3,shutil
from pathlib import Path
import test_app as fixture
from catalog import collection,ranked,aggregate_performance,voting_records
from database import migrate
from trivia import trivia_match

class Patch324Checks(unittest.TestCase):
 setUp=fixture.AppChecks.setUp
 db=fixture.AppChecks.db
 admin=fixture.AppChecks.admin
 def songs(self):
  with self.db() as c:
   c.execute("INSERT INTO albums(title) VALUES('V324 record')");album=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   c.execute("INSERT INTO artists(name) VALUES('V324 artist')");artist=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   ids=[]
   for title in ('Track A','Track B','Track C'):
    c.execute('INSERT INTO songs(title,album_id,matches_played) VALUES(?,?,999)',(title,album));ids.append(c.execute('SELECT last_insert_rowid()').fetchone()[0])
   for sid in ids[:2]:c.execute('INSERT INTO song_artists VALUES(?,?)',(sid,artist))
  return ids,album,artist
 def history(self,ids):
  a,b,c=ids
  with self.db() as db:
   for w,l,mode in [(a,b,'standard'),(a,b,'standard'),(b,a,'standard'),(a,c,'blind'),(c,a,'blind'),(c,a,'blind'),(a,b,'legacy_tournament'),(b,a,'unknown'),(a,a,'blind')]:
    db.execute('INSERT INTO history(winner_id,loser_id,mode) VALUES(?,?,?)',(w,l,mode))
 def test_song_rates_ignore_unlabelled_and_tournament_votes(self):
  ids,_,_=self.songs();self.history(ids)
  rows={s['id']:s for s in collection()['songs']};v=rows[ids[0]]['voting']
  self.assertEqual((v['wins'],v['losses'],v['matches'],v['win_rate']),(3,3,6,50))
  self.assertAlmostEqual(v['standard_win_rate'],200/3);self.assertAlmostEqual(v['blind_win_rate'],100/3)
  self.assertEqual((v['standard_wins'],v['blind_wins']),(2,1))
  self.assertNotEqual(v['matches'],rows[ids[0]]['matches_played'])
 def test_group_rates_pool_unique_songs_including_internal_matches(self):
  ids,album,artist=self.songs();self.history(ids);data=collection()
  grouped=next(a for a in ranked(data,'artists') if a['id']==artist)['voting']
  self.assertEqual((grouped['wins'],grouped['losses']),(4,5));self.assertAlmostEqual(grouped['win_rate'],400/9)
  rows=[s for s in data['songs'] if s['id'] in ids[:2]]
  self.assertEqual(aggregate_performance(rows+[rows[0]])['voting'],grouped)
  self.assertEqual(next(a for a in ranked(data,'albums') if a['id']==album)['voting']['win_rate'],50)
 def test_unplayed_has_no_rate_and_global_has_mode_leaders(self):
  ids,_,_=self.songs();data={s['id']:s for s in collection()['songs']}
  self.assertIsNone(data[ids[0]]['voting']['win_rate']);self.assertEqual(data[ids[0]]['voting']['wins'],0)
  self.history(ids);response=self.c.get('/global_stats');self.assertEqual(response.status_code,200)
  self.assertIn(b'Voting Results',response.data);self.assertIn(b'Highest track win rates',response.data)
 def test_bracket_notes_optional_but_core_title_must_match(self):
  cases=[('After Hours','After Hours (Deluxe Edition)','album'),('City Lights','City Lights (feat. A Very Long Artist Name)','title'),('Night Drive','Night Drive [with Another Artist]','title'),('Main Title','Main Title (Deluxe (Expanded))','album'),('city light','City Lights (feat. Juniper)','title')]
  for guess,actual,field in cases:self.assertTrue(trivia_match(guess,actual,field),(guess,actual))
  self.assertFalse(trivia_match('Blue (feat. A Very Long Artist Name)','Red (feat. A Very Long Artist Name)','title'))
  self.assertFalse(trivia_match('Deluxe','After Hours (Deluxe)','album'))
  self.assertFalse(trivia_match('(feat. Juniper)','City Lights (feat. Juniper)','title'))
  self.assertFalse(trivia_match('Other Track','City Lights (feat. Juniper)','title'))
  self.assertTrue(trivia_match('(Intro)','(Intro)','title'))
 def test_schema6_backup_retains_rounds_corrections_and_live_records(self):
  ids,_,_=self.songs();path=fixture.TMP/'v324_migration.db';shutil.copyfile(fixture.TMP/'active.db',path)
  with sqlite3.connect(path) as c:
   c.execute("INSERT INTO trivia_rounds(token,song_id,album_available,completed_at,title_correct,artist_correct,album_correct,user_score_after,streak_after) VALUES('retained',?,1,1,1,0,1,.8,1)",(ids[0],))
   c.execute('DROP VIEW trivia_stats');c.execute('DROP TABLE trivia_adjustments')
   c.execute('CREATE TABLE trivia_legacy(song_id INTEGER PRIMARY KEY,attempts INTEGER,correct INTEGER,new_attempts_delta INTEGER,title_correct_delta INTEGER,artist_correct_delta INTEGER,album_attempts_delta INTEGER,album_correct_delta INTEGER)')
   c.execute('INSERT INTO trivia_legacy VALUES(?,10,19,2,1,2,1,0)',(ids[0],))
   c.execute('CREATE VIEW trivia_stats AS SELECT song_id,attempts,correct FROM trivia_legacy')
   c.execute("INSERT OR REPLACE INTO global_stats VALUES('trivia_legacy_high_score',999)");c.execute("UPDATE global_stats SET value=4.5 WHERE key='trivia_high_score'");c.execute('PRAGMA user_version=5')
   before_rounds=c.execute('SELECT * FROM trivia_rounds').fetchall();before_songs=c.execute('SELECT * FROM songs').fetchall()
  migrate(path)
  with sqlite3.connect(path) as c:
   self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],8)
   self.assertEqual(c.execute('SELECT * FROM trivia_rounds').fetchall(),before_rounds);self.assertEqual(c.execute('SELECT * FROM songs').fetchall(),before_songs)
   self.assertFalse(c.execute("SELECT 1 FROM sqlite_master WHERE name='trivia_legacy'").fetchone())
   self.assertFalse(c.execute("SELECT 1 FROM global_stats WHERE key='trivia_legacy_high_score'").fetchone())
   self.assertEqual(c.execute("SELECT value FROM global_stats WHERE key='trivia_high_score'").fetchone()[0],4.5)
   self.assertEqual(c.execute('SELECT attempts,correct,available_points FROM trivia_stats WHERE song_id=?',(ids[0],)).fetchone(),(3,5,8))
   self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
  backups=list((path.parent/'database_backups').glob('pre_upgrade_*.db'))
  self.assertTrue(any(sqlite3.connect(p).execute("SELECT 1 FROM sqlite_master WHERE name='trivia_legacy'").fetchone() for p in backups))
  first=path.read_bytes();migrate(path);self.assertEqual(first,path.read_bytes())
 def test_manual_field_corrections_sparse_and_clearable(self):
  ids,_,_=self.songs();self.admin();sid=ids[0]
  counts=dict(new_attempts=3,title_correct=2,artist_correct=3,album_attempts=2,album_correct=1)
  self.assertEqual(self.c.post(f'/api/dev/trivia/{sid}',json=counts).status_code,200)
  with self.db() as c:self.assertEqual(c.execute('SELECT attempts,correct,available_points FROM trivia_stats WHERE song_id=?',(sid,)).fetchone(),(3,6,8))
  self.assertEqual(self.c.post(f'/api/dev/trivia/{sid}',json=dict(new_attempts=0,title_correct=0,artist_correct=0,album_attempts=0,album_correct=0)).status_code,200)
  with self.db() as c:self.assertFalse(c.execute('SELECT 1 FROM trivia_adjustments WHERE song_id=?',(sid,)).fetchone())
  self.assertEqual(self.c.post(f'/api/dev/trivia/{sid}',json={'legacy_attempts':3}).status_code,400)
 def test_trivia_api_credits_unbracketed_answers_keeps_canonical(self):
  ids,album,_=self.songs()
  with self.db() as c:
   c.execute("UPDATE songs SET audio_url=NULL");c.execute("UPDATE songs SET title='City Lights (feat. A Very Long Artist Name)',audio_url='https://example.test/audio' WHERE id=?",(ids[0],));c.execute("UPDATE albums SET title='After Hours (Deluxe)' WHERE id=?",(album,))
  state=self.c.get('/api/trivia/round').json;url=f"/api/trivia/{state['token']}";self.c.post(url+'/start',json={})
  song=self.c.post(url+'/field',json={'field':'title','guess':'City Lights'}).json
  self.assertTrue(song['fields']['title']['correct']);self.assertEqual(song['fields']['title']['actual'],'City Lights (feat. A Very Long Artist Name)')
  result=self.c.post(url+'/finish',json={'guesses':{'album':'After Hours'}}).json
  self.assertTrue(result['fields']['album']['correct']);self.assertEqual(result['fields']['album']['actual'],'After Hours (Deluxe)')
