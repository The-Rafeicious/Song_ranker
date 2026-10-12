import sqlite3
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import requests
import test_app as fixture
import apple_access as apple


class AppleChecks(unittest.TestCase):
    setUp=fixture.AppChecks.setUp
    db=fixture.AppChecks.db
    admin=fixture.AppChecks.admin

    def response(self,status=200,headers=None,data=None,chunks=None):
        response=Mock(status_code=status,headers=headers or {})
        response.json.return_value=data or {'results':[]}
        response.iter_content.return_value=iter(chunks or [b'preview'])
        return response

    def source(self):
        with self.db() as conn:
            sid=conn.execute('SELECT MIN(id) FROM songs').fetchone()[0]
            conn.execute("UPDATE songs SET audio_url='https://audio-ssl.itunes.apple.com/itunes-assets/test.m4a' WHERE id=?",(sid,))
        return sid

    def test_gate_spacing_window_and_byte_range_reservations(self):
        clock=[0];gate=apple.RequestGate(2,5,lambda:clock[0])
        gate.admit('clip-a');gate.admit('clip-a')
        self.assertEqual(len(gate.starts),1)
        with self.assertRaises(apple.AppleRequestError) as error:gate.admit('clip-b')
        self.assertEqual(error.exception.retry_after,5)
        clock[0]=5;gate.admit('clip-b')
        clock[0]=10
        with self.assertRaises(apple.AppleRequestError) as error:gate.admit('clip-c')
        self.assertEqual(error.exception.retry_after,50)
        gate.block(90)
        with self.assertRaises(apple.AppleRequestError):gate.admit('clip-a')
        clock[0]=101;gate.admit('clip-c')
        self.assertEqual(len(gate.starts),1)

    def test_retry_header_numeric_date_and_unknown(self):
        self.assertEqual(apple.retry_seconds('120'),120)
        self.assertEqual(apple.retry_seconds('bad'),60)
        future=format_datetime(datetime.now(timezone.utc)+timedelta(seconds=180))
        self.assertTrue(178<=apple.retry_seconds(future)<=180)

    def test_lookup_cache_and_local_spacing_avoid_upstream_calls(self):
        url='https://itunes.apple.com/search?term=test'
        with patch.object(apple.requests,'get',return_value=self.response(data={'results':[{'trackName':'cached'}]})) as get:
            self.assertEqual(apple.apple_lookup(url),apple.apple_lookup(url))
            self.assertEqual(get.call_count,1)
            with self.assertRaises(apple.AppleRequestError) as error:apple.apple_lookup(url+'&limit=2')
            self.assertEqual(error.exception.state,'throttled')
            self.assertEqual(get.call_count,1)

    def test_lookup_429_cooldown_and_busy_no_retry_storm(self):
        self.admin()
        with patch.object(apple.requests,'get',return_value=self.response(429,{'Retry-After':'123'})) as get:
            first=self.c.get('/api/dev/search_apple?q=limit')
            self.assertEqual(first.status_code,429)
            self.assertEqual(first.headers['Retry-After'],'123')
            self.assertEqual(first.json['upstream_status'],429)
            self.assertEqual(self.c.get('/api/dev/search_apple?q=another').status_code,429)
            self.assertEqual(get.call_count,1)
        apple.lookup_lock.acquire()
        try:
            with self.assertRaises(apple.AppleRequestError) as error:apple.apple_lookup('https://itunes.apple.com/lookup?id=1')
            self.assertEqual(error.exception.state,'throttled')
        finally:apple.lookup_lock.release()

    def test_lookup_html_and_transport_failures_are_visible(self):
        response=self.response();response.json.side_effect=ValueError('HTML')
        with patch.object(apple.requests,'get',return_value=response):
            with self.assertRaises(apple.AppleRequestError):apple.apple_lookup('https://itunes.apple.com/search?term=html')
        apple.lookup_gate.starts.clear()
        with patch.object(apple.requests,'get',side_effect=requests.Timeout):
            with self.assertRaises(apple.AppleRequestError) as error:apple.apple_lookup('https://itunes.apple.com/search?term=timeout')
            self.assertEqual(error.exception.retry_after,10)

    def test_preview_stream_ranges_and_connection_close(self):
        sid=self.source();headers={'Content-Type':'audio/mp4','Content-Length':'7','Content-Range':'bytes 0-6/7','Accept-Ranges':'bytes'}
        upstream=self.response(206,headers,chunks=[b'preview'])
        with patch.object(apple.requests,'get',return_value=upstream) as get:
            response=self.c.get(f'/api/previews/{sid}?play=one',headers={'Range':'bytes=0-6'})
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,b'preview')
            self.assertEqual(response.headers['Content-Range'],'bytes 0-6/7')
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(get.call_args.kwargs['headers']['Range'],'bytes=0-6')
            response.close();self.assertTrue(upstream.close.called)
            # A second range of the same clip must not be rate-limited.
            upstream.iter_content.return_value=iter([b'preview'])
            self.assertEqual(self.c.get(f'/api/previews/{sid}?play=one').status_code,206)
            self.assertEqual(len(apple.preview_gate.starts),1)
        self.assertEqual(self.c.get(f'/api/previews/{sid}/status').json['state'],'streaming')

    def test_preview_429_stops_all_new_upstream_requests(self):
        sid=self.source()
        with patch.object(apple.requests,'get',return_value=self.response(429,{'Retry-After':'180'})) as get:
            response=self.c.get(f'/api/previews/{sid}?play=one')
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.json['upstream_status'],429)
            self.assertEqual(self.c.get(f'/api/previews/{sid}?play=two').status_code,429)
            self.assertEqual(get.call_count,1)
        status=self.c.get(f'/api/previews/{sid}/status').json
        self.assertEqual(status['state'],'rate_limited')
        self.assertGreaterEqual(status['retry_after'],179)

    def test_refusal_missing_and_non_audio_are_not_silent(self):
        sid=self.source()
        for code,state in [(403,'refused'),(404,'missing'),(200,'unavailable')]:
            apple.preview_gate.cooldown=0;apple.preview_gate.starts.clear();apple.preview_gate.sessions.clear()
            with patch.object(apple.requests,'get',return_value=self.response(code,{'Content-Type':'text/html'})):
                response=self.c.get(f'/api/previews/{sid}?play=test')
                self.assertEqual(response.json['state'],state)
                self.assertNotEqual(response.status_code,200)

    def test_relay_cannot_fetch_arbitrary_saved_or_redirected_urls(self):
        sid=self.source()
        with patch.object(apple.requests,'get',return_value=self.response(302,{'Location':'http://127.0.0.1/private'})) as get:
            self.assertEqual(self.c.get(f'/api/previews/{sid}?play=redirect').status_code,502)
            self.assertEqual(get.call_count,1)
        with self.db() as conn:conn.execute("UPDATE songs SET audio_url='http://127.0.0.1/private' WHERE id=?",(sid,))
        with patch.object(apple.requests,'get') as get:
            self.assertEqual(self.c.get(f'/api/previews/{sid}').status_code,400)
            get.assert_not_called()
        self.assertFalse(apple.apple_preview_url('https://audio-ssl.itunes.apple.com.evil.test/a'))
        self.assertFalse(apple.apple_preview_url('https://user:pass@audio-ssl.itunes.apple.com/a'))

if __name__=='__main__':unittest.main()
