"""Fresh PIN, reviewed destination and browser acknowledgement for app shutdown."""
import hmac
import time
from threading import Lock
from flask import g,jsonify,request
from songranker import services
from songranker.services import app,admin_required
from songranker.hosting import StopCoordinator
from songranker.developer.catalog_sources import owner
from songranker.developer.dev_system import signed,unpack
from songranker.developer.git_sync import GitSync
from songranker.lan_security import WRITE_GET_ENDPOINTS

coordinator=StopCoordinator(services.ROOT,services.DB_NAME)
app.extensions['song_ranker_stop']=coordinator
_attempts={};_attempt_lock=Lock()


@app.before_request
def stop_request_guard():
    if request.path.startswith('/api/dev/stop'):return None
    # Track entire requests, including direct-SQL metadata fills and Git tasks.
    # Reject new API reads too: they must not queue behind the final DB gate.
    if coordinator.busy and request.path.startswith('/api/'):
        return jsonify(message='The app is preparing to stop. Wait, or cancel the stop task.'),503
    if request.method not in ('GET','HEAD','OPTIONS') or request.endpoint in WRITE_GET_ENDPOINTS:
        if not coordinator.enter():return jsonify(message='The app is preparing to stop.'),503
        g.stop_lease=True


@app.teardown_request
def release_stop_request(error):
    if g.pop('stop_lease',False):coordinator.leave()


@app.route('/api/dev/stop')
@admin_required
def stop_status():
    state=coordinator.status(owner())
    if state['state']=='idle' or state['state'] in ('failed','cancelled'):
        target=GitSync(services.ROOT,services.DB_NAME).status()
        fingerprint=target.pop('fingerprint',None)
        state.update(target=target,review_token=signed('stop',fingerprint=fingerprint))
    return jsonify(state)


@app.route('/api/dev/stop/prepare',methods=['POST'])
@admin_required
def stop_prepare():
    data=request.get_json(silent=True);browser=owner()
    if not isinstance(data,dict) or type(data.get('sync_git')) is not bool:return jsonify(message='Choose whether to upload to Git.'),400
    now=time.monotonic()
    with _attempt_lock:
        for key,(_,stamp) in list(_attempts.items()):
            if now-stamp>=60:_attempts.pop(key,None)
        failures,stamp=_attempts.get(browser,(0,now))
        if failures>=5:return jsonify(message='Too many incorrect PIN attempts. Wait one minute and try again.'),429
        pin=data.get('pin')
        if not isinstance(pin,str) or not hmac.compare_digest(pin.encode(),services.DEV_PIN.encode()):
            if len(_attempts)>=256:_attempts.pop(next(iter(_attempts)))
            _attempts[browser]=(failures+1,stamp)
            return jsonify(message='Incorrect developer PIN. The app is still running.'),403
        _attempts.pop(browser,None)
    try:
        review=unpack(data.get('review_token'),'stop')
        if data['sync_git'] and not review.get('fingerprint'):raise ValueError('Git is not configured. Choose a local-only stop, or configure Git first.')
        return jsonify(coordinator.begin(browser,data['sync_git'],review.get('fingerprint'))),202
    except ValueError as error:return jsonify(message=str(error)),409


@app.route('/api/dev/stop/confirm',methods=['POST'])
@app.route('/api/dev/stop/cancel',methods=['POST'])
@admin_required
def stop_signal():
    data=request.get_json(silent=True)
    try:
        if not isinstance(data,dict):raise ValueError('Choose the current stop task.')
        coordinator.signal(owner(),data.get('job_id'),'cancel' if request.path.endswith('/cancel') else 'stop')
        return jsonify(status='success',message='Stop cancelled.' if request.path.endswith('/cancel') else 'Shutdown acknowledged.')
    except ValueError as error:return jsonify(message=str(error)),409
