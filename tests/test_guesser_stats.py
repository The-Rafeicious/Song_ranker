"""Elo Guesser reporting: isolated memory fixtures, no live database writes."""
import sqlite3
import unittest
from unittest.mock import patch

from services import app
from special_schema import ensure_special_schema
from guesser_stats_data import build_guesser_stats
import pages
import special_modes

NOW = 1800000000


class GuesserStatsTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
            CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,audio_url TEXT,elo_score REAL);
            CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT,cover_url TEXT);
            CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
            CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
            CREATE TABLE song_genres(song_id INTEGER,genre_id INTEGER);
        ''')
        ensure_special_schema(self.c)
        self.c.commit()

    def insert(self, table, **values):
        self.c.execute('INSERT INTO '+table+' ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',tuple(values.values()))

    def seed(self):
        for sid,name in ((1,'Artist, One'),(2,'Artist Two')):
            self.insert('artists',id=sid,name=name,cover_url='/artist.png')
        for sid,title in ((1,'Proper Album'),(2,'Track - Single'),(3,'Unknown Album')):
            self.insert('albums',id=sid,title=title,cover_url='/cover.png')
        self.insert('genres',id=1,name='Tag One')
        for sid in range(1,13):
            self.insert('songs',id=sid,title='Track '+str(sid),album_id=1 if sid<10 else 2 if sid==10 else 3 if sid==11 else None,audio_url='',elo_score=1200+sid)
            self.insert('song_artists',song_id=sid,artist_id=1)
            self.insert('song_genres',song_id=sid,genre_id=1)
        self.insert('song_artists',song_id=1,artist_id=1)
        self.insert('song_artists',song_id=1,artist_id=2)
        self.insert('song_genres',song_id=1,genre_id=1)

    def round(self, sid, correct=True, gap=40, **extra):
        row=dict(id=sid,token='private-token-'+str(sid),song1_id=1,song2_id=2,
                 elo1=1200,elo2=1200+gap,started_at=NOW-2000+sid,
                 completed_at=NOW-1000+sid,chosen_slot=2 if correct else 1)
        row.update(extra)
        self.insert('elo_guess_rounds',**row)

    def data(self, **kwargs):
        return build_guesser_stats(self.c,now=NOW,**kwargs)

    def render(self, data):
        with app.test_request_context('/elo_guesser_stats'):
            return app.jinja_env.get_template('guesser_stats.html').render(**data,app_version='3.4.7')

    def test_empty_rates_are_unknown_and_counts_zero(self):
        d=self.data()
        self.assertEqual(d['summary']['rounds'],0)
        self.assertIsNone(d['summary']['accuracy'])
        self.assertIsNone(d['coverage']['share'])
        self.assertIsNone(d['gap_summary']['closest_correct'])
        self.assertEqual(d['history_pages'],1)
        html=self.render(d)
        self.assertIn('No completed Elo guesses yet.',html)
        self.assertIn('aria-valuetext="No attempts yet"',html)

    def test_aggregates_use_all_history_and_only_display_is_paged(self):
        self.seed()
        for sid in range(1,126):self.round(sid,correct=sid%5!=0)
        d=self.data(history_page=13)
        self.assertEqual(d['summary']['rounds'],125)
        self.assertEqual(d['summary']['correct'],100)
        self.assertEqual(d['summary']['wrong'],25)
        self.assertEqual(d['history_pages'],13)
        self.assertEqual([r['id'] for r in d['history']],[5,4,3,2,1])
        self.assertEqual(d['history_start'],121)
        self.assertEqual(d['history_end'],125)
        self.assertEqual(sum(r['rounds'] for r in d['gaps']),125)
        self.assertEqual(d['pairs'][0]['rounds'],125)

    def test_streaks_and_summary_match_existing_game_records(self):
        self.seed()
        for sid,correct in enumerate((True,True,False,False,False,True,True,True),1):self.round(sid,correct)
        d=self.data()['summary']
        _,existing,_,_=special_modes.special_records(self.c)
        self.assertEqual((d['current_streak'],d['best_streak'],d['longest_miss']),(3,3,3))
        for new,old in (('rounds','rounds'),('correct','correct'),('current_streak','streak'),('best_streak','best_streak')):
            self.assertEqual(d[new],existing['guesser'][old])

    def test_pending_questions_and_tokens_are_not_exposed(self):
        self.seed();self.round(1)
        self.round(2,completed_at=None,chosen_slot=None)
        d=self.data()
        self.assertEqual(d['summary']['rounds'],1)
        self.assertEqual(len(d['history']),1)
        self.assertFalse(any('token' in row or 'started_at' in row for row in d['history']))
        self.assertNotIn('private-token-',self.render(d))

    def test_snapshot_ratings_not_live_elo_control_result_and_gap(self):
        self.seed();self.round(1,False,gap=75)
        before=self.data()
        self.c.execute('UPDATE songs SET elo_score=9999-id')
        after=self.data()
        self.assertEqual(before['summary'],after['summary'])
        self.assertEqual(before['gaps'],after['gaps'])
        self.assertEqual(after['history'][0]['elo1'],1200)
        self.assertEqual(after['history'][0]['elo2'],1275)
        self.assertIn('1200 saved Elo',self.render(after))

    def test_gap_bands_have_exact_nonoverlapping_fractional_boundaries(self):
        self.seed()
        for sid,gap in enumerate((.5,24.999,25,49.999,50,99.999,100,199.999,200,900),1):self.round(sid,gap=gap)
        d=self.data()
        self.assertEqual([r['rounds'] for r in d['gaps']],[2,2,2,2,2])
        self.assertEqual(d['gap_summary']['closest_correct'],.5)
        self.assertEqual(d['gap_summary']['widest_wrong'],None)

    def test_choice_statistics_count_questions_not_two_track_appearances(self):
        self.seed();self.round(1);self.round(2,False);self.round(3)
        choices=self.data()['choices']
        self.assertEqual([(r['rounds'],r['correct'],r['wrong']) for r in choices],[(1,0,1),(2,2,0)])
        self.assertEqual(sum(r['rounds'] for r in choices),3)
        self.assertEqual([r['accuracy'] for r in choices],[0,100])

    def test_recent_windows_include_boundaries_and_exclude_future_results(self):
        self.seed()
        for sid,stamp in enumerate((NOW,NOW-7*86400,NOW-7*86400-1,NOW-30*86400,NOW-30*86400-1,NOW+1),1):
            self.round(sid,completed_at=stamp)
        windows=self.data()['windows']
        self.assertEqual([r['rounds'] for r in windows],[6,2,4])
        self.assertEqual(windows[0]['accuracy'],100)
        self.assertEqual(self.data()['summary']['active_days'],3)

    def test_latest_ten_form_is_limited_independently_of_lifetime(self):
        self.seed()
        for sid in range(1,31):self.round(sid,correct=sid>20)
        d=self.data()
        self.assertEqual(d['windows'][0]['rounds'],10)
        self.assertEqual(d['windows'][0]['accuracy'],100)
        self.assertEqual(d['summary']['accuracy'],33.3)

    def test_coverage_does_not_require_previews_but_needs_distinct_live_ratings(self):
        self.seed();self.round(1)
        d=self.data()
        self.assertEqual((d['coverage']['eligible'],d['coverage']['tested'],d['coverage']['untested']),(12,2,10))
        self.c.execute('UPDATE songs SET elo_score=1200')
        d=self.data()
        self.assertEqual(d['coverage']['eligible'],0)
        self.assertEqual(d['coverage']['other_tested'],2)
        self.assertIsNone(d['coverage']['share'])
        self.c.execute('UPDATE songs SET elo_score=? WHERE id=1',(float('inf'),))
        self.c.execute('UPDATE songs SET elo_score=1201 WHERE id=3')
        self.assertEqual(self.data()['coverage']['eligible'],11)

    def test_duplicate_collaboration_and_tag_links_do_not_multiply_records(self):
        self.seed();self.round(1);self.round(2,False)
        groups={r['kind']:r for r in self.data()['categories']}
        artist=next(r for r in groups['artist']['best'] if r['id']==1)
        self.assertEqual((artist['attempts'],artist['correct'],artist['tested']),(4,2,2))
        other=next(r for r in groups['artist']['best'] if r['id']==2)
        self.assertEqual(other['attempts'],2)
        self.assertEqual(groups['tag']['best'][0]['attempts'],4)

    def test_album_groups_exclude_single_unknown_and_absent_albums(self):
        self.seed();self.round(1,song1_id=10,song2_id=11);self.round(2,song1_id=12,song2_id=1)
        album=next(r for r in self.data()['categories'] if r['kind']=='album')
        self.assertEqual([r['id'] for r in album['best']],[1])
        self.assertEqual(album['best'][0]['attempts'],1)
        html=self.render(self.data())
        self.assertNotIn('/album/Track%20-%20Single',html)
        self.assertNotIn('/album/Unknown%20Album',html)

    def test_deleted_identities_keep_global_outcomes_without_broken_links(self):
        self.seed();self.round(1,song1_id=None,song2_id=None)
        d=self.data()
        self.assertEqual(d['summary']['correct'],1)
        self.assertEqual(d['coverage']['tested'],0)
        self.assertFalse(d['pairs'])
        html=self.render(d)
        self.assertIn('Removed track',html)
        self.assertNotIn('/song/None',html)
        self.assertNotIn('/song/0',html)

    def test_reversed_pair_order_pools_saved_comparisons(self):
        self.seed();self.round(1);self.round(2,False,song1_id=2,song2_id=1,gap=80)
        pair=self.data()['pairs'][0]
        self.assertEqual((pair['rounds'],pair['correct'],pair['wrong'],pair['average_gap']),(2,1,1,60))
        self.assertEqual({pair['first']['id'],pair['second']['id']},{1,2})

    def test_practice_excludes_perfect_tracks_and_top_ties_use_more_evidence(self):
        self.seed();self.round(1,song1_id=1,song2_id=2)
        for sid in range(2,8):self.round(sid,song1_id=3,song2_id=4)
        self.round(8,False,song1_id=5,song2_id=6)
        d=self.data()
        self.assertEqual([r['id'] for r in d['top_tracks'][:2]],[3,4])
        self.assertEqual({r['id'] for r in d['practice_tracks']},{5,6})

    def test_invalid_comparison_data_is_unknown_not_a_guessed_win_or_loss(self):
        self.seed();self.c.execute('PRAGMA ignore_check_constraints=ON')
        self.round(1,elo1='invalid');self.round(2,elo1=float('inf'))
        self.round(3,elo1=1200,elo2=1200);self.round(4,chosen_slot=0)
        self.round(5,song1_id=1,song2_id=1)
        d=self.data()
        self.assertEqual((d['summary']['rounds'],d['summary']['graded'],d['summary']['unknown']),(5,0,5))
        self.assertEqual(d['summary']['correct'],0)
        self.assertEqual(d['summary']['wrong'],0)
        self.assertIsNone(d['summary']['accuracy'])
        self.assertIsNone(d['summary']['current_streak'])
        self.assertIn('incomplete comparison data',self.render(d))

    def test_undated_and_epoch_results_remain_distinct(self):
        self.seed();self.round(1,completed_at='bad date');self.round(2,completed_at=0)
        d=self.data()
        self.assertEqual(d['summary']['rounds'],2)
        self.assertEqual(d['summary']['undated'],1)
        self.assertIsNone(d['summary']['current_streak'])
        self.assertEqual(d['history'][0]['date']['seconds'],0)
        self.assertEqual(d['windows'][1]['rounds'],0)
        self.assertIn('1970-01-01',self.render(d))

    def test_missing_names_are_escaped_and_full_names_retained(self):
        self.seed();self.round(1)
        long='Long <script>"& name '+('unbroken'*35)
        for table,column in (('songs','title'),('artists','name'),('albums','title'),('genres','name')):
            self.c.execute('UPDATE '+table+' SET '+column+'=?',(long,))
        html=self.render(self.data())
        self.assertIn('Long &lt;script&gt;&#34;&amp; name',html)
        self.assertNotIn(long,html)
        self.assertIn('unbroken'*35,html)

    def test_report_uses_only_seven_selects_and_does_not_write(self):
        self.seed();self.round(1);self.c.commit()
        changes=self.c.total_changes;statements=[]
        self.c.set_trace_callback(statements.append)
        self.data()
        self.c.set_trace_callback(None)
        self.assertEqual(len(statements),7)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))
        self.assertEqual(self.c.total_changes,changes)

    def test_route_uses_read_snapshot_closes_connection_and_clamps_pages(self):
        self.seed();self.round(1);self.c.commit()
        test=self
        class Tracked:
            closed=False
            def execute(self,*args):return test.c.execute(*args)
            def close(self):self.closed=True;test.c.rollback()
        for page in ('bad','999','-5'):
            conn=Tracked()
            with patch('special_modes.get_db_connection',return_value=conn):
                response=app.test_client().get('/elo_guesser_stats?history_page='+page)
            self.assertEqual(response.status_code,200)
            self.assertTrue(conn.closed)
            self.assertIn(b'Page 1 / 1',response.data)


if __name__=='__main__':unittest.main()
