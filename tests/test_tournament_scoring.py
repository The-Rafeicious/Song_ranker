"""Bracket depth rewards must not turn a bronze-playoff loss into an early-exit advantage."""
from copy import deepcopy
import unittest
from songranker.modes.tournament_scoring import round_points, scored_match, entry_results
from songranker.catalog import song_performance
from songranker.overall import features, evaluate


def bracket_data(size=32,scope='global'):
    songs=[dict(id=s,title=f'Song {s}',album_id=None,artist_ids=[],tag_ids=[],elo_score=1200,highest_elo=1200,matches_played=0,audio_url='') for s in range(1,size+1)]
    matches=[];active=list(range(1,size+1));stage=0;semis=[]
    while len(active)>1:
        stage+=1;next_round=[]
        for index in range(0,len(active),2):
            a,b=active[index:index+2];next_round.append(a)
            matches.append(dict(id=len(matches)+1,tournament_id=1,round_number=stage,match_number=index//2+1,song1_id=a,song2_id=b,winner_id=a,loser_id=b,status='completed',match_type='bracket',points_awarded=7*2**(stage-1)/(size-1)))
            if len(active)==4:semis.append(b)
        active=next_round
    third,fourth=semis
    matches.append(dict(id=len(matches)+1,tournament_id=1,round_number=stage,match_number=1,song1_id=third,song2_id=fourth,winner_id=third,loser_id=fourth,status='completed',match_type='third_place',points_awarded=0.5*7*2**(stage-2)/(size-1)))
    t=dict(id=1,size=size,status='completed',scope_type=scope,champion_id=1,runner_up_id=1+size//2,third_place_id=third,fourth_place_id=fourth)
    return dict(songs=songs,artists=[],albums=[],tags=[],tournaments=[t],tournament_matches=matches,tournament_entries=[dict(song_id=s,tournament_id=1) for s in range(1,size+1)])


class TournamentScoringTests(unittest.TestCase):
    def test_size_and_finish_points_hierarchy(self):
        for size,totals in [(8,(6,3,2,1)),(16,(10,6,4.5,3)),(32,(15,10,8,6))]:
            data=bracket_data(size);t=data['tournaments'][0];before=deepcopy(data)
            stats=song_performance(data)
            for key,want in zip(['champion_id','runner_up_id','third_place_id','fourth_place_id'],totals):
                self.assertEqual(stats[t[key]]['tournament_points'],want)
            self.assertEqual(data,before,'Historical saved point facts are never rewritten by reports')
            self.assertEqual(sum(round_points(size,r) for r in range(1,size.bit_length())),totals[0])

    def test_fourth_beats_quarter_exit_in_all_overall_components_and_score(self):
        data=bracket_data();fourth=data['tournaments'][0]['fourth_place_id'];quarter=5
        stats=song_performance(data)
        self.assertLess(stats[fourth]['tournament_wins']/(stats[fourth]['tournament_wins']+stats[fourth]['tournament_losses']),stats[quarter]['tournament_wins']/(stats[quarter]['tournament_wins']+stats[quarter]['tournament_losses']))
        values=features(data)
        for key in ['tournament_wins','tournament_podium','tournament_points']:
            self.assertGreater(values[fourth][key]['value'],values[quarter][key]['value'],key)
        scored={s['id']:s for s in evaluate(data)['entities']['songs']}
        self.assertGreater(scored[fourth]['score'],scored[quarter]['score'])

    def test_bronze_loss_never_deducts_progress_or_points(self):
        data=bracket_data();fourth=data['tournaments'][0]['fourth_place_id']
        with_bronze=features(data)[fourth]
        data['tournament_matches']=[m for m in data['tournament_matches'] if m['match_type']!='third_place']
        without=features(data)[fourth]
        for key in ['tournament_wins','tournament_podium','tournament_points']:
            self.assertEqual(with_bronze[key],without[key])

    def test_titles_and_fourth_place_gain_significance_in_larger_brackets(self):
        title=[];fourth=[]
        for size in [8,16,32]:
            data=bracket_data(size);rows=features(data)
            title.append(rows[1]['tournament_podium']['value'])
            fourth.append(rows[data['tournaments'][0]['fourth_place_id']]['tournament_podium']['value'])
        self.assertEqual(title,[.6,.8,1]);self.assertTrue(0<fourth[0]<fourth[1]<fourth[2])

    def test_local_and_pending_brackets_do_not_affect_overall(self):
        for scope in ['artist','album']:
            self.assertIsNone(features(bracket_data(scope=scope))[1]['tournament_podium']['value'])
        data=bracket_data();data['tournaments'][0]['status']='in_progress'
        self.assertEqual(entry_results(data),{})
        self.assertIsNone(features(data)[1]['tournament_points']['value'])

    def test_missing_finish_metadata_is_recovered_from_saved_final_and_bronze(self):
        data=bracket_data();fourth=data['tournaments'][0]['fourth_place_id']
        expected=features(data)[fourth]
        for key in ['champion_id','runner_up_id','third_place_id','fourth_place_id']:data['tournaments'][0][key]=None
        recovered=features(data)[fourth]
        for key in ['tournament_wins','tournament_podium','tournament_points']:self.assertEqual(expected[key],recovered[key])

    def test_bad_and_unsupported_archives_keep_saved_points(self):
        data=bracket_data();m=data['tournament_matches'][0]
        for altered,t in [(dict(m,winner_id=m['loser_id']),data['tournaments'][0]),(dict(m,round_number=99),data['tournaments'][0]),(m,dict(size=3))]:
            self.assertEqual(scored_match(altered,t)['points_awarded'],altered['points_awarded'])


import sqlite3
import test_tournament_policy as policy_fixture
from songranker.modes.preferences import save_tournament_preference
from songranker.storage.database_io import capture


class TournamentPointsAPITests(unittest.TestCase):
    setUp=policy_fixture.TournamentPolicyTests.setUp

    def test_first_round_elo_and_archival_facts_are_preserved(self):
        for sid in range(9,33):
            self.conn.execute('INSERT INTO songs(id,title,album_id,audio_url) VALUES(?,?,1,?)',(sid,f'Track {sid}',f'preview-{sid}'))
            self.conn.execute('INSERT INTO song_artists VALUES(?,1)',(sid,))
        self.conn.commit()
        for size in [8,16,32]:
            response=self.client.get('/api/generate_bracket',query_string=dict(size=size,scope='global'),content_type='application/json')
            self.assertEqual(response.status_code,200,response.json)
            t_id=response.json['tournament_id'];m=response.json['matches'][0]
            t=dict(self.conn.execute('SELECT * FROM tournaments WHERE id=?',(t_id,)).fetchone())
            copy=sqlite3.connect(':memory:');copy.row_factory=sqlite3.Row;self.conn.backup(copy)
            try:
                copy.execute('BEGIN')
                event_id=save_tournament_preference(copy,t,m,m['song1_id'],m['song2_id']);copy.commit()
                expected=dict(copy.execute('SELECT winner_before,winner_after,loser_before,loser_after FROM preference_rating_projection WHERE event_id=?',(event_id,)).fetchone())
            finally:copy.close()
            payload=dict(tournament_id=t_id,match_id=m['id'],winner_id=m['song1_id'],loser_id=m['song2_id'])
            result=self.client.post('/api/tournament_vote',json=payload)
            self.assertEqual(result.status_code,200,result.json);self.assertEqual(result.json['points_awarded'],1)
            actual=dict(self.conn.execute('SELECT winner_before,winner_after,loser_before,loser_after FROM preference_rating_projection WHERE event_id=?',(result.json['preference_event_id'],)).fetchone())
            self.assertEqual(actual,expected,'Only tournament points change; canonical first-round Elo remains identical')
            self.assertEqual(self.client.post('/api/tournament_vote',json=payload).json,result.json)
            old=7/(size-1)
            self.conn.execute('UPDATE tournament_matches SET points_awarded=? WHERE id=?',(old,m['id']));self.conn.commit()
            before=capture(self.conn)
            viewed=self.client.get(f'/api/tournaments/{t_id}')
            self.assertEqual(viewed.status_code,200,viewed.json)
            shown=next(row for row in viewed.json['matches'] if row['id']==m['id'])
            self.assertEqual(shown['points_awarded'],1)
            collection=self.client.get('/api/collection')
            self.assertEqual(collection.status_code,200)
            self.assertEqual(next(row for row in collection.json['tournament_matches'] if row['id']==m['id'])['points_awarded'],1)
            self.assertEqual(capture(self.conn),before,'Viewing rebalanced history never rewrites the saved database')
