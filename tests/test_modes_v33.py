"""Independent mode state, snapshots, order scoring and schema-8 preservation."""
import math
import shutil
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import test_app
from special_modes import grade_shelf, special_records
from database import migrate


class Mode33Checks(unittest.TestCase):
    def setUp(self):
        shutil.copyfile(test_app.ROOT/'song_ranker_v2.db',test_app.TMP/'active.db')
        test_app.services.init_db()
        self.c=test_app.main.app.test_client()

    def db(self):return test_app.services.get_db_connection()

    def guess(self):
        response=self.c.post('/api/elo-guesser/round',json={})
        self.assertEqual(response.status_code,200,response.text)
        with self.db() as db:
            row=dict(db.execute('SELECT * FROM elo_guess_rounds WHERE token=?',(response.json['token'],)).fetchone())
        return response.json,row

    def answer_guess(self,correct=True):
        question,row=self.guess()
        high=row['song1_id'] if row['elo1']>row['elo2'] else row['song2_id']
        low=row['song2_id'] if row['elo1']>row['elo2'] else row['song1_id']
        return self.c.post('/api/elo-guesser/answer',json={'token':question['token'],'song_id':high if correct else low})

    def seed_shelves(self,counts=(5,3,2)):
        with self.db() as db:
            db.execute('UPDATE songs SET track_number=NULL')
            for index,count in enumerate(counts):
                aid=db.execute('INSERT INTO albums(title) VALUES(?)',('V33 shelf '+str(index),)).lastrowid
                for n in range(count):
                    db.execute('INSERT INTO songs(title,album_id,track_number,audio_url) VALUES(?,?,?,?)',
                        ('V33 track '+str(index)+'-'+str(n),aid,1+n*3,'https://example.test/sample.mp3'))
        response=self.c.post('/api/album-shelves/round',json={'album_count':len(counts)})
        self.assertEqual(response.status_code,200,response.text)
        with self.db() as db:
            rows=[dict(r) for r in db.execute('SELECT i.* FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id WHERE r.token=? ORDER BY track_number',(response.json['token'],))]
        placements={str(a['slot']):[r['item_slot'] for r in rows if r['album_slot']==a['slot']] for a in response.json['albums']}
        return response.json,rows,placements

    def test_elo_snapshot_hidden_independent_and_idempotent(self):
        with self.db() as db:before=[tuple(r) for r in db.execute('SELECT elo_score,matches_played FROM songs')];history=db.execute('SELECT COUNT(*) FROM history').fetchone()[0]
        q,row=self.guess();self.assertNotEqual(q['songs'][0]['id'],q['songs'][1]['id'])
        self.assertFalse({'elo_score','highest_elo','matches_played','elo1','elo2'} & set(q['songs'][0]))
        high=row['song1_id'] if row['elo1']>row['elo2'] else row['song2_id']
        r=self.c.post('/api/elo-guesser/answer',json={'token':q['token'],'song_id':high});self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['points'],1);self.assertEqual(r.json['records']['streak'],1)
        self.assertEqual(self.c.post('/api/elo-guesser/answer',json={'token':q['token'],'song_id':high}).status_code,409)
        with self.db() as db:
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT elo_score,matches_played FROM songs')])
            self.assertEqual(history,db.execute('SELECT COUNT(*) FROM history').fetchone()[0])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM elo_guess_rounds WHERE completed_at IS NOT NULL').fetchone()[0],1)

    def test_question_keeps_frozen_ratings_and_resumes_pending(self):
        q,row=self.guess();self.assertEqual(self.c.post('/api/elo-guesser/round',json={}).json['token'],q['token'])
        high=row['song1_id'] if row['elo1']>row['elo2'] else row['song2_id']
        with self.db() as db:db.execute('UPDATE songs SET elo_score=1 WHERE id=?',(high,))
        r=self.c.post('/api/elo-guesser/answer',json={'token':q['token'],'song_id':high})
        self.assertTrue(r.json['correct']);self.assertEqual(r.json['ratings'],[row['elo1'],row['elo2']])

    def test_guess_streaks_bad_requests_and_equal_ratings(self):
        self.assertEqual(self.answer_guess().json['records']['best_streak'],1)
        self.assertEqual(self.answer_guess().json['records']['best_streak'],2)
        r=self.answer_guess(False);self.assertEqual(r.json['records']['streak'],0);self.assertEqual(r.json['records']['best_streak'],2)
        q,row=self.guess()
        for data in [{},{'token':q['token'],'song_id':True},{'token':q['token'],'song_id':999999}]:
            self.assertEqual(self.c.post('/api/elo-guesser/answer',json=data).status_code,400)
        self.assertEqual(self.c.post('/api/elo-guesser/answer',json={'token':'wrong','song_id':row['song1_id']}).status_code,409)
        outsider=test_app.main.app.test_client();self.assertEqual(outsider.post('/api/elo-guesser/answer',json={'token':q['token'],'song_id':row['song1_id']}).status_code,409)
        with self.db() as db:db.execute('DELETE FROM elo_guess_rounds');db.execute('UPDATE songs SET elo_score=1200')
        self.assertEqual(self.c.post('/api/elo-guesser/round',json={}).status_code,400)

    def test_guesser_cannot_accidentally_be_saved_as_a_vote(self):
        q,row=self.guess()
        self.assertEqual(self.c.post('/api/vote',json={'winner_id':row['song1_id'],'loser_id':row['song2_id'],'mode':'guesser'}).status_code,400)

    def test_shelves_exactly_ten_hidden_metadata_and_gaps(self):
        q,rows,p=self.seed_shelves()
        self.assertEqual(len(q['songs']),10);self.assertEqual(len(q['albums']),3)
        self.assertEqual(len({s['id'] for s in q['songs']}),10)
        for song in q['songs']:self.assertFalse({'album','album_id','cover_url','track_number','album_slot'} & set(song))
        self.assertEqual(sorted(map(len,p.values())),[2,3,5])
        r=self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json['points'],30)
        self.assertEqual(r.json['available'],30);self.assertEqual(r.json['album_correct'],10)
        self.assertIn(13,[i['track_number'] for i in r.json['answers']])
        self.assertEqual(self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p}).status_code,409)

    def test_uneven_single_track_shelves_have_no_free_order_points(self):
        q,rows,p=self.seed_shelves((8,1,1))
        r=self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        self.assertEqual(r.json['points'],26);self.assertEqual(r.json['available'],26);self.assertEqual(r.json['accuracy'],100)

    def test_two_shelves_are_supported_without_even_track_counts(self):
        q,rows,p=self.seed_shelves((7,3))
        self.assertEqual(len(q['albums']),2);self.assertEqual(sorted(map(len,p.values())),[3,7])
        r=self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['points'],30)

    def test_order_is_more_valuable_and_misplaced_tracks_do_not_cascade(self):
        q,rows,p=self.seed_shelves()
        first=next(k for k,v in p.items() if len(v)==5);p[first][0],p[first][1]=p[first][1],p[first][0]
        r=self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        self.assertEqual(r.json['album_correct'],10);self.assertGreater(r.json['points'],28);self.assertLess(r.json['points'],30)
        self.assertGreater(r.json['order_right'],0)

    def test_malformed_shelves_are_atomic_and_cannot_supply_score(self):
        q,rows,p=self.seed_shelves();bad={k:list(v) for k,v in p.items()};key=next(iter(bad));bad[key][0]=bad[key][1]
        for placements in [bad,{'99':list(range(1,11))},{'1':[]}, {'1':[True]*10}]:
            self.assertEqual(self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':placements,'points':999}).status_code,400)
        with self.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM album_shelf_items WHERE answer_slot IS NOT NULL').fetchone()[0],0)
        r=self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p,'points':999});self.assertEqual(r.json['points'],30)

    def test_pending_shelves_reuse_fresh_and_bad_selection(self):
        q,rows,p=self.seed_shelves()
        self.assertEqual(self.c.post('/api/album-shelves/round',json={}).json['token'],q['token'])
        new=self.c.post('/api/album-shelves/round',json={'fresh':True});self.assertNotEqual(new.json['token'],q['token'])
        for value in [True,4,'2']:
            self.assertEqual(self.c.post('/api/album-shelves/round',json={'album_count':value}).status_code,400)
        with self.db() as db:db.execute("UPDATE albums SET title=title || ' - Single'")
        self.c.post('/api/album-shelves/round',json={'fresh':True})
        self.assertEqual(self.c.post('/api/album-shelves/round',json={'fresh':True}).status_code,400)

    def test_stats_profiles_global_and_mode_pages(self):
        self.answer_guess();q,rows,p=self.seed_shelves();self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        stats=self.c.get('/api/special-modes/stats').json
        self.assertEqual(stats['summary']['guesser']['correct'],1);self.assertEqual(stats['summary']['shelves']['points'],30)
        data=self.c.get('/api/collection').json
        self.assertEqual(sum(s['guess_attempts'] for s in data['songs']),2)
        self.assertEqual(sum(s['shelf_attempts'] for s in data['songs']),10)
        for path in ['/game?mode=guesser','/elo_guesser_stats','/album_shelves','/album_shelves_stats']+[f'/mode_rankings/{m}' for m in ['trivia','tournament','guesser','shelves']]:
            r=self.c.get(path);self.assertEqual(r.status_code,200);self.assertIn('V3.3',r.text);self.assertIn('special_modes.js',r.text)
        r=self.c.get('/global_stats');self.assertEqual(r.status_code,200);self.assertIn('Elo Guesser',r.text);self.assertIn('Album Shelves',r.text)

    def test_new_mode_resets_are_separate_and_backed_up(self):
        self.answer_guess();q,rows,p=self.seed_shelves();self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        test_app.services.ROOT=test_app.TMP
        self.addCleanup(setattr,test_app.services,'ROOT',test_app.ROOT)
        with self.c.session_transaction() as s:s['is_admin']=True
        with self.db() as db:count=db.execute('SELECT COUNT(*) FROM history').fetchone()[0];songs=db.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
        r=self.c.post('/api/dev/reset-history/guesser',json={'confirmation':'RESET GUESSER'});self.assertEqual(r.status_code,200)
        self.assertTrue((test_app.TMP/'database_backups'/r.json['backup']).exists())
        stats=self.c.get('/api/special-modes/stats').json['summary'];self.assertEqual(stats['guesser']['rounds'],0);self.assertEqual(stats['shelves']['rounds'],1)
        r=self.c.post('/api/dev/reset-history/shelves',json={'confirmation':'RESET SHELVES'});self.assertEqual(r.status_code,200)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM history').fetchone()[0],count)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM songs').fetchone()[0],songs)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM album_shelf_items').fetchone()[0],0)

    def test_schema_eight_preserves_existing_records_and_backup_is_idempotent(self):
        path=test_app.TMP/'v33-migration.db';shutil.copyfile(test_app.TMP/'active.db',path)
        with sqlite3.connect(path) as db:
            for table in ['album_shelf_items','album_shelf_rounds','elo_guess_rounds']:db.execute('DROP TABLE '+table)
            db.execute('PRAGMA user_version=7')
            before={table:db.execute(f'SELECT * FROM {table}').fetchall() for table in ['songs','albums','artists','history','trivia_rounds','tournaments','tournament_matches']}
        migrate(path)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],8)
            for table,rows in before.items():self.assertEqual(db.execute(f'SELECT * FROM {table}').fetchall(),rows)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        digest=path.read_bytes();migrate(path);self.assertEqual(digest,path.read_bytes())

    def test_deleted_song_keeps_completed_scoring_and_dev_deletion_is_protected(self):
        q,rows,p=self.seed_shelves()
        self.c.post('/api/album-shelves/answer',json={'token':q['token'],'placements':p})
        with self.db() as db:
            db.execute('DELETE FROM songs WHERE id=?',(rows[0]['song_id'],))
            rid=db.execute('SELECT id FROM album_shelf_rounds WHERE token=?',(q['token'],)).fetchone()[0]
        self.assertEqual(self.c.get('/api/special-modes/stats').json['summary']['shelves']['points'],30)
        self.assertEqual(self.c.post('/api/dev/special-round/shelves/'+str(rid),json={}).status_code,302)
        with self.c.session_transaction() as s:s['is_admin']=True
        with patch.object(test_app.services,'ROOT',test_app.TMP):
            r=self.c.post('/api/dev/special-round/shelves/'+str(rid),json={})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.c.get('/api/special-modes/stats').json['summary']['shelves']['rounds'],0)
        with self.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM album_shelf_items').fetchone()[0],0)
