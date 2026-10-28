"""Entity analysis uses current production projections and remains read-only."""
import unittest
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
