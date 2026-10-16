"""Shelves reporting regressions: saved facts, isolated in-memory fixtures."""
import sqlite3
import unittest
from unittest.mock import patch

from services import app
from special_schema import ensure_special_schema
from special_modes import special_records, shelf_pool
from shelves_stats_data import build_shelves_stats
import pages
import special_modes

NOW = 1800000000


class ShelvesStatsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
            CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,audio_url TEXT,track_number INTEGER);
            CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT,cover_url TEXT);
            CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
            CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
            CREATE TABLE song_genres(song_id INTEGER,genre_id INTEGER);
        ''')
        ensure_special_schema(self.c)
        self.c.commit();self.song_ids={}

    def insert(self,table,**values):
        self.c.execute('INSERT INTO '+table+' ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',tuple(values.values()))

    def seed(self,sizes=(10,10,10)):
        for sid,name in ((1,'Artist, One'),(2,'Artist Two')):self.insert('artists',id=sid,name=name,cover_url='/artist.png')
        self.insert('genres',id=1,name='Tag One')
        sid=0
        for aid,count in enumerate(sizes,1):
            self.insert('albums',id=aid,title='Album '+str(aid),cover_url='/cover.png')
            self.song_ids[aid]=[]
            for j in range(count):
                sid+=1;self.song_ids[aid].append(sid)
                self.insert('songs',id=sid,title='Song '+str(sid),album_id=aid,audio_url='',track_number=j*3+1)
                self.insert('song_artists',song_id=sid,artist_id=1)
                self.insert('song_genres',song_id=sid,genre_id=1)
        self.insert('song_artists',song_id=1,artist_id=1)
        self.insert('song_artists',song_id=1,artist_id=2)
        self.insert('song_genres',song_id=1,genre_id=1)

    def round(self,rid,counts=(5,5),albums=(1,2),completed=True,stamp=None,reverse=False):
        self.insert('album_shelf_rounds',id=rid,token='private-shelf-token-'+str(rid),started_at=NOW-2000+rid,
                    completed_at=(NOW-1000+rid if stamp is None else stamp) if completed else None)
        slot=0
        for shelf,(aid,count) in enumerate(zip(albums,counts),1):
            for j,sid in enumerate(self.song_ids[aid][:count],1):
                slot+=1
                self.insert('album_shelf_items',round_id=rid,item_slot=slot,song_id=sid,album_id=aid,album_slot=shelf,
                            track_number=(j-1)*3+1,answer_slot=shelf if completed else None,
                            answer_position=count-j+1 if reverse and shelf==1 else j if completed else None)

    def data(self,**kwargs):return build_shelves_stats(self.c,now=NOW,**kwargs)

    def render(self,data):
        with app.test_request_context('/album_shelves_stats'):
            return app.jinja_env.get_template('shelves_stats.html').render(**data,app_version='3.4.8')

    def test_empty_counts_and_rates_are_not_invented(self):
        d=self.data();self.assertEqual(d['summary']['rounds'],0)
        self.assertIsNone(d['summary']['order_accuracy']);self.assertIsNone(d['coverage']['album_share'])
        self.assertIsNone(d['best_round']);self.assertEqual(d['history_pages'],1)
        html=self.render(d)
        self.assertIn('No completed Shelves rounds yet.',html)
        self.assertIn('aria-valuetext="No attempts yet"',html)

    def test_perfect_round_preserves_gapped_track_numbers(self):
        self.seed();self.round(1);d=self.data();s=d['summary']
        self.assertEqual((s['rounds'],s['tracks'],s['points'],s['available'],s['perfect']),(1,10,30,30,1))
        self.assertEqual((s['order_right'],s['order_pairs'],s['order_accuracy']),(40,40,100))
        self.assertEqual((s['fully_correct'],s['wrong_album'],s['order_affected']),(10,0,0))
        self.assertEqual([i['saved_track'] for i in d['history'][0]['groups'][0]['items']],[1,4,7,10,13])

    def test_summary_agrees_with_existing_shared_grader(self):
        self.seed();self.round(1);self.round(2,reverse=True)
        old=special_records(self.c)[1]['shelves'];new=self.data()['summary']
        for key in ('rounds','tracks','points','available','perfect','album_correct','order_right','order_pairs','albums_played'):
            self.assertAlmostEqual(new[key],old[key],msg=key)

    def test_order_errors_differ_from_album_placement(self):
        self.seed();self.round(1,reverse=True);s=self.data()['summary']
        self.assertEqual((s['album_correct'],s['order_right'],s['order_pairs']),(10,20,40))
        self.assertEqual(s['order_accuracy'],50)
        self.assertEqual(s['points'],17.5)
        self.assertEqual((s['fully_correct'],s['wrong_album'],s['order_affected']),(5,0,5))

    def test_misplaced_counterpart_affects_order_without_double_counting_track_outcomes(self):
        self.seed();self.round(1)
        self.c.execute('UPDATE album_shelf_items SET answer_slot=2,answer_position=6 WHERE round_id=1 AND item_slot=1')
        s=self.data()['summary']
        self.assertEqual((s['fully_correct'],s['wrong_album'],s['order_affected']),(5,1,4))
        self.assertEqual(s['order_right'],32);self.assertEqual(s['order_accuracy'],80)
        self.assertEqual(s['points'],24.5)

    def test_zero_score_round_is_not_missing_data(self):
        self.seed();self.round(1)
        self.c.execute('UPDATE album_shelf_items SET answer_slot=3-album_slot')
        d=self.data();self.assertEqual(d['history'][0]['outcome'],'zero')
        self.assertEqual(d['summary']['points'],0);self.assertEqual(d['summary']['order_accuracy'],0)
        self.assertEqual(d['summary']['unknown'],0)

    def test_legacy_singletons_have_half_point_denominator_and_no_free_order(self):
        self.seed();self.round(1,counts=(1,1));d=self.data();s=d['summary']
        self.assertEqual((s['points'],s['available'],s['perfect']),(1,1,1))
        self.assertEqual(s['order_pairs'],0);self.assertIsNone(s['order_accuracy'])
        self.assertEqual(d['top_tracks'],[]);self.assertEqual(s['legacy_sizes'],1)

    def test_ten_track_legacy_round_can_have_less_than_thirty_available_points(self):
        self.seed();self.round(1,counts=(1,1,8),albums=(1,2,3))
        s=self.data()['summary'];self.assertEqual((s['tracks'],s['available'],s['points']),(10,25,25))
        self.assertEqual(s['order_pairs'],56)

    def test_all_history_counts_and_only_archive_display_is_paged(self):
        self.seed()
        for rid in range(1,66):self.round(rid)
        d=self.data(history_page=7)
        self.assertEqual((d['summary']['rounds'],d['summary']['tracks']),(65,650))
        self.assertEqual(d['history_pages'],7)
        self.assertEqual([r['id'] for r in d['history']],[5,4,3,2,1])
        self.assertEqual((d['history_start'],d['history_end']),(61,65))

    def test_selected_older_round_opens_its_own_page(self):
        self.seed()
        for rid in range(1,26):self.round(rid)
        d=self.data(selected=1)
        self.assertEqual(d['history_page'],3);self.assertEqual(d['selected_round'],1)
        self.assertIn('id="shelf-round-1" data-shelf-round="1" open',self.render(d))
        self.assertTrue(self.data(selected=999)['selection_missing'])

    def test_pending_rounds_and_tokens_never_enter_report(self):
        self.seed();self.round(1);self.round(2,completed=False)
        d=self.data();self.assertEqual(d['summary']['rounds'],1)
        self.assertFalse(any('token' in r or 'started_at' in r for r in d['history']))
        self.assertTrue(self.data(selected=2)['selection_missing'])
        self.assertNotIn('private-shelf-token-',self.render(d))

    def test_rolling_windows_latest_ten_and_future_exclusion(self):
        self.seed()
        for rid,stamp in enumerate((NOW,NOW-7*86400,NOW-7*86400-1,NOW-30*86400,NOW-30*86400-1,NOW+1),1):self.round(rid,stamp=stamp)
        d=self.data();self.assertEqual([w['rounds'] for w in d['windows']],[6,2,4])
        self.assertEqual(d['summary']['active_days'],3)
        for rid in range(7,17):self.round(rid,reverse=True)
        self.assertEqual(self.data()['windows'][0]['rounds'],10)

    def test_perfect_streaks_follow_completion_order(self):
        self.seed()
        for rid in range(1,7):self.round(rid,reverse=rid==3)
        s=self.data()['summary'];self.assertEqual((s['current_streak'],s['best_streak']),(3,3))

    def test_order_percentages_pool_comparisons_not_round_percentages(self):
        self.seed();self.round(1,counts=(2,8));self.round(2)
        self.c.execute('UPDATE album_shelf_items SET answer_slot=3-album_slot WHERE round_id=2')
        s=self.data()['summary'];self.assertEqual((s['order_right'],s['order_pairs']),(58,98))
        self.assertEqual(s['order_accuracy'],59.2)
        self.assertEqual((s['points'],s['available']),(30,60))

    def test_frozen_album_participation_and_numbers_survive_catalogue_changes(self):
        self.seed();self.round(1);before=self.data()
        self.c.execute('UPDATE songs SET album_id=3,track_number=900+id WHERE album_id=1')
        after=self.data()
        self.assertEqual(before['summary']['points'],after['summary']['points'])
        albums={r['id']:r for r in after['album_records']['rows']}
        self.assertEqual(albums[1]['attempts'],5)
        self.assertEqual([i['saved_track'] for i in after['history'][0]['groups'][0]['items']],[1,4,7,10,13])

    def test_deleted_tracks_and_albums_preserve_slots_and_scores(self):
        self.seed();self.round(1)
        self.c.execute('UPDATE album_shelf_items SET song_id=NULL,album_id=NULL')
        self.c.execute('DELETE FROM songs');self.c.execute('DELETE FROM albums')
        d=self.data();self.assertEqual((d['summary']['points'],d['summary']['available']),(30,30))
        self.assertEqual(d['summary']['albums_played'],0)
        self.assertEqual(d['summary']['missing_album_slots'],2)
        self.assertEqual([g['slot'] for g in d['history'][0]['groups']],[1,2])
        html=self.render(d);self.assertIn('Removed track',html);self.assertIn('Album unavailable',html)
        self.assertNotIn('/song/None',html);self.assertNotIn('/album/Album%20unavailable',html)

    def test_duplicate_artist_tag_links_are_deduplicated(self):
        self.seed();self.round(1);d=self.data()
        groups={g['kind']:g for g in d['categories']}
        artist=next(r for r in groups['artist']['best'] if r['id']==1)
        self.assertEqual((artist['attempts'],artist['order_pairs']),(10,40))
        collaborator=next(r for r in groups['artist']['best'] if r['id']==2)
        self.assertEqual((collaborator['attempts'],collaborator['order_pairs']),(1,4))
        self.assertEqual(groups['tag']['best'][0]['order_pairs'],40)

    def test_coverage_uses_actual_ten_track_round_feasibility(self):
        self.seed(sizes=(4,3,3,2))
        self.assertEqual(set(shelf_pool(self.c)),{1,2,3,4})
        coverage=self.data()['coverage']
        self.assertEqual((coverage['albums'],coverage['tracks']),(3,10))
        self.c.execute('DELETE FROM songs WHERE album_id=3')
        self.assertEqual(self.data()['coverage']['albums'],0)

    def test_eligibility_excludes_bad_positions_singles_unknown_and_has_no_audio_requirement(self):
        self.seed(sizes=(10,10,10))
        self.c.execute("UPDATE albums SET title='Track - Single' WHERE id=3")
        self.c.execute('UPDATE songs SET track_number=1 WHERE id=2')
        self.c.execute('UPDATE songs SET track_number=0 WHERE id=3')
        self.c.execute('UPDATE songs SET track_number=1.5 WHERE id=4')
        self.assertEqual(self.data()['coverage']['tracks'],16)
        self.c.execute("UPDATE albums SET title='Unknown Album' WHERE id=2")
        self.assertEqual(self.data()['coverage']['tracks'],0)

    def test_all_played_albums_remain_accessible_with_pagination(self):
        self.seed(sizes=(5,)*14)
        for rid in range(1,8):self.round(rid,albums=(rid*2-1,rid*2))
        d=self.data(album_page=2)
        self.assertEqual((d['summary']['albums_played'],d['album_records']['pages']),(14,2))
        self.assertEqual(len(d['album_records']['rows']),4)
        self.assertEqual(d['album_records']['total'],14)

    def test_current_nonalbum_identity_is_unlinked_but_not_erased_from_history(self):
        self.seed();self.round(1)
        self.c.execute("UPDATE albums SET title='Changed - Single' WHERE id=1")
        d=self.data();self.assertEqual(d['summary']['albums_played'],2)
        self.assertTrue(any(r['name']=='Changed - Single' for r in d['album_records']['rows']))
        self.assertFalse(any(r['name']=='Changed - Single' for r in d['album_records']['best']))
        html=self.render(d);self.assertNotIn('/album/Changed%20-%20Single',html)

    def test_practice_omits_perfect_and_singleton_only_tracks(self):
        self.seed(sizes=(10,)*5);self.round(1);self.round(2)
        self.round(3,albums=(4,5),reverse=True)
        d=self.data();self.assertTrue(d['practice_tracks'])
        self.assertTrue(all(r['order_wrong']>0 for r in d['practice_tracks']))
        self.assertFalse(any(r['id'] in self.song_ids[1] for r in d['practice_tracks']))

    def test_incomplete_and_invalid_answers_are_unavailable_not_zero_or_perfect(self):
        self.seed()
        for rid in range(1,5):self.round(rid)
        self.c.execute('UPDATE album_shelf_items SET answer_position=NULL,answer_slot=NULL WHERE round_id=1 AND item_slot=1')
        self.c.execute('UPDATE album_shelf_items SET answer_position=1 WHERE round_id=2 AND item_slot=2')
        self.c.execute('UPDATE album_shelf_items SET track_number=1 WHERE round_id=3 AND item_slot=2')
        self.c.execute('UPDATE album_shelf_items SET answer_slot=3 WHERE round_id=4 AND item_slot=1')
        s=self.data()['summary'];self.assertEqual((s['rounds'],s['unknown'],s['scored_rounds']),(4,4,0))
        self.assertEqual(s['perfect'],0);self.assertIsNone(s['order_accuracy'])
        self.assertIsNone(s['current_streak'])

    def test_header_only_unknown_rules_and_undated_history_are_explicit(self):
        self.seed();self.round(1);self.round(2,stamp='bad date')
        self.insert('album_shelf_rounds',id=3,token='header-only',started_at=NOW-1,completed_at=NOW)
        self.c.execute('PRAGMA ignore_check_constraints=ON')
        self.c.execute('UPDATE album_shelf_rounds SET rules_version=99 WHERE id=1')
        d=self.data();self.assertEqual(d['summary']['unknown'],2)
        self.assertEqual(d['summary']['undated'],1);self.assertIsNone(d['summary']['current_streak'])
        self.assertEqual(len(d['formats']),3)
        self.assertIn('incomplete saved answers',self.render(d))

    def test_long_names_are_escaped_and_full_names_preserved(self):
        self.seed();self.round(1)
        long='Long <script>"& name '+('unbroken'*35)
        for table,column in (('songs','title'),('artists','name'),('albums','title'),('genres','name')):
            self.c.execute('UPDATE '+table+' SET '+column+'=?',(long,))
        html=self.render(self.data())
        self.assertNotIn(long,html);self.assertIn('Long &lt;script&gt;&#34;&amp; name',html)
        self.assertIn('unbroken'*35,html)

    def test_report_is_nine_selects_without_writes(self):
        self.seed();self.round(1);self.c.commit();before=self.c.total_changes;statements=[]
        self.c.set_trace_callback(statements.append);self.data();self.c.set_trace_callback(None)
        self.assertEqual(len(statements),9)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))
        self.assertEqual(before,self.c.total_changes)

    def test_route_clamps_pages_and_closes_read_snapshot_on_success_and_failure(self):
        self.seed();self.round(1);self.c.commit();test=self
        class Tracked:
            closed=False
            def execute(self,*args):return test.c.execute(*args)
            def close(self):self.closed=True;test.c.rollback()
        for query in ('history_page=bad','history_page=999','album_page=-1','round=1'):
            conn=Tracked()
            with patch('special_modes.get_db_connection',return_value=conn):response=app.test_client().get('/album_shelves_stats?'+query)
            self.assertEqual(response.status_code,200);self.assertTrue(conn.closed)
        conn=Tracked()
        with patch('special_modes.get_db_connection',return_value=conn),patch('shelves_stats_data.build_shelves_stats',side_effect=RuntimeError('isolated failure')),patch.dict(app.config,TESTING=True):
            self.assertRaises(RuntimeError,app.test_client().get,'/album_shelves_stats')
        self.assertTrue(conn.closed)


if __name__=='__main__':unittest.main()
