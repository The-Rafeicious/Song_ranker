"""Single-process, acknowledged shutdown; never kill a WSGI host or other process."""
from threading import Condition, Event, Thread
import secrets
import time
from pathlib import Path

from songranker.storage.database_access import gate
from songranker.storage.database_io import create_rolling_backup
from songranker.developer.git_sync import GitSync


class StopCoordinator:
    def __init__(self,root,database,shutdown=None,*,ack_timeout=120,ack_delay=1):
        self.root=root;self.database=database;self.shutdown=shutdown
        self.condition=Condition();self.inflight=0;self.busy=False;self.job=None
        self.ack_timeout=ack_timeout;self.ack_delay=ack_delay

    def enter(self):
        with self.condition:
            if self.busy:return False
            self.inflight+=1;return True

    def leave(self):
        with self.condition:
            self.inflight-=1;self.condition.notify_all()

    def status(self,owner):
        with self.condition:
            if not self.job or self.job['owner']!=owner:return dict(state='idle',supported=self.shutdown is not None)
            return dict(supported=self.shutdown is not None,**{k:v for k,v in self.job.items() if k not in ('owner','event','action')})

    def begin(self,owner,sync_git,expected=None):
        with self.condition:
            if self.shutdown is None:raise ValueError('Start the app with python main.py to use website shutdown. This host is managed externally.')
            if self.busy:
                if self.job['owner']==owner:return self.status(owner)
                raise ValueError('Another stop task is already running.')
            job=dict(owner=owner,id=secrets.token_urlsafe(24),state='draining',message='Finishing active requests…',backup=None,git=None,event=Event(),action=None)
            self.job=job;self.busy=True
            Thread(target=self.run,args=(job,sync_git,expected),daemon=True).start()
            return self.status(owner)

    def signal(self,owner,job_id,action):
        with self.condition:
            job=self.job
            if not job or job['owner']!=owner or job['id']!=job_id:raise ValueError('This stop task is not available in this browser.')
            if action=='stop' and job['state']!='ready':raise ValueError('Wait for a successful backup and Git result before stopping.')
            if action=='cancel' and job['state'] not in ('draining','backup','git','ready'):raise ValueError('This stop task has already finished.')
            job['action']=action;job['event'].set()

    def update(self,job,**values):
        with self.condition:job.update(values)

    def run(self,job,sync_git,expected):
        try:
            with self.condition:
                deadline=time.monotonic()+30
                while self.inflight:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise ValueError('An active request did not finish. The app stays running; try again later.')
                    self.condition.wait(remaining)
            with gate.maintenance():
                if job['action']=='cancel':raise ValueError('Stop cancelled. The app is running.')
                self.update(job,state='backup',message='Saving rotating database backup…')
                backup=create_rolling_backup(self.database)
                self.update(job,backup=Path(backup).name)
                if sync_git:
                    self.update(job,state='git',message='Local backup saved. Uploading database snapshot to Git…')
                    result=GitSync(self.root,self.database).upload(expected)
                    self.update(job,git={k:result.get(k) for k in ('ok','code','message','commit')})
                    if not result.get('ok'):raise ValueError(result.get('message') or 'Git upload failed. The app stays running.')
                else:self.update(job,git=dict(ok=None,code='skipped',message='Git upload not requested.'))
                if job['action']=='cancel':raise ValueError('Stop cancelled. Backup outcomes are shown; the app is running.')
                self.update(job,state='ready',message='Backup completed. Review the results before shutdown.')
                if not job['event'].wait(self.ack_timeout):raise ValueError('Shutdown confirmation timed out. Backup outcomes are kept; the app is running.')
                if job['action']!='stop':raise ValueError('Stop cancelled. Backup outcomes are kept; the app is running.')
                self.update(job,state='stopping',message='Backups confirmed. Stopping the app…')
                time.sleep(self.ack_delay)  # Give the acknowledgement response time to leave the socket.
                self.shutdown()
                self.update(job,state='stopped',message='App stopped. You can close this tab.')
        except Exception as error:
            self.update(job,state='cancelled' if job['action']=='cancel' else 'failed',message=str(error))
        finally:
            with self.condition:self.busy=False;self.condition.notify_all()


def register_waitress_shutdown(server,coordinator):
    """Use Waitress's own dispatcher/socket map; no signal or forced process exit."""
    def shutdown():
        from waitress import wasyncore
        server.task_dispatcher.shutdown()
        wasyncore.close_all(getattr(server,'map',None) or server._map)
    coordinator.shutdown=shutdown
