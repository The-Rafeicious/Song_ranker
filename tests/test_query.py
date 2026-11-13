"""Cross-mode queries preserve pooled evidence, relation semantics and stable pages."""
import unittest
from unittest.mock import patch
import test_elo_replay as fixture
from songranker import services
from songranker.catalog import collection
from songranker.reports.query import execute, validate, identities, search_identities, search_matches
from songranker.storage.database_io import capture

class QueryTests(unittest.TestCase):
    setUp=fixture.EloReplayTests.setUp
    vote=fixture.EloReplayTests.vote

    def data(self, matches=False):
        with patch('songranker.catalog.get_db_connection', lambda: self.connect()):
            return collection(include_overall_sources=True, include_query_sources=matches)

    def connect(self):
        import sqlite3
        conn=sqlite3.connect(self.path);conn.row_factory=sqlite3.Row
        return conn

    def query(self, **kw):
        return execute(self.data(any(f.get('field') in ('won_against','lost_to') for f in kw.get('filters',[]))),kw)

    def test_pooled_rates_missing_evidence_and_current_links(self):
        self.vote(1,2);self.vote(1,3);self.vote(2,3,'blind')
        result=self.query(entity='artists')
        self.assertEqual(result['items'][0]['values']['win_rate'],50)
        self.assertEqual(result['items'][0]['values']['matches'],6)
        self.assertEqual(result['items'][0]['values']['tracks'],8)
        self.assertIn('Artist%20%3Cunsafe%3E',result['items'][0]['url'])
        missing=self.query(filters=[dict(field='win_rate',op='missing')])
        self.assertEqual(missing['total'],5)
        zero=self.query(filters=[dict(field='win_rate',op='eq',value=0)])
        self.assertEqual([r['id'] for r in zero['items']],[3])

    def test_inclusive_elo_and_three_level_null_last_sort(self):
        self.vote(1,2)
        data=self.data()
        low=min(s['elo_score'] for s in data['songs']); high=max(s['elo_score'] for s in data['songs'])
        self.assertEqual(execute(data,dict(filters=[dict(field='elo',op='between',value=low,max=high)]))['total'],8)
        result=execute(data,dict(sort=[dict(field='win_rate',direction='asc'),dict(field='matches',direction='desc'),dict(field='name',direction='asc')]))
        self.assertEqual([r['id'] for r in result['items'][:2]],[2,1])
        self.assertTrue(all(r['values']['win_rate'] is None for r in result['items'][2:]))

    def test_relationships_visibility_and_readonly(self):
        self.vote(1,2);self.vote(3,2,'blind')
        before=capture(self.conn)
        result=self.query(filters=[dict(field='won_against',target_id=2,source='voting',mode='blind')])
        self.assertEqual([r['id'] for r in result['items']],[3])
        self.assertEqual(result['spec']['filters'][0]['target_name'],'Song 2')
        self.assertEqual(self.query(filters=[dict(field='lost_to',target_id=3)])['items'][0]['id'],2)
        self.assertEqual(capture(self.conn),before)
        self.assertEqual(self.query(filters=[dict(field='album',target_id=1)])['total'],8)

    def test_twenty_per_page_clamping_and_empty(self):
        for sid in range(9,54): self.conn.execute('INSERT INTO songs(id,title,album_id) VALUES(?,?,1)',(sid,f'Song {sid}'))
        self.conn.commit()
        self.assertEqual(len(self.query()['items']),20)
        final=self.query(page=99)
        self.assertEqual((final['page'],final['pages'],len(final['items'])),(3,3,13))
        empty=self.query(q='does not exist')
        self.assertEqual((empty['page'],empty['pages'],empty['total']),(1,1,0))

    def test_local_tournaments_are_separate_and_incomplete_results_are_hidden(self):
        data=self.data()
        data['tournaments']=[dict(id=1,status='completed',scope_type='global',size=2,champion_id=1),dict(id=2,status='completed',scope_type='artist',size=2,champion_id=2),dict(id=3,status='playing',scope_type='global',size=2)]
        data['tournament_entries']=[]
        data['tournament_matches']=[dict(id=i,tournament_id=i,status='completed',song1_id=1,song2_id=2,winner_id=1 if i!=2 else 2,loser_id=2 if i!=2 else 1,round_number=1,points_awarded=2) for i in (1,2,3)]
        data['query_matches']=[dict(winner_id=2,loser_id=1,mode='blind',source='first_round',scope='artist')]
        values={r['id']:r['values'] for r in execute(data,{})['items']}
        self.assertEqual((values[1]['tournament_wins'],values[1]['local_wins'],values[2]['local_wins']),(1,0,1))
        self.assertEqual(execute(data,dict(filters=[dict(field='won_against',target_id=1)]))['total'],0)
        self.assertEqual(execute(data,dict(filters=[dict(field='won_against',target_id=1,source='local')]))['items'][0]['id'],2)

    def test_collection_rates_pool_unequal_denominators_and_unrated_elo_is_missing(self):
        data=self.data()
        for s in data['songs']:
            s['artist_ids']=[1] if s['id'] in (1,2) else []
        data['songs'][0].update(correct=1,available_points=1,attempts=1)
        data['songs'][1].update(correct=0,available_points=9,attempts=3)
        row=execute(data,dict(entity='artists'))['items'][0]
        self.assertEqual(row['values']['trivia_accuracy'],10)
        self.assertIsNone(row['values']['elo'])

    def test_word_search_accents_metadata_and_lookup_priority(self):
        self.assertTrue(search_matches('rapp cafe', 'Café by Reneé Rapp'))
        self.assertFalse(search_matches('rapp missing', 'Café by Reneé Rapp'))
        rows=[dict(id=3,name='Z track',related=[dict(name='Café')]),dict(id=2,name='Café remix'),dict(id=1,name='Cafe')]
        self.assertEqual([r['id'] for r in search_identities(rows,'cafe')],[1,2,3])
        result=self.query(q='Artist Song 2')
        self.assertEqual([r['id'] for r in result['items']],[2])
        from songranker import pages
        with patch('songranker.pages.collection',lambda **kw:self.data()):
            client=services.app.test_client()
            self.assertEqual(client.get('/api/query?lookup=songs&q=').json['total'],0)
            self.assertEqual(client.get('/api/query?lookup=songs&q=Artist%20Song%202').json['items'][0]['id'],2)

    def test_album_queries_exclude_placeholders_and_tags_never_borrow_covers(self):
        self.conn.execute("INSERT INTO albums(id,title,cover_url,shelves_excluded) VALUES(2,'A Song - Single','single-cover',1),(3,'Unknown Album','unknown-cover',0),(4,'Full Album','full-cover',0)")
        self.conn.execute('UPDATE songs SET album_id=2 WHERE id=1')
        self.conn.execute('UPDATE songs SET album_id=3 WHERE id=2')
        self.conn.execute('UPDATE songs SET album_id=4 WHERE id=3')
        self.conn.execute("INSERT INTO genres(id,name) VALUES(7,'Pop')")
        self.conn.execute('INSERT INTO song_genres(song_id,genre_id) VALUES(1,7)')
        self.conn.commit()
        data=self.data(); public=identities(data)
        self.assertEqual(public['songs'][1]['cover'],'single-cover')
        self.assertIsNone(public['songs'][1]['album'])
        self.assertIsNone(public['songs'][2]['album'])
        self.assertEqual(public['songs'][3]['album']['name'],'Full Album')
        self.assertEqual(public['songs'][1]['artists'][0]['name'],'Artist <unsafe>')
        self.assertFalse(any(r['kind']=='albums' for r in public['songs'][1]['related']))
        self.assertEqual(public['tags'][7]['cover'],'')
        self.assertEqual({r['id'] for r in execute(data,dict(entity='albums'))['items']},{1,4})
        tag=execute(data,dict(entity='tags'))['items'][0]
        self.assertEqual((tag['track_count'],tag['artist_count'],tag['album_count']),(1,1,0))
        with patch('songranker.pages.collection',lambda **kw:self.data()):
            client=services.app.test_client()
            self.assertEqual(client.get('/api/query?lookup=albums&q=Single').json['total'],0)
            self.assertEqual(client.get('/api/query?lookup=albums&q=Full').json['items'][0]['id'],4)

    def test_collection_tag_badges_cover_all_tracks_and_exclude_own_tag(self):
        self.conn.execute("INSERT INTO genres(id,name) VALUES(17,'Pop'),(18,'Quiet')")
        self.conn.executemany('INSERT INTO song_genres(song_id,genre_id) VALUES(?,?)',[(8,17),(1,17),(1,18)])
        self.conn.commit()
        artist=self.query(entity='artists')['items'][0]
        self.assertEqual([(t['id'],t['track_count']) for t in artist['tags']],[(17,2),(18,1)])
        self.assertNotIn(8,[s['id'] for s in artist['related']])
        tag=next(r for r in self.query(entity='tags')['items'] if r['id']==17)
        self.assertEqual([(t['id'],t['track_count']) for t in tag['tags']],[(18,1)])

    def test_invalid_combinations(self):
        for spec in [dict(filters=[dict(field='elo',op='between',value=1300,max=1200)]),dict(filters=[dict(field='win_rate',value=101)]),dict(sort=[dict(field='elo',direction='desc')]*2),dict(filters=[dict(field='won_against',target_id=1,mode='trivia')]),dict(columns=['not-a-stat'])]:
            with self.assertRaises((ValueError,TypeError)):validate(spec)

    def test_api_schema_errors_and_page_assets(self):
        from songranker import pages
        client=services.app.test_client()
        self.assertEqual(client.get('/api/query?schema=1').status_code,200)
        self.assertEqual(client.get('/api/query?spec=%5B%5D').status_code,400)
        with patch('songranker.pages.collection',lambda **kw:self.data(kw.get('include_query_sources',False))):
            self.assertEqual(client.get('/api/query').json['total'],8)
            self.assertEqual(client.get('/api/query?lookup=songs&q=Song%202').json['items'][0]['id'],2)
        html=client.get('/query').get_data(as_text=True)
        self.assertIn('js/query.js',html);self.assertIn('css/query.css',html)
        self.assertNotIn('audio_url',str(identities(self.data())))
