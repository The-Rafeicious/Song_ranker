"""Opponent graph topology, deduplication, privacy and bounded display reads."""
import unittest
from unittest.mock import patch
import test_elo_replay as fixture
from songranker import services
from songranker.modes.preferences import record_preference
from songranker.reports.match_network import build_match_network, search_network_songs
from songranker.storage.database_io import capture


class MatchNetworkTests(unittest.TestCase):
    setUp = fixture.EloReplayTests.setUp
    vote = fixture.EloReplayTests.vote

    def bracket(self, tid, scope='global', status='completed', blind=False):
        """Store a finished or private bracket with explicit scope/visibility."""
        self.conn.execute('INSERT INTO tournaments(id,size,scope_type,status,is_blind) VALUES(?,8,?,?,?)',(tid,scope,status,blind))

    def match(self, tid, winner, loser, round_no=1):
        """Store a decided match; Elo can be attached separately for first-round dedup."""
        index=self.conn.execute('SELECT COUNT(*) FROM tournament_matches WHERE tournament_id=?',(tid,)).fetchone()[0]+1
        return self.conn.execute("INSERT INTO tournament_matches(tournament_id,round_number,match_number,song1_id,song2_id,winner_id,loser_id,status,points_awarded,played_at) VALUES(?,?,?,?,?,?,?,'completed',1.5,'2026-11-01 12:00:00')",(tid,round_no,index,winner,loser,winner,loser)).lastrowid

    def raw_votes(self, pairs):
        """Seed large legacy-style effective history without recalculating Elo."""
        self.conn.executemany("INSERT INTO preference_events(winner_id,loser_id,mode,origin,created_at) VALUES(?,?,'standard','ordinary','2026-11-01 11:00:00')",pairs)

    def test_first_round_is_once_later_round_has_no_invented_elo_and_local_is_explicit(self):
        self.vote(7,8)
        self.bracket(1,blind=True);mid=self.match(1,7,6)
        record_preference(self.conn,7,6,'blind',{7:dict(id=7),6:dict(id=6)},tournament_id=1,tournament_match_id=mid)
        self.match(1,6,7,2)
        self.bracket(2,'artist');self.match(2,7,5)
        self.bracket(3,status='in_progress',blind=True);pending=self.match(3,7,4)
        record_preference(self.conn,7,4,'blind',{7:dict(id=7),4:dict(id=4)},tournament_id=3,tournament_match_id=pending)
        self.conn.commit()
        before=capture(self.conn)
        d=build_match_network(self.conn)
        self.assertEqual(d['totals']['matches'],3)
        edge=next(e for e in d['edges'] if e['id']=='6-7')
        self.assertEqual((edge['count'],edge['a_wins'],edge['b_wins']),(2,1,1))
        self.assertEqual(edge['sources'],dict(first_round=1,tournament=1))
        self.assertEqual(build_match_network(self.conn,source='first_round')['totals']['matches'],1)
        self.assertEqual(build_match_network(self.conn,source='tournament')['totals']['matches'],1)
        self.assertEqual(build_match_network(self.conn,include_local=True)['totals']['matches'],4)
        pair=build_match_network(self.conn,pair=(6,7))
        self.assertEqual(pair['total'],2)
        first=next(r for r in pair['history'] if r['source']=='first_round')
        self.assertIsNotNone(first['winner_after'])
        later=next(r for r in pair['history'] if r['source']=='tournament')
        self.assertIsNone(later['winner_after']);self.assertEqual(later['points'],1.5)
        self.assertEqual(capture(self.conn),before)

    def test_breadth_depth_cycles_and_disconnected_focus(self):
        self.raw_votes([(i,i+1) for i in range(1,7)])
        d=build_match_network(self.conn,1,depth=4,branches=4)
        self.assertEqual({n['id'] for n in d['nodes']},{1,2,3,4,5})
        self.assertEqual({n['id']:n['level'] for n in d['nodes']},{i:i-1 for i in range(1,6)})
        self.raw_votes([(1,i) for i in range(3,8)])
        d=build_match_network(self.conn,1,depth=1,branches=3)
        self.assertEqual(len(d['nodes']),4)
        self.raw_votes([(3,7),(7,1)])
        cyclic=build_match_network(self.conn,1,depth=5,branches=5)
        self.assertEqual(len(cyclic['nodes']),len({n['id'] for n in cyclic['nodes']}))
        self.assertTrue(all(n['level']<=5 for n in cyclic['nodes']))
        empty=build_match_network(self.conn,8)
        self.assertEqual([n['id'] for n in empty['nodes']],[8]);self.assertEqual(empty['edges'],[])

    def test_timeline_changes_connections_but_current_elo_and_pair_paging_remain_honest(self):
        self.raw_votes([(1,2)]*25+[(2,3)])
        self.conn.execute('UPDATE songs SET elo_score=1600 WHERE id=1')
        d=build_match_network(self.conn,through=1)
        self.assertEqual((d['timeline']['position'],d['timeline']['total']),(1,26))
        self.assertEqual(d['totals']['matches'],1)
        self.assertEqual(next(n['elo'] for n in d['nodes'] if n['id']==1),1600)
        self.assertEqual(build_match_network(self.conn,through=0)['nodes'],[])
        p=build_match_network(self.conn,pair=(1,2))
        self.assertEqual((p['total'],p['pages'],len(p['history'])),(25,2,20))
        self.assertEqual(len(build_match_network(self.conn,pair=(1,2),page=2)['history']),5)
        self.assertIsNone(p['history'][0]['winner_after'])

    def test_effective_voids_and_unavailable_participants_are_not_resurrected(self):
        self.vote(1,2)
        self.conn.execute("INSERT INTO preference_corrections(event_id,request_token,action,winner_id,loser_id,mode,active) VALUES(1,'void','void',1,2,'standard',0)")
        self.assertEqual(build_match_network(self.conn)['totals']['matches'],0)
        self.raw_votes([(3,4)])
        self.conn.execute('DELETE FROM songs WHERE id=4')
        d=build_match_network(self.conn)
        self.assertEqual(d['totals']['matches'],0);self.assertEqual(d['omitted'],1)

    def test_drawing_caps_do_not_limit_song_search_or_pair_history(self):
        self.conn.executemany('INSERT INTO songs(id,title) VALUES(?,?)',[(i,f'Network {i}') for i in range(9,1506)])
        self.raw_votes([(i,i+1) for i in range(1,1505)])
        d=build_match_network(self.conn)
        self.assertEqual(len(d['nodes']),1400);self.assertTrue(d['limits']['limited'])
        self.assertEqual(build_match_network(self.conn,pair=(1504,1505))['total'],1)
        self.assertEqual(search_network_songs(self.conn,'Network 1505')['songs'][0]['id'],1505)
        self.conn.execute('DELETE FROM preference_events')
        self.raw_votes([((i-2)//4+1,i) for i in range(2,600)])
        focused=build_match_network(self.conn,1,depth=5,branches=5)
        self.assertEqual(len(focused['nodes']),180);self.assertTrue(focused['limits']['limited'])

    def test_dense_network_caps_edges_without_changing_full_counts(self):
        self.conn.executemany('INSERT INTO songs(id,title) VALUES(?,?)',[(i,f'Dense {i}') for i in range(9,121)])
        self.raw_votes([(a,b) for a in range(1,121) for b in range(a+1,121)])
        d=build_match_network(self.conn)
        self.assertEqual(d['totals']['connections'],7140)
        self.assertEqual(len(d['edges']),6000);self.assertTrue(d['limits']['edges_limited'])
        self.assertEqual(build_match_network(self.conn,pair=(1,2))['total'],1)

    def test_api_validation_asset_registry_and_accent_insensitive_catalogue_lookup(self):
        self.conn.execute("UPDATE songs SET title='Reneé <unsafe>' WHERE id=8")
        self.conn.commit()
        with patch.object(services,'DB_NAME',str(self.path)),patch('songranker.catalog.collection',side_effect=AssertionError('No collection hydration')):
            client=services.app.test_client()
            for suffix in ['depth=0','depth=6','branches=2','branches=6','song_id=bad','song_id=0','mode=bad','source=bad','local=yes','through=bad','pair=1,1','pair=1','page=0']:
                self.assertEqual(client.get('/api/match-network?'+suffix).status_code,400,suffix)
            self.assertEqual(client.get('/api/match-network?song_id=99999').status_code,404)
            self.assertEqual(client.get('/api/match-network?search=renee').json['songs'][0]['title'],'Reneé <unsafe>')
            response=client.get('/api/match-network?song_id=8')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertNotIn('token',response.get_data(as_text=True))
            html=client.get('/match-network?song_id=8').get_data(as_text=True)
            self.assertIn('data-network-full',html)
            self.assertEqual(html.count('/js/match_network.js?'),1)
            self.assertNotIn('/js/profiles.js?',html)
