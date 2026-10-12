"""Existing empty entities and nullable trivia fields retain usable stats pages."""
import shutil
import unittest
import test_app

class Patch327Checks(unittest.TestCase):
 def setUp(self):
  shutil.copyfile(test_app.ROOT/'song_ranker_v2.db',test_app.TMP/'active.db')
  test_app.services.init_db();self.c=test_app.main.app.test_client()
 def test_empty_profiles_render_and_missing_records_still_404(self):
  db=test_app.services.get_db_connection()
  try:
   db.execute("INSERT INTO artists(name) VALUES('Empty artist V327')")
   db.execute("INSERT INTO albums(title) VALUES('Empty album V327')");db.commit()
  finally:db.close()
  for kind in ['artist','album']:
   response=self.c.get('/'+kind+'/Empty%20'+kind+'%20V327')
   self.assertEqual(response.status_code,200)
   self.assertIn('id="profile-data"',response.text)
   self.assertEqual(self.c.get('/'+kind+'/Missing%20record%20V327').status_code,404)
 def test_trivia_stats_keep_field_denominators_and_null_album(self):
  db=test_app.services.get_db_connection()
  try:
   sid=db.execute('SELECT id FROM songs LIMIT 1').fetchone()[0]
   db.execute('DELETE FROM trivia_rounds');db.execute('DELETE FROM trivia_adjustments')
   db.execute('''INSERT INTO trivia_rounds(token,song_id,album_available,started_at,completed_at,
                 title_correct,artist_correct,album_correct,title_seconds,user_score_after,streak_after)
                 VALUES('v327-stats',?,0,1700000000,1700000030,1,0,NULL,3,.7,1)''',(sid,))
   db.commit()
  finally:db.close()
  response=self.c.get('/trivia_stats');self.assertEqual(response.status_code,200)
  self.assertIn('aria-label="Album: not applicable"',response.text)
  self.assertIn('data-trivia-field="title"',response.text);self.assertIn('data-trivia-field="album"',response.text)
  self.assertIn('1 correct',response.text);self.assertIn('1 missed',response.text)
  self.assertIn('100%',response.text);self.assertIn('0%',response.text)
  self.assertIn('Best streak 🔥',response.text);self.assertIn('data-timestamp="1700000030',response.text)
  self.assertNotIn('None score',response.text)
