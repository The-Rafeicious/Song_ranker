"""Scoped descriptive cards preserve membership, evidence and database state."""
import unittest
from songranker import pages
from songranker.modes import vibe_map
from songranker.reports.vibe_entity_data import build_entity_vibe
from songranker.reports.vibe_stats_data import build_vibe_stats
from songranker.storage.database_io import capture
import test_preferences as fixture


class VibeEntityTests(unittest.TestCase):
    def setUp(self):
        fixture.PreferenceTests.setUp(self)
        context=pages.app.app_context();context.push();self.addCleanup(context.pop)
    connect=fixture.PreferenceTests.connect

    def place(self,sid,x=0,y=0,maps=4,samples=1):
        for key,*_ in vibe_map.MAPS[:maps]:
            self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=?,y=?,updated_at=1,sample_count=? WHERE song_id=? AND map_id=?",(x,y,samples,sid,key))
        self.conn.commit()

    def test_collection_membership_deduplicates_collaborations_and_scopes_tags(self):
        self.conn.execute("INSERT INTO artists(id,name) VALUES(2,'Second artist')")
        self.conn.execute('INSERT INTO song_artists VALUES(1,2),(2,2)')
        self.conn.execute("INSERT INTO genres(id,name) VALUES(2,'Second tag')")
        self.conn.execute('INSERT INTO song_genres VALUES(2,2),(6,2)');self.conn.commit()
        self.place(1,-.5,.8,samples=9);self.place(2,-.4,.8);self.place(6,.5,-.8)
        album=build_entity_vibe(self.conn,'album',1)
        self.assertEqual(album['summary']['total'],5)
        self.assertEqual([p['song_id'] for p in album['maps'][0]['points']],[1,2])
        artist=build_entity_vibe(self.conn,'artist',2)
        self.assertEqual(artist['summary']['total'],2)
        self.assertEqual([p['song_id'] for p in artist['maps'][0]['points']],[1,2])
        tag=build_entity_vibe(self.conn,'tag',2)
        self.assertEqual([p['song_id'] for p in tag['maps'][0]['points']],[2,6])
        self.assertTrue(all(len(m['points'])==2 for m in artist['maps']))
        self.assertGreater(artist['summary']['consistency'],tag['summary']['consistency'])

    def test_partial_missing_and_na_are_not_full_profiles_or_false_centre_dots(self):
        self.place(1,.3,.4);self.place(2,.2,.1,maps=1)
        self.conn.execute("UPDATE song_vibe_positions SET status='not_applicable',updated_at=1 WHERE song_id=3")
        self.conn.commit();data=build_entity_vibe(self.conn,'album',1)
        self.assertEqual(data['summary'],dict(total=5,full=1,partial=2,consistency=None))
        self.assertEqual([m['count'] for m in data['maps']],[2,1,1,1])
        self.assertEqual(data['html'].count('data-vibe-mini-song='),5)
        self.assertNotIn('data-vibe-mini-song="3"',data['html'])

    def test_consistency_equals_dashboard_and_repeats_never_duplicate_dots(self):
        for sid,x in ((1,-.7),(2,-.5),(3,.8)):self.place(sid,x,.4,samples=7)
        scoped=build_entity_vibe(self.conn,'album',1)
        row=next(r for r in build_vibe_stats(self.conn)['groups'][0]['most'] if r['id']==1)
        self.assertEqual(scoped['summary']['consistency'],row['consistency'])
        self.assertEqual(scoped['summary']['full'],row['mapped'])
        self.assertEqual([m['count'] for m in scoped['maps']],[3]*4)
        self.assertEqual(scoped['html'].count('data-vibe-mini-song='),12)

    def test_empty_existing_collections_have_four_empty_maps_without_a_fake_percentage(self):
        self.conn.execute("INSERT INTO albums(id,title) VALUES(3,'Empty album')");self.conn.commit()
        data=build_entity_vibe(self.conn,'album',3)
        self.assertEqual(data['summary'],dict(total=0,full=0,partial=0,consistency=None))
        self.assertEqual(len(data['maps']),4)
        self.assertTrue(all(not m['points'] for m in data['maps']))
        self.assertEqual(data['html'].count('No placements yet'),4)

    def test_gets_are_read_only_no_store_and_validate_entity_identity(self):
        self.place(1);self.place(2)
        client=pages.app.test_client();before=capture(self.conn)
        for kind in ('album','artist','tag'):
            response=client.get('/api/vibe-map/entity/'+kind+'/1')
            self.assertEqual(response.status_code,200,response.data[:500])
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(response.json['summary']['full'],2)
        for path,status in [('album/9999',404),('song/1',400),('artist/0',400)]:
            self.assertEqual(client.get('/api/vibe-map/entity/'+path).status_code,status)
        self.assertEqual(capture(self.conn),before)

    def test_profile_assets_are_versioned_for_all_four_pages_and_titles_are_escaped(self):
        self.conn.execute('UPDATE songs SET title=? WHERE id=1',('<img src=x onerror=alert(1)>',));self.conn.commit();self.place(1)
        html=build_entity_vibe(self.conn,'tag',1)['html']
        self.assertIn('&lt;img',html);self.assertNotIn('<img',html)
        for path in ('/song/1','/album/Album','/artist/Artist,%20One','/tag/Tag'):
            response=pages.app.test_client().get(path)
            self.assertEqual(response.status_code,200,response.data[:500])
            source=response.get_data(as_text=True)
            self.assertIn('js/vibe_profiles.js?v=Vibe-Map-v1.0.6',source)
            self.assertIn('css/vibe_song_stats.css?v=Vibe-Map-v1.0.6',source)
            self.assertLess(source.index('js/vibe_profiles.js'),source.index('js/site.js'))
