"""Review replaces one contribution; public similarity has explicit evidence."""
from unittest.mock import patch
import unittest
from songranker.modes import vibe_map as V
from songranker.modes.vibe_similarity import compare_profiles
from songranker.storage.database_io import capture, rebuild, readonly, validate
import test_vibe_runtime as runtime


class VibeReviewTests(unittest.TestCase):
    # Share realistic fixtures and helpers without rerunning the original suite.
    setUp=runtime.VibeRuntimeTests.setUp
    connect=runtime.VibeRuntimeTests.connect
    start=runtime.VibeRuntimeTests.start
    draft=runtime.VibeRuntimeTests.draft
    advance=runtime.VibeRuntimeTests.advance
    finish=runtime.VibeRuntimeTests.finish
    def edit(self,row,map_id='mood_energy',x=5,y=-5,status='placed',owner='browser'):
        body=dict(token=row['token'],map_id=map_id,revision=row['revision'],request_id='edit-'+str(row['revision']),status=status)
        if status=='placed':body.update(x=x,y=y)
        row=V.draft(self.conn,owner,body)['round'];self.now+=5
        request=dict(token=row['token'],map_id=map_id,revision=row['revision'],request_id='edit-save-'+str(row['revision']))
        result=V.advance(self.conn,owner,request)
        return result['round'],request

    def test_review_completed_round_replaces_sample_without_counting_pass(self):
        row=self.finish(self.start(),x=-5,y=5)
        row,request=self.edit(row)
        point=V.profile(self.conn,1)['maps']['mood_energy']
        self.assertEqual((point['x'],point['y'],point['sample_count']),(5,-5,1))
        self.assertEqual(row['summary']['aggregate']['completed_passes'],1)
        self.assertTrue(V.advance(self.conn,'browser',request)['replayed'])
        self.assertEqual(V.profile(self.conn,1)['maps']['mood_energy']['sample_count'],1)
        self.assertEqual(row['map_index'],4)
        validate(self.conn)

    def test_review_preserves_other_browser_and_previous_pass_contributions(self):
        a=self.finish(self.start('a'),x=-5,y=-5,owner='a')
        b=self.finish(self.start('b'),x=5,y=5,owner='b')
        a,_=self.edit(a,x=0,y=0,owner='a')
        point=V.profile(self.conn,1)['maps']['mood_energy']
        self.assertEqual((point['x'],point['y'],point['sample_count']),(2.5,2.5,2))
        self.assertEqual(V.profile(self.conn,1)['completed_passes'],2)
        b,_=self.edit(b,status='not_applicable',owner='b')
        point=V.profile(self.conn,1)['maps']['mood_energy']
        self.assertEqual((point['x'],point['y'],point['sample_count'],point['not_applicable_count']),(0,0,1,1))
        a,_=self.edit(a,status='not_applicable',owner='a')
        point=V.profile(self.conn,1)['maps']['mood_energy']
        self.assertEqual((point['status'],point['sample_count'],point['not_applicable_count']),('not_applicable',0,2))
        b,_=self.edit(b,x=4,y=-3,owner='b')
        point=V.profile(self.conn,1)['maps']['mood_energy']
        self.assertEqual((point['x'],point['y'],point['sample_count'],point['not_applicable_count']),(4,-3,1,1))

    def test_backtracking_never_unlocks_uncompleted_map(self):
        row,_=self.draft(self.start());self.now+=5;row=self.advance(row)[0]['round']
        row,_=self.edit(row,x=3,y=4)
        self.assertEqual(row['map_index'],1)
        self.assertEqual(row['current_map']['id'],'relationships')
        with self.assertRaises(V.VibeError):self.edit(row,map_id='self_social')
        self.assertEqual(len(row['saved_maps']),1)

    def test_pending_review_restores_target_and_survives_canonical_export(self):
        row=self.finish(self.start())
        body=dict(token=row['token'],map_id='relationships',revision=row['revision'],request_id='review-draft',x=1,y=3)
        row=V.draft(self.conn,'browser',body)['round']
        self.assertEqual(row['draft']['map_id'],'relationships')
        self.assertEqual(self.start(previous=row['token'])['token'],row['token'])
        state=capture(self.conn);target=self.path.parent/'review.db';rebuild(state,target)
        with readonly(target) as conn:
            validate(conn);self.assertEqual(capture(conn),state)
            self.assertEqual(V.payload(conn,V.current(conn,'browser'))['round']['draft']['map_id'],'relationships')

    def test_similarity_ranks_coordinates_and_ignores_missing_or_na(self):
        self.finish(self.start(),x=-5,y=-5)
        with patch.object(V,'vibe_song',return_value=dict(id=2)):
            self.finish(self.start('two'),x=-5,y=-5,owner='two')
        with patch.object(V,'vibe_song',return_value=dict(id=3)):
            self.finish(self.start('three'),x=5,y=5,owner='three')
        before=capture(self.conn);result=V.similar_songs(self.conn,1)
        self.assertEqual([m['song_id'] for m in result['matches']],[2,3])
        self.assertEqual(result['matches'][0]['similarity'],100)
        self.assertLessEqual(result['matches'][1]['similarity'],.01)
        self.assertTrue(all(m['shared_maps']==4 for m in result['matches']))
        self.assertEqual(capture(self.conn),before)
        self.assertEqual(V.similar_songs(self.conn,4)['matches'],[])
        self.assertIsNone(compare_profiles({}, {})['similarity'])
        one={'mood_energy':dict(status='placed',x=0,y=0)}
        self.assertEqual(compare_profiles(one,one)['coverage'],.25)
        self.assertEqual(compare_profiles(one,{'mood_energy':dict(status='not_applicable',x=None,y=None)})['shared_maps'],0)
        client=V.app.test_client()
        self.assertEqual(client.get('/api/vibe-map/similar/1').json['matches'][0]['song']['id'],2)
        self.assertEqual(client.get('/api/vibe-map/similar/1?limit=0').status_code,400)
        self.assertEqual(client.get('/api/vibe-map/similar/9999').status_code,404)

    def test_similarity_has_fixed_curve_and_penalises_a_mismatched_map(self):
        import math
        from songranker.storage.vibe_state import MAPS
        first={key:dict(status='placed',x=0,y=0) for key,*_ in MAPS}
        second={key:dict(status='placed',x=.5,y=.5) for key,*_ in MAPS}
        score=compare_profiles(first,second)['similarity']
        self.assertAlmostEqual(score,100*math.exp(-.5/(2*.65**2)))
        self.assertLess(score,60)  # Old diagonal-normalised formula said 75%.
        second={key:dict(status='placed',x=0,y=0) for key,*_ in MAPS}
        second['relationships'].update(x=1,y=1)
        self.assertAlmostEqual(compare_profiles(first,second)['similarity'],score)
        self.assertEqual(compare_profiles(first,first)['similarity'],100)
        self.assertEqual(compare_profiles(second,first),compare_profiles(first,second))

    def test_play_page_loads_real_assets_and_no_write_on_get(self):
        before=capture(self.conn)
        response=V.app.test_client().get('/vibe-map')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'css/vibe_map.css',response.data)
        self.assertIn(b'js/vibe_map.js',response.data)
        self.assertIn(b'js/vibe_charts.js',response.data)
        self.assertEqual(capture(self.conn),before)


if __name__=='__main__':unittest.main()
