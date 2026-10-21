"""Library Vibe summaries, consistency boards and top-twenty boundaries."""
import unittest
from songranker import pages
from songranker.modes import special_modes, vibe_map
from songranker.reports.vibe_library_data import build_library_vibe, build_vibe_rankings
from songranker.reports.vibe_stats_data import build_vibe_stats
from songranker.storage.database_io import capture
import test_preferences as fixture


class VibeLibraryTests(unittest.TestCase):
    connect=fixture.PreferenceTests.connect

    def setUp(self):
        fixture.PreferenceTests.setUp(self)
        context=pages.app.app_context();context.push();self.addCleanup(context.pop)

    def place(self,sid,x=0,y=0,maps=4):
        for key,*_ in vibe_map.MAPS[:maps]:
            self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=?,y=?,sample_count=1,updated_at=1 WHERE song_id=? AND map_id=?",(x,y,sid,key))
        self.conn.commit()

    def test_empty_and_partial_library_keeps_missing_points_missing(self):
        data=build_library_vibe(self.conn)
        self.assertFalse(data['profile_ready']);self.assertTrue(all(not rows for rows in data['banner'].values()))
        self.assertEqual(data['summary']['coverage'],0)
        self.place(1,maps=1);self.place(2,.5,.5)
        data=build_library_vibe(self.conn)
        self.assertEqual((data['summary']['full'],data['summary']['partial'],data['summary']['selected']),(1,1,2))
        self.assertEqual([m['count'] for m in data['maps']],[2,1,1,1])
        self.assertEqual(data['counts'],dict(albums=0,artists=0,tags=0))
        self.assertFalse(data['profile_ready'])

    def test_rankings_match_dashboard_scores_and_library_dots_cover_every_song_once(self):
        for sid,x in ((1,-.8),(2,-.6),(6,.6),(7,.6)):self.place(sid,x,.2)
        before=capture(self.conn);data=build_library_vibe(self.conn)
        self.assertTrue(data['profile_ready']);self.assertEqual([m['count'] for m in data['maps']],[4]*4)
        self.assertEqual(data['html'].count('data-vibe-mini-song='),16)
        self.assertEqual(data['summary']['total'],10)
        dashboard=build_vibe_stats(self.conn)
        for category,group in zip(('albums','artists','tags'),dashboard['groups']):
            board=build_vibe_rankings(self.conn,category,'top')
            self.assertEqual([(r['id'],r['consistency']) for r in board['items']],[(r['id'],r['consistency']) for r in group['most']])
            self.assertEqual(data['banner'][category],board['items'])
        self.assertEqual(capture(self.conn),before)

    def test_top_and_bottom_twenty_use_the_full_population_rank_and_fixed_limit(self):
        self.place(1);self.place(2,.3,.2)
        for aid in range(2,27):
            self.conn.execute('INSERT INTO artists(id,name) VALUES(?,?)',(aid,'Artist '+str(aid)))
            self.conn.execute('INSERT INTO song_artists VALUES(1,?),(2,?)',(aid,aid))
        self.conn.commit()
        top=build_vibe_rankings(self.conn,'artists','top');bottom=build_vibe_rankings(self.conn,'artists','bottom')
        self.assertEqual(top['total'],26);self.assertEqual(top['limit'],20)
        self.assertEqual([r['rank'] for r in top['items']],list(range(1,21)))
        self.assertEqual([r['rank'] for r in bottom['items']],list(range(26,6,-1)))
        self.assertEqual(len(build_library_vibe(self.conn)['banner']['artists']),20)
        self.assertTrue(all(r['mapped']==2 for r in top['items']))

    def test_proper_album_and_two_complete_track_rules_apply(self):
        self.place(1);self.place(2);self.place(6);self.place(7,maps=3)
        self.conn.execute("UPDATE albums SET title='Album - Single' WHERE id=1");self.conn.commit()
        self.assertEqual(build_vibe_rankings(self.conn,'albums','top')['items'],[])
        self.place(7)
        self.assertEqual([r['id'] for r in build_vibe_rankings(self.conn,'albums','top')['items']],[2])

    def test_unrounded_scores_sort_before_ids_or_displayed_percentages(self):
        self.place(1);self.place(2,.0002,0)
        self.conn.execute("INSERT INTO albums(id,title) VALUES(3,'Closer')")
        for sid in (11,12):self.conn.execute('INSERT INTO songs(id,title,album_id) VALUES(?,?,3)',(sid,'Close '+str(sid)))
        self.conn.commit();self.place(11);self.place(12,.0001,0)
        rows=build_vibe_rankings(self.conn,'albums','top')['items']
        self.assertEqual([r['id'] for r in rows],[3,1]);self.assertEqual([r['consistency'] for r in rows],[100,100])

    def test_http_read_only_routes_assets_and_validation(self):
        client=pages.app.test_client();before=capture(self.conn)
        for url in ('/api/vibe-map/library','/api/vibe-map/rankings?entity=tags&view=bottom'):
            response=client.get(url);self.assertEqual(response.status_code,200,response.data[:500]);self.assertEqual(response.headers['Cache-Control'],'no-store')
        for query in ('entity=songs','entity=bogus','view=middle'):
            self.assertEqual(client.get('/api/vibe-map/rankings?'+query).status_code,400)
        for url in ('/','/global_stats','/mode_rankings/vibe'):
            response=client.get(url);self.assertEqual(response.status_code,200,response.data[:500]);self.assertIn('js/vibe_library.js',response.get_data(as_text=True))
        self.assertEqual(capture(self.conn),before)
