import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_app
from metadata_fill import plan_metadata, apply_plan, text_report, connection, artwork_key, paced_lookup, ScanStopped
from apple_access import AppleRequestError

ART='https://is1-ssl.mzstatic.com/image/thumb/Music126/v4/aabbccdd/unique-asset-12345/100x100bb.jpg'
ART_BIG=ART.replace('is1-ssl','is5-ssl').replace('100x100bb','600x600bb')

def remote(title='First', number=2, **extra):
    return dict(wrapperType='track',kind='song',trackName=title,artistName='Artist',collectionName='Album',
                collectionId=10,artworkUrl100=ART,trackNumber=number,trackCount=10,discNumber=1,discCount=1,**extra)

def album(**changes):
    row=dict(wrapperType='collection',collectionName='Album',artistName='Artist',collectionId=10,
             artworkUrl100=ART,releaseDate='2020-02-03T08:00:00Z');row.update(changes);return row

class MetadataChecks(unittest.TestCase):
    def setUp(self):
        self.dir=Path(tempfile.mkdtemp(prefix='metadata_test_'));self.addCleanup(shutil.rmtree,self.dir)
        self.path=self.dir/'active.db';self.db=sqlite3.connect(self.path)
        self.db.executescript('''CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT,release_date TEXT);
          CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,audio_url TEXT,track_number INTEGER,elo_score REAL);
          CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT);CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
          CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
          INSERT INTO artists VALUES(1,'Artist');INSERT INTO genres VALUES(1,'custom');
          INSERT INTO song_artists VALUES(1,1);''')
        self.db.execute('INSERT INTO albums VALUES(1,?,?,NULL)',('Album',ART_BIG))
        self.db.execute('INSERT INTO songs VALUES(1,?,1,?,NULL,1234)',('First','https://audio.example/unchanged.m4a'))
        self.db.commit();self.addCleanup(self.db.close);self.calls=[]
    def lookup(self,url):
        self.calls.append(url)
        return {'results':[album()] if '/search?' in url else [album(),remote(releaseDate='1999-01-01T00:00:00Z')]}
    def plan(self,lookup=None):return plan_metadata(self.path,lookup=lookup or self.lookup)
    def test_fill_only_real_positions_collection_date_and_backup(self):
        before=self.path.read_bytes();plan=self.plan();self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(plan['tracks'][0]['value'],2);self.assertEqual(plan['dates'][0]['value'],'2020-02-03')
        self.assertEqual(len(self.calls),2);apply_plan(self.path,plan)
        self.assertEqual(self.db.execute('SELECT * FROM songs').fetchone(),(1,'First',1,'https://audio.example/unchanged.m4a',2,1234))
        self.assertEqual(self.db.execute('SELECT * FROM albums').fetchone(),(1,'Album',ART_BIG,'2020-02-03'))
        self.assertEqual(self.db.execute('SELECT * FROM genres').fetchone(),(1,'custom'))
        with sqlite3.connect(plan['backup']) as db:self.assertIsNone(db.execute('SELECT track_number FROM songs').fetchone()[0])
        report=text_report(plan);self.assertIn('[FILLED] Album #1',report);self.assertNotIn('Song #1',report)
        with self.assertRaises(ValueError):apply_plan(self.path,plan)
    def test_write_failure_rolls_back_all_changes(self):
        p=self.plan()
        self.db.execute("CREATE TRIGGER reject_date BEFORE UPDATE OF release_date ON albums BEGIN SELECT RAISE(ABORT,'test failure'); END")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):apply_plan(self.path,p)
        self.assertIsNone(self.db.execute('SELECT track_number FROM songs').fetchone()[0])
        self.assertIsNone(self.db.execute('SELECT release_date FROM albums').fetchone()[0])
        self.assertFalse(p['applied'])
    def test_track_with_missing_artist_does_not_abort_album_scan(self):
        self.db.execute('DELETE FROM song_artists WHERE song_id=1')
        self.db.execute("INSERT INTO songs VALUES(2,'Second',1,'stay',NULL,1200)")
        self.db.execute('INSERT INTO song_artists VALUES(2,1)');self.db.commit()
        p=self.plan(lambda url:{'results':[album()] if '/search?' in url else [album(),remote(),remote('Second',3)]})
        self.assertEqual([r['id'] for r in p['tracks']],[2])
        self.assertEqual(p['track_failures'][0]['id'],1)
        self.assertEqual(p['dates'][0]['status'],'proposed')
    def test_existing_values_no_lookup_no_overwrite(self):
        self.db.execute('UPDATE songs SET track_number=7');self.db.execute("UPDATE albums SET release_date='2019-09-09'");self.db.commit()
        plan=self.plan();self.assertFalse(self.calls);self.assertFalse(plan['tracks']);self.assertEqual(plan['dates'][0]['status'],'kept')
        apply_plan(self.path,plan);self.assertIsNone(plan['backup']);self.assertEqual(self.db.execute('SELECT track_number FROM songs').fetchone()[0],7)
    def test_artwork_identity_not_size_or_cdn_host(self):
        self.assertEqual(artwork_key(ART),artwork_key(ART_BIG));self.assertIsNone(artwork_key('https://other.example/a/100x100bb.jpg'))
        for field,value in [('artworkUrl100',ART.replace('unique-asset','different-asset')),('artistName','Wrong'),('collectionName','Album (Deluxe)')]:
            self.calls.clear()
            def lookup(url):return {'results':[album(**{field:value})]}
            p=self.plan(lookup);self.assertFalse(p['tracks']);self.assertEqual(p['dates'][0]['status'],'failed');self.assertEqual(len(p['track_failures']),1)
    def test_ambiguous_edition_not_guessed(self):
        p=self.plan(lambda url:{'results':[album(),album(collectionId=11)]})
        self.assertFalse(p['tracks']);self.assertEqual(p['dates'][0]['status'],'failed')
    def test_track_identity_checked_again(self):
        for changes in [{'trackName':'First (Live)'},{'artistName':'Wrong'},{'artworkUrl100':ART.replace('unique','other')}]:
            row=remote();row.update(changes)
            p=self.plan(lambda url:{'results':[album()] if '/search?' in url else [album(),row]})
            self.assertFalse(p['tracks']);self.assertEqual(p['dates'][0]['status'],'failed')
    def test_multidisc_missing_and_invalid_positions_flagged(self):
        for changes in [{'discCount':2},{'discCount':None},{'discCount':True},{'trackNumber':0},{'trackNumber':None},{'trackNumber':11}]:
            row=remote();row.update(changes)
            p=self.plan(lambda url:{'results':[album()] if '/search?' in url else [album(),row]})
            self.assertFalse(p['tracks']);self.assertEqual(len(p['track_failures']),1);self.assertEqual(p['dates'][0]['status'],'proposed')
    def test_invalid_date_does_not_prevent_valid_position(self):
        p=self.plan(lambda url:{'results':[album(releaseDate='2020-02-30')] if '/search?' in url else [album(releaseDate='2020-02-30'),remote()]})
        self.assertEqual(p['dates'][0]['status'],'failed');self.assertEqual(p['tracks'][0]['value'],2)
    def test_existing_occupied_and_duplicate_proposals_not_written(self):
        self.db.execute("INSERT INTO songs VALUES(2,'Second',1,'stay',2,1200)");self.db.execute('INSERT INTO song_artists VALUES(2,1)');self.db.commit()
        p=self.plan();self.assertFalse(p['tracks']);self.assertIn('occupied',p['track_failures'][0]['reason'])
        self.db.execute('UPDATE songs SET track_number=NULL WHERE id=2');self.db.commit()
        p=self.plan(lambda url:{'results':[album()] if '/search?' in url else [album(),remote(),remote('Second')]})
        self.assertFalse(p['tracks']);self.assertEqual(len(p['track_failures']),2)
    def test_local_single_preserved_without_query_for_position(self):
        self.db.execute("UPDATE albums SET title='First - Single',release_date='2020-02-03'");self.db.commit()
        p=self.plan();self.assertFalse(self.calls);self.assertEqual(p['tracks'][0]['value'],1)
        self.db.execute('UPDATE albums SET release_date=NULL');self.db.commit()
        p=self.plan(lambda url:{'results':[remote()] if '/search?' in url else [album(),remote()]})
        self.assertEqual(p['tracks'][0]['value'],1);self.assertEqual(p['dates'][0]['value'],'2020-02-03')
        apply_plan(self.path,p);self.assertEqual(self.db.execute('SELECT title FROM albums').fetchone()[0],'First - Single')
    def test_multi_track_single_no_duplicate_ones(self):
        self.db.execute("UPDATE albums SET title='First - Single',release_date='2020-02-03'")
        self.db.execute("INSERT INTO songs VALUES(2,'Second',1,'stay',NULL,1200)");self.db.commit()
        p=self.plan();self.assertFalse(self.calls);self.assertFalse(p['tracks']);self.assertEqual(len(p['track_failures']),2)
    def test_stale_identity_or_target_rejected_but_scores_can_change(self):
        p=self.plan();self.db.execute("UPDATE albums SET title='Changed'");self.db.commit()
        with self.assertRaisesRegex(ValueError,'changed'):apply_plan(self.path,p)
        self.assertIsNone(self.db.execute('SELECT track_number FROM songs').fetchone()[0])
        self.db.execute("UPDATE albums SET title='Album'");self.db.commit();p=self.plan()
        self.db.execute('UPDATE songs SET elo_score=1400');self.db.commit();apply_plan(self.path,p)
        self.assertEqual(self.db.execute('SELECT elo_score FROM songs').fetchone()[0],1400)
    def test_remote_refusal_stops_queries_reports_remaining(self):
        self.db.execute("INSERT INTO albums VALUES(2,'Other',?,NULL)",(ART,));self.db.execute("INSERT INTO songs VALUES(2,'Second',2,'stay',NULL,1200)");self.db.commit()
        calls=[]
        def bad(url):calls.append(url);raise ScanStopped('HTTP 429: wait 60 seconds')
        p=self.plan(bad);self.assertEqual(len(calls),1);self.assertEqual(len(p['track_failures']),2);self.assertEqual(len(p['dates']),2)
        self.assertIn('429',text_report(p))
        with patch('metadata_fill.apple_lookup',side_effect=AppleRequestError('429',429,60,'rate_limited',429)):
            with self.assertRaises(ScanStopped):paced_lookup('https://itunes.apple.com/search?term=test')
    def test_no_missing_database_created(self):
        path=self.dir/'missing.db'
        with self.assertRaises(ValueError):connection(path)
        self.assertFalse(path.exists())
    def test_cli_dry_run_apply_and_report_collision(self):
        self.db.execute("UPDATE albums SET title='First - Single',release_date='2020-02-03'");self.db.commit()
        report=self.dir/'report.txt';script=test_app.ROOT/'fill_missing_metadata.py'
        command=[sys.executable,str(script),'--database',str(self.path),'--report',str(report)]
        r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
        self.assertIsNone(self.db.execute('SELECT track_number FROM songs').fetchone()[0]);self.assertIn('Dry run',report.read_text())
        r=subprocess.run(command+['--apply'],capture_output=True,text=True);self.assertNotEqual(r.returncode,0)
        self.assertIsNone(self.db.execute('SELECT track_number FROM songs').fetchone()[0])
        report.unlink();r=subprocess.run(command+['--apply'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.db.execute('SELECT track_number FROM songs').fetchone()[0],1)

class TagAndToolChecks(unittest.TestCase):
    def setUp(self):
        shutil.copyfile(test_app.ROOT/'song_ranker_v2.db',test_app.TMP/'active.db');test_app.services.init_db()
        self.c=test_app.main.app.test_client()
        with self.c.session_transaction() as session:session['is_admin']=True
    def test_description_validation_preservation_and_collection(self):
        data=self.c.get('/api/collection').json;tag=data['tags'][0]
        response=self.c.post('/api/dev/edit_genre/'+str(tag['id']),json={'name':tag['name'],'description':'Quiet evenings <script>bad</script>'})
        self.assertEqual(response.status_code,200)
        tag=next(t for t in self.c.get('/api/collection').json['tags'] if t['id']==tag['id'])
        self.assertEqual(tag['description'],'Quiet evenings <script>bad</script>')
        self.assertEqual(self.c.post('/api/dev/edit_genre/'+str(tag['id']),json={'name':tag['name'],'description':'x'*2001}).status_code,400)
        self.assertEqual(self.c.post('/api/dev/edit_genre/'+str(tag['id']),json={'name':tag['name']}).status_code,200)
        self.assertEqual(next(t for t in self.c.get('/api/collection').json['tags'] if t['id']==tag['id'])['description'],tag['description'])
        with test_app.services.get_db_connection() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],8)
    def test_metadata_endpoints_auth_country_busy_and_reports(self):
        import metadata_tools as tools
        old=tools._job;self.addCleanup(lambda:setattr(tools,'_job',old));tools._job=None
        self.assertEqual(self.c.get('/api/dev/metadata').json['state'],'idle')
        self.assertEqual(self.c.post('/api/dev/metadata',json={'country':'bad'}).status_code,400)
        with patch('metadata_tools.Thread'):
            result=self.c.post('/api/dev/metadata',json={'country':'gb'});self.assertEqual(result.status_code,200)
            token=result.json['token'];self.assertEqual(self.c.post('/api/dev/metadata',json={}).status_code,409)
            self.assertEqual(self.c.post('/api/dev/metadata/'+token+'/cancel',json={}).status_code,200)
            self.assertTrue(tools._job['cancel'].is_set())
            self.assertEqual(self.c.post('/api/dev/metadata/'+token+'/apply',json={}).status_code,409)
            self.assertEqual(self.c.get('/api/dev/metadata/'+token+'/report').status_code,409)
        tools._job.update(state='ready',plan=plan_metadata(test_app.services.DB_NAME,lookup=lambda url:(_ for _ in ()).throw(ValueError('offline fixture'))))
        report=self.c.get('/api/dev/metadata/'+token+'/report');self.assertEqual(report.status_code,200);self.assertIn('attachment',report.headers['Content-Disposition'])
        self.assertIn('TRACK NUMBER FAILURES ONLY',report.text)
        self.assertEqual(self.c.post('/api/dev/metadata/'+token+'/apply',json={}).status_code,200)
        self.assertEqual(self.c.post('/api/dev/metadata/'+token+'/apply',json={}).status_code,409)
        with self.c.session_transaction() as session:session.clear()
        self.assertEqual(self.c.get('/api/dev/metadata').status_code,302)
