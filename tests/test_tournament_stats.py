"""Tournament reporting regressions. Every write is to an isolated memory DB."""
import sqlite3
import unittest
from unittest.mock import patch

from services import app, ensure_tournament_schema
from mode_schema import ensure_mode_schema
from tournament_stats_data import build_tournament_stats, stage_name
import pages
import games

NOW = 1800000000


class TournamentStatsTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
            CREATE TABLE songs(id INTEGER PRIMARY KEY,title TEXT,album_id INTEGER,audio_url TEXT);
            CREATE TABLE artists(id INTEGER PRIMARY KEY,name TEXT,cover_url TEXT);
            CREATE TABLE albums(id INTEGER PRIMARY KEY,title TEXT,cover_url TEXT);
            CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE song_artists(song_id INTEGER,artist_id INTEGER);
            CREATE TABLE song_genres(song_id INTEGER,genre_id INTEGER);
            CREATE TABLE global_stats(key TEXT PRIMARY KEY,value REAL);
            CREATE TABLE history(id INTEGER PRIMARY KEY);
            CREATE TABLE tournaments(id INTEGER PRIMARY KEY,size INTEGER,scope_type TEXT,scope_id INTEGER,champion_id INTEGER,timestamp TEXT);
        ''')
        ensure_tournament_schema(self.c)
        ensure_mode_schema(self.c)
        self.c.commit()

    def insert(self, table, **values):
        self.c.execute('INSERT INTO '+table+' ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')', tuple(values.values()))

    def seed(self):
        for id, name in [(1, 'Artist, One'), (2, 'Artist Two')]:
            self.insert('artists', id=id, name=name, cover_url='/artist.png')
        for id, name in [(1, 'Full Album'), (2, 'Track - Single'), (3, 'Unknown Album')]:
            self.insert('albums', id=id, title=name, cover_url='/cover.png')
        for id in (1, 2):
            self.insert('genres', id=id, name='Tag '+str(id))
        for id in range(1, 13):
            self.insert('songs', id=id, title='Song '+str(id), album_id=1 if id<10 else 2 if id==10 else 3 if id==11 else None, audio_url='')
            self.insert('song_artists', song_id=id, artist_id=1)
            self.insert('song_genres', song_id=id, genre_id=1)
        self.insert('song_artists', song_id=1, artist_id=2)
        self.insert('song_artists', song_id=1, artist_id=1)
        self.insert('song_genres', song_id=1, genre_id=1)

    def bracket(self, id, **extra):
        row=dict(id=id, size=8, scope_type='global', status='completed', champion_id=1,
                 completed_at=NOW-id, created_at=NOW-id-60, is_blind=0, playoff_enabled=1)
        row.update(extra)
        self.insert('tournaments', **row)

    def entry(self, bracket, song, seed):
        self.insert('tournament_entries', tournament_id=bracket, song_id=song, seed=seed)

    def match(self, id, bracket=1, **extra):
        row=dict(id=id, tournament_id=bracket, round_number=1, match_number=id,
                 song1_id=1, song2_id=2, winner_id=1, loser_id=2, status='completed',
                 points_awarded=1, played_at=NOW-id, match_type='bracket')
        row.update(extra)
        self.insert('tournament_matches', **row)

    def data(self, **kwargs):
        return build_tournament_stats(self.c, now=NOW, **kwargs)

    def render(self, d):
        with app.test_request_context('/tournament_stats'):
            return app.jinja_env.get_template('tournament_stats.html').render(**d,app_version='3.4.6')

    def test_empty_dashboard_rates_are_unknown_and_counts_are_zero(self):
        d=self.data()
        self.assertEqual(d['summary']['brackets'],0)
        self.assertIsNone(d['summary']['completion'])
        self.assertIsNone(d['summary']['points'])
        self.assertIsNone(d['seeds']['upset_share'])
        self.assertIsNone(d['coverage']['share'])
        html=self.render(d)
        self.assertIn('No tournaments yet.',html)
        self.assertIn('aria-valuetext="No attempts yet"',html)
        self.assertNotIn('≥0',html)

    def test_all_saved_brackets_count_and_recent_archive_is_paged(self):
        self.seed()
        for id in range(1,122):self.bracket(id)
        d=self.data()
        self.assertEqual(d['summary']['brackets'],121)
        self.assertEqual(d['summary']['entries'],968)
        self.assertEqual(d['archive_pages'],13)
        self.assertEqual([t['id'] for t in d['archive']],list(range(1,11)))
        self.assertEqual(d['latest']['id'],1)
        self.assertEqual([t['id'] for t in d['recent_champions']],[2,3,4,5,6])

    def test_only_completed_status_awards_places_and_completion(self):
        self.seed()
        self.bracket(1,status='in_progress',champion_id=1,completed_at=None)
        self.entry(1,1,1);self.match(1)
        d=self.data()
        self.assertEqual(d['summary']['unfinished'],1)
        self.assertEqual(d['summary']['finished'],0)
        self.assertEqual(d['summary']['matches'],1)
        self.assertEqual(d['coverage']['champions'],0)
        self.assertIsNone(d['latest'])
        self.assertEqual(d['summary']['completion'],0)
        self.assertIn('(1 unfinished)',self.render(d))

    def test_entry_counts_use_declared_slots_or_saved_entries_and_disclose_unknown(self):
        self.seed()
        self.bracket(1,size=8);self.bracket(2,size=16);self.bracket(3,size=0);self.bracket(4,size=0)
        for song in range(1,5):self.entry(3,song,song)
        d=self.data()
        self.assertEqual((d['summary']['entries'],d['summary']['missing_entries']),(28,1))
        self.assertEqual(d['coverage']['entered'],4)
        self.assertIn('≥28',self.render(d))
        self.assertEqual(d['sizes'][-1]['count'],2)

    def test_breakdowns_count_every_scope_visibility_and_size(self):
        self.seed()
        for id,(size,kind,blind) in enumerate([(32,'global',1),(16,'artist',0),(8,'album',1),(8,'tag',0),(4,'legacy',2)],1):
            self.bracket(id,size=size,scope_type=kind,is_blind=blind,scope_id=1)
        d=self.data()
        for key in ('sizes','scopes','visibility'):
            self.assertEqual(sum(r['count'] for r in d[key]),5)
            self.assertAlmostEqual(sum(r['share'] for r in d[key]),100)
        self.assertEqual(d['scopes'][-1]['label'],'Not recorded')
        self.assertEqual(d['visibility'][-1]['count'],1)

    def test_stages_use_saved_round_not_last_created_round(self):
        self.seed();self.bracket(1,status='in_progress',champion_id=None,completed_at=None)
        self.match(1,round_number=1,match_number=1)
        d=self.data()
        self.assertEqual(d['stages'][0]['label'],'Quarter-finals')
        self.assertEqual(d['archive'][0]['rounds'][0]['label'],'Quarter-finals')
        self.assertEqual(d['archive'][0]['progress'],12.5)
        self.assertEqual(stage_name(16,1),'Round of 16')
        self.assertEqual(stage_name(32,5),'Final')
        self.assertEqual(stage_name(32,5,'third_place'),'Third-place playoff')

    def test_podium_recovers_exact_final_and_bronze_and_uses_actual_points(self):
        self.seed();self.bracket(1,champion_id=None)
        self.match(1,round_number=1,match_number=1,points_awarded=1)
        self.match(2,round_number=2,match_number=1,points_awarded=2)
        self.match(3,round_number=3,match_number=1,points_awarded=4)
        self.match(4,round_number=3,match_number=0,song1_id=3,song2_id=4,winner_id=3,loser_id=4,match_type='third_place',points_awarded=.5)
        d=self.data();t=d['latest']
        self.assertEqual([p['song']['id'] for p in t['podium']],[1,2,3])
        self.assertEqual([p['points'] for p in t['podium']],[7,0,.5])
        self.assertEqual(d['summary']['points'],7.5)
        self.assertEqual((d['summary']['main_matches'],d['summary']['bronze_matches']),(3,1))
        self.assertEqual(self.c.execute('SELECT champion_id FROM tournaments').fetchone()[0],None)
        self.assertEqual(d['categories'][0]['rows'][0]['podiums'],3)

    def test_legacy_header_without_rounds_keeps_champion_but_not_fake_points(self):
        self.seed();self.bracket(1)
        d=self.data()
        self.assertEqual(d['coverage']['champions'],1)
        self.assertEqual(d['latest']['podium'][0]['song']['id'],1)
        self.assertIsNone(d['latest']['podium'][0]['points'])
        self.assertIsNone(d['latest']['podium'][1]['song']['id'])
        self.assertIsNone(d['latest']['podium'][1]['points'])
        self.assertIn('Detailed rounds were not recorded',self.render(d))

    def test_seed_patterns_use_saved_seeds_and_eligible_pairs_only(self):
        self.seed();self.bracket(1,champion_id=1);self.bracket(2,champion_id=3)
        self.entry(1,1,1);self.entry(1,2,8);self.entry(2,3,8)
        self.match(1,winner_id=2,loser_id=1)
        self.match(2,winner_id=1,loser_id=2)
        self.match(3,song1_id=1,song2_id=3,winner_id=3,loser_id=1)
        self.match(4,song1_id=3,song2_id=4,winner_id=2,loser_id=1)
        d=self.data();s=d['seeds']
        self.assertEqual((s['known'],s['first'],s['top_half'],s['bottom_half']),(2,1,1,1))
        self.assertEqual((s['matches'],s['upsets'],s['upset_share']),(2,1,50))
        self.assertEqual(s['largest']['seed'],8)

    def test_groups_deduplicate_collaborations_and_exclude_non_albums(self):
        self.seed();self.bracket(1);self.entry(1,1,1);self.entry(1,2,2);self.entry(1,10,3);self.entry(1,11,4);self.entry(1,12,5)
        self.match(1)
        d=self.data()
        a={r['id']:r for r in d['categories'][0]['rows']}
        self.assertEqual((a[1]['titles'],a[1]['tracks'],a[1]['brackets']),(1,5,1))
        self.assertEqual(a[2]['titles'],1)
        self.assertEqual(d['categories'][2]['rows'][0]['titles'],1)
        self.assertEqual([r['id'] for r in d['categories'][1]['rows']],[1])
        html=self.render(d)
        self.assertIn('/artist/Artist,%20One',html)
        self.assertNotIn('/album/Track%20-%20Single',html)
        self.assertNotIn('/album/Unknown%20Album',html)

    def test_points_keep_real_zero_and_exclude_invalid_saved_values(self):
        self.seed();self.bracket(1)
        for id,points in enumerate([0,'',-1,'invalid',float('inf')],1):self.match(id,points_awarded=points)
        d=self.data()
        self.assertEqual(d['summary']['points'],0)
        self.assertEqual(d['summary']['missing_points'],4)
        self.assertEqual(d['summary']['matches'],5)

    def test_group_points_are_pooled_before_rounding(self):
        self.seed();self.bracket(1)
        self.match(1,points_awarded=.2258)
        self.match(2,song1_id=3,song2_id=4,winner_id=3,loser_id=4,points_awarded=.2258)
        d=self.data()
        self.assertEqual(d['summary']['points'],.45)
        self.assertEqual(d['categories'][0]['rows'][0]['points'],.45)

    def test_missing_champion_evidence_has_no_fake_zero_or_conflicting_final(self):
        self.seed();self.bracket(1,champion_id=999)
        self.match(1,round_number=3,match_number=1)
        d=self.data()
        self.assertIsNone(d['latest']['podium'][0]['song']['id'])
        self.assertIsNone(d['latest']['podium'][0]['points'])
        self.assertIsNone(d['latest']['podium'][1]['song']['id'])

    def test_participation_includes_unfinished_and_legacy_results_without_entries(self):
        self.seed();self.bracket(1,status='in_progress',champion_id=None,completed_at=None)
        self.match(1)
        self.bracket(2,champion_id=3)
        d=self.data()
        self.assertEqual(d['coverage']['entered'],3)
        self.assertEqual(d['coverage']['unentered'],9)
        self.assertEqual(d['coverage']['champions'],1)
        self.assertEqual(d['coverage']['share'],25)

    def test_selected_old_bracket_opens_its_page_and_active_brackets_come_first(self):
        self.seed()
        for id in range(1,26):self.bracket(id)
        self.bracket(26,status='in_progress',champion_id=None,completed_at=None)
        d=self.data(selected=25)
        self.assertEqual(d['archive_page'],3)
        self.assertEqual([t['id'] for t in self.data()['archive']][:2],[26,1])
        self.assertTrue(next(t for t in d['archive'] if t['id']==25)['selected'])
        self.assertIn('id="tournament-25" open',self.render(d))
        self.assertEqual(self.data(archive_page=100)['archive_page'],3)
        self.assertEqual(self.data(archive_page=-3)['archive_page'],1)
        self.assertTrue(self.data(selected=999)['selected_missing'])

    def test_activity_windows_and_dates_are_actual_completion_not_creation(self):
        self.seed()
        for id,seconds in enumerate([0,7*86400,7*86400+1,30*86400,30*86400+1,-1],1):
            self.bracket(id,completed_at=NOW-seconds,created_at=NOW-1000*86400)
        self.bracket(7,completed_at=None,created_at=NOW-20)
        self.match(1,played_at=NOW-7*86400);self.match(2,played_at=NOW+1)
        d=self.data()
        self.assertEqual((d['summary']['week'],d['summary']['month'],d['summary']['match_week']),(2,4,1))
        self.assertEqual(d['latest']['id'],6)
        self.assertEqual(d['summary']['finished'],7)

    def test_missing_identities_and_long_names_keep_safe_links(self):
        self.seed();self.bracket(1,champion_id=999,scope_type='artist',scope_id=999)
        self.match(1,song1_id=None,song2_id=2,winner_id=None,loser_id=2)
        long='Long <script>unsafe()</script> & "name" '*20
        self.c.execute('UPDATE songs SET title=? WHERE id=2',(long,))
        html=self.render(self.data(selected=1))
        self.assertIn('Track unavailable',html)
        self.assertNotIn('/song/999',html)
        self.assertNotIn('/song/None',html)
        self.assertNotIn('<script>unsafe()',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('Artist scope',html)

    def test_read_only_projection_has_fixed_select_count(self):
        self.seed();self.bracket(1);self.match(1);self.c.commit()
        before='\n'.join(self.c.iterdump());changes=self.c.total_changes;statements=[]
        self.c.set_trace_callback(statements.append);self.data();self.c.set_trace_callback(None)
        self.assertEqual(len(statements),9)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))
        self.assertEqual(self.c.total_changes,changes)
        self.assertEqual('\n'.join(self.c.iterdump()),before)

    def test_route_owns_snapshot_passes_filters_and_closes(self):
        with patch.object(games,'get_db_connection') as get_conn,patch('tournament_stats_data.build_tournament_stats',return_value=self.data()) as build:
            r=app.test_client().get('/tournament_stats?tournament=23&archive_page=2')
            self.assertEqual(r.status_code,200)
            get_conn.return_value.execute.assert_called_once_with('BEGIN')
            build.assert_called_once_with(get_conn.return_value,selected=23,archive_page=2)
            get_conn.return_value.close.assert_called_once()


if __name__=='__main__':unittest.main()
