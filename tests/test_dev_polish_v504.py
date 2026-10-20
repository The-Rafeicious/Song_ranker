"""V5 developer maintenance contracts against disposable databases only."""
from unittest.mock import patch
import unittest

import test_preferences as fixture
from songranker import services
from songranker.developer import dev, metadata_tools, dev_system


class DeveloperPolishTests(unittest.TestCase):
    setUp = fixture.PreferenceTests.setUp
    connect = fixture.PreferenceTests.connect

    def client(self):
        client = services.app.test_client()
        with client.session_transaction() as session:
            session['is_admin'] = True
        return client

    def test_entity_edits_reject_non_objects_and_non_text_without_writing(self):
        client = self.client()
        for route, valid in [('artist/1', {'name':'Artist'}), ('album/1', {'title':'Album'}), ('genre/1', {'name':'Tag'})]:
            kind, sid = route.split('/')
            for value in [[], ['wrong'], 'wrong', 7, {**valid, 'cover_url':[]}] if kind!='genre' else [[], 'wrong', 7, {'name':False}]:
                with self.subTest(kind=kind, value=value):
                    response = client.post(f'/api/dev/edit_{kind}/{sid}', json=value)
                    self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.conn.execute('SELECT name FROM artists WHERE id=1').fetchone()[0], 'Artist, One')

    def test_album_date_and_tag_info_validation_keep_existing_values(self):
        client = self.client()
        self.assertEqual(client.post('/api/dev/edit_album/1', json={'title':'Changed','release_date':'2026-02-30'}).status_code, 400)
        self.assertEqual(self.conn.execute('SELECT title FROM albums WHERE id=1').fetchone()[0], 'Album')
        self.conn.execute("UPDATE genres SET description='Retained' WHERE id=1");self.conn.commit()
        self.assertEqual(client.post('/api/dev/edit_genre/1',json={'name':'Renamed'}).status_code,200)
        self.assertEqual(self.conn.execute('SELECT description FROM genres WHERE id=1').fetchone()[0], 'Retained')
        self.assertEqual(client.post('/api/dev/edit_genre/1',json={'name':'Renamed','description':'x'*2001}).status_code,400)

    def test_bulk_moves_require_bounded_positive_ids_and_boolean_clear(self):
        client = self.client()
        for data in [[], {'song_ids':[True]}, {'song_ids':[1.5]}, {'song_ids':['1']}, {'song_ids':list(range(1,502))},
                     {'song_ids':[1],'action':'move_album','album_id':True},
                     {'song_ids':[1],'action':'move_album','album_id':2,'clear_track_numbers':'yes'}]:
            with self.subTest(data=data):
                self.assertEqual(client.post('/api/dev/bulk_songs',json=data).status_code,400)
        self.assertEqual(self.conn.execute('SELECT album_id FROM songs WHERE id=1').fetchone()[0],1)
        self.assertEqual(client.post('/api/dev/bulk_songs',json={'song_ids':[1],'action':'move_album','album_id':2,'clear_track_numbers':True}).status_code,200)

    def test_legacy_overview_quotes_extension_names_and_matches_system_inventory(self):
        self.conn.execute('CREATE TABLE "custom notes" (value TEXT)');self.conn.commit()
        result = self.client().get('/api/dev/overview')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['counts']['custom notes'],0)
        self.assertEqual(result.json['counts']['songs'],10)

    def test_invalid_maintenance_payloads_return_errors_instead_of_500s(self):
        client=self.client()
        for route in ['/api/dev/trivia-records','/api/dev/reset-history/matches','/api/dev/reset-database','/api/dev/metadata']:
            with self.subTest(route=route), patch.object(metadata_tools,'Thread') as worker:
                self.assertEqual(client.post(route,json=['invalid']).status_code,400)
                worker.assert_not_called()

    def test_entity_delete_missing_row_returns_404_and_valid_delete_keeps_songs(self):
        client=self.client()
        for kind in ['artist','album','genre']:
            self.assertEqual(client.delete(f'/api/dev/delete_{kind}/999',json={}).status_code,404)
        self.assertEqual(client.delete('/api/dev/delete_genre/1',json={}).status_code,200)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0],10)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_genres').fetchone()[0],0)
