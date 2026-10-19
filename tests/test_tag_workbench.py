"""Tag review/apply HTTP and atomicity checks. Only isolated fixture DBs are used."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
import json
import time
import unittest

import test_preferences as fixture
from songranker import services
from songranker.developer import dev_tags
from songranker.storage.database_io import (capture, write_export, read_export, rebuild, readonly, reconcile)
from songranker.developer.tag_operations import (normalized, proposal, canonical_proposal)


class TagProposalTests(unittest.TestCase):
    def test_normalization_preserves_meaning_and_binds_repeated_names(self):
        result=proposal(dict(song_ids=[2,1,2],action='add_tags',new_tags=[' #Night ','Ｎｉｇｈｔ','night']))
        self.assertEqual(result['song_ids'],[1,2]);self.assertEqual(result['new_tags'],['Night'])
        self.assertNotEqual(normalized('Café'),normalized('Cafe'))

    def test_only_explicit_replace_can_clear_all_tags(self):
        for action in ('add_tags','remove_tags'):
            with self.assertRaises(ValueError):proposal(dict(song_ids=[1],action=action))
        self.assertEqual(proposal(dict(song_ids=[1],action='replace_tags'))['tag_ids'],[])

    def test_identifiers_names_and_size_limits_reject_malformed_changes(self):
        for extra in [dict(song_ids=[]),dict(song_ids='1'),dict(song_ids=[True]),dict(song_ids=[0]),dict(song_ids=[1.1]),
          dict(tag_ids=[False]),dict(tag_ids='1'),dict(action='delete_songs'),dict(new_tags='name'),dict(new_tags=[1]),
          dict(new_tags=['']),dict(new_tags=['one,two']),dict(new_tags=['x\nname']),dict(new_tags=['x'*121]),
          dict(new_tags=['a']*26),dict(song_ids=[1]*10001)]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):proposal(dict(song_ids=[1],action='add_tags',tag_ids=[1])|extra)
        for value in (None,[],True):
            with self.assertRaises(ValueError):proposal(value)


class TagWorkbenchTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect
    scalar=fixture.PreferenceTests.scalar

    def client(self):
        client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        return client

    def state(self):return capture(self.conn)

    def tags(self,sid):return [r[0] for r in self.conn.execute('SELECT genre_id FROM song_genres WHERE song_id=? ORDER BY genre_id',(sid,))]

    def review(self,client,**data):
        response=client.post('/api/dev/tags/review',json=dict(song_ids=[1,2],action='add_tags',tag_ids=[2])|data)
        self.assertEqual(response.status_code,200,response.get_json());return response.json

    def apply(self,client,review,**extra):return client.post('/api/dev/tags/apply',json=dict(review_token=review['review_token'])|extra)

    def add_tag(self,name='Extra',description='A useful description',tid=2):
        self.conn.execute('INSERT INTO genres(id,name,description) VALUES(?,?,?)',(tid,name,description));self.conn.commit()

    def test_new_routes_require_local_authenticated_json_requests(self):
        client=services.app.test_client()
        self.assertEqual(client.post('/api/dev/tags/review',json={}).status_code,302)
        client=self.client()
        self.assertEqual(client.post('/api/dev/tags/review',json={},environ_overrides={'REMOTE_ADDR':'10.103.199.228'}).status_code,403)
        self.assertEqual(client.post('/api/dev/tags/review',json={},headers={'Origin':'https://example.org'}).status_code,403)

    def test_review_is_read_only_and_returns_exact_before_after(self):
        self.add_tag();before=self.state()
        with patch.object(dev_tags,'create_database_backup') as backup:
            r=self.review(self.client());backup.assert_not_called()
        self.assertEqual(before,self.state());self.assertEqual(r['changed_songs'],2)
        self.assertEqual(r['added_links'],2);self.assertEqual(r['removed_links'],0)
        self.assertEqual([t['id'] for t in r['rows'][0]['before']],[1])
        self.assertEqual({t['id'] for t in r['rows'][0]['after']},{1,2})
        self.assertEqual(r['rows'][0]['artist'],'Artist, One')

    def test_add_keeps_unselected_links_and_all_game_catalogue_cells(self):
        self.add_tag();client=self.client();r=self.review(client);before=self.state()
        with patch.object(dev_tags,'create_database_backup',return_value='pre_tag_edit_fixture.db') as backup:
            saved=self.apply(client,r)
        self.assertEqual(saved.status_code,200);self.assertEqual(saved.json['updated'],2);backup.assert_not_called()
        after=self.state()
        self.assertTrue(all(after['tables'][t]==rows for t,rows in before['tables'].items() if t!='song_genres'))
        self.assertEqual(self.tags(1),[1,2]);self.assertEqual(self.tags(3),[1])

    def test_remove_touches_memberships_without_deleting_tag_definitions(self):
        self.add_tag();client=self.client();r=self.review(client,action='remove_tags',tag_ids=[1])
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):saved=self.apply(client,r)
        self.assertEqual(saved.json['removed_links'],2);self.assertEqual(self.tags(1),[])
        self.assertEqual(self.tags(3),[1]);self.assertEqual(self.scalar('SELECT COUNT(*) FROM genres'),2)

    def test_replace_lists_all_removals_and_can_clear_selected_songs(self):
        client=self.client();r=self.review(client,action='replace_tags',tag_ids=[])
        self.assertEqual(r['removed_links'],2);self.assertEqual(r['rows'][0]['after'],[])
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):saved=self.apply(client,r)
        self.assertEqual(saved.status_code,200);self.assertEqual(self.tags(1),[]);self.assertEqual(self.tags(3),[1])

    def test_new_names_reuse_existing_unicode_case_and_description(self):
        self.add_tag('Night','Keep this description');client=self.client()
        r=self.review(client,tag_ids=[],new_tags=[' #ＮＩＧＨＴ ','night'])
        self.assertEqual(r['new_tags'],[]);self.assertEqual(r['rows'][0]['added'][0]['description'],'Keep this description')
        self.assertEqual([t['id'] for t in r['target_tags']],[2])
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):self.apply(client,r)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM genres'),2)

    def test_ambiguous_existing_names_require_an_explicit_tag_id(self):
        self.add_tag('Night');self.add_tag('ＮＩＧＨＴ',tid=3)
        client=self.client();r=client.post('/api/dev/tags/review',json=dict(song_ids=[1],action='add_tags',new_tags=['night']))
        self.assertEqual(r.status_code,400)
        self.assertEqual(self.review(client,tag_ids=[2])['changed_songs'],2)

    def test_new_tags_created_only_when_apply_saves_and_retry_is_a_no_op(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM genres'),1)
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db') as backup:
            saved=self.apply(client,r);again=self.apply(client,r)
        self.assertEqual(saved.status_code,200);self.assertEqual(saved.json['created_tags'][0]['name'],'Night')
        self.assertEqual(again.status_code,200);self.assertTrue(again.json['already_matches']);self.assertIsNone(again.json['backup'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM genres'),2);self.assertEqual(backup.call_count,0)

    def test_repeated_existing_tag_add_and_unchanged_review_need_no_backup(self):
        client=self.client();r=self.review(client,tag_ids=[1])
        self.assertEqual(r['changed_songs'],0)
        with patch.object(dev_tags,'create_database_backup') as backup:saved=self.apply(client,r);backup.assert_not_called()
        self.assertEqual(saved.json['updated'],0);self.assertTrue(saved.json['already_matches'])

    def test_concurrent_tabs_save_once_and_create_one_new_tag(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night'])
        cookie=client.get_cookie(services.app.config['SESSION_COOKIE_NAME']).value;gate=Barrier(4)
        def work(_):
            local=services.app.test_client();local.set_cookie(services.app.config['SESSION_COOKIE_NAME'],cookie);gate.wait()
            result=self.apply(local,r);return result.status_code,result.json
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db') as backup,ThreadPoolExecutor(4) as pool:results=list(pool.map(work,range(4)))
        self.assertTrue(all(status==200 for status,_ in results));self.assertEqual(sum(not r['already_matches'] for _,r in results),1)
        self.assertEqual(backup.call_count,0);self.assertEqual(self.scalar("SELECT COUNT(*) FROM genres WHERE name='Night'"),1)

    def test_review_tokens_reject_tampering_and_foreign_browser(self):
        self.add_tag();client=self.client();r=self.review(client)
        self.assertEqual(self.apply(self.client(),r).status_code,400)
        self.assertEqual(self.apply(client,dict(review_token=r['review_token']+'tampered')).status_code,400)

    def test_expired_review_requires_review_again(self):
        self.add_tag()
        with patch('time.time',return_value=time.time()-90000):client=self.client();r=self.review(client)
        self.assertEqual(self.apply(client,r).status_code,400)

    def test_extra_client_fields_cannot_substitute_reviewed_targets(self):
        self.add_tag();client=self.client();r=self.review(client)
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):saved=self.apply(client,r,song_ids=[3],tag_ids=[1],action='remove_tags')
        self.assertEqual(saved.status_code,200);self.assertEqual(self.tags(1),[1,2]);self.assertEqual(self.tags(3),[1])

    def test_stale_memberships_reject_before_backup_or_writes(self):
        self.add_tag();self.add_tag('Other',tid=3);client=self.client();r=self.review(client)
        self.conn.execute('INSERT INTO song_genres VALUES(1,3)');self.conn.commit();before=self.state()
        with patch.object(dev_tags,'create_database_backup') as backup:saved=self.apply(client,r);backup.assert_not_called()
        self.assertEqual(saved.status_code,409);self.assertEqual(before,self.state())

    def test_selected_identity_or_tag_metadata_changes_make_review_stale(self):
        self.add_tag();client=self.client()
        for sql in ["UPDATE songs SET title=title||' changed' WHERE id=1","UPDATE albums SET title=title||' changed' WHERE id=1",
            "UPDATE artists SET name=name||' changed' WHERE id=1","UPDATE genres SET description=description||' changed' WHERE id=2",
            "UPDATE genres SET name=name||' changed' WHERE id=1"]:
            r=self.review(client);self.conn.execute(sql);self.conn.commit();before=self.state()
            self.assertEqual(self.apply(client,r).status_code,409);self.assertEqual(before,self.state())

    def test_game_activity_does_not_stale_review_or_get_overwritten(self):
        self.add_tag();client=self.client();r=self.review(client)
        self.conn.execute('UPDATE songs SET elo_score=1301,matches_played=42 WHERE id=1');self.conn.commit()
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):self.assertEqual(self.apply(client,r).status_code,200)
        self.assertEqual(tuple(self.conn.execute('SELECT elo_score,matches_played FROM songs WHERE id=1').fetchone()),(1301,42))

    def test_unrelated_tag_metadata_does_not_stale_selected_review(self):
        self.add_tag();self.add_tag('Unrelated',tid=3);client=self.client();r=self.review(client)
        self.conn.execute("UPDATE genres SET description='new info' WHERE id=3");self.conn.commit()
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):self.assertEqual(self.apply(client,r).status_code,200)

    def test_deleted_song_or_selected_tag_rejects_stale_review(self):
        self.add_tag();client=self.client();r=self.review(client)
        self.conn.execute('DELETE FROM song_artists WHERE song_id=1');self.conn.execute('DELETE FROM song_genres WHERE song_id=1');self.conn.execute('DELETE FROM songs WHERE id=1');self.conn.commit()
        self.assertEqual(self.apply(client,r).status_code,409)
        r=self.review(client,song_ids=[2]);self.conn.execute('DELETE FROM genres WHERE id=2');self.conn.commit()
        self.assertEqual(self.apply(client,r).status_code,409)

    def test_concurrent_identical_new_definition_can_be_reused(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night']);self.add_tag('Night','')
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):saved=self.apply(client,r)
        self.assertEqual(saved.status_code,200);self.assertEqual(saved.json['created_tags'],[]);self.assertEqual(self.tags(1),[1,2])

    def test_concurrent_new_name_with_different_description_requires_new_review(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night']);self.add_tag('Night','Different meaning')
        self.assertEqual(self.apply(client,r).status_code,409)

    def test_delete_and_recreate_same_named_existing_target_is_not_same_identity(self):
        self.add_tag();client=self.client();r=self.review(client)
        self.conn.execute('DELETE FROM genres WHERE id=2');self.conn.commit();self.add_tag(tid=3)
        self.assertEqual(self.apply(client,r).status_code,409)

    def test_tag_save_does_not_require_backup_storage(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night']);before=self.state()
        with patch.object(dev_tags,'create_database_backup',side_effect=OSError('injected backup failure')),patch.dict(services.app.config,TESTING=False):saved=self.apply(client,r)
        self.assertEqual(saved.status_code,200);self.assertIsNone(saved.json['backup']);self.assertNotEqual(before,self.state())

    def test_mid_apply_failure_rolls_back_new_definition_and_earlier_links(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night'])
        self.conn.execute("CREATE TRIGGER fail_tags BEFORE INSERT ON song_genres WHEN NEW.song_id=2 BEGIN SELECT RAISE(ABORT,'injected tag failure');END");self.conn.commit();before=self.state()
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'),patch.dict(services.app.config,TESTING=False):saved=self.apply(client,r)
        self.assertEqual(saved.status_code,500);self.assertEqual(before,self.state())
        self.assertIn('No tag changes were applied',saved.json['message'])

    def test_malformed_http_payloads_and_unknown_ids_do_not_write(self):
        client=self.client();before=self.state()
        for value in (None,[],True,dict(song_ids=[],action='add_tags',tag_ids=[1]),dict(song_ids=[999],action='add_tags',tag_ids=[1]),dict(song_ids=[1],action='add_tags',tag_ids=[999]),dict(song_ids=[1],action='remove_tags',new_tags=['New'])):
            self.assertEqual(client.post('/api/dev/tags/review',data=json.dumps(value),content_type='application/json').status_code,400)
        for value in (None,[],{},dict(review_token=1),dict(review_token='bad')):
            self.assertEqual(client.post('/api/dev/tags/apply',data=json.dumps(value),content_type='application/json').status_code,400)
        self.assertEqual(before,self.state())

    def test_large_selection_is_chunked_and_each_song_is_counted_once(self):
        self.add_tag();self.conn.executemany('INSERT INTO songs(id,title,album_id) VALUES(?,?,1)',[(i,'Song '+str(i)) for i in range(11,1016)]);self.conn.commit()
        client=self.client();r=self.review(client,song_ids=list(range(1,1016))+[1,2])
        self.assertEqual(r['selected_count'],1015);self.assertEqual(r['changed_songs'],1015)
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):saved=self.apply(client,r)
        self.assertEqual(saved.json['updated'],1015);self.assertEqual(self.scalar('SELECT COUNT(*) FROM song_genres WHERE genre_id=2'),1015)

    def test_new_links_and_definitions_survive_full_export_rebuild(self):
        client=self.client();r=self.review(client,action='replace_tags',tag_ids=[],new_tags=['Night'])
        with patch.object(dev_tags,'create_database_backup',return_value='backup.db'):self.assertEqual(self.apply(client,r).status_code,200)
        export=Path(self.temp.name)/'all.json';out=Path(self.temp.name)/'rebuilt.db';write_export(self.path,export);rebuild(read_export(export),out)
        with readonly(out) as conn:reconcile(self.state(),capture(conn));self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())

    def test_requested_backup_before_tag_edit_can_be_restored(self):
        client=self.client();r=self.review(client,tag_ids=[],new_tags=['Night']);before=self.state()
        requested=client.post('/api/dev/backup',json={});self.assertEqual(requested.status_code,200)
        backup=requested.json['backup'];self.assertTrue(backup.startswith('rolling_'))
        saved=self.apply(client,r);self.assertEqual(saved.status_code,200,saved.get_json());self.assertIsNone(saved.json['backup'])
        self.assertTrue((Path(self.temp.name)/'database_backups'/backup).is_file())
        self.conn.close()
        restored=client.post('/api/dev/restore-backup',json=dict(filename=backup))
        self.assertEqual(restored.status_code,200,restored.get_json())
        self.conn=self.connect();self.addCleanup(self.conn.close)
        reconcile(before,self.state())


if __name__=='__main__':unittest.main()
