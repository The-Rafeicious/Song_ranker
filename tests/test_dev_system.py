"""Dashboard/recovery contracts against isolated fixture databases only."""
from pathlib import Path
from unittest.mock import patch
import json
import sqlite3
import unittest

import test_preferences as fixture
from songranker import services
from songranker.developer import dev_system as system
from songranker.storage.database_schema import SCHEMA_VERSION
from songranker.storage.database_io import (capture, create_backup, readonly, read_export)


class DeveloperSystemTests(unittest.TestCase):
    connect=fixture.PreferenceTests.connect
    scalar=fixture.PreferenceTests.scalar

    def setUp(self):
        fixture.PreferenceTests.setUp(self)
        p=patch.object(services,'ROOT',Path(self.temp.name));p.start();self.addCleanup(p.stop)
        self.client=services.app.test_client()
        with self.client.session_transaction() as session:session['is_admin']=True

    def backup(self,prefix='manual'):return create_backup(self.path,prefix)

    def review(self,backup):
        r=self.client.post('/api/dev/backups/review',json={'filename':Path(backup).name})
        self.assertEqual(r.status_code,200,r.json);return r.json

    def restore(self,review):return self.client.post('/api/dev/backups/restore',json={'review_token':review['review_token']})

    def current(self):
        with readonly(self.path) as db:return capture(db)

    def test_routes_require_local_authenticated_requests(self):
        urls=['/api/dev/system','/api/dev/git/status','/api/dev/database/export','/api/dev/database/guide']
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(services.app.test_client().get(url).status_code,302)
                self.assertEqual(self.client.get(url,environ_overrides={'REMOTE_ADDR':'10.2.3.4'}).status_code,403)
        for url in ['/api/dev/git/check','/api/dev/git/upload','/api/dev/backups/review','/api/dev/backups/restore']:
            with self.subTest(url=url):
                self.assertEqual(services.app.test_client().post(url,json={}).status_code,302)
                self.assertEqual(self.client.post(url,json={},headers={'Origin':'https://example.org'}).status_code,403)

    def test_inventory_is_read_only_and_labels_all_objects(self):
        self.conn.executescript('CREATE TABLE "custom notes"(value TEXT); INSERT INTO "custom notes" VALUES(\'keep\'); CREATE VIEW "custom view" AS SELECT * FROM "custom notes";')
        before=capture(self.conn)
        with patch.object(system.GitSync,'fetch') as fetch:
            r=self.client.get('/api/dev/system');fetch.assert_not_called()
        self.assertEqual(r.status_code,200);self.assertEqual(before,capture(self.conn))
        rows={r['name']:r for r in r.json['inventory']}
        self.assertEqual(len(rows),35);self.assertEqual(rows['custom notes']['group'],'Extensions')
        self.assertEqual(rows['custom view']['role'],'Derived / read-only')
        self.assertEqual(rows['preference_mode_ratings']['role'],'Rebuildable projection')
        self.assertEqual(rows['songs']['rows'],10);self.assertEqual(r.json['integrity'],'ok')
        self.assertEqual(r.json['totals']['missing_previews'],6);self.assertEqual(r.json['totals']['missing_sources'],10)
        self.assertFalse(r.json['git']['available'])

    def test_backup_listing_includes_all_regular_databases_excludes_links_and_other_files(self):
        p=self.backup();folder=p.parent
        (folder/'custom older.DB').write_bytes(p.read_bytes())
        (folder/'linked.db').symlink_to(p);(folder/'notes.txt').write_text('keep')
        r=self.client.get('/api/dev/system').json['backups']
        self.assertEqual({x['name'] for x in r},{p.name,'custom older.DB'})
        self.assertTrue(all(x['bytes']>0 and x['purpose'] for x in r))

    def test_full_export_preserves_extension_fields_and_pending_game_facts(self):
        fixture.PreferenceTests.offer(self)
        self.conn.execute('CREATE TABLE "extra"(id INTEGER, payload BLOB)')
        self.conn.execute('INSERT INTO extra VALUES(?,?)',(1,b'\x00\xff'));self.conn.commit();before=capture(self.conn)
        r=self.client.get('/api/dev/database/export');self.assertEqual(r.status_code,200)
        p=Path(self.temp.name)/'export.json';p.write_bytes(r.data);r.close()
        self.assertEqual(before,read_export(p));self.assertEqual(before,capture(self.conn))

    def test_guide_is_downloaded_without_disclosing_other_files(self):
        docs=Path(self.temp.name)/'docs';docs.mkdir();(docs/'TECHNICAL_GUIDE.md').write_text('# Recovery guide')
        r=self.client.get('/api/dev/database/guide');self.assertEqual(r.data,b'# Recovery guide')
        self.assertIn('attachment',r.headers['Content-Disposition']);r.close()

    def test_binary_backup_download_is_exact(self):
        p=self.backup();r=self.client.get('/api/dev/backups/'+p.name+'/download')
        self.assertEqual(r.status_code,200);self.assertEqual(r.data,p.read_bytes());r.close()

    def test_backup_paths_reject_traversal_links_missing_or_invalid_contents(self):
        p=self.backup();(p.parent/'linked.db').symlink_to(p);(p.parent/'broken.db').write_text('not sqlite')
        for name in ['../test.db','..\\test.db','/test.db','linked.db','missing.db','broken.db','file.sql',None,5]:
            with self.subTest(name=name):self.assertEqual(self.client.post('/api/dev/backups/review',json={'filename':name}).status_code,400)
        self.assertEqual(self.client.get('/api/dev/backups/linked.db/download').status_code,404)

    def test_restore_review_is_read_only_and_binds_backup_and_live_state(self):
        p=self.backup();before=self.current();r=self.review(p)
        self.assertEqual(r['live']['Songs'],10);self.assertEqual(r['backup']['Songs'],10)
        self.assertEqual(r['target_schema'],SCHEMA_VERSION);self.assertEqual(before,self.current())
        token=system.signer().loads(r['review_token']);self.assertEqual(token['kind'],'restore')
        self.assertIn('backup',token);self.assertIn('live',token)

    def test_whole_restore_retains_pre_restore_backup_and_saved_offer(self):
        offer=fixture.PreferenceTests.offer(self);p=self.backup();original=self.current()
        self.conn.execute("UPDATE songs SET title='Changed' WHERE id=1");self.conn.commit()
        before=self.current();r=self.review(p);response=self.restore(r)
        self.assertEqual(response.status_code,200,response.json);self.assertEqual(self.current(),original)
        with readonly(p.parent/response.json['safety_backup']) as db:self.assertEqual(capture(db),before)
        with readonly(self.path) as db:self.assertEqual(db.execute('SELECT token FROM preference_offers').fetchone()[0],offer['token'])

    def test_saved_activity_after_review_is_rejected_without_writing(self):
        r=self.review(self.backup());self.conn.execute("UPDATE songs SET title='New activity' WHERE id=1");self.conn.commit();before=self.current()
        response=self.restore(r);self.assertEqual(response.status_code,409,response.json)
        self.assertIn('live database changed',response.json['message'].lower());self.assertEqual(self.current(),before)

    def test_changed_backup_after_review_is_rejected(self):
        p=self.backup();r=self.review(p)
        with sqlite3.connect(p) as db:db.execute("UPDATE songs SET title='Backup changed' WHERE id=1")
        before=self.current();response=self.restore(r);self.assertEqual(response.status_code,409,response.json);self.assertEqual(self.current(),before)

    def test_review_tokens_cannot_be_reused_in_another_browser_or_task(self):
        r=self.review(self.backup());other=services.app.test_client()
        with other.session_transaction() as session:session['is_admin']=True
        self.assertEqual(other.post('/api/dev/backups/restore',json={'review_token':r['review_token']}).status_code,400)
        self.assertEqual(self.client.post('/api/dev/git/upload',json={'review_token':r['review_token']}).status_code,400)
        self.assertEqual(self.restore(dict(review_token=r['review_token']+'bad')).status_code,400)

    def test_expired_and_missing_reviews_require_a_new_review(self):
        p=self.backup();r=self.review(p)
        payload=system.signer().loads(r['review_token'])
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp',return_value=1):r['review_token']=system.signer().dumps(payload)
        self.assertEqual(self.restore(r).status_code,400)
        self.assertEqual(self.client.post('/api/dev/backups/restore',json={'filename':p.name}).status_code,400)
        self.assertEqual(self.client.post('/api/dev/backups/restore',json=[]).status_code,400)

    def test_legacy_restore_endpoint_stays_compatible(self):
        p=self.backup();response=self.client.post('/api/dev/restore-backup',json={'filename':p.name})
        self.assertEqual(response.status_code,200,response.json)

    def test_multi_worker_restore_is_blocked(self):
        r=self.review(self.backup());response=self.client.post('/api/dev/backups/restore',json={'review_token':r['review_token']},environ_overrides={'wsgi.multiprocess':True})
        self.assertEqual(response.status_code,409);self.assertIn('WSGI',response.json['message'])

    def test_git_status_is_local_and_replaces_internal_fingerprint_with_signed_review(self):
        state=dict(available=True,fingerprint='target-1',branch='main')
        with patch.object(system.GitSync,'status',return_value=state),patch.object(system.GitSync,'fetch') as fetch:
            r=self.client.get('/api/dev/git/status');fetch.assert_not_called()
        self.assertNotIn('fingerprint',r.json);self.assertEqual(system.signer().loads(r.json['review_token'])['fingerprint'],'target-1')

    def test_git_upload_binds_review_to_target_and_refreshes_state(self):
        with patch.object(system.GitSync,'status',return_value=dict(available=True,fingerprint='target-1')):
            token=self.client.get('/api/dev/git/status').json['review_token']
            with patch.object(system.GitSync,'upload',return_value=dict(ok=True,code='uploaded',message='Saved')) as upload:
                r=self.client.post('/api/dev/git/upload',json={'review_token':token});upload.assert_called_once_with('target-1')
        self.assertEqual(r.status_code,200);self.assertIn('review_token',r.json['git'])

    def test_git_failures_return_actionable_status_and_current_review(self):
        with patch.object(system.GitSync,'status',return_value=dict(available=True,fingerprint='target-1')):
            token=self.client.get('/api/dev/git/status').json['review_token']
            for code,status in [('stale_target',409),('pending_code',409),('database_behind',409),('database_conflict',409),('database_check_failed',409),('push_failed',502),('busy',409)]:
                with self.subTest(code=code),patch.object(system.GitSync,'upload',return_value=dict(ok=False,code=code,message='Retry after checking')):
                    r=self.client.post('/api/dev/git/upload',json={'review_token':token});self.assertEqual(r.status_code,status);self.assertIn('git',r.json)

    def test_check_remote_requires_json_and_legacy_upload_requires_review(self):
        self.assertEqual(self.client.post('/api/dev/git/check',json=[]).status_code,400)
        self.assertEqual(self.client.post('/api/dev/sync',json={}).status_code,400)
        with patch.object(system.GitSync,'check',return_value=dict(ok=True,code='up_to_date',message='Checked')),patch.object(system.GitSync,'status',return_value=dict(available=False,state='not_repo')):
            self.assertEqual(self.client.post('/api/dev/git/check',json={}).status_code,200)


if __name__=='__main__':unittest.main()

