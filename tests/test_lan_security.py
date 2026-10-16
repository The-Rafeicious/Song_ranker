"""Direct-LAN security boundaries; isolated Flask clients and temporary keys only."""
import os
from pathlib import Path
import tempfile
import unittest

from flask import Flask, jsonify, render_template_string, request, session
from lan_security import configure_security, load_secret, allowed_addresses, DEFAULT_ALLOWED_IPS


class LanSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = Flask('lan_security_test')
        self.app.testing = True
        self.key = 'isolated-test-key-with-at-least-32-characters'
        configure_security(self.app, self.root, {'SONG_RANKER_SECRET':self.key,
                                                 'SONG_RANKER_ALLOWED_IPS':'192.168.10.22'})
        self.calls = []
        @self.app.route('/')
        def home():return 'home'
        @self.app.route('/api/change', methods=['POST','DELETE'])
        def change():self.calls.append('change');return jsonify(ok=True)
        @self.app.route('/api/generate_bracket', endpoint='api_generate_bracket')
        def bracket():self.calls.append('bracket');return jsonify(ok=True)
        @self.app.route('/api/trivia/round', endpoint='api_trivia_round')
        def trivia():self.calls.append('trivia');return jsonify(ok=True)
        @self.app.route('/api/previews/1')
        def preview():return 'media'
        @self.app.route('/dev/login', methods=['GET','POST'], endpoint='dev_login')
        def login():
            if request.method=='POST':session['is_admin']=True;return 'unlocked'
            return render_template_string('<form><input name="csrf_token" value="{{ csrf_token() }}"></form>')
        @self.app.route('/api/dev/private')
        def private():return jsonify(admin=bool(session.get('is_admin')))
        self.client = self.app.test_client()

    def get(self,path='/',peer='127.0.0.1',**kwargs):
        return self.client.get(path,environ_overrides={'REMOTE_ADDR':peer},**kwargs)

    def test_local_and_explicit_phone_are_allowed(self):
        for peer in ('127.0.0.1','::1','::ffff:127.0.0.1','192.168.10.22','::ffff:192.168.10.22'):
            with self.subTest(peer=peer):self.assertEqual(self.get(peer=peer).status_code,200)

    def test_other_devices_and_missing_peers_are_rejected(self):
        for peer in ('192.168.10.23','8.8.8.8','not-an-ip',None):
            with self.subTest(peer=peer):self.assertEqual(self.get(peer=peer).status_code,403)

    def test_forwarded_headers_cannot_spoof_allowed_peer(self):
        headers={'X-Forwarded-For':'192.168.10.22','Forwarded':'for=127.0.0.1','X-Real-IP':'127.0.0.1'}
        self.assertEqual(self.get(peer='192.168.10.23',headers=headers).status_code,403)

    def test_private_numeric_and_local_hosts_are_allowed(self):
        for host in ('localhost','127.0.0.1:5000','[::1]:5000','192.168.10.5:5000','10.0.0.5:5000'):
            with self.subTest(host=host):self.assertEqual(self.get(headers={'Host':host}).status_code,200)

    def test_untrusted_dns_public_hosts_and_bad_ports_are_rejected(self):
        for host in ('untrusted.example','127.0.0.1.untrusted.example','8.8.8.8:5000','localhost:99999','0.0.0.0:5000'):
            with self.subTest(host=host):self.assertEqual(self.get(headers={'Host':host}).status_code,400)

    def test_remote_admin_is_blocked_even_with_signed_admin_cookie(self):
        with self.client.session_transaction() as s:s['is_admin']=True
        for path in ('/dev/login','/dev/dashboard','/api/dev/private','/api/dev/metadata'):
            with self.subTest(path=path):self.assertEqual(self.get(path,peer='192.168.10.22').status_code,403)
        self.assertEqual(self.get('/api/dev/private').json,{'admin':True})

    def test_cross_origin_and_different_port_actions_do_not_reach_routes(self):
        for source in ('https://untrusted.example','null','http://localhost:5001','https://localhost'):
            with self.subTest(source=source):self.assertEqual(self.client.post('/api/change',json={},headers={'Origin':source}).status_code,403)
        self.assertEqual(self.calls,[])

    def test_referer_and_fetch_metadata_are_checked_when_present(self):
        for headers in ({'Referer':'https://untrusted.example/page'},{'Sec-Fetch-Site':'cross-site'},
                        {'Sec-Fetch-Site':'same-site'},{'Sec-Fetch-Site':'CROSS-SITE'}):
            with self.subTest(headers=headers):self.assertEqual(self.client.post('/api/change',json={},headers=headers).status_code,403)
        self.assertEqual(self.calls,[])

    def test_plain_forms_text_and_headerless_deletes_are_blocked(self):
        self.assertEqual(self.client.post('/api/change',data={}).status_code,403)
        self.assertEqual(self.client.post('/api/change',data='{}',content_type='text/plain').status_code,403)
        self.assertEqual(self.client.delete('/api/change').status_code,403)
        self.assertEqual(self.calls,[])

    def test_json_actions_without_optional_browser_headers_still_work(self):
        self.assertEqual(self.client.post('/api/change',json={}).status_code,200)
        self.assertEqual(self.client.delete('/api/change',content_type='application/json').status_code,200)
        self.assertEqual(len(self.calls),2)

    def test_same_origin_phone_json_and_same_origin_referer_work(self):
        r=self.client.post('/api/change',json={},base_url='http://192.168.10.5:5000',
                           environ_overrides={'REMOTE_ADDR':'192.168.10.22'},headers={'Origin':'http://192.168.10.5:5000'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post('/api/change',json={},headers={'Referer':'http://localhost/page'}).status_code,200)

    def test_state_changing_gets_require_json_header_and_head_never_writes(self):
        for path in ('/api/generate_bracket','/api/trivia/round'):
            self.assertEqual(self.get(path).status_code,403)
            self.assertEqual(self.client.head(path,headers={'Content-Type':'application/json'}).status_code,405)
            self.assertEqual(self.get(path,headers={'Content-Type':'application/json'}).status_code,200)
        self.assertEqual(self.calls,['bracket','trivia'])

    def test_ordinary_audio_requests_and_options_do_not_need_json(self):
        self.assertEqual(self.get('/api/previews/1',peer='192.168.10.22',headers={'Range':'bytes=0-3'}).status_code,200)
        self.assertEqual(self.client.options('/api/change').status_code,200)
        self.assertNotIn('Access-Control-Allow-Origin',self.client.options('/api/change').headers)

    def test_login_requires_session_token_not_just_an_allowed_address(self):
        self.assertEqual(self.client.post('/dev/login',data={'csrf_token':'wrong'}).status_code,403)
        self.get('/dev/login')
        with self.client.session_transaction() as s:token=s['_login_csrf']
        self.assertEqual(self.client.post('/dev/login',data={'csrf_token':token}).status_code,200)
        with self.client.session_transaction() as s:self.assertTrue(s['is_admin'])

    def test_login_rejects_cross_origin_even_with_token_and_handles_unicode(self):
        self.get('/dev/login')
        with self.client.session_transaction() as s:token=s['_login_csrf']
        self.assertEqual(self.client.post('/dev/login',data={'csrf_token':token},headers={'Origin':'https://untrusted.example'}).status_code,403)
        self.assertEqual(self.client.post('/dev/login',data={'csrf_token':'é'}).status_code,403)

    def test_cookie_and_response_policies_preserve_http_phone_sessions(self):
        r=self.get('/dev/login');cookie=r.headers.get('Set-Cookie','')
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Lax',cookie);self.assertNotIn('Secure',cookie)
        self.assertEqual(r.headers['X-Frame-Options'],'DENY')
        self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(r.headers['Referrer-Policy'],'same-origin')
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertFalse(self.app.debug)

    def test_default_matches_uploaded_phone_and_bad_allowlists_fail_closed(self):
        self.assertEqual(len(allowed_addresses(DEFAULT_ALLOWED_IPS)),1)
        for value in ('*','192.168.10.0/24','0.0.0.0','invalid'):
            with self.subTest(value=value):self.assertRaises(RuntimeError,allowed_addresses,value)
        self.assertEqual(allowed_addresses(''),frozenset())

    def test_secret_is_random_persistent_private_and_environment_override_is_validated(self):
        first=load_secret(self.root,{})
        self.assertEqual(first,load_secret(self.root,{}))
        self.assertEqual(len(first),64)
        if os.name!='nt':self.assertEqual((self.root/'instance/session_secret').stat().st_mode&0o777,0o600)
        other=self.root/'other';other.mkdir()
        self.assertNotEqual(first,load_secret(other,{}))
        self.assertEqual(load_secret(other,{'SONG_RANKER_SECRET':self.key}),self.key)
        self.assertRaises(RuntimeError,load_secret,self.root,{'SONG_RANKER_SECRET':'short'})

    def test_cookies_signed_by_another_install_cannot_grant_admin(self):
        other=Flask('other_install');other.secret_key='unrelated-old-shared-key'
        serializer=other.session_interface.get_signing_serializer(other)
        self.client.set_cookie(self.app.config['SESSION_COOKIE_NAME'],serializer.dumps({'is_admin':True}))
        self.assertEqual(self.get('/api/dev/private').json,{'admin':False})


if __name__=='__main__':unittest.main()
