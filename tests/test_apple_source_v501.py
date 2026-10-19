"""Apple imports must persist identity/advisory facts, including flat clients."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_catalog_sources as fixture
from songranker.developer import dev, catalog_sources as sources
from songranker.storage.database_io import capture


class AppleSourcePersistenceTests(unittest.TestCase):
    setUp=fixture.CatalogSourceTests.setUp
    connect=fixture.CatalogSourceTests.connect
    client=fixture.CatalogSourceTests.client
    result=fixture.CatalogSourceTests.result
    add=fixture.CatalogSourceTests.add

    def assert_saved(self,client,response,track_id='9001',label='Explicit'):
        self.assertEqual(response.status_code,200,response.get_json())
        sid=response.json['song_id']
        with self.connect() as reopened:
            saved=sources.current_source(reopened,sid)
            self.assertIsNotNone(saved,'An Apple add must save its source in the same transaction')
            self.assertEqual(saved['external_id'],track_id)
            self.assertEqual(saved['source']['track_url'],'https://music.apple.com/gb/album/new/8001?i='+track_id)
            self.assertEqual(sources.source_label(saved['source']),label)
        self.assertEqual(response.json['source_id'],saved['id'])
        self.assertEqual(response.json['source']['track_id'],track_id)
        detail=client.get('/api/dev/song-source/'+str(sid)).json
        summary=client.get('/api/dev/song-sources').json['songs'][str(sid)]
        self.assertEqual(detail['current']['track_id'],track_id)
        self.assertEqual(summary['status'],'linked')
        self.assertEqual(summary['content_label'],label)
        return sid

    def test_signed_import_returns_the_saved_source_and_duplicate_receipt(self):
        client=self.client();row,_=self.result(client)
        first=self.add(client,row)
        sid=self.assert_saved(client,first)
        again=self.add(client,row)
        self.assertEqual(again.json['song_id'],sid)
        self.assertTrue(again.json['already_present'])
        self.assert_saved(client,again)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],1)

    def test_flat_search_result_verifies_and_saves_instead_of_dropping_source(self):
        client=self.client();track=fixture.apple()
        data={**sources.apple_metadata(track),'source':sources.public_source(sources.observation(track,'gb'))}
        data['source']['explicitness']='notExplicit'
        with patch.object(dev,'apple_lookup',return_value={'results':[track]}) as lookup:
            response=client.post('/api/dev/add_song',json=data)
        self.assert_saved(client,response)
        self.assertIn('id=9001',lookup.call_args.args[0])

    def test_flat_apple_id_and_link_are_verified_before_saving(self):
        for fields in ({'apple_id':'9001'},{'apple_url':'https://music.apple.com/gb/album/new/8001?i=9001'}):
            with self.subTest(fields=fields):
                client=self.client()
                with patch.object(dev,'apple_lookup',return_value={'results':[fixture.apple()]}) as lookup:
                    response=client.post('/api/dev/add_song',json=dict(title='New Song',artist='Artist, One',**fields))
                self.assert_saved(client,response)
                self.assertTrue(lookup.called)

    def test_empty_offer_cannot_silently_fall_back_to_a_manual_add(self):
        client=self.client()
        for token in (None,'',False):
            before=capture(self.conn)
            response=client.post('/api/dev/add_song',json=dict(title='No source',source_token=token))
            self.assertEqual(response.status_code,400,response.get_json())
            self.assertEqual(capture(self.conn),before)

    def test_marked_apple_import_without_identity_is_atomic(self):
        before=capture(self.conn)
        response=self.client().post('/api/dev/add_song',json=dict(title='No source',import_source='apple'))
        self.assertEqual(response.status_code,400,response.get_json())
        self.assertEqual(capture(self.conn),before)

    def test_unmatched_or_invalid_flat_identity_does_not_create_an_unlinked_song(self):
        client=self.client()
        for fields in ({'apple_id':'not-an-id'},{'apple_id':False},{'apple_id':0},{'apple_id':None},{'apple_id':'9002'},
                       {'apple_url':'https://example.com/song/9001'},{'apple_url':123},{'apple_url':''},{'apple_url':None},
                       {'source':{'explicitness':'explicit'}},
                       {'source':{'track_id':'9001','track_url':'https://music.apple.com/gb/song/9002'}}):
            with self.subTest(fields=fields),patch.object(dev,'apple_lookup',return_value={'results':[fixture.apple()]}):
                before=capture(self.conn)
                response=client.post('/api/dev/add_song',json=dict(title='No source',**fields))
                self.assertEqual(response.status_code,400,response.get_json())
                self.assertEqual(capture(self.conn),before)

    def test_source_only_repair_retains_catalogue_and_game_data(self):
        client=self.client();row,_=self.result(client)
        before=capture(self.conn)
        fingerprint=client.get('/api/dev/song-source/1').json['fingerprint']
        response=client.post('/api/dev/song-source/1',json=dict(source_token=row['source_token'],fingerprint=fingerprint))
        self.assertEqual(response.status_code,200,response.get_json())
        after=capture(self.conn)
        for table in before['tables']:
            if table!='song_sources':self.assertEqual(before['tables'][table],after['tables'][table],table)
        self.assertEqual(client.get('/api/dev/song-source/1').json['current']['content_label'],'Explicit')

    def test_missing_advisory_stays_non_explicit_after_reload(self):
        client=self.client();row,_=self.result(client,fixture.apple(trackExplicitness=None))
        self.assert_saved(client,self.add(client,row),label='Not explicit')

    def test_source_insert_failure_rolls_back_the_entire_import(self):
        client=self.client();row,_=self.result(client);before=capture(self.conn)
        with patch.object(sources,'save_source',side_effect=sqlite3.IntegrityError('injected source failure')):
            response=self.add(client,row)
        self.assertEqual(response.status_code,409)
        self.assertEqual(capture(self.conn),before)

    def test_plain_manual_song_remains_supported(self):
        response=self.client().post('/api/dev/add_song',json=dict(title='Manual song',artist='Manual artist'))
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertIsNone(response.json['source_id'])
        self.assertIsNone(sources.current_source(self.conn,response.json['song_id']))


if __name__=='__main__':unittest.main()
