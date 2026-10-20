"""Spotlight dashboard: flexible scoring, bounded lists and read-only reports."""
from pathlib import Path
from unittest.mock import patch
import re
import sqlite3
import tempfile
import unittest

from test_mode_updates_v51 import fixture
from songranker import services
from songranker.modes import judgement_pages
from songranker.modes.judgements import get_offer, save_answer
from songranker.reports.judgement_page_data import build_judgement_page
from songranker.storage.database_io import capture


class SpotlightStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'stats.db'
        fixture(self.path)
        self.c=sqlite3.connect(self.path);self.c.row_factory=sqlite3.Row
        self.c.execute('PRAGMA foreign_keys=ON')
        self.addCleanup(self.c.close)
        p=patch.object(services,'DB_NAME',str(self.path));p.start();self.addCleanup(p.stop)
        self.client=services.app.test_client()

    def answer(self,positions,ids=(1,2,3,4),legacy=False):
        with patch('songranker.modes.judgements.draw',return_value=list(ids)):
            offer=get_offer(self.c,'stats','spotlight')
        if legacy:
            self.c.execute('UPDATE judgement_rounds SET rules_version=1 WHERE id=?',(offer['id'],))
            self.c.commit()
        return save_answer(self.c,'stats','spotlight',
            dict(token=offer['token'],rules_version=1 if legacy else 2,
                 **({'allocations':positions} if legacy else {'positions':positions})))

    def test_empty_values_remain_unknown_and_page_renders(self):
        data=build_judgement_page(self.c,'spotlight')
        score=data['details']['scoring']
        self.assertIsNone(score['mean_round']);self.assertIsNone(score['mean_track'])
        self.assertIsNone(score['mean_connection']);self.assertIsNone(score['highest'])
        response=self.client.get('/shared_spotlight_stats')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Connection &amp; points',response.data)
        self.assertIn(b'mode-stats-comparisons',response.data)

    def test_scoring_averages_separate_legacy_connection_and_keep_removed_facts(self):
        self.answer([0]*4)
        self.answer([100]*4)
        self.answer([3]*4,legacy=True)
        self.c.execute('DELETE FROM songs WHERE id=1');self.c.commit()
        before=capture(self.c)
        data=build_judgement_page(self.c,'spotlight')
        score=data['details']['scoring']
        self.assertEqual(score['points'],36)
        self.assertEqual(score['mean_round'],12)
        self.assertEqual(score['mean_track'],3)
        self.assertEqual(score['connecting_rounds'],2)
        self.assertEqual(score['legacy_rounds'],1)
        self.assertEqual(score['connection_samples'],8)
        self.assertEqual(score['mean_connection'],50)
        self.assertEqual(score['not_connecting'],4)
        self.assertEqual(score['really_connecting'],4)
        self.assertEqual(score['zero_points'],4)
        self.assertEqual(score['track_samples'],12)
        self.assertEqual(score['lowest_round'],0);self.assertEqual(score['highest_round'],24)
        self.assertEqual(len(data['details']['songs']),3)
        self.assertEqual(sum(r['count'] for r in data['details']['distribution']),12)
        self.assertEqual(capture(self.c),before)
        response=self.client.get('/shared_spotlight_stats')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Legacy shares',response.data)

    def test_every_continuing_record_list_stops_at_five(self):
        for _ in range(3):
            for start in (1,5,9):
                self.answer([80,60,40,20],tuple(range(start,start+4)))
        before=capture(self.c)
        data=build_judgement_page(self.c,'spotlight')
        self.assertEqual(len(data['details']['leaders']),5)
        for record in data['details']['records']:
            self.assertEqual(len(record['rows']),5)
        response=self.client.get('/shared_spotlight_stats')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        records=re.findall(r'<ol[^>]*data-spotlight-record="([^"]+)"[^>]*>(.*?)</ol>',html,re.S)
        self.assertEqual(len(records),4)
        for metric,body in records:
            self.assertEqual(body.count('<li class="mode-stats-row">'),5,metric)
        self.assertNotIn('More track records',html)
        self.assertNotIn('Up to 50',html)
        self.assertIn('Round history',html)
        self.assertEqual(capture(self.c),before)
        # Category counts pool actual appearances rather than four-song round counts.
        artist=data['details']['categories'][0]['most'][0]
        self.assertEqual(artist['offers'],21)
        self.assertEqual(artist['tracks'],7)

    def test_points_and_connection_rankings_wait_for_repeated_evidence(self):
        self.answer([80,60,40,20])
        records=build_judgement_page(self.c,'spotlight')['details']['records']
        self.assertEqual(len(records[0]['rows']),4)
        self.assertEqual(records[1]['rows'],[])
        self.assertEqual(records[3]['rows'],[])


if __name__=='__main__':unittest.main()
