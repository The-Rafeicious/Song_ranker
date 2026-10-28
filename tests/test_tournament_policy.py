"""Tournament scope policy and backed-up removal of historical selective Elo."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from songranker import services, pages
from songranker.modes import tournament
from songranker.modes.preferences import record_preference
from songranker.storage.database import initialize_database, retire_selective_tournament_elo
from songranker.storage.database_io import capture, readonly


class TournamentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db';initialize_database(self.path)
        self.conn=sqlite3.connect(self.path);self.conn.row_factory=sqlite3.Row;self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO albums(id,title) VALUES(1,'Album')")
        self.conn.execute("INSERT INTO artists(id,name) VALUES(1,'Artist')")
        self.conn.execute("INSERT INTO genres(id,name) VALUES(1,'Tag')")
        for sid in range(1,9):
            self.conn.execute("INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,1,?)",(sid,f'Track {sid}',sid))
            self.conn.execute('INSERT INTO song_artists VALUES(?,1)',(sid,));self.conn.execute('INSERT INTO song_genres VALUES(?,1)',(sid,))
        self.conn.commit()
        self.mock=patch.object(services,'DB_NAME',str(self.path));self.mock.start();self.addCleanup(self.mock.stop)
        self.client=services.app.test_client()

    def generate(self,scope):
        result=self.client.get('/api/generate_bracket',query_string=dict(size=8,scope=scope,scope_id=1),content_type='application/json')
        self.assertEqual(result.status_code,200,result.json)
        return result.json

    def test_scopes_have_correct_exchange_and_points_only_retries(self):
        for scope,weight in [('artist',0),('album',0),('tag',.5),('global',1)]:
            data=self.generate(scope);self.assertEqual(data['elo_weight'],weight)
            m=data['matches'][0];payload=dict(tournament_id=data['tournament_id'],match_id=m['id'],winner_id=m['song1_id'],loser_id=m['song2_id'])
            before=self.conn.execute('SELECT COUNT(*) FROM preference_events').fetchone()[0]
            result=self.client.post('/api/tournament_vote',json=payload)
            self.assertEqual(result.status_code,200,result.json);self.assertGreater(result.json['points_awarded'],0)
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM preference_events').fetchone()[0]-before,int(weight>0))
            self.assertEqual(result.json['elo_result'] is not None,weight>0)
            if weight:self.assertEqual(self.conn.execute('SELECT rating_weight FROM preference_events WHERE id=?',(result.json['preference_event_id'],)).fetchone()[0],weight)
            duplicate=self.client.post('/api/tournament_vote',json=payload)
            self.assertEqual(duplicate.status_code,200,duplicate.json)
            self.assertEqual(duplicate.json,result.json)

    def old_artist_vote(self):
        data=self.generate('artist');m=data['matches'][0]
        self.conn.execute('BEGIN IMMEDIATE')
        self.conn.execute('UPDATE tournaments SET elo_policy_version=1,elo_weight=.5 WHERE id=?',(data['tournament_id'],))
        event=record_preference(self.conn,m['song1_id'],m['song2_id'],'standard',{sid:dict(id=sid,title=f'Track {sid}') for sid in (m['song1_id'],m['song2_id'])},tournament_id=data['tournament_id'],tournament_match_id=m['id'],weight=.5)
        self.conn.execute("UPDATE tournament_matches SET status='completed',winner_id=song1_id,loser_id=song2_id,points_awarded=1 WHERE id=?",(m['id'],));self.conn.commit()
        return event

    def test_historical_artist_elo_is_archived_voided_and_replayed_once(self):
        event=self.old_artist_vote();before=capture(self.conn)
        report=retire_selective_tournament_elo(self.path)
        self.assertEqual(report['events'],1)
        with readonly(report['backup']) as archived:self.assertEqual(capture(archived),before)
        after=capture(self.conn)
        self.assertEqual(before['tables']['preference_events'],after['tables']['preference_events'])
        self.assertEqual(before['tables']['tournament_matches'],after['tables']['tournament_matches'])
        self.assertTrue(all(r[0]==1200 for r in self.conn.execute('SELECT elo_score FROM songs')))
        self.assertEqual(self.conn.execute('SELECT active FROM preference_effective WHERE id=?',(event,)).fetchone()[0],0)
        self.assertTrue(all(r[0]==0 for r in self.conn.execute('SELECT matches FROM preference_mode_ratings')))
        self.assertIsNone(retire_selective_tournament_elo(self.path));self.assertEqual(capture(self.conn),after)

    def test_failure_during_scope_replay_rolls_back_and_retains_archive(self):
        self.old_artist_vote();before=capture(self.conn)
        with patch('songranker.storage.preference_state.rebuild_preference_ratings',side_effect=RuntimeError('replay interrupted')):
            with self.assertRaises(RuntimeError):retire_selective_tournament_elo(self.path)
        self.assertEqual(capture(self.conn),before)
        self.assertEqual(len(list(self.path.parent.glob('database_backups/pre_tournament_scope_*.db'))),1)

    def test_report_has_semantic_colours_depth_and_bracket_payload(self):
        self.generate('artist')
        before=capture(self.conn)
        from songranker.modes.tournament import build_tournament_stats
        data=build_tournament_stats(self.conn,selected=1)
        self.assertEqual(len(data['archive'][0]['map_data']['entries']),8)
        self.assertEqual(data['coverage']['single'],8)
        redirected=self.client.get('/tournament_stats?tournament=1')
        self.assertEqual(redirected.status_code,302)
        rendered=self.client.get('/tournament_stats')
        self.assertEqual(rendered.status_code,200)
        for text in ['Entry depth','ts-entity-artist']:
            self.assertIn(text,rendered.text)
        self.assertNotIn('data-tournament-map',rendered.text)
        self.assertNotIn('Competition records use scope credit',rendered.text)
        self.assertIn('not its current rank',rendered.text)
        self.assertIn('later seed beat an earlier one',rendered.text)
        bracket=self.client.get('/tournament/1/bracket')
        self.assertEqual(bracket.status_code,200)
        self.assertIn('data-tournament-map',bracket.text)
        self.assertIn('Tournament stats',bracket.text)
        self.assertNotIn('Recent first-round Elo history',rendered.text)
        self.assertNotIn('class="ts-bracket-champion"',rendered.text)
        local=self.client.get('/tournament_local_stats?scope=artist&scope_id=1')
        self.assertEqual(local.status_code,200)
        self.assertIn('Explore bracket',local.text)
        self.assertIn('Head-to-head',local.text)
        self.assertEqual(capture(self.conn),before)

    def test_local_comparisons_filter_finished_results_and_keep_raw_counts(self):
        data=self.generate('artist');second=self.generate('artist');tid=data['tournament_id']
        for bracket_id in (tid,second['tournament_id']):
            self.conn.execute("UPDATE tournament_matches SET status='completed',winner_id=song1_id,loser_id=song2_id,points_awarded=1 WHERE tournament_id=?",(bracket_id,))
            self.conn.execute("UPDATE tournaments SET status='completed',champion_id=1 WHERE id=?",(bracket_id,))
        self.conn.commit()
        from songranker.modes.tournament import build_local_tournament_stats, build_tournament_stats
        local=build_local_tournament_stats(self.conn,'artist',1)
        self.assertEqual(local['summary']['completed'],2)
        self.assertEqual(local['summary']['matches'],8)
        self.assertEqual(len(local['tracks']),8)
        self.assertEqual(sum(r['tournament_wins'] for r in local['tracks']),8)
        self.assertEqual(sum(p['total'] for p in local['pairs']),8)
        self.assertTrue(all(s['tournament_appearances']==2 for s in local['tracks']))
        self.assertEqual(local['groups'][0]['rows'][0]['championships'],2)
        self.assertEqual(build_local_tournament_stats(self.conn,'album',1)['summary']['matches'],0)
        self.assertEqual(build_tournament_stats(self.conn,competition_only=True)['summary']['brackets'],0)
        page=self.client.get('/tournament_local_stats?view=artist:1&lookup=song:1')
        self.assertEqual(page.status_code,200)
        self.assertIn('Top 5',page.text)
        self.assertIn('Bottom 3',page.text)
        self.assertIn('Title / entry rate',page.text)
        self.assertEqual(local['depth']['entries'],16)
        self.assertEqual(local['depth']['repeated'],8)
        self.assertEqual(local['depth']['completion'],100)
        self.assertIn('Bracket mix',page.text)
        self.assertEqual(sum(r['count'] for r in local['distributions'][0]['rows']),2)
        self.assertIn('local-lookup-result',page.text)
        artist_page=self.client.get('/tournament_local_stats?view=artist:1&lookup_kind=artist&lookup=artist:1')
        self.assertEqual(artist_page.status_code,200)
        self.assertIn('value="artist:1" data-cover=',artist_page.text)
        self.assertNotIn('value="song:1" data-cover=',artist_page.text)
        self.assertEqual(self.client.get('/tournament_local_stats?lookup_kind=bad').status_code,400)
        missing=self.client.get('/tournament_local_stats?view=album:1&lookup=song:1')
        self.assertIn('No result found in this selection',missing.text)
        self.assertEqual(self.client.get('/tournament_local_stats?view=artist:1&lookup=artist:1').status_code,200)
        self.assertEqual(self.client.get('/tournament_local_stats?view=artist:invalid').status_code,400)
        self.assertEqual(self.client.get('/tournament_local_stats?scope=artist&scope_id=99999').status_code,404)

    def test_unfinished_blind_comparisons_hide_identities(self):
        data=self.generate('artist');tid=data['tournament_id']
        self.conn.execute('UPDATE tournaments SET is_blind=1 WHERE id=?',(tid,))
        self.conn.execute("UPDATE tournament_matches SET status='completed',winner_id=song1_id,loser_id=song2_id WHERE tournament_id=?",(tid,));self.conn.commit()
        from songranker.modes.tournament import build_local_tournament_stats
        local=build_local_tournament_stats(self.conn)
        self.assertEqual(local['tracks'],[])
        self.assertEqual(local['pairs'],[])
        self.assertIsNone(local['archive'][0]['winner'])

if __name__=='__main__':unittest.main()
