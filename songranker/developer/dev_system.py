"""Local-admin dashboard inventory, explicit Git tasks and reviewed recovery."""
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sqlite3

from flask import jsonify,request,send_file
from itsdangerous import URLSafeTimedSerializer,BadData

from songranker import services
from songranker.services import (app, admin_required, get_db_connection)
from songranker.developer.catalog_sources import owner
from songranker.storage.database_schema import (SCHEMA_VERSION, definitions)
from songranker.storage.database_io import (capture, digest, snapshot, readonly, prepare_candidate, restore_live_database, DatabaseValidationError, write_export, quote)
from songranker.developer.git_sync import GitSync
from songranker.version import APP_VERSION


def signer():return URLSafeTimedSerializer(app.secret_key,salt='developer-system-review-v1')


def signed(kind,**data):return signer().dumps(dict(owner=owner(),kind=kind,**data))


def unpack(token,kind):
    if not isinstance(token,str) or len(token)>10000:raise ValueError('Open the current task review before applying it.')
    try:result=signer().loads(token,max_age=3600)
    except BadData as error:raise ValueError('This task review expired or changed. Review it again.') from error
    if result.get('owner')!=owner() or result.get('kind')!=kind:raise ValueError('Review this task in the current browser first.')
    return result


def git():return GitSync(services.ROOT,services.DB_NAME)


def git_payload(state=None):
    state=dict(state or git().status())
    fingerprint=state.pop('fingerprint',None)
    if fingerprint:state['review_token']=signed('git',fingerprint=fingerprint)
    return state


def git_reply(result):
    result=dict(result);result['git']=git_payload(result.pop('git',None))
    result['status']='success' if result['ok'] else 'error'
    status=200 if result['ok'] else 409 if result['code'] in ('busy','stale_target','pending_code','behind','diverged','operation_in_progress','database_behind','database_conflict','database_check_failed') else 502
    return jsonify(result),status


@app.route('/api/dev/git/status')
@admin_required
def git_status():return jsonify(git_payload())


@app.route('/api/dev/git/check',methods=['POST'])
@admin_required
def git_check():
    if not isinstance(request.get_json(silent=True),dict):return jsonify(message='Send a Git task as an object.'),400
    return git_reply(git().check())


def upload_database():
    data=request.get_json(silent=True)
    try:
        if not isinstance(data,dict):raise ValueError('Open the Git panel before uploading.')
        review=unpack(data.get('review_token'),'git')
    except ValueError as error:return jsonify(message=str(error)),400
    return git_reply(git().upload(review['fingerprint']))


@app.route('/api/dev/git/upload',methods=['POST'])
@admin_required
def git_upload():return upload_database()


def backup_folder():return Path(services.DB_NAME).resolve().parent/'database_backups'


def backup_path(name):
    if not isinstance(name,str) or name!=os.path.basename(name) or '/' in name or '\\' in name or not name.lower().endswith('.db'):
        raise ValueError('Choose a backup filename from this app’s backup folder.')
    path=backup_folder()/name
    if path.is_symlink() or not path.is_file():raise ValueError('Backup not found, or it is not a regular local backup file.')
    return path


def purpose(name):
    if name in ('rolling_1.db','rolling_2.db','rolling_3.db'):return 'Rotating requested / shutdown backup'
    for prefix,label in [('incoming_git_','Incoming Git database — compare before restore'),('pre_git_database_','Before Git database update'),('pre_v5_v2_','V2 archive before V5'),('pre_git_update_','Before code update'),('pre_restore_','Before restore'),('pre_upgrade_','Before schema upgrade'),
        ('pre_tag_edit_','Before tag change'),('pre_move_single_','Before Single move'),('pre_source_refresh_','Before source refresh'),
        ('pre_delete_song_','Before song removal'),('pre_reset_','Before competition reset'),('manual_mode_delete_','Before result removal'),
        ('manual_','Manual backup'),('song_ranker_','Database backup')]:
        if name.startswith(prefix):return label
    return 'Other database backup'


def backups():
    folder=backup_folder();rows=[]
    if folder.is_dir():
        for path in folder.iterdir():
            if path.is_file() and not path.is_symlink() and path.suffix.lower()=='.db':
                st=path.stat();rows.append(dict(name=path.name,purpose=purpose(path.name),bytes=st.st_size,modified=datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat()))
    return sorted(rows,key=lambda r:(r['modified'],r['name']),reverse=True)


def area(name,kind):
    if kind=='view':return 'Derived views'
    if name.startswith('preference_'):return 'Voting'
    if name.startswith('trivia_'):return 'Trivia'
    if name.startswith('tournament'):return 'Tournaments'
    if name.startswith('album_shelf'):return 'Album Shelves'
    if name=='competition_state':return 'Competition'
    if name=='listening_observations':return 'Listening analysis'
    if name=='elo_guess_rounds':return 'Elo Guesser'
    if name in ('challenge_runs','global_stats'):return 'Runs and records'
    if name in ('songs','albums','artists','genres','song_artists','song_genres','song_sources','song_details'):return 'Catalogue'
    return 'Extensions'


def inventory():
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        known={name for _,name,_ in definitions()};items=[]
        for row in conn.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type,name"):
            try:count=conn.execute('SELECT COUNT(*) FROM '+quote(row['name'])).fetchone()[0]
            except sqlite3.Error:count=None
            items.append(dict(name=row['name'],kind=row['type'],group=area(row['name'],row['type']) if row['name'] in known else 'Extensions',
                rows=count,role='Derived / read-only' if row['type']=='view' else 'Rebuildable projection' if row['name'] in ('preference_rating_projection','preference_mode_ratings') else 'Stored facts'))
        counts={r['name']:r['rows'] for r in items}
        song_rows=conn.execute('SELECT id,audio_url FROM songs').fetchall()
        totals=dict(songs=len(song_rows),artists=counts.get('artists',0),releases=counts.get('albums',0),tags=counts.get('genres',0),
            untagged=conn.execute('SELECT COUNT(*) FROM songs WHERE NOT EXISTS(SELECT 1 FROM song_genres WHERE song_id=songs.id)').fetchone()[0],
            missing_previews=sum(not str(r['audio_url'] or '').strip() for r in song_rows),
            missing_sources=len(song_rows)-conn.execute('SELECT COUNT(DISTINCT song_id) FROM song_sources').fetchone()[0])
        return dict(version=APP_VERSION,schema=conn.execute('PRAGMA user_version').fetchone()[0],totals=totals,inventory=items,
            integrity=conn.execute('PRAGMA integrity_check').fetchone()[0],foreign_key_errors=len(conn.execute('PRAGMA foreign_key_check').fetchall()))
    finally:conn.close()


@app.route('/api/dev/system')
@admin_required
def system_status():return jsonify(**inventory(),backups=backups(),git=git_payload())


def counts(db):
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    result={}
    for label,table in [('Songs','songs'),('Artists','artists'),('Releases','albums'),('Tags','genres'),('Preferences','preference_events'),
        ('Trivia rounds','trivia_rounds'),('Guesser rounds','elo_guess_rounds'),('Shelf rounds','album_shelf_rounds'),('Tournaments','tournaments')]:
        if table in tables:result[label]=db.execute('SELECT COUNT(*) FROM '+quote(table)).fetchone()[0]
    return result


@app.route('/api/dev/backups/review',methods=['POST'])
@admin_required
def backup_review():
    data=request.get_json(silent=True)
    try:
        if not isinstance(data,dict):raise ValueError('Choose a stored backup first.')
        path=backup_path(data.get('filename'))
        require_v3_backup(path)
        with TemporaryDirectory(dir=backup_folder(),prefix='.review_') as tmp:
            candidate=prepare_candidate(path,Path(tmp)/'candidate.db')
            with readonly(path) as original:source_version=original.execute('PRAGMA user_version').fetchone()[0]
            with readonly(candidate) as prepared:backup_digest=digest(capture(prepared));backup_counts=counts(prepared)
        with snapshot(services.DB_NAME) as live:live_digest=digest(capture(live));live_counts=counts(live)
        return jsonify(filename=path.name,purpose=purpose(path.name),source_schema=source_version,target_schema=SCHEMA_VERSION,
            backup=backup_counts,live=live_counts,review_token=signed('restore',filename=path.name,backup=backup_digest,live=live_digest))
    except (ValueError,sqlite3.Error) as error:return jsonify(message=str(error)),400


def restore_database(*,require_review=False):
    if request.environ.get('wsgi.multiprocess'):return jsonify(message='Stop all WSGI workers and use the offline recovery guide.'),409
    data=request.get_json(silent=True)
    try:
        if not isinstance(data,dict):raise ValueError('Choose and review a stored backup.')
        expected_live=expected_backup=None
        if require_review or data.get('review_token'):
            reviewed=unpack(data.get('review_token'),'restore');name=reviewed['filename']
            expected_live=reviewed['live'];expected_backup=reviewed['backup']
        else:name=data.get('filename') # Compatibility for the prior authenticated endpoint.
        path=backup_path(name)
        require_v3_backup(path)
        backup=restore_live_database(path,services.DB_NAME,expected_live=expected_live,expected_backup=expected_backup)
        return jsonify(status='success',message='Backup restored. Reload open game tabs before continuing.',safety_backup=Path(backup).name)
    except TimeoutError as error:return jsonify(message=str(error)),503
    except DatabaseValidationError as error:return jsonify(message=str(error)),409
    except (ValueError,sqlite3.Error) as error:return jsonify(message=str(error)),400
    except Exception:
        app.logger.exception('Reviewed database restore failed')
        return jsonify(message='Restore could not finish. Check the safety backup and database health.'),500


@app.route('/api/dev/backups/restore',methods=['POST'])
@admin_required
def backup_restore():return restore_database(require_review=True)


@app.route('/api/dev/backups/<name>/download')
@admin_required
def backup_download(name):
    try:path=backup_path(name)
    except ValueError as error:return jsonify(message=str(error)),404
    return send_file(path,as_attachment=True,download_name=path.name,mimetype='application/vnd.sqlite3',max_age=0)


@app.route('/api/dev/database/export')
@admin_required
def full_export():
    with TemporaryDirectory(dir=Path(services.DB_NAME).resolve().parent,prefix='.export_') as tmp:
        path=write_export(services.DB_NAME,Path(tmp)/'export.json');data=path.read_bytes()
    return send_file(BytesIO(data),as_attachment=True,download_name='Song_Ranker_full_export.json',mimetype='application/json',max_age=0)


@app.route('/api/dev/database/guide')
@admin_required
def database_guide():
    return send_file(Path(services.ROOT)/'docs'/'TECHNICAL_GUIDE.md',as_attachment=True,download_name='Song_Ranker_Technical_Guide.md',max_age=0)


@app.route('/api/dev/selection-health')
@admin_required
def selection_health():
    from flask import session
    from songranker.reports.selection_health import build_selection_health
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        response=jsonify(build_selection_health(conn,context={key:session.get(key) for key in
            ('preference_owner','challenge_owner','trivia_round_token','guess_token')}))
        response.headers['Cache-Control']='no-store'
        return response
    finally:
        conn.close()


@app.route('/api/dev/song-quality/<int:song_id>',methods=['GET','POST'])
@admin_required
def song_quality(song_id):
    conn=get_db_connection()
    try:
        if not conn.execute('SELECT 1 FROM songs WHERE id=?',(song_id,)).fetchone():return jsonify(message='Song not found.'),404
        if request.method=='POST':
            data=request.get_json(silent=True)
            if not isinstance(data,dict) or type(data.get('preview_bad')) is not bool or not isinstance(data.get('preview_note',''),str) or len(data.get('preview_note',''))>1000:
                return jsonify(message='Choose a preview flag and a note up to 1000 characters.'),400
            conn.execute('INSERT OR IGNORE INTO song_details(song_id) VALUES(?)',(song_id,))
            conn.execute('UPDATE song_details SET preview_bad=?,preview_note=?,flagged_at=unixepoch() WHERE song_id=?',
                (int(data['preview_bad']),data.get('preview_note','').strip(),song_id));conn.commit()
        row=conn.execute('SELECT preview_bad,preview_note,flagged_at FROM song_details WHERE song_id=?',(song_id,)).fetchone()
        return jsonify(dict(row) if row else dict(preview_bad=0,preview_note='',flagged_at=None))
    finally:conn.close()


@app.route('/api/dev/analysis')
@admin_required
def analysis_data():
    from songranker.listening import (summary, song_summaries)
    from songranker.developer.catalog_sources import current_sources
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        return jsonify(sources=[{key:value for key,value in saved.items() if key!='snapshot'} for saved in current_sources(conn).values()],
            listening=summary(conn),songs=song_summaries(conn),observations=[dict(r) for r in conn.execute('SELECT o.*,s.title,q.preview_bad,q.preview_note FROM listening_observations o LEFT JOIN songs s ON s.id=o.song_id LEFT JOIN song_details q ON q.song_id=o.song_id ORDER BY o.id')],
            preview_flags=[dict(r) for r in conn.execute('SELECT s.id,s.title,q.preview_note,q.flagged_at FROM song_details q JOIN songs s ON s.id=q.song_id WHERE q.preview_bad=1 ORDER BY s.id')])
    finally:conn.close()


def require_v3_backup(path):
    with readonly(path) as conn:
        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='competition_state'").fetchone()
        if not exists or not conn.execute('SELECT 1 FROM competition_state WHERE id=1 AND generation=3').fetchone():
            raise DatabaseValidationError('This is a V2 archive. V5 restores accept V3 competition backups; retain the V2 archive for catalogue recovery.')

