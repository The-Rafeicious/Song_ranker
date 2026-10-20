"""Authenticated, single-job developer metadata scan and report endpoints."""
from secrets import token_urlsafe
from threading import Thread, Lock, Event
from flask import jsonify, request, Response
from songranker.services import (app, DB_NAME, admin_required)
from songranker.developer.metadata_fill import (plan_metadata, paced_lookup, apply_plan, text_report)
from songranker.developer.catalog_sources import source_label

_lock = Lock()
_job = None


def public(job):
    plan = job.get('plan')
    return {'token':job['token'],'state':job['state'],'done':job['done'],'total':job['total'],
            'album':job['album'],'error':job.get('error',''),
            'tracks':len(plan['tracks']) if plan else 0,
            'dates':sum(d['status']=='proposed' for d in plan['dates']) if plan else 0,
            'song_dates':len(plan.get('song_dates',[])) if plan else 0,
            'sources':len(plan.get('sources',[])) if plan else 0,
            'metadata_failures':len(plan.get('metadata_failures',[])) if plan else 0,
            'song_date_changes':plan.get('song_dates',[]) if plan else [],
            'source_changes':[dict(id=r['id'],title=r['title'],fields=r['fields'],
                content_label=source_label(r['source'])) for r in plan.get('sources',[])] if plan else [],
            'track_failures':len(plan['track_failures']) if plan else 0,
            'date_failures':sum(d['status']=='failed' for d in plan['dates']) if plan else 0,
            'stopped':plan['stopped'] if plan else '',
            'date_changes':[d for d in plan['dates'] if d['status'] in ('proposed','filled')] if plan else [],
            'failures':plan['track_failures'] if plan else []}


def run_scan(job, country):
    def progress(done,total,album):
        with _lock:
            job.update(done=done,total=total,album=album)
    try:
        plan = plan_metadata(DB_NAME, country,
                             lookup=lambda url:paced_lookup(url,job['cancel'].is_set),
                             progress=progress,cancelled=job['cancel'].is_set)
        with _lock:
            job.update(plan=plan,state='ready')
    except Exception as error:
        app.logger.exception('Metadata scan failed')
        with _lock:
            job.update(error=str(error),state='error')


@app.route('/api/dev/metadata', methods=['GET','POST'])
@admin_required
def metadata_scan():
    global _job
    with _lock:
        if request.method == 'POST':
            if _job and _job['state'] in ('scanning','applying'):
                return jsonify(message='A metadata task is already running.'),409
            data = request.get_json(silent=True)
            if not isinstance(data,dict):
                return jsonify(message='Send a metadata task as an object.'),400
            country = data.get('country','gb')
            if not isinstance(country,str) or len(country)!=2 or not country.isascii() or not country.isalpha():
                return jsonify(message='Choose a two-letter Apple store code.'),400
            _job = {'token':token_urlsafe(24),'state':'scanning','done':0,'total':0,'album':'',
                    'cancel':Event(),'plan':None,'error':''}
            Thread(target=run_scan,args=(_job,country.lower()),daemon=True).start()
        return jsonify(public(_job) if _job else {'state':'idle'})


@app.route('/api/dev/metadata/<token>/cancel', methods=['POST'])
@admin_required
def cancel_scan(token):
    with _lock:
        if not _job or token != _job['token']:
            return jsonify(message='Scan not found.'),404
        if _job['state'] == 'scanning':
            _job['cancel'].set()
        return jsonify(public(_job))


@app.route('/api/dev/metadata/<token>/apply', methods=['POST'])
@admin_required
def apply_scan(token):
    with _lock:
        if not _job or token != _job['token']:
            return jsonify(message='Scan not found.'),404
        if _job['state'] != 'ready':
            return jsonify(message='Only a completed, unapplied scan can be applied.'),409
        _job['state']='applying'
        job = _job
    try:
        apply_plan(DB_NAME,job['plan'])
    except Exception as error:
        with _lock:
            job.update(state='ready',error=str(error))
        return jsonify(message=str(error)),409
    with _lock:
        job.update(state='applied',error='')
        return jsonify(public(job))


@app.route('/api/dev/metadata/<token>/report')
@admin_required
def scan_report(token):
    with _lock:
        if not _job or token != _job['token']:
            return jsonify(message='Scan not found.'),404
        if _job['state'] in ('scanning','applying'):
            return jsonify(message='Wait for the task to finish.'),409
        report = text_report(_job['plan']) if _job['plan'] else 'METADATA SCAN FAILED\n'+_job['error']+'\nNo metadata written.\n'
        if _job['plan'] and _job['error']:
            report += '\nAPPLY ERROR: '+_job['error']+'\n' 
    return Response(report,content_type='text/plain; charset=utf-8',headers={
        'Content-Disposition':'attachment; filename="metadata_fill_report.txt"','Cache-Control':'no-store'})

