"""Backend-only continuous maps, timed autosave, compact averages and recovery."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
import json
import sqlite3
import unittest

import test_preferences as fixture
from songranker import services
from songranker.modes import vibe_map as V
from songranker.modes import shelves
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture, readonly, rebuild, reconcile, validate, sql_dump
from songranker.vibe_maps import pass_counts


class VibeRuntimeTests(unittest.TestCase):
    connect=fixture.PreferenceTests.connect

    def setUp(self):
        fixture.PreferenceTests.setUp(self)
        self.now=1000.0
        clock=patch.object(V.time,'time',side_effect=lambda:self.now)
        clock.start();self.addCleanup(clock.stop)
        from songranker.modes.selection import eligible_vibe_ids
        chooser=patch.object(V,'vibe_song',side_effect=lambda conn,**kw: next((dict(id=sid) for sid in sorted(eligible_vibe_ids(conn,kw.get('scope','all'),kw.get('scope_id')))),None))
        chooser.start();self.addCleanup(chooser.stop)

    def start(self,owner='browser',previous=None):
        return V.start(self.conn,owner,dict(previous_token=previous))['round']

    def draft(self,row,x=1.234567,y=-2.345678,status='placed',owner='browser'):
        data=dict(token=row['token'],map_id=row['current_map']['id'],revision=row['revision'],
                  request_id='draft-'+str(row['revision']),status=status)
        if status=='placed':data.update(x=x,y=y)
        return V.draft(self.conn,owner,data)['round'],data

    def advance(self,row,owner='browser'):
        data=dict(token=row['token'],map_id=row['current_map']['id'],revision=row['revision'],
                  request_id='advance-'+str(row['revision']))
        return V.advance(self.conn,owner,data),data

    def finish(self,row,x=1,y=2,status='placed',owner='browser'):
        while row['status']=='active':
            row,_=self.draft(row,x,y,status,owner);self.now+=5
            result,_=self.advance(row,owner);row=result['round']
        return row

    def test_chooser_is_read_only_and_filters_completed_songs_and_collections(self):
        self.finish(self.start())
        before=capture(self.conn)
        songs=V.mapping_options(self.conn,'song','Song')
        self.assertEqual(songs['library_remaining'],9)
        self.assertNotIn(1,[r['id'] for r in songs['results']])
        self.assertEqual(V.mapping_options(self.conn,'artist')['results'][0]['remaining'],9)
        albums=V.mapping_options(self.conn,'album')['results']
        self.assertEqual({r['id']:r['remaining'] for r in albums},{1:4,2:5})
        self.assertEqual(V.mapping_options(self.conn,'song','Song 2')['results'][0]['id'],2)
        self.assertEqual(capture(self.conn),before)
        client=V.app.test_client()
        self.assertEqual(client.get('/api/vibe-map/options?kind=artist').status_code,200)
        self.assertEqual(client.get('/api/vibe-map/options?kind=bad').status_code,400)
        self.assertEqual(capture(self.conn),before)

    def test_selected_cohort_and_specific_song_are_server_enforced(self):
        row=V.start(self.conn,'album',dict(scope='album',scope_id=2))['round']
        self.assertEqual(row['song']['id'],6)
        row=self.finish(row,owner='album')
        row=V.start(self.conn,'album',dict(scope='album',scope_id=2,previous_token=row['token']))['round']
        self.assertEqual(row['song']['id'],7)
        row=V.start(self.conn,'one',dict(scope='song',scope_id=3))['round']
        self.assertEqual(row['song']['id'],3)
        before=capture(self.conn)
        for data in [dict(scope='bad'),dict(scope=[]),dict(scope='song',scope_id=True),dict(scope='album',scope_id=99999)]:
            with self.assertRaises(V.VibeError):V.start(self.conn,'invalid',data)
        self.assertEqual(capture(self.conn),before)

    def test_fully_mapped_legacy_averages_are_retired_without_changing_values(self):
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=.3,y=-.4,updated_at=1,sample_count=3 WHERE song_id=1")
        self.conn.commit();before=capture(self.conn)
        self.assertNotIn(1,[r['id'] for r in V.mapping_options(self.conn)['results']])
        with self.assertRaises(V.VibeError):V.start(self.conn,'legacy',dict(scope='song',scope_id=1))
        self.assertEqual(capture(self.conn),before)

    def test_pending_same_mapping_review_can_resume_or_leave_without_another_pass(self):
        row=self.finish(self.start())
        row=V.draft(self.conn,'browser',dict(token=row['token'],map_id='pace_mood',revision=row['revision'],request_id='review',x=2,y=3))['round']
        self.assertTrue(row['can_resume'])
        V.cancel(self.conn,'browser',dict(token=row['token'],revision=row['revision']))
        self.assertIsNone(V.current(self.conn,'browser')['draft_status'])
        self.assertEqual(pass_counts(self.conn,[1])[1],1)
        self.assertEqual(self.start(previous=row['token'])['song']['id'],2)

    def test_upgrade_does_not_resume_an_old_repeat_but_still_allows_switching(self):
        row=self.start()
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=.3,y=.4,updated_at=1,sample_count=2 WHERE song_id=1")
        self.conn.execute('UPDATE song_vibe_progress SET completed_passes=2 WHERE song_id=1');self.conn.commit()
        before=capture(self.conn)
        self.assertFalse(V.payload(self.conn,V.current(self.conn,'browser'))['round']['can_resume'])
        with self.assertRaises(V.VibeError):self.draft(row)
        self.assertEqual(capture(self.conn),before)
        V.cancel(self.conn,'browser',dict(token=row['token'],revision=row['revision']))
        next_round=V.start(self.conn,'browser',dict(previous_token=row['token'],scope='song',scope_id=2))['round']
        self.assertEqual(next_round['song']['id'],2)
        self.assertEqual(V.profile(self.conn,1)['completed_passes'],2)
        self.assertTrue(all(p['sample_count']==2 for p in V.profile(self.conn,1)['maps'].values()))

    def test_exhausted_sequence_does_not_create_another_round(self):
        self.conn.execute('UPDATE song_vibe_progress SET completed_passes=1');self.conn.commit()
        before=capture(self.conn)
        with self.assertRaises(V.VibeError) as error:self.start()
        self.assertEqual(error.exception.code,'selection_complete')
        self.assertEqual(V.mapping_options(self.conn)['library_remaining'],0)
        self.assertEqual(capture(self.conn),before)

    def test_start_and_get_are_resumable_and_do_not_count_attempts(self):
        row=self.start();again=self.start()
        self.assertEqual(row['token'],again['token'])
        self.assertEqual(row['map_index'],0)
        self.assertIsNone(row['draft'])
        self.assertEqual(row['current_map']['min'],-5)
        self.assertEqual(row['current_map']['max'],5)
        self.assertIsNone(row['current_map']['step'])
        self.assertEqual(pass_counts(self.conn,[1])[1],0)
        self.assertEqual(self.conn.execute('SELECT SUM(sample_count) FROM song_vibe_positions').fetchone()[0],0)

    def test_continuous_draft_rounding_timer_restart_and_retry(self):
        row=self.start();row,original=self.draft(row)
        deadline=row['advance_at'];self.assertEqual(row['draft']['display_x'],1.23)
        self.assertEqual(row['draft']['x'],1.234567)
        self.now+=3
        replay=V.draft(self.conn,'browser',original)['round']
        self.assertEqual(replay['advance_at'],deadline)
        self.assertEqual(replay['revision'],row['revision'])
        row,_=self.draft(row,x=4.98765,y=-4.22222)
        self.assertEqual(row['advance_at'],self.now+5)
        self.now+=2
        with self.assertRaises(V.VibeError) as error:self.advance(row)
        self.assertEqual(error.exception.code,'readjusting')
        self.assertEqual(error.exception.details['remaining_ms'],3000)
        self.assertEqual(self.conn.execute('SELECT SUM(sample_count) FROM song_vibe_positions').fetchone()[0],0)
        self.now+=3;result,request=self.advance(row)
        self.assertEqual(result['round']['map_index'],1)
        point=self.conn.execute("SELECT * FROM song_vibe_positions WHERE song_id=1 AND map_id='pace_mood'").fetchone()
        self.assertAlmostEqual(point['x'],4.98765/5)
        self.assertAlmostEqual(point['y'],-4.22222/5)
        self.assertEqual(point['sample_count'],1)
        self.assertEqual(pass_counts(self.conn,[1])[1],0)
        self.now+=1
        self.assertTrue(V.advance(self.conn,'browser',request)['replayed'])
        self.assertEqual(self.conn.execute('SELECT SUM(sample_count) FROM song_vibe_positions').fetchone()[0],1)

    def test_summary_has_eight_spokes_and_pass_counts_only_after_four_maps(self):
        row=self.finish(self.start(),x=-5,y=5)
        self.assertEqual(row['status'],'complete');self.assertEqual(len(row['saved_maps']),4)
        spokes=row['summary']['selection_radar']['spokes']
        self.assertEqual(len(spokes),8)
        self.assertEqual([p['radius'] for p in spokes],[1,1,0,0,1,1,0,0])
        self.assertEqual(row['summary']['aggregate']['completed_passes'],1)
        self.assertEqual(self.start()['token'],row['token'])
        next_round=self.start(previous=row['token'])
        self.assertNotEqual(next_round['token'],row['token'])
        self.assertEqual(next_round['saved_maps'],[])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM vibe_rounds').fetchone()[0],1)

    def test_completed_song_cannot_receive_another_pass(self):
        row=self.finish(self.start(),x=-5,y=5)
        before=capture(self.conn)
        with self.assertRaises(V.VibeError) as error:
            V.start(self.conn,'browser',dict(previous_token=row['token'],scope='song',scope_id=1))
        self.assertEqual(error.exception.code,'selection_complete')
        self.assertEqual(capture(self.conn),before)
        self.assertEqual(self.start(previous=row['token'])['song']['id'],2)
        self.assertEqual(pass_counts(self.conn,[1])[1],1)
        self.assertTrue(all(r[0]==1 for r in self.conn.execute('SELECT sample_count FROM song_vibe_positions WHERE song_id=1')))

    def test_not_applicable_completes_once_without_fabricated_coordinates(self):
        row=self.finish(self.start(),status='not_applicable')
        self.assertTrue(all(p['radius'] is None for p in row['summary']['selection_radar']['spokes']))
        self.assertEqual(pass_counts(self.conn,[1])[1],1)
        for point in V.profile(self.conn,1)['maps'].values():
            self.assertEqual(point['status'],'not_applicable');self.assertEqual(point['sample_count'],0)
            self.assertEqual(point['not_applicable_count'],1);self.assertIsNone(point['x'])
        self.assertNotEqual(self.start(previous=row['token'])['song']['id'],1)

    def test_cancelled_partial_resumes_only_missing_maps(self):
        row,_=self.draft(self.start());self.now+=5
        row=self.advance(row)[0]['round']
        V.cancel(self.conn,'browser',dict(token=row['token'],revision=row['revision']))
        row=V.start(self.conn,'browser',dict(previous_token=row['token'],scope='song',scope_id=1))['round']
        self.assertEqual(row['map_index'],1);self.assertTrue(row['saved_maps'][0]['read_only'])
        row=self.finish(row,x=4,y=3)
        points=V.profile(self.conn,1)['maps']
        self.assertAlmostEqual(points['pace_mood']['x'],1.234567)
        self.assertTrue(all(p['sample_count']==1 for p in points.values()))
        self.assertEqual(pass_counts(self.conn,[1])[1],1)

    def test_parallel_browser_cannot_add_another_sample(self):
        first=self.start();second=self.start(owner='second')
        first,_=self.draft(first);second,_=self.draft(second,owner='second');self.now+=5
        self.advance(first);before=capture(self.conn)
        with self.assertRaises(V.VibeError) as error:self.advance(second,owner='second')
        self.assertEqual(error.exception.code,'already_mapped');self.assertEqual(capture(self.conn),before)

    def test_reordered_stale_and_foreign_requests_are_rejected_without_writes(self):
        row,_=self.draft(self.start());before=capture(self.conn)
        data=dict(token=row['token'],map_id='sound_impact',revision=row['revision'],request_id='wrong')
        for owner,body in [('browser',data),('other',dict(data,map_id='pace_mood')),
                           ('browser',dict(data,map_id='pace_mood',revision=0)),
                           ('browser',dict(data,map_id=['bad']))]:
            with self.assertRaises(V.VibeError):V.advance(self.conn,owner,body)
            self.assertEqual(capture(self.conn),before)

    def test_invalid_coordinates_and_reused_request_keys_fail_closed(self):
        row=self.start()
        for x,y in ((None,1),(True,1),(6,0),(0,-6),(float('nan'),0),('1',0),(10**1000,0)):
            with self.assertRaises(V.VibeError):self.draft(row,x,y)
        row,body=self.draft(row)
        with self.assertRaises(V.VibeError):V.draft(self.conn,'browser',dict(body,x=4))

    def test_cancellation_keeps_saved_maps_and_discards_only_draft(self):
        row,_=self.draft(self.start());self.now+=5
        result,_=self.advance(row);row=result['round'];row,_=self.draft(row)
        cancelled=V.cancel(self.conn,'browser',dict(token=row['token'],revision=row['revision']))['round']
        self.assertEqual(cancelled['status'],'cancelled');self.assertIsNone(cancelled['draft'])
        self.assertEqual(pass_counts(self.conn,[1])[1],0)
        self.assertEqual(self.conn.execute('SELECT SUM(sample_count) FROM song_vibe_positions').fetchone()[0],1)

    def test_failure_on_fourth_map_rolls_back_average_receipt_and_pass_together(self):
        row=self.start()
        for _ in range(3):
            row,_=self.draft(row);self.now+=5;result,_=self.advance(row);row=result['round']
        row,_=self.draft(row);self.now+=5
        self.conn.execute("CREATE TRIGGER fail_pass BEFORE UPDATE ON song_vibe_progress BEGIN SELECT RAISE(ABORT,'injected'); END")
        self.conn.commit();before=capture(self.conn)
        with self.assertRaises(sqlite3.IntegrityError):self.advance(row)
        self.assertEqual(capture(self.conn),before)

    def test_simultaneous_duplicate_saves_count_once(self):
        row,_=self.draft(self.start());self.now+=5
        body=dict(token=row['token'],map_id='pace_mood',revision=row['revision'],request_id='same-save')
        barrier=Barrier(2)
        def save():
            c=self.connect()
            try:barrier.wait();return V.advance(c,'browser',body)['replayed']
            finally:c.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:save(),range(2)))
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(self.conn.execute('SELECT SUM(sample_count) FROM song_vibe_positions').fetchone()[0],1)

    def test_two_browsers_keep_first_saved_mapping_without_averaging(self):
        a,_=self.draft(self.start('a'),x=-5,y=-5,owner='a')
        b,_=self.draft(self.start('b'),x=5,y=5,owner='b');self.now+=5
        self.advance(a,'a')
        with self.assertRaises(V.VibeError):self.advance(b,'b')
        p=V.profile(self.conn,1)['maps']['pace_mood']
        self.assertEqual(p['sample_count'],1);self.assertEqual(p['x'],-5);self.assertEqual(p['y'],-5)

    def test_active_draft_and_receipts_survive_rebuild_and_restart(self):
        row,_=self.draft(self.start());self.now+=5
        accepted,_=self.advance(row)
        row,_=self.draft(accepted['round']);self.now+=2
        before=capture(self.conn);output=self.path.parent/'restored.db';rebuild(before,output)
        initialize_database(output)
        with readonly(output) as c:
            self.assertEqual(capture(c),before)
            resumed=V.payload(c,V.current(c,'browser'))['round']
            self.assertEqual(resumed['token'],row['token']);self.assertEqual(resumed['remaining_ms'],3000)
            self.assertEqual(len(resumed['saved_maps']),1)
        sql=self.path.parent/'round.sql';sql.write_text(sql_dump(self.conn))
        restored=self.path.parent/'sql-restored.db';initialize_database(restored,sql)
        with readonly(restored) as c:self.assertEqual(capture(c),before)

    def test_song_delete_removes_its_round_counter_and_map_slots(self):
        self.start();self.conn.execute('DELETE FROM song_artists WHERE song_id=1')
        self.conn.execute('DELETE FROM song_genres WHERE song_id=1')
        self.conn.execute('DELETE FROM songs WHERE id=1');self.conn.commit();validate(self.conn)
        self.assertIsNone(V.current(self.conn,'browser'))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_vibe_progress WHERE song_id=1').fetchone()[0],0)

    def test_heatmaps_use_one_aggregate_point_per_song_not_one_per_attempt(self):
        self.finish(self.start(),x=2,y=-3);before=capture(self.conn)
        for kind,eid,count in [('all',None,10),('artist',1,10),('album',1,5),('tag',1,10)]:
            result=V.heatmap(self.conn,kind,eid)
            self.assertEqual(result['song_count'],count)
            for m in result['maps'].values():
                self.assertEqual(len(m['points']),1);self.assertEqual(m['points'][0]['weight'],1)
                self.assertEqual(m['unmapped'],count-1)
        self.assertEqual(capture(self.conn),before)

    def test_http_contract_is_same_origin_browser_owned_and_read_only_on_get(self):
        client=services.app.test_client();before=capture(self.conn)
        self.assertEqual(client.get('/api/vibe-map/state').json['round'],None)
        self.assertEqual(capture(self.conn),before)
        row=client.post('/api/vibe-map/round',json={}).json['round']
        self.assertEqual(client.get('/api/vibe-map/state').json['round']['token'],row['token'])
        response=client.post('/api/vibe-map/draft',json=dict(token=row['token'],map_id='pace_mood',revision=0,request_id='http',x=1,y=2))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(services.app.test_client().post('/api/vibe-map/advance',json=dict(token=row['token'],map_id='pace_mood',revision=1,request_id='foreign')).status_code,409)
        self.assertEqual(client.post('/api/vibe-map/round',json={},headers={'Origin':'https://elsewhere.example'}).status_code,403)
        self.assertEqual(client.post('/api/vibe-map/round',data='{}').status_code,403)
        self.assertEqual(client.post('/api/vibe-map/round',json=[]).status_code,400)
        self.assertEqual(client.get('/api/vibe-map/heatmap?kind=album&id=nope').status_code,400)
        self.assertEqual(client.get('/api/vibe-map/profile/999999').status_code,404)

    def test_schema17_migration_clears_incompatible_old_points_once(self):
        old=self.path.parent/'v17.db';c=sqlite3.connect(old);c.row_factory=sqlite3.Row
        c.executescript(Path('tests/fixtures/schema_v17.sql').read_text())
        from songranker.storage.vibe_state import seed_definitions
        seed_definitions(c,legacy=True)
        c.execute("INSERT INTO songs(id,title) VALUES(1,'Mapped'),(2,'Partial')")
        c.execute("UPDATE song_vibe_positions SET x=.123456789,y=-.5,status='placed',updated_at=42 WHERE song_id=1")
        c.execute("UPDATE song_vibe_positions SET x=.4,y=.2,status='placed',updated_at=43 WHERE song_id=2 AND map_id='mood_energy'")
        c.execute('PRAGMA user_version=17');c.commit();before=capture(c);c.close()
        initialize_database(old)
        with readonly(old) as c:
            validate(c);reconcile(before,capture(c))
            self.assertEqual(pass_counts(c,[1,2]),{1:0,2:0})
            p=c.execute("SELECT * FROM song_vibe_positions WHERE song_id=1 AND map_id='pace_mood'").fetchone()
            self.assertEqual(p['sample_count'],0);self.assertIsNone(p['x'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM vibe_rounds').fetchone()[0],0)


if __name__=='__main__':unittest.main()
