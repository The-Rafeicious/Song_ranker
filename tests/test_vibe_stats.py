"""Descriptive dashboard facts, evidence boundaries and read-only HTTP contract."""
import unittest
from unittest.mock import patch
from songranker.reports.vibe_stats_data import build_vibe_stats, consistency, density, common_patterns
from songranker.modes import vibe_map  # Register mode routes before exercising Flask.
from songranker.modes.vibe_similarity import compare_positions
from songranker.storage.vibe_state import MAPS
from songranker.storage.database_io import capture
from songranker import pages
import test_preferences as fixture


class VibeStatsTests(unittest.TestCase):
    setUp = fixture.PreferenceTests.setUp
    connect = fixture.PreferenceTests.connect

    def place(self,sid,x=0,y=0,maps=4,samples=1):
        for key,*_ in MAPS[:maps]:
            self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=?,y=?,sample_count=?,updated_at=1 WHERE song_id=? AND map_id=?",(x,y,samples,sid,key))
        self.conn.commit()

    def test_empty_and_partial_points_do_not_invent_evidence(self):
        data=build_vibe_stats(self.conn)
        self.assertEqual(data['overview']['selected'],0)
        self.assertEqual(data['closest'],[])
        self.assertTrue(all(not m['points'] for m in data['maps']))
        self.place(1,-.8,-.8,maps=1,samples=3)
        self.conn.execute("UPDATE song_vibe_positions SET status='not_applicable',updated_at=1 WHERE song_id=2")
        self.conn.commit();data=build_vibe_stats(self.conn)
        self.assertEqual((data['overview']['selected'],data['overview']['partial'],data['overview']['full']),(2,2,0))
        self.assertEqual(data['overview']['samples'],3)
        self.assertEqual([m['count'] for m in data['maps']],[1,0,0,0])
        self.assertEqual(data['maps'][0]['points'][0]['song_id'],1)
        self.assertEqual(data['closest'],[])
        self.assertTrue(all(not g['most'] for g in data['groups']))

    def test_consistency_matches_two_track_similarity_and_includes_every_map(self):
        a={key:(-.5,.7) for key,*_ in MAPS};b={key:(.1,-.2) for key,*_ in MAPS}
        self.assertAlmostEqual(consistency([a,b]),compare_positions(a,b)['similarity'])
        self.assertEqual(consistency([a,a,a]),100)
        self.assertIsNone(consistency([a]))
        mixed=dict(a);mixed[MAPS[-1][0]]=(1,-1)
        self.assertLess(consistency([a,mixed]),100)
        # Three-track closed form equals the explicit average squared pair distance.
        import math
        from itertools import combinations
        from songranker.modes.vibe_similarity import WIDTH
        vectors=[a,b,mixed]
        distances=[sum(sum((x-y)**2 for x,y in zip(v[key],w[key])) for key,*_ in MAPS)/4 for v,w in combinations(vectors,2)]
        self.assertAlmostEqual(consistency(vectors),100*math.exp(-sum(distances)/len(distances)/(2*WIDTH**2)))

    def test_density_preserves_overlaps_and_fixed_radius(self):
        points=[dict(x=0,y=0),dict(x=0,y=0),dict(x=.2,y=0),dict(x=1,y=1)]
        self.assertEqual(density(points),3)
        self.assertEqual([p['nearby'] for p in points],[3,3,3,1])
        self.assertEqual([(p['x'],p['y']) for p in points],[(0,0),(0,0),(.2,0),(1,1)])

    def test_common_combinations_use_only_shared_placed_evidence(self):
        key=MAPS[0][0];future=MAPS[-1][0]
        balances,patterns=common_patterns({1:{key:(-.8,-.8)},2:{key:(.8,0),future:(0,.8)},3:{key:(0,0)}})
        names={p['label']:p for p in patterns}
        self.assertEqual(names['Slow + Sad']['count'],1)
        self.assertEqual(names['Slow + Sad']['total'],3)
        self.assertEqual(names['Upbeat + Hopeful']['total'],1)
        self.assertEqual(names['Upbeat + Hopeful']['share'],100)
        self.assertEqual(balances[0]['middle_count'],1)
        self.assertEqual(balances[-2]['centre'],'Present')

    def test_rankings_counts_pairs_and_read_only_repeats(self):
        self.place(1,-1,-1,samples=6);self.place(2,-1,-1);self.place(3,1,1);self.place(6,.3,.2);self.place(7,.3,.2)
        self.conn.execute("UPDATE albums SET title='Other - Single' WHERE id=2")
        self.conn.commit();before=capture(self.conn);data=build_vibe_stats(self.conn)
        self.assertEqual(capture(self.conn),before)
        self.assertEqual(data['overview']['full'],5)
        self.assertEqual(data['overview']['repeated'],1)
        self.assertTrue(all(m['count']==5 for m in data['maps']))
        self.assertTrue(all(len({p['song_id'] for p in m['points']})==5 for m in data['maps']))
        self.assertEqual(len(data['closest']),2)
        self.assertEqual(data['closest'][0]['similarity'],100)
        self.assertEqual(len(data['contrasts']),2)
        pairs=[(p['first']['id'],p['second']['id']) for p in data['closest']]
        self.assertTrue(all(a<b for a,b in pairs));self.assertEqual(len(set(pairs)),2)
        album,artist,tag=data['groups']
        self.assertEqual(album['eligible'],1)
        self.assertEqual((album['most'][0]['mapped'],album['most'][0]['total']),(3,5))
        self.assertEqual(artist['most'][0]['mapped'],5)
        self.assertEqual(tag['most'][0]['mapped'],5)
        self.assertNotIn('_score',artist['most'][0])
        self.assertEqual(data,build_vibe_stats(self.conn))

    def test_group_order_and_top_five_cap(self):
        for sid in range(1,11):self.place(sid,0 if sid<6 else (sid-6)/4,0)
        for tid in range(2,9):
            self.conn.execute('INSERT INTO genres(id,name) VALUES(?,?)',(tid,'Tag '+str(tid)))
            for sid in (1,tid+1):self.conn.execute('INSERT INTO song_genres VALUES(?,?)',(sid,tid))
        self.conn.commit();data=build_vibe_stats(self.conn);tags=data['groups'][2]
        self.assertEqual(tags['eligible'],8)
        self.assertEqual(len(tags['most']),5);self.assertEqual(len(tags['least']),5)
        self.assertEqual(tags['most'][0]['consistency'],100)
        self.assertLess(tags['least'][0]['consistency'],100)
        self.assertEqual([r['consistency'] for r in tags['least']],sorted(r['consistency'] for r in tags['least']))

    def test_dashboard_and_api_are_read_only_and_handle_empty_and_filled_data(self):
        client=pages.app.test_client()
        with patch.object(pages,'get_db_connection',side_effect=self.connect):
            for filled in (False,True):
                if filled:self.place(1,-.8,-.8);self.place(2,-.8,-.8)
                before=capture(self.conn)
                response=client.get('/vibe_map_stats')
                self.assertEqual(response.status_code,200,response.data[:500])
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                html=response.get_data(as_text=True)
                self.assertIn('Common combinations',html);self.assertIn('data-page="vibe_stats"',html)
                self.assertEqual(html.count('data-vibe-point'),8 if filled else 0)
                response=client.get('/api/vibe-map/stats')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['overview']['full'],2 if filled else 0)
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertEqual(capture(self.conn),before)

    def test_inspector_radar_links_and_top_two_use_saved_averages_without_writes(self):
        from songranker.modes.vibe_map import similar_songs
        self.place(1,-.7,.6,samples=3);self.place(2,-.7,.6);self.place(3,.9,-.9);self.place(4,-.6,.5)
        before=capture(self.conn)
        expected=similar_songs(self.conn,1)['matches']
        response=pages.app.test_client().get('/api/vibe-map/inspect/1')
        self.assertEqual(response.status_code,200,response.data[:500])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        data=response.json
        self.assertEqual([m['song_id'] for m in data['matches']],[m['song_id'] for m in expected])
        self.assertEqual([m['similarity'] for m in data['matches']],[m['similarity'] for m in expected])
        self.assertEqual(len(data['profile']['radar']['spokes']),8)
        self.assertEqual(data['profile']['maps']['pace_mood']['sample_count'],3)
        self.assertIn('/song/1',data['html']);self.assertIn('/album/Album',data['html'])
        self.assertIn('class="artist"',data['html'])
        self.assertIn('data-vibe-song-radar',data['html'])
        self.assertEqual(capture(self.conn),before)

    def test_inspector_handles_partial_unmapped_and_deleted_songs(self):
        client=pages.app.test_client()
        data=client.get('/api/vibe-map/inspect/1').json
        self.assertEqual(data['matches'],[])
        self.assertTrue(all(s['radius'] is None for s in data['profile']['radar']['spokes']))
        self.place(1,0,0,maps=1);self.place(2,0,0,maps=1)
        data=client.get('/api/vibe-map/inspect/1').json
        self.assertEqual(len(data['matches']),1)
        self.assertEqual(data['matches'][0]['shared_maps'],1)
        self.assertEqual(sum(s['radius'] is not None for s in data['profile']['radar']['spokes']),2)
        self.assertIn('1 / 4 maps',data['html'])
        for sid in (0,99999):self.assertEqual(client.get('/api/vibe-map/inspect/'+str(sid)).status_code,400 if sid==0 else 404)

    def test_inspector_escapes_catalogue_text_and_excludes_unknown_album_links(self):
        self.conn.execute('UPDATE songs SET title=? WHERE id=1',('<script>alert(1)</script>',))
        self.conn.execute("UPDATE albums SET title='Unknown Album' WHERE id=1")
        self.conn.execute('UPDATE artists SET name=? WHERE id=1',('A "quoted" <artist>',))
        self.conn.commit()
        data=pages.app.test_client().get('/api/vibe-map/inspect/1').json
        self.assertIn('&lt;script&gt;',data['html']);self.assertNotIn('<script>',data['html'])
        self.assertIn('&lt;artist&gt;',data['html'])
        self.assertNotIn('class="album"',data['html'])

    def test_heatmap_points_are_inspect_buttons_with_explicit_song_links_separate(self):
        self.place(1)
        with patch.object(pages,'get_db_connection',side_effect=self.connect):
            html=pages.app.test_client().get('/vibe_map_stats').get_data(as_text=True)
        self.assertIn('role="button" tabindex="-1" aria-controls="vibe-song-inspector" data-song-id="1"',html)
        self.assertNotIn('<a href="/song/1" tabindex="-1" data-vibe-point',html)
        self.assertIn('Select a map point.',html)
