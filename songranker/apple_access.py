"""Bounded in-memory lookup/preview caching and streamed Apple diagnostics.

At most ten complete previews live in page-scoped RAM for ten minutes; no audio files,
request logs or database counters are stored. Search/lookup and
preview media have separate safeguards; Apple's published search limit does not
specify a preview-CDN quota.
"""

from collections import OrderedDict, deque
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlsplit, urljoin
import math
import re
import time
import requests
from flask import Response, jsonify, request, stream_with_context
from songranker.services import app, get_db_connection


class AppleRequestError(Exception):
    def __init__(self, message, status=502, retry_after=0, state='unavailable', upstream_status=None):
        super().__init__(message)
        self.status, self.retry_after, self.state = status, retry_after, state
        self.upstream_status = upstream_status

    def response(self):
        response = jsonify(message=str(self), error=str(self), state=self.state,
                           retry_after=self.retry_after, upstream_status=self.upstream_status)
        response.status_code = self.status
        response.headers['Cache-Control'] = 'no-store'
        if self.retry_after:
            response.headers['Retry-After'] = str(self.retry_after)
        return response


def retry_seconds(value, fallback=60):
    try:
        return max(1, math.ceil(float(value)))
    except (ValueError, TypeError, OverflowError):
        try:
            date = parsedate_to_datetime(str(value))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(1, math.ceil((date-datetime.now(timezone.utc)).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            return fallback


class RequestGate:
    def __init__(self, limit, spacing, clock=time.monotonic):
        self.limit, self.spacing, self.clock = limit, spacing, clock
        self.lock = Lock()
        self.starts = deque()
        self.sessions = OrderedDict()
        self.cooldown = 0
        self.reason = 'rate_limited'

    def wait(self):
        with self.lock:
            return max(0, math.ceil(self.cooldown-self.clock()))

    def block(self, seconds, reason='rate_limited'):
        with self.lock:
            self.cooldown = max(self.cooldown, self.clock()+seconds)
            self.reason = reason

    def admit(self, key=None):
        with self.lock:
            now = self.clock()
            if self.cooldown > now:
                raise AppleRequestError('Apple access paused. Try again in '+str(math.ceil(self.cooldown-now))+' seconds.',
                                        429, math.ceil(self.cooldown-now), self.reason)
            while self.starts and self.starts[0] <= now-60:
                self.starts.popleft()
            while self.sessions and next(iter(self.sessions.values())) <= now:
                self.sessions.popitem(last=False)
            # Byte-range requests for one active clip share a reservation.
            if key and key in self.sessions:
                return
            wait = max(self.starts[-1]+self.spacing-now if self.starts else 0,
                       self.starts[0]+60-now if len(self.starts)>=self.limit else 0)
            if wait > 0:
                raise AppleRequestError('Local request limit. Try again in '+str(math.ceil(wait))+' seconds.',
                                        429, math.ceil(wait), 'throttled')
            self.starts.append(now)
            if key:
                self.sessions[key] = now+120
                while len(self.sessions)>256:
                    self.sessions.popitem(last=False)


lookup_gate = RequestGate(12, 5)
preview_gate = RequestGate(18, .5)
lookup_lock = Lock()
lookup_cache = OrderedDict()
preview_status = OrderedDict()
status_lock = Lock()


def upstream_error(response, gate, label):
    status = response.status_code
    if status == 429:
        wait = retry_seconds(response.headers.get('Retry-After'))
        gate.block(wait)
        return AppleRequestError(f'Apple {label} returned HTTP 429 (too many requests). Wait {wait} seconds.',
                                 429, wait, 'rate_limited', status)
    if status in (401, 403):
        # Refused access is not proof of a rate limit. Stop repeated attempts.
        wait = retry_seconds(response.headers.get('Retry-After'))
        gate.block(wait, 'refused')
        return AppleRequestError(f'Apple refused this {label} (HTTP {status}). Access may be restricted. Try again after {wait} seconds.',
                                 502, wait, 'refused', status)
    if status in (404, 410):
        return AppleRequestError(f'Apple {label} is no longer available (HTTP {status}). Refresh this song’s preview URL in Dev.',
                                 404, 0, 'missing', status)
    if status >= 500:
        gate.block(15, 'unavailable')
    return AppleRequestError(f'Apple {label} failed (HTTP {status}).',502,
                             15 if status>=500 else 0,'unavailable',status)


def apple_lookup(url):
    """12 upstream requests/minute, at least 5 seconds apart, 10-minute cache."""
    parsed = urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname!='itunes.apple.com' or parsed.path not in ('/search','/lookup'):
        raise ValueError('Invalid Apple lookup URL.')
    if not lookup_lock.acquire(blocking=False):
        raise AppleRequestError('An Apple lookup is already loading. Try again shortly.',429,1,'throttled')
    try:
        now=time.monotonic()
        cached=lookup_cache.get(url)
        if cached and cached[0]>now:
            lookup_cache.move_to_end(url)
            return cached[1]
        lookup_gate.admit()
        try:
            response=requests.get(url,timeout=(3,8),allow_redirects=False)
            try:
                if response.status_code!=200:
                    raise upstream_error(response,lookup_gate,'lookup')
                try:
                    data=response.json()
                except ValueError:
                    raise AppleRequestError('Apple lookup returned an invalid response. Try again later.')
                if not isinstance(data,dict) or not isinstance(data.get('results'),list):
                    message=str(data.get('errorMessage','')) if isinstance(data,dict) else ''
                    if re.search(r'too many|rate.?limit',message,re.I):
                        lookup_gate.block(60)
                        raise AppleRequestError('Apple lookup reported too many requests. Wait 60 seconds.',429,60,'rate_limited',200)
                    raise AppleRequestError('Apple lookup returned an invalid response. Try again later.')
            finally:
                response.close()
        except requests.RequestException:
            lookup_gate.block(10,'unavailable')
            raise AppleRequestError('Apple lookup could not connect. Try again in 10 seconds.',502,10)
        lookup_cache[url]=(now+600,data)
        lookup_cache.move_to_end(url)
        while len(lookup_cache)>128:
            lookup_cache.popitem(last=False)
        return data
    finally:
        lookup_lock.release()


class PreviewMemoryCache:
    """Ten RAM previews; page/pair invalidation also rejects late downloads."""
    def __init__(self, limit=10, ttl=600, max_bytes=4*1024*1024, clock=time.monotonic):
        self.limit, self.ttl, self.max_bytes, self.clock = limit, ttl, max_bytes, clock
        self.entries=OrderedDict()
        self.reservations=OrderedDict()
        self.closed_pages=OrderedDict()
        self.lock=Lock()

    def _expire(self):
        now=self.clock()
        for key,entry in list(self.entries.items()):
            if entry[0]<=now:del self.entries[key]
        for key,entry in list(self.reservations.items()):
            if entry[1]<=now:del self.reservations[key]
        for page,expires in list(self.closed_pages.items()):
            if expires<=now:del self.closed_pages[page]

    def reserve(self, key):
        with self.lock:
            self._expire()
            if key not in self.reservations:self.reservations[key]=(object(),self.clock()+self.ttl)
            self.reservations.move_to_end(key)
            while len(self.reservations)>128:self.reservations.popitem(last=False)
            return self.reservations[key][0]

    def discard(self, page, song_ids=None, close=False):
        with self.lock:
            self._expire();removed=0
            for mapping in (self.entries,self.reservations):
                for key in list(mapping):
                    if isinstance(key,tuple) and key[0]==page and (song_ids is None or key[1] in song_ids):
                        del mapping[key]
                        if mapping is self.entries:removed+=1
            if close:
                self.closed_pages[page]=self.clock()+self.ttl
                self.closed_pages.move_to_end(page)
                while len(self.closed_pages)>128:self.closed_pages.popitem(last=False)
            return removed

    def get(self, key):
        with self.lock:
            self._expire()
            entry=self.entries.get(key)
            if entry is None:return None
            self.entries.move_to_end(key)
            return entry[1],entry[2]

    def put(self, key, body, content_type, reservation=None):
        if not body or len(body)>self.max_bytes:return False
        with self.lock:
            self._expire()
            if isinstance(key,tuple) and key[0] in self.closed_pages:return False
            if reservation is not None and self.reservations.get(key,(None,))[0] is not reservation:return False
            self.entries[key]=(self.clock()+self.ttl,body,content_type)
            self.entries.move_to_end(key)
            while len(self.entries)>self.limit:self.entries.popitem(last=False)
        return True


preview_cache=PreviewMemoryCache()


@app.route('/api/previews/cache',methods=['POST'])
def api_preview_cache():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return AppleRequestError('Invalid preview cache request.',400).response()
    page=data.get('page');action=data.get('action')
    if not isinstance(page,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',page):
        return AppleRequestError('Invalid preview page.',400).response()
    if action=='clear':removed=preview_cache.discard(page,close=True)
    elif action=='forget':
        ids=data.get('song_ids')
        if not isinstance(ids,list) or len(ids)>10 or any(type(i) is not int or i<=0 for i in ids):
            return AppleRequestError('Invalid preview songs.',400).response()
        removed=preview_cache.discard(page,set(ids))
    else:return AppleRequestError('Invalid preview cache action.',400).response()
    response=jsonify(cleared=removed);response.headers['Cache-Control']='no-store'
    return response


def complete_preview(status, headers, length):
    expected=headers.get('Content-Length')
    if expected is not None:
        try:
            if int(expected)!=length:return False
        except (ValueError,TypeError):return False
    if status==200:return True
    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',headers.get('Content-Range',''))
    return bool(status==206 and match and int(match[1])==0 and
                int(match[2])+1==int(match[3])==length)


def cached_preview_response(body, content_type, byte_range):
    length=len(body);status=200;start=0;end=length-1
    if byte_range:
        first,last=byte_range[6:].split('-',1)
        if first:
            start=int(first);end=min(length-1,int(last)) if last else length-1
        else:
            amount=int(last);start=max(0,length-amount)
            if amount<=0:start=length
        if start>=length or end<start:
            response=AppleRequestError('Unsupported preview byte range.',416).response()
            response.headers['Content-Range']=f'bytes */{length}'
            return response
        status=206
    response=Response(body[start:end+1],status=status,content_type=content_type)
    response.headers['Content-Length']=end-start+1
    response.headers['Accept-Ranges']='bytes'
    response.headers['Cache-Control']='no-store'
    response.headers['X-Preview-Cache']='hit'
    if status==206:response.headers['Content-Range']=f'bytes {start}-{end}/{length}'
    return response


def apple_preview_url(url):
    try:
        parsed=urlsplit(url)
        host=(parsed.hostname or '').lower()
        return parsed.scheme in ('http','https') and not parsed.username and not parsed.password and parsed.port in (None,80,443) and (host.endswith('.itunes.apple.com') or host.endswith('.mzstatic.com'))
    except ValueError:
        return False


def remember(song_id, state, message='', retry_after=0, upstream_status=None):
    with status_lock:
        preview_status[song_id]=dict(state=state,message=message,retry_after=retry_after,
                                     upstream_status=upstream_status,retry_until=time.monotonic()+retry_after,expires=time.monotonic()+300)
        preview_status.move_to_end(song_id)
        while len(preview_status)>128:
            preview_status.popitem(last=False)


@app.route('/api/previews/<int:song_id>/status')
def api_preview_status(song_id):
    wait=preview_gate.wait()
    with status_lock:
        info=preview_status.get(song_id)
        if not info or info['expires']<=time.monotonic():
            info=dict(state='unknown',message='Preview could not play. Check the connection or refresh its URL in Dev.')
        else:
            info={k:v for k,v in info.items() if k not in ('expires','retry_until')}
            info['retry_after']=max(0,math.ceil(preview_status[song_id]['retry_until']-time.monotonic()))
    if wait:
        info.update(state=preview_gate.reason,retry_after=wait)
        if info.get('state')=='rate_limited':
            info['message']=f'Apple preview access paused after HTTP 429. Try again in {wait} seconds.'
    response=jsonify(info)
    response.headers['Cache-Control']='no-store'
    return response


@app.route('/api/previews/<int:song_id>',methods=['GET'])
def api_preview(song_id):
    conn=get_db_connection()
    try:
        row=conn.execute('SELECT audio_url FROM songs WHERE id=?',(song_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row['audio_url']:
        return AppleRequestError('No preview URL for this song.',404,0,'missing').response()
    url=row['audio_url']
    if not apple_preview_url(url):
        return AppleRequestError('This preview is not an Apple media URL.',400).response()
    page=request.args.get('page','')
    if page and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',page):
        return AppleRequestError('Invalid preview page.',400).response()
    cache_key=(page,song_id,url) if page else url
    byte_range=request.headers.get('Range')
    if byte_range and not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)',byte_range):
        return AppleRequestError('Unsupported preview byte range.',416).response()
    cached=preview_cache.get(cache_key)
    if cached is not None:
        remember(song_id,'cached')
        return cached_preview_response(*cached,byte_range)
    reservation=preview_cache.reserve(cache_key)
    play=request.args.get('play','')
    key=(song_id,play) if re.fullmatch(r'[A-Za-z0-9_-]{1,64}',play) else None
    upstream=None
    try:
        preview_gate.admit(key)
        headers={'Accept':'audio/*,application/octet-stream;q=0.9,*/*;q=0.5','Accept-Encoding':'identity'}
        if byte_range:
            if not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)',byte_range):
                raise AppleRequestError('Unsupported preview byte range.',416)
            headers['Range']=byte_range
        for _ in range(4):
            upstream=requests.get(url,headers=headers,stream=True,timeout=(3,10),allow_redirects=False)
            if upstream.status_code in (301,302,303,307,308):
                redirect=urljoin(url,upstream.headers.get('Location',''))
                upstream.close();upstream=None
                if redirect==url or not apple_preview_url(redirect):
                    raise AppleRequestError('Apple preview redirected to an unsupported address.')
                url=redirect
                continue
            break
        if upstream is None or upstream.status_code not in (200,206):
            if upstream is not None:
                raise upstream_error(upstream,preview_gate,'preview')
            raise AppleRequestError('Apple preview redirected too many times.')
        mime=upstream.headers.get('Content-Type','').split(';')[0].strip().lower()
        if not (mime.startswith('audio/') or mime in ('application/octet-stream','video/mp4')):
            raise AppleRequestError('Apple returned a non-audio response instead of a preview.')
        remember(song_id,'streaming',upstream_status=upstream.status_code)
        stream=upstream
        def chunks():
            parts=[];length=0;cacheable=True;finished=False
            try:
                for chunk in stream.iter_content(chunk_size=16384):
                    if not chunk:continue
                    length+=len(chunk)
                    if cacheable:
                        if length<=preview_cache.max_bytes:parts.append(chunk)
                        else:cacheable=False;parts.clear()
                    yield chunk
                finished=True
            except requests.RequestException:
                remember(song_id,'unavailable','Preview stream was interrupted. Check the connection, then retry.')
            finally:
                stream.close()
                if finished and cacheable and complete_preview(stream.status_code,stream.headers,length):
                    preview_cache.put(cache_key,b''.join(parts),stream.headers.get('Content-Type','application/octet-stream'),reservation)
        response=Response(stream_with_context(chunks()),status=stream.status_code)
        for name in ('Content-Type','Content-Length','Content-Range','Accept-Ranges'):
            if name in stream.headers:
                response.headers[name]=stream.headers[name]
        response.headers['Cache-Control']='no-store'
        response.headers['X-Preview-Cache']='miss'
        response.call_on_close(stream.close)
        return response
    except requests.RequestException:
        error=AppleRequestError('Apple preview could not connect. Try again in 10 seconds.',502,10)
        preview_gate.block(10,'unavailable')
    except AppleRequestError as exc:
        error=exc
    if upstream is not None:
        upstream.close()
    remember(song_id,error.state,str(error),error.retry_after,error.upstream_status)
    return error.response()
