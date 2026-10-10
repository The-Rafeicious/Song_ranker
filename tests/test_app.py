import sys,os,sqlite3,shutil,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TMP=Path(tempfile.mkdtemp(prefix='song_ranker_tests_'))
shutil.copyfile(ROOT/'song_ranker_v2.db',TMP/'active.db')
os.environ['SONG_RANKER_DB']=str((TMP/'active.db').resolve())
import main,services,dev,games
ORIGINAL=next(p for p in (ROOT/'database_backups').glob('pre_upgrade_*.db') if sqlite3.connect(p).execute("SELECT COUNT(*) FROM sqlite_master WHERE name='elo_history'").fetchone()[0])
from catalog import collection,ranked,proper_album
from database import migrate
class AppChecks(unittest.TestCase):
 def setUp(self):
  shutil.copyfile(ROOT/'song_ranker_v2.db',TMP/'active.db')
  export_root=patch.object(services,'ROOT',TMP);export_root.start();self.addCleanup(export_root.stop)
  self.c=main.app.test_client();main.app.config['TESTING']=True
 def db(self):return sqlite3.connect(TMP/'active.db')
 def admin(self):
  with self.c.session_transaction() as s:s['is_admin']=True
 def test_all_pages_and_entities(self):
  data=collection()
  paths=['/','/game','/leaderboard','/artists','/albums','/search','/history','/global_stats','/trivia','/trivia_stats','/tournament','/tournament_stats','/tiers','/tags','/dev/login']
  from urllib.parse import quote
  paths+=['/song/'+str(data['songs'][0]['id']),'/artist/'+quote(data['artists'][0]['name']),'/album/'+quote(data['albums'][0]['title']),'/tag/'+quote(data['tags'][0]['name'])]
  self.admin();paths+=['/dev/dashboard']
  for path in paths:
   with self.subTest(path=path):self.assertEqual(self.c.get(path).status_code,200)
  self.assertEqual(self.c.get('/song/999999').status_code,404)
 def test_migration_preserves_domain_rows(self):
  old=TMP/'original.db';shutil.copyfile(ORIGINAL,old)
  before=sqlite3.connect(old);snapshot={t:before.execute(f'SELECT * FROM {t}').fetchall() for t in ['songs','artists','albums','song_artists','song_genres','tournaments','tournament_entries','tournament_matches','global_stats']};trivia=before.execute('SELECT SUM(attempts),SUM(correct) FROM trivia_stats').fetchone();before.close()
  migrate(old);after=sqlite3.connect(old)
  for table,rows in snapshot.items():self.assertEqual(after.execute(f'SELECT * FROM {table}').fetchall(),rows,table)
  self.assertEqual(after.execute('SELECT SUM(attempts),SUM(correct) FROM trivia_stats').fetchone(),trivia)
  tables={r[0] for r in after.execute("SELECT name FROM sqlite_master WHERE type='table'")};self.assertFalse(tables&{'admin_audit_log','interaction_events','elo_history'})
  history=after.execute('SELECT winner_before,winner_after,loser_before,loser_after FROM history').fetchone();self.assertEqual(history,(1200,1216,1200,1184))
  self.assertEqual(after.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertFalse(after.execute('PRAGMA foreign_key_check').fetchall());after.close()
  first=old.read_bytes();migrate(old);self.assertEqual(old.read_bytes(),first)
 def test_regular_and_blind_votes(self):
  a,b=collection()['songs'][:2]
  total=a['elo_score']+b['elo_score']
  for mode in ['standard','blind']:
   r=self.c.post('/api/vote',json={'winner_id':a['id'],'loser_id':b['id'],'mode':mode});self.assertEqual(r.status_code,200)
   self.assertAlmostEqual(r.json['winner']['elo_score']+r.json['loser']['elo_score'],total)
  with self.db() as db:
   self.assertEqual(db.execute('SELECT COUNT(*) FROM history').fetchone()[0],3)
   self.assertEqual([r[0] for r in db.execute('SELECT mode FROM history ORDER BY id DESC LIMIT 2')],['blind','standard'])
   self.assertEqual(db.execute('SELECT matches_played FROM songs WHERE id=?',(a['id'],)).fetchone()[0],a['matches_played']+2)
   self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name IN ('elo_history','admin_audit_log','interaction_events')").fetchall())
  services.init_db();services.init_db()
  self.assertEqual(self.c.get('/api/collection').json['history'][0]['mode'],'blind')
 def test_bad_votes_leave_database_unchanged(self):
  a=collection()['songs'][0]['id'];before=collection()['history']
  for payload in [{},{'winner_id':a,'loser_id':a},{'winner_id':a,'loser_id':999999}]:self.assertIn(self.c.post('/api/vote',json=payload).status_code,(400,404))
  self.assertEqual(collection()['history'],before)
 def test_matchups_and_proper_albums(self):
  for mode in ['blind','standard']:
   r=self.c.get('/api/matchup?mode='+mode);self.assertEqual(r.status_code,200);a,b=r.json['songs'];self.assertNotEqual(a['id'],b['id']);self.assertIn('album',a);self.assertIn('album_is_single',a);self.assertNotIn('elo_score',a)
   if mode=='blind':self.assertTrue(a['audio_url'] and b['audio_url'])
  data=self.c.get('/api/library?type=albums&limit=200').json;self.assertEqual(data['total'],57)
  self.assertTrue(all(proper_album(r) for r in data['items']))
  for item in ranked(collection(),'albums'):
   ss=[s for s in collection()['songs'] if s['album_id']==item['id']];self.assertEqual(item['song_count'],len(ss));self.assertEqual(item['impact_score'],1200+sum(s['elo_score']-1200 for s in ss))
 def test_trivia_totals_and_high_score(self):
  song=ranked(collection(),'songs')[0]
  r=self.c.post('/api/trivia_guess',json={'song_id':song['id'],'title_guess':song['title'],'artist_guess':song['artist'],'time_taken':1});self.assertEqual(r.status_code,200);self.assertTrue(r.json['title_correct']);self.assertTrue(r.json['artist_correct'])
  with self.db() as db:self.assertEqual(db.execute('SELECT attempts,correct FROM trivia_stats WHERE song_id=?',(song['id'],)).fetchone(),(song['attempts']+1,song['correct']+2))
 def test_tournament_resume_complete_and_replay_guard(self):
  initial=collection();response=self.c.get('/api/generate_bracket?size=8');self.assertEqual(response.status_code,200);tid=response.json['tournament_id'];champ=None;first=None
  while True:
   detail=self.c.get(f'/api/tournaments/{tid}').json
   pending=[m for m in detail['matches'] if m['status']=='pending']
   if not pending:break
   for match in pending:
    vote={'tournament_id':tid,'match_id':match['id'],'winner_id':match['song1_id'],'loser_id':match['song2_id']}
    r=self.c.post('/api/tournament_vote',json=vote);self.assertEqual(r.status_code,200,r.json);champ=match['song1_id'];first=first or vote
  self.assertEqual(self.c.post('/api/tournament_vote',json=first).status_code,409)
  r=self.c.post('/api/tournament_complete',json={'tournament_id':tid,'champion_id':champ});self.assertEqual(r.status_code,200,r.json)
  self.assertTrue(self.c.post('/api/tournament_complete',json={'tournament_id':tid,'champion_id':champ}).json['already_completed'])
  now=collection();self.assertEqual([(s['id'],s['elo_score']) for s in initial['songs']],[(s['id'],s['elo_score']) for s in now['songs']]);self.assertEqual(len(now['history']),len(initial['history']));self.assertEqual(len([m for m in now['tournament_matches'] if m['tournament_id']==tid]),7)
 def test_dev_crud_and_stats(self):
  self.admin();data=collection();song=ranked(data,'songs')[0]
  r=self.c.post('/api/dev/edit_song/'+str(song['id']),json={'title':song['title'],'artist':song['artist'],'album':song['album'],'audio_url':song['audio_url'],'cover_url':song['cover_url'],'genres':'Test tag','track_number':17});self.assertEqual(r.status_code,200)
  with self.db() as db:self.assertEqual(db.execute('SELECT track_number FROM songs WHERE id=?',(song['id'],)).fetchone()[0],17)
  for typ,col in [('artist','artists'),('album','albums'),('genre','tags')]:
   item=collection()[col][0];payload={'name':item.get('name'),'title':item.get('title'),'cover_url':item.get('cover_url',''),'release_date':item.get('release_date','')};self.assertEqual(self.c.post(f'/api/dev/edit_{typ}/{item["id"]}',json=payload).status_code,200)
  self.assertEqual(self.c.post('/api/dev/elo-correction',json={'song_id':song['id'],'new_elo':1234}).status_code,200)
  self.assertEqual(self.c.post('/api/dev/trivia/'+str(song['id']),json={'attempts':3,'correct':6}).status_code,200)
  self.assertEqual(self.c.post('/api/dev/trivia/'+str(song['id']),json={'attempts':1,'correct':4}).status_code,400)
  self.assertEqual(self.c.delete('/api/dev/trivia/'+str(song['id'])).status_code,200)
  self.assertEqual(self.c.delete('/api/dev/delete_song/'+str(song['id'])).status_code,200)
  self.assertFalse(self.c.get('/api/dev/integrity').json['foreign_key_errors'])
 def test_apple_import_with_mocked_service(self):
  self.admin()
  with patch.object(dev.requests,'get',return_value=Mock(json=lambda:{'results':[{'trackName':'Test import','artistName':'Test artist','collectionName':'Test album','previewUrl':'https://example.org/audio.m4a'}]})):
   search=self.c.get('/api/dev/search_apple?q=test');self.assertEqual(search.status_code,200);row=search.json[0]
   self.assertEqual(self.c.post('/api/dev/add_song',json=row).status_code,200)
   self.assertEqual(self.c.post('/api/dev/add_song',json=row).status_code,400)
  self.assertTrue(any(s['title']=='Test import' for s in collection()['songs']))
 def test_backup_restore_reset(self):
  self.admin();original=collection();r=self.c.post('/api/dev/backup',json={});self.assertEqual(r.status_code,200);name=r.json['backup']
  self.assertEqual(self.c.post('/api/dev/reset-database',json={'confirmation':'no'}).status_code,400)
  r=self.c.post('/api/dev/reset-database',json={'confirmation':'RESET COMPETITION'});self.assertEqual(r.status_code,200,r.json)
  reset=collection();self.assertEqual(len(reset['songs']),389);self.assertFalse(reset['history']);self.assertFalse(reset['tournaments']);self.assertTrue(all(s['elo_score']==1200 and s['attempts']==0 for s in reset['songs']))
  r=self.c.post('/api/dev/restore-backup',json={'filename':name});self.assertEqual(r.status_code,200,r.json);self.assertEqual(collection(),original)
 def test_unsupported_restore_keeps_live_database(self):
  self.admin();before=collection();backups=TMP/'database_backups';backups.mkdir(exist_ok=True)
  shutil.copyfile(ROOT/'legacy_data/song_ranker.db',backups/'manual_old.db')
  r=self.c.post('/api/dev/restore-backup',json={'filename':'manual_old.db'});self.assertEqual(r.status_code,400);self.assertEqual(collection(),before)
 def test_active_bracket_delete_protection(self):
  self.admin();bracket=self.c.get('/api/generate_bracket?size=8').json;id=bracket['tracks'][0]['id']
  self.assertEqual(self.c.delete('/api/dev/delete_song/'+str(id)).status_code,409)
  self.assertEqual(self.c.delete('/api/dev/tournaments/'+str(bracket['tournament_id'])).status_code,200)
  self.assertEqual(self.c.delete('/api/dev/delete_song/'+str(id)).status_code,200)
  self.assertFalse(self.c.get('/api/dev/integrity').json['foreign_key_errors'])
 def test_dev_auth_and_export(self):
  self.assertEqual(self.c.get('/dev/dashboard').status_code,302);self.assertEqual(self.c.post('/api/dev/backup',json={}).status_code,302)
  self.admin();self.assertEqual(self.c.get('/api/dev/overview').status_code,200);self.assertEqual(self.c.get('/api/dev/activity').status_code,200);self.assertEqual(self.c.post('/api/dev/export',json={}).status_code,200)
  self.assertTrue((TMP/'database_snapshot.txt').is_file())
if __name__=='__main__':
 try: unittest.main(verbosity=2)
 finally: shutil.rmtree(TMP,ignore_errors=True)
