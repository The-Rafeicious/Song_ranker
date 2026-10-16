"""Voting report: in-memory history, saved ratings, no live DB writes."""
import sqlite3
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from services import app
from voting_stats_data import build_voting_stats
import pages
import games

NOW=datetime(2026,10,16,12,tzinfo=timezone.utc).timestamp()


class VotingStatsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
        CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,elo_score REAL,highest_elo REAL);
        CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT,cover_url TEXT);
        CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
        CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
        CREATE TABLE song_genres(song_id INTEGER,genre_id INTEGER);
        CREATE TABLE history(id INTEGER PRIMARY KEY,winner_id INTEGER,loser_id INTEGER,mode TEXT,created_at TEXT,
                             winner_before REAL,winner_after REAL,loser_before REAL,loser_after REAL);
        INSERT INTO albums VALUES(1,'Album <one>','cover'),(2,'Track - Single',''),(3,'Unknown Album','');
        INSERT INTO songs VALUES(1,'One <test>',1,1300,1350),(2,'Two',1,1250,1280),(3,'Three',2,1150,1200),(4,'Four',3,1200,1200);
        INSERT INTO artists VALUES(1,'Name, With Comma',''),(2,'Guest','');
        INSERT INTO genres VALUES(1,'Tag <one>');
        INSERT INTO song_artists VALUES(1,1),(1,2),(2,1),(3,2);
        INSERT INTO song_genres VALUES(1,1),(2,1);
        ''')

    def vote(self,winner=1,loser=2,mode='standard',before=(1200,1200),change=16,date='2026-10-16 10:00:00'):
        wb,lb=before
        self.c.execute('INSERT INTO history(winner_id,loser_id,mode,created_at,winner_before,winner_after,loser_before,loser_after) VALUES(?,?,?,?,?,?,?,?)',
                       (winner,loser,mode,date,wb,wb+change if wb is not None else None,lb,lb-change if lb is not None else None))

    def build(self,**kwargs):return build_voting_stats(self.c,now=NOW,**kwargs)

    def request(self,path='/voting_stats'):
        self.c.commit()
        def connection():
            dest=sqlite3.connect(':memory:');dest.row_factory=sqlite3.Row;self.c.backup(dest);return dest
        with patch('pages.get_db_connection',side_effect=connection):return app.test_client().get(path)

    def test_empty(self):
        d=self.build();self.assertEqual(d['summary']['matches'],0);self.assertIsNone(d['summary']['upset_rate'])
        self.assertEqual(d['coverage']['unplayed'],4);self.assertEqual(d['history_pages'],1)
        self.assertEqual(sum(b['count'] for b in d['distribution']['bands']),4);self.assertEqual(d['distribution']['median'],1225)

    def test_both_modes_only_and_invalid_pairs(self):
        self.vote();self.vote(mode='blind');self.vote(mode='trivia');self.vote(winner=1,loser=1)
        self.c.execute("INSERT INTO history(winner_id,loser_id,mode) VALUES(NULL,1,'blind')")
        d=self.build();self.assertEqual(d['summary']['matches'],2);self.assertEqual(d['summary']['skipped'],2)
        self.assertEqual([m['matches'] for m in d['modes']],[1,1]);self.assertEqual(d['coverage']['both'],2)

    def test_upsets_ties_and_gap_bands_use_saved_ratings(self):
        self.vote(before=(1100,1300),change=24);self.vote(before=(1400,1200),change=8);self.vote()
        self.c.execute('UPDATE songs SET elo_score=1800 WHERE id=1')
        d=self.build();self.assertEqual(d['summary']['upsets'],1);self.assertEqual(d['summary']['level'],1)
        self.assertEqual(d['summary']['upset_rate'],50);self.assertEqual(d['movement']['largest_upset'],200)
        self.assertEqual(d['upsets'][0]['winner_before'],1100);self.assertEqual(sum(g['matches'] for g in d['gaps']),3)

    def test_saved_movement_and_net_zero(self):
        self.vote(before=(1100,1300),change=24);self.vote(winner=2,loser=1,change=8)
        d=self.build();self.assertEqual(d['movement']['total'],32);self.assertEqual(d['movement']['avg_gain'],16)
        self.assertEqual(d['movement']['drift'],0);self.assertEqual(d['gain_tracks'][0]['net'],16);self.assertEqual(d['loss_tracks'][0]['net'],-16)

    def test_missing_and_invalid_ratings_do_not_become_zero(self):
        self.vote(before=(None,1200));self.vote(before=(1200,1300));self.c.execute('UPDATE history SET winner_after=1100 WHERE id=2')
        d=self.build();self.assertEqual(d['summary']['matches'],2);self.assertEqual(d['summary']['rated'],1)
        self.assertEqual(d['summary']['snapshots'],0);self.assertIsNone(d['movement']['avg_gain']);self.assertEqual(d['movement']['missing'],2)

    def test_deleted_tracks_keep_history_without_profile_link(self):
        self.vote(winner=99,loser=1,before=(1100,1200),change=20)
        d=self.build();self.assertEqual(d['summary']['matches'],1);self.assertEqual(d['summary']['removed'],1)
        self.assertIsNone(d['history'][0]['winner']['id']);self.assertEqual(d['most_played'][0]['losses'],1)

    def test_reverse_pairs_combine(self):
        self.vote();self.vote(winner=2,loser=1,mode='blind');d=self.build();p=d['pairs'][0]
        self.assertEqual(d['unique_pairs'],1);self.assertEqual(d['repeated_pairs'],1)
        self.assertEqual((p['first_wins'],p['second_wins'],p['standard'],p['blind']),(1,1,1,1))

    def test_mode_difference_minimums_and_percentage_points(self):
        for _ in range(3):self.vote(winner=2,loser=1);self.vote(winner=1,loser=2,mode='blind')
        d=self.build();self.assertEqual(d['blind_lift'][0]['id'],1);self.assertEqual(d['blind_lift'][0]['blind_lift'],100)
        self.assertEqual(d['standard_lift'][0]['id'],2)

    def test_category_pooling_and_single_exclusion(self):
        for _ in range(3):self.vote()
        self.vote(winner=3,loser=4);d=self.build();artist,album,tag=d['categories'];a=next(r for r in artist['most'] if r['id']==1)
        self.assertEqual(a['matches'],6);self.assertEqual(a['wins'],3);self.assertEqual(a['win_rate'],50)
        self.assertEqual([r['id'] for r in album['most']],[1]);self.assertEqual(tag['most'][0]['matches'],6)
        self.assertEqual(d['history'][0]['winner']['artist_links'][0]['name'],'Guest')

    def test_chronological_track_runs_and_undated_safety(self):
        self.vote(date='2026-10-12');self.vote(date='2026-10-10');self.vote(date='2026-10-11')
        self.assertEqual(self.build()['runs'][0]['best_run'],3)
        self.vote(date='not a date');d=self.build();self.assertEqual(d['summary']['undated'],1);self.assertEqual(d['runs'],[])

    def test_windows_utc_days_and_future_dates(self):
        self.vote(date='2026-10-16T00:30:00+01:00');self.vote(mode='blind',date='2026-10-16 11:00:00')
        self.vote(date='2026-10-17');self.vote(date='2026-01-01');d=self.build()
        self.assertEqual(d['windows'][0]['matches'],2);self.assertEqual(d['activity'][-2]['standard'],1)
        self.assertEqual(d['activity'][-1]['blind'],1);self.assertEqual(d['summary']['active_days'],3)

    def test_all_history_aggregates_but_display_paginates(self):
        for n in range(125):self.vote(mode='blind' if n%2 else 'standard')
        d=self.build(history_page=2,history_mode='blind');self.assertEqual(d['summary']['matches'],125)
        self.assertEqual(len(d['history']),10);self.assertEqual(d['history_total'],62);self.assertEqual(d['history_page'],2)
        self.assertTrue(all(r['mode']=='blind' for r in d['history']))
        self.assertEqual(self.build(history_page='bad',history_mode='bad')['history_page'],1)
        self.assertEqual(self.build(history_page=999)['history_page'],13)

    def test_read_only(self):
        self.vote();before=self.c.total_changes;trace=[];self.c.set_trace_callback(trace.append);self.build()
        self.assertEqual(self.c.total_changes,before);self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in trace))

    def test_route_template_and_empty_state(self):
        response=self.request();self.assertEqual(response.status_code,200);html=response.get_data(as_text=True)
        for text in ['Voting overview','Shared Elo distribution','Biggest upsets','Non-blind &amp; Blind','Artist records','Album records','Tag records','Recent votes','css/mode_stats.css','css/voting_stats.css']:self.assertIn(text,html)
        self.assertNotIn('NaN',html)

    def test_removed_and_partial_snapshot_render(self):
        self.vote(winner=99,loser=1,before=(None,1200));self.assertEqual(self.request('/voting_stats?history_mode=blind').status_code,200)
        response=self.request();self.assertEqual(response.status_code,200)
        self.assertIn('Removed track',response.get_data(as_text=True));self.assertNotIn('/song/99',response.get_data(as_text=True))

    def test_legacy_history_without_snapshot_columns(self):
        self.c.execute('DROP TABLE history')
        self.c.execute('CREATE TABLE history(id INTEGER PRIMARY KEY,winner_id INTEGER,loser_id INTEGER,mode TEXT,created_at TEXT)')
        self.c.execute("INSERT INTO history VALUES(1,1,2,'standard','2026-10-16')")
        d=self.build();self.assertEqual(d['summary']['matches'],1);self.assertEqual(d['summary']['snapshots'],0)
        self.assertIsNone(d['summary']['avg_gain']);self.assertEqual(self.request().status_code,200)

    def test_elo_distribution_uses_exact_boundaries_and_missing_values(self):
        for sid,value in [(1,1000),(2,1050),(3,1400),(4,None)]:self.c.execute('UPDATE songs SET elo_score=? WHERE id=?',(value,sid))
        d=self.build();self.assertEqual(d['distribution']['rated'],3);self.assertEqual(d['distribution']['unavailable'],1)
        self.assertEqual([b['count'] for b in d['distribution']['bands']],[0,1,1,0,0,0,0,0,0,1])
        self.c.execute('UPDATE songs SET elo_score=? WHERE id=1',(float('inf'),))
        self.assertEqual(self.build()['distribution']['unavailable'],2)

    def test_minimum_samples_and_populated_html(self):
        for _ in range(4):self.vote()
        self.assertEqual(self.build()['best_rates'],[])
        self.vote();self.vote(mode='blind')
        self.assertEqual(self.build()['blind_lift'],[])
        response=self.request();self.assertEqual(response.status_code,200);html=response.get_data(as_text=True)
        self.assertIn('One &lt;test&gt;',html);self.assertNotIn('One <test>',html)
        self.assertIn('Name, With Comma',html);self.assertIn('Tag &lt;one&gt;',html)
        self.assertNotIn('/album/Track%20-%20Single',html)


if __name__=='__main__':unittest.main()
