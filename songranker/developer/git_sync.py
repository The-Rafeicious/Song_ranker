"""Database-only Git uploads and guarded, startup-only fast-forward updates.

No Flask imports: startup can update before loading any application modules.
All process calls use argument lists; remote errors never expose credential URLs.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile


class SyncError(RuntimeError):
    def __init__(self,code,message):super().__init__(message);self.code=code


def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def display_remote(value):
    """Show the destination, excluding URL credentials, query strings and fragments."""
    try:
        if '://' in value:
            parsed=urlsplit(value)
            return (parsed.hostname or 'Local remote')+'/'+('/'.join(parsed.path.strip('/').split('/')[-2:]))
        if '@' in value and ':' in value:return value.split('@',1)[1].split('?',1)[0].split('#',1)[0]
        return 'Local remote / '+Path(value).name
    except ValueError:return 'Configured remote'


class GitSync:
    def __init__(self,root,database):
        self.root=Path(root).resolve();self.database=Path(database).resolve()
        self.repo=None;self.gitdir=None;self.prefix='';self.sql=self.root/'database_backup.sql'

    def run(self,*args,check=True,network=False):
        env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GIT_OPTIONAL_LOCKS='0')
        try:
            result=subprocess.run(['git',*args],cwd=self.repo or self.root,env=env,stdin=subprocess.DEVNULL,
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25 if network else 12)
        except FileNotFoundError as error:raise SyncError('git_missing','Git is not installed or is unavailable to this app.') from error
        except subprocess.TimeoutExpired as error:raise SyncError('timeout','Git did not finish in time. Check the target and retry; local data is kept.') from error
        except OSError as error:raise SyncError('git_unavailable','Git could not run. Check the local repository and permissions.') from error
        if check and result.returncode:
            text=(result.stderr+' '+result.stdout).lower()
            if any(s in text for s in ('authentication failed','permission denied','could not read username','could not read password')):
                raise SyncError('authentication_failed','Git could not authenticate. Check access in your terminal; no credentials are entered here.')
            raise SyncError('remote_unavailable' if network else 'git_failed',
                'Could not contact the configured remote. Check network/access and retry.' if network else 'Git could not complete this operation. Review repository state in your terminal.')
        return result

    def discover(self):
        result=self.run('rev-parse','--show-toplevel',check=False)
        if result.returncode:raise SyncError('not_repo','This app folder is not in a Git repository. Local backups and downloads still work.')
        self.repo=Path(result.stdout.strip()).resolve()
        try:
            relative=self.root.relative_to(self.repo).as_posix();self.prefix='' if relative=='.' else relative
        except ValueError:raise SyncError('outside_repo','The app folder is outside the reported repository.')
        self.sql_rel=(self.prefix+'/' if self.prefix else '')+'database_backup.sql'
        raw=self.run('rev-parse','--absolute-git-dir').stdout.strip();self.gitdir=Path(raw)
        return self

    @property
    def state_dir(self):return self.gitdir/'song_ranker_sync'

    @contextmanager
    def lock(self):
        self.state_dir.mkdir(exist_ok=True);path=self.state_dir/'operation.lock'
        f=path.open('a+b')
        if path.stat().st_size==0:f.write(b'0');f.flush()
        f.seek(0)
        try:
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as error:raise SyncError('busy','Another Git task is running. Wait for it to finish before trying again.') from error
            yield
        finally:
            f.close() # OS locks are released even if a process exits unexpectedly.

    def history(self):
        try:return json.loads((self.state_dir/'history.json').read_text())[:10]
        except (OSError,ValueError,TypeError):return []

    def record(self,result):
        result=dict(result,at=stamp());events=[result,*self.history()][:10]
        self.state_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.state_dir,mode='w',encoding='utf-8',delete=False) as f:
            json.dump(events,f,ensure_ascii=True,indent=2);f.flush();os.fsync(f.fileno());temp=f.name
        os.replace(temp,self.state_dir/'history.json');return result

    def protected(self,path):
        p=PurePosixPath(path);parts={s.casefold() for s in p.parts};name=p.name.casefold()
        try:db_rel=self.database.relative_to(self.repo).as_posix().casefold()
        except ValueError:db_rel=None
        return (path.casefold() in {db_rel,(db_rel or '')+'-wal',(db_rel or '')+'-shm',(db_rel or '')+'-journal'}
            or name.endswith(('.db','.sqlite','.sqlite3','.pyc','-wal','-shm','-journal'))
            or bool(parts&{'instance','database_backups','__pycache__','.venv','venv','node_modules','.pytest_cache'})
            or name in {'database_snapshot.txt','current_elo_rankings.txt','.env'}
            or any(s.startswith(('.restore_','.export_')) for s in p.parts))

    def changes(self):
        fields=self.run('status','--porcelain=v1','-z','--untracked-files=all').stdout.split('\0');result=[];i=0
        while i<len(fields):
            item=fields[i];i+=1
            if not item:continue
            code=item[:2];path=item[3:];old=None
            if 'R' in code or 'C' in code:
                if i<len(fields):old=fields[i];i+=1
            result.append(dict(path=path,old_path=old,status=code,staged=code[0] not in (' ','?'),protected=self.protected(path)))
        return result

    def inspect(self):
        if self.repo is None:self.discover()
        branch=self.run('symbolic-ref','--quiet','--short','HEAD',check=False).stdout.strip()
        head=self.run('rev-parse','--verify','HEAD',check=False).stdout.strip()
        if not head:raise SyncError('unborn','The repository has no initial commit. Finish Git setup in your terminal first.')
        if not branch:raise SyncError('detached','Git is on a detached commit. Choose the intended branch in your terminal first.')
        remote=self.run('config','--get',f'branch.{branch}.remote',check=False).stdout.strip() or 'origin'
        merge=self.run('config','--get',f'branch.{branch}.merge',check=False).stdout.strip() or 'refs/heads/'+branch
        if remote not in self.run('remote').stdout.splitlines() or not merge.startswith('refs/heads/'):
            raise SyncError('no_remote','No usable named remote/upstream is configured for this branch. Finish Git setup first.')
        if remote.startswith('-') or any(c.isspace() for c in remote):raise SyncError('invalid_target','The configured remote name is invalid.')
        target=merge[len('refs/heads/'):];tracking=f'refs/remotes/{remote}/{target}'
        if self.run('check-ref-format',tracking,check=False).returncode:raise SyncError('invalid_target','The configured target branch is invalid.')
        url=self.run('remote','get-url',remote).stdout.strip()
        push_url=self.run('remote','get-url','--push',remote).stdout.strip()
        # Multiple destinations make a single target/receipt ambiguous.
        push_urls=self.run('remote','get-url','--push','--all',remote).stdout.splitlines()
        if len(push_urls)!=1:raise SyncError('multiple_targets','This remote has multiple push destinations. Use a single destination for app backup uploads.')
        if push_url!=url:raise SyncError('different_targets','Fetch and push use different destinations. Configure one destination or sync this setup through Git manually.')
        remote_head=self.run('rev-parse','--verify',tracking,check=False).stdout.strip() or None
        ahead=behind=None;pending_files=[];commits=[]
        if remote_head:
            counts=self.run('rev-list','--left-right','--count',head+'...'+remote_head).stdout.split();ahead,behind=map(int,counts)
            if ahead:
                pending_files=sorted(set(filter(None,self.run('log','--format=','--name-only','-z',remote_head+'..'+head).stdout.replace('\n','\0').split('\0'))))
                commits=[dict(hash=line.split(' ',1)[0],subject=line.split(' ',1)[1] if ' ' in line else '') for line in self.run('log','--format=%h %s','-10',remote_head+'..'+head).stdout.splitlines()]
        conflicts=bool(self.run('ls-files','-u','-z').stdout)
        in_progress=conflicts or any((self.gitdir/name).exists() for name in ('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply'))
        changes=self.changes();code_changes=[r for r in changes if not r['protected'] and r['path']!=self.sql_rel]
        state='operation_in_progress' if in_progress else 'not_checked' if remote_head is None else 'diverged' if ahead and behind else 'behind' if behind else 'ahead' if ahead else 'up_to_date'
        fingerprint=digest(dict(repo=str(self.repo),prefix=self.prefix,branch=branch,head=head,remote=remote,target=target,url=url,push_url=push_url))
        return dict(available=True,state=state,branch=branch,head=head,remote=remote,target=target,destination=display_remote(push_url),
            tracking_head=remote_head,ahead=ahead,behind=behind,pending_files=pending_files,commits=commits,
            pending_code=any(p!=self.sql_rel for p in pending_files),changes=changes,code_changes=len(code_changes),
            staged_changes=sum(r['staged'] for r in changes),in_progress=in_progress,fingerprint=fingerprint,
            history=self.history(),snapshot=dict(name='database_backup.sql',exists=self.sql.is_file(),bytes=self.sql.stat().st_size if self.sql.is_file() else 0))

    def status(self):
        try:return self.inspect()
        except SyncError as error:return dict(available=False,state=error.code,message=str(error),history=self.history() if self.gitdir else [])

    def fetch(self,state):
        self.run('fetch','--no-tags','--no-write-fetch-head',state['remote'],
            '+refs/heads/'+state['target']+':refs/remotes/'+state['remote']+'/'+state['target'],network=True)

    def check(self):
        try:
            self.discover()
            with self.lock():
                before=self.inspect();self.fetch(before);after=self.inspect()
                self.record(dict(ok=True,action='check',code=after['state'],message='Remote checked. Local code and live database were not changed.'))
                return dict(ok=True,code=after['state'],message='Remote checked. Local code and live database were not changed.',git=self.inspect())
        except SyncError as error:return self.failure('check',error)

    def failure(self,action,error,**extra):
        result=dict(ok=False,action=action,code=error.code,message=str(error),**extra)
        if self.gitdir:
            try:self.record(result)
            except OSError:pass
        return result

    def archive_sql(self,label):
        if not self.sql.exists():return None
        if self.sql.is_symlink():raise SyncError('linked_snapshot','The SQL snapshot is a symbolic link. Use a normal file before syncing.')
        self.state_dir.mkdir(exist_ok=True)
        dest=self.state_dir/(label+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sql')
        shutil.copy2(self.sql,dest)
        for old in sorted(self.state_dir.glob('before_*.sql'),key=lambda p:p.name.rsplit('_',3)[1:],reverse=True)[10:]:old.unlink()
        return dest

    def write_snapshot(self):
        if not self.database.is_file():raise SyncError('database_missing','The live database does not exist. Start/restore the app before uploading a backup.')
        if self.sql.is_symlink():raise SyncError('linked_snapshot','The SQL snapshot is a symbolic link. Use a normal file before syncing.')
        from songranker.storage.database_io import (snapshot, validate, sql_dump)
        with snapshot(self.database) as db:
            validate(db)
            content=sql_dump(db)
            with tempfile.NamedTemporaryFile(dir=self.root,mode='w',encoding='utf-8',newline='\n',delete=False,prefix='.git_snapshot_') as f:
                name=f.name
                try:
                    f.write(content)
                    f.flush();os.fsync(f.fileno())
                except BaseException:
                    Path(name).unlink(missing_ok=True);raise
        try:
            if self.sql.is_file() and Path(name).read_bytes()==self.sql.read_bytes():return
            self.archive_sql('before_upload');os.replace(name,self.sql)
        finally:Path(name).unlink(missing_ok=True)

    def upload(self,expected=None):
        commit=None
        try:
            self.discover()
            with self.lock():
                before=self.inspect()
                if expected and expected!=before['fingerprint']:raise SyncError('stale_target','The branch or target changed. Check Git again before uploading.')
                if before['in_progress']:raise SyncError('operation_in_progress','Finish the current merge/rebase/conflict work in your terminal before syncing.')
                self.fetch(before);state=self.inspect()
                if state['behind']:raise SyncError(state['state'],'The remote has updates. Restart for a safe fast-forward update, or resolve diverged history in your terminal. No database rows are merged.')
                if state['pending_code']:raise SyncError('pending_code','Unpublished code commits are on this branch. Review/publish them through Git first; this button uploads database backups only.')
                self.write_snapshot()
                self.run('add','--',self.sql_rel)
                changed=self.run('diff','--cached','--quiet','--',self.sql_rel,check=False).returncode
                if changed not in (0,1):raise SyncError('snapshot_diff_failed','Could not check the generated SQL snapshot. The local file is kept.')
                if changed:
                    result=self.run('commit','--only','-m','Save Song Ranker database backup','--',self.sql_rel,check=False)
                    if result.returncode:raise SyncError('commit_failed','The snapshot is saved locally, but Git could not commit it. Check identity, signing or hooks in your terminal, then retry.')
                    commit=self.run('rev-parse','HEAD').stdout.strip()
                    paths=set(filter(None,self.run('diff-tree','--no-commit-id','--name-only','-z','-r',commit).stdout.split('\0')))
                    if paths!={self.sql_rel}:raise SyncError('commit_scope_changed','Git created a commit containing additional changes. Review it in your terminal before publishing; no push was made.')
                latest=self.inspect()
                if latest['pending_code']:raise SyncError('pending_code','The branch acquired unpublished code commits. Review it in your terminal before publishing the backup.')
                if latest['ahead']:
                    result=self.run('push','--porcelain',latest['remote'],'HEAD:refs/heads/'+latest['target'],check=False,network=True)
                    if result.returncode:raise SyncError('push_failed','Upload was not confirmed. The local snapshot/commit is kept. Check remote access/history and retry; no force-push is used.')
                    self.run('update-ref','refs/remotes/'+latest['remote']+'/'+latest['target'],latest['head'])
                    code='uploaded';message='Database backup uploaded. Local code edits and the live database were kept.'
                else:code='unchanged';message='The database backup already matches the remote. No new commit or upload was needed.'
                result=self.record(dict(ok=True,action='upload',code=code,message=message,commit=commit))
                return dict(result,git=self.inspect())
        except SyncError as error:return self.failure('upload',error,commit=commit)
        except (OSError,sqlite3.Error,ValueError):return self.failure('upload',SyncError('snapshot_failed','Could not finish the local snapshot. The live database was not changed.'),commit=commit)

    def startup(self):
        """Called only before application imports, while the server is stopped."""
        sql_copy=None;modified_sql=False;applying=False;backup=None
        try:
            self.discover()
            with self.lock():
                state=self.inspect()
                if state['in_progress']:raise SyncError('operation_in_progress','Update skipped: finish the existing Git operation first. Using local code/data.')
                self.fetch(state);state=self.inspect()
                if state['ahead'] and state['behind']:raise SyncError('diverged','Update skipped: local and remote commits diverged. Resolve them in Git; no automatic merge/rebase is attempted.')
                if not state['behind']:
                    return self.record(dict(ok=True,action='startup',code='unchanged',message='No incoming code update. Using local code and database.'))
                if state['staged_changes']:raise SyncError('staged_changes','Update skipped: staged changes need attention in Git. Using local code/data.')
                if state['code_changes']:raise SyncError('local_changes','Update skipped: local code edits are kept. Commit/reconcile them in Git before updating.')
                changed=list(filter(None,self.run('diff','--name-only','-z',state['head'],state['tracking_head']).stdout.split('\0')))
                if any(self.protected(p) for p in changed):raise SyncError('protected_changes','Update skipped: the incoming commit changes a database/private/generated file. Review it manually; local data was kept.')
                if self.prefix and any(not p.startswith(self.prefix+'/') for p in changed):raise SyncError('outside_project','Update skipped: incoming changes extend outside this app folder. Review the repository update manually.')
                if self.database.is_file():
                    from songranker.storage.database_io import create_backup
                    backup=str(create_backup(self.database,'pre_git_update'))
                if self.sql_rel in changed and any(r['path']==self.sql_rel for r in state['changes']):
                    sql_copy=self.archive_sql('before_update');modified_sql=True
                    exists=self.run('cat-file','-e',state['head']+':'+self.sql_rel,check=False).returncode==0
                    if exists:self.run('restore','--source='+state['head'],'--worktree','--',self.sql_rel)
                    else:self.sql.unlink(missing_ok=True)
                if self.inspect()['fingerprint']!=state['fingerprint']:raise SyncError('stale_target','Update stopped: the branch/target changed while preparing. Restart after checking Git.')
                applying=True;self.run('merge','--ff-only','--no-edit',state['tracking_head'])
                # Timestamp/size-only Python caches can otherwise survive a rapid update.
                for relative in changed:
                    source=self.repo/relative
                    if source.suffix=='.py':
                        cache=source.parent/'__pycache__'
                        if cache.is_dir():
                            for p in cache.glob(source.stem+'.*.pyc'):p.unlink()
                return self.record(dict(ok=True,action='startup',code='updated',message='Code updated by fast-forward. Loading the updated app; the existing live database is kept.',
                    head=state['tracking_head'],backup=Path(backup).name if backup else None))
        except (SyncError,OSError,sqlite3.Error) as error:
            if modified_sql and sql_copy:
                try:shutil.copy2(sql_copy,self.sql)
                except OSError:applying=True
            error=error if isinstance(error,SyncError) else SyncError('update_failed','Could not prepare the update safely. Local data is kept; check backups and Git state.')
            return self.failure('startup',error,stop_startup=applying or error.code=='busy')
