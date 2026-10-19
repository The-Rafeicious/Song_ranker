"""Rotating backup durability, fresh-PIN shutdown, acknowledgement and failure recovery."""
from pathlib import Path
from unittest.mock import Mock,patch
import os,time,unittest
import test_preferences as fixture
from songranker import services
from songranker.storage.database_io import create_rolling_backup,readonly,capture
from songranker.storage import database_io
from songranker import hosting
from songranker.developer import dev_shutdown

class ShutdownTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def wait(self,manager,state):
        end=time.monotonic()+3
        while time.monotonic()<end:
            result=manager.status('browser')
            if result['state'] in state:return result
            time.sleep(.005)
        self.fail(str(manager.status('browser')))

    def manager(self,**kwargs):return hosting.StopCoordinator(self.path.parent,self.path,Mock(),ack_delay=0,**kwargs)

    def test_three_rotating_slots_keep_latest_versions_and_old_archives(self):
        folder=self.path.parent/'database_backups';folder.mkdir();archive=folder/'pre_upgrade_original.db';archive.write_bytes(b'keep')
        for n in range(5):
            self.conn.execute('UPDATE songs SET title=? WHERE id=1',(str(n),));self.conn.commit()
            p=create_rolling_backup(self.path);os.utime(p,ns=(1000000000+n,1000000000+n))
        slots=list(folder.glob('rolling_*.db'));self.assertEqual(len(slots),3)
        values=[]
        for p in slots:
            with readonly(p) as c:values.append(c.execute('SELECT title FROM songs WHERE id=1').fetchone()[0])
        self.assertEqual(set(values),{'2','3','4'});self.assertEqual(archive.read_bytes(),b'keep')

    def test_failed_atomic_replace_preserves_existing_slot(self):
        for _ in range(3):create_rolling_backup(self.path)
        folder=self.path.parent/'database_backups';before={p.name:p.read_bytes() for p in folder.glob('*.db')}
        with patch.object(database_io.os,'replace',side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):create_rolling_backup(self.path)
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.glob('*.db')})
        self.assertEqual(list(folder.glob('.rolling_*')),[])
        with patch.object(hosting,'create_rolling_backup',side_effect=OSError('disk unavailable')):
            manager=self.manager();manager.begin('browser',False);self.wait(manager,{'failed'})
        self.assertFalse(manager.busy);manager.shutdown.assert_not_called()
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.glob('*.db')})

    def test_success_waits_for_ui_ack_and_pushes_only_database(self):
        manager=self.manager()
        with patch.object(hosting,'GitSync') as sync:
            sync.return_value.upload.return_value=dict(ok=True,code='uploaded',message='Database uploaded.')
            manager.begin('browser',True,'reviewed-target');ready=self.wait(manager,{'ready'})
            manager.shutdown.assert_not_called();sync.return_value.upload.assert_called_once_with('reviewed-target')
            self.assertTrue((self.path.parent/'database_backups'/ready['backup']).exists())
            self.assertFalse(manager.enter());self.assertEqual(manager.status('other')['state'],'idle')
            with self.assertRaises(ValueError):manager.signal('other',ready['id'],'stop')
            manager.signal('browser',ready['id'],'stop');self.wait(manager,{'stopped'})
        manager.shutdown.assert_called_once();self.assertTrue(manager.enter());manager.leave()

    def test_git_failure_keeps_running_with_local_backup(self):
        manager=self.manager()
        with patch.object(hosting,'GitSync') as sync:
            sync.return_value.upload.return_value=dict(ok=False,code='push_failed',message='Push not confirmed.')
            manager.begin('browser',True,'target');result=self.wait(manager,{'failed'})
        self.assertTrue(result['backup']);self.assertFalse(result['git']['ok']);self.assertFalse(manager.busy);manager.shutdown.assert_not_called()

    def test_no_ui_ack_or_cancel_leaves_app_running(self):
        for action in ('timeout','cancel'):
            manager=self.manager(ack_timeout=.03);manager.begin('browser',False);ready=self.wait(manager,{'ready'})
            if action=='cancel':manager.signal('browser',ready['id'],'cancel')
            result=self.wait(manager,{'failed','cancelled'});manager.shutdown.assert_not_called();self.assertFalse(manager.busy)

    def test_drains_requests_and_rejects_early_ack(self):
        manager=self.manager();self.assertTrue(manager.enter());result=manager.begin('browser',False)
        self.assertEqual(manager.status('browser')['state'],'draining');self.assertFalse(manager.enter())
        with self.assertRaises(ValueError):manager.signal('browser',result['id'],'stop')
        manager.leave();ready=self.wait(manager,{'ready'});manager.signal('browser',ready['id'],'cancel');self.wait(manager,{'cancelled'})

    def test_external_wsgi_host_is_never_terminated(self):
        manager=hosting.StopCoordinator(self.path.parent,self.path)
        with self.assertRaises(ValueError):manager.begin('browser',False)
        self.assertFalse((self.path.parent/'database_backups').exists())

    def test_pin_required_even_for_admin_and_stop_blocks_new_writes(self):
        manager=self.manager();client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        with patch.object(dev_shutdown,'coordinator',manager):
            review=client.get('/api/dev/stop').json
            data=dict(pin='wrong',sync_git=False,review_token=review['review_token'])
            self.assertEqual(client.post('/api/dev/stop/prepare',json=data).status_code,403)
            self.assertIsNone(manager.job)
            response=client.post('/api/dev/stop/prepare',json=dict(data,pin=services.DEV_PIN));self.assertEqual(response.status_code,202,response.json)
            self.assertEqual(client.post('/api/dev/backup',json={}).status_code,503)
            self.assertEqual(client.post('/api/dev/stop/confirm',json={'job_id':'wrong'}).status_code,409)
            client.post('/api/dev/stop/cancel',json={'job_id':response.json['id']})
            end=time.monotonic()+2
            while manager.busy and time.monotonic()<end:time.sleep(.005)
            self.assertFalse(manager.busy);manager.shutdown.assert_not_called()

if __name__=='__main__':unittest.main()
