"""Entity analysis uses current production projections and remains read-only."""
import unittest
import shutil
import subprocess
import os
from threading import Thread
from werkzeug.serving import make_server
from unittest.mock import patch
import test_preferences as fixture
from songranker import pages, services
from songranker.catalog import collection
from songranker.reports.analysis import build_analysis
from songranker.storage.database_io import capture


class AnalysisTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def test_entity_pages_charts_and_guide_render_without_writes(self):
        c=self.connect();before=capture(c);c.close()
        client=services.app.test_client()
        for kind in ('song','artist','album','tag'):
            for chart in ('bars','scatter','activity','elo'):
                result=client.get('/analysis',query_string=dict(kind=kind,chart=chart))
                self.assertEqual(result.status_code,200,result.text[:300])
                self.assertIn('Library benchmarks',result.text)
        self.assertEqual(client.get('/analysis/guide').status_code,200)
        for args in ({'kind':'bad'},{'chart':'bad'},{'metric':'bad'},{'id':'bad'},{'minimum':'bad'}):
            self.assertEqual(client.get('/analysis',query_string=args).status_code,400)
        c=self.connect();self.assertEqual(capture(c),before);c.close()

    def test_missing_evidence_is_unavailable_and_comparisons_keep_links(self):
        with services.app.test_request_context('/analysis'):
            data=collection(include_overall_sources=True,include_analysis_sources=True)
            sid=data['songs'][0]['id']
            result=build_analysis(data,dict(kind='song',id=str(sid),metric='win_rate'))
            self.assertIsNone(result['primary']['win_rate']['value'])
            self.assertEqual(result['bars'],[])
            self.assertEqual(result['coverage'][0]['tested'],0)
            self.assertEqual(result['event_count'],0)

    def test_internal_votes_pool_track_opportunities_but_count_one_event(self):
        from songranker.modes.preferences import record_preference
        self.conn.execute('BEGIN IMMEDIATE')
        record_preference(self.conn,1,2,'standard',{sid:dict(id=sid,title=f'Song {sid}') for sid in (1,2)})
        self.conn.commit()
        with services.app.test_request_context('/analysis'):
            data=collection(include_overall_sources=True,include_analysis_sources=True)
            album=build_analysis(data,dict(kind='album',id='1'))
            self.assertEqual(album['primary']['win_rate']['value'],50)
            self.assertEqual(album['event_count'],1)
            self.assertEqual(album['opponents'],[])
            pair=build_analysis(data,dict(kind='song',id='1',compare='2',metric='win_rate'))
            self.assertEqual(pair['primary']['win_rate']['value'],100)
            self.assertEqual(pair['comparison']['win_rate']['value'],0)
            self.assertEqual(len(pair['bars']),2)
            scatter=build_analysis(data,dict(kind='song',id='1',compare='2',chart='scatter',metric='elo',y='win_rate'))
            self.assertEqual(scatter['chart'],'scatter')
            invalid=build_analysis(data,dict(kind='song',id='1',chart='scatter',metric='elo',y='elo'))
            self.assertEqual(invalid['chart'],'bars')
            self.assertTrue(invalid['chart_notice'])
            self.assertFalse(invalid['chart_config']['charts']['scatter'])

    @unittest.skipUnless(shutil.which('google-chrome') or shutil.which('chromium'), 'Chromium is unavailable')
    def test_analysis_browser_layout_and_controls(self):
        from songranker.modes.preferences import record_preference
        self.conn.execute('BEGIN IMMEDIATE')
        record_preference(self.conn,1,2,'standard',{sid:dict(id=sid,title=f'Song {sid}') for sid in (1,2)})
        self.conn.commit()
        server=make_server('127.0.0.1',0,services.app,threaded=True)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env=dict(os.environ,ANALYSIS_URL=f'http://127.0.0.1:{server.server_port}',ANALYSIS_CHROME=shutil.which('google-chrome') or shutil.which('chromium'))
            subprocess.run(['node','tests/browser_analysis.cjs'],env=env,check=True,timeout=120)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
