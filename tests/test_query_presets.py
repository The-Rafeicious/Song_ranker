"""Named Query presets survive backup transport and enforce Dev edits."""

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from songranker import pages, services
from songranker.storage.database import initialize_database, migrate
from songranker.storage.database_io import sql_dump
from songranker.storage.git_database import prepare_sql


class QueryPresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / 'preset.db'
        initialize_database(self.db)
        self.patch = patch.object(services, 'DB_NAME', str(self.db))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client = services.app.test_client()

    def test_create_edit_delete_and_backup(self):
        # A device with a pre-preset database must upgrade before saving.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute('DROP TABLE query_presets')
            conn.execute('PRAGMA user_version=23')
        migrate(self.db)

        endpoint = '/api/query/presets'
        self.assertEqual(self.client.get(endpoint).json, {'presets': []})
        payload = {'name': '  Tourney cuts  ', 'spec': {
            'entity': 'artists', 'q': 'Rose', 'page': 4,
            'filters': [{'field': 'won_against', 'target_id': 12,
                         'source': 'first_round', 'mode': 'blind'}],
            'sort': [{'field': 'name', 'direction': 'asc'}],
            'columns': ['tournament_wins', 'elo'],
        }}
        saved = self.client.post(endpoint, json=payload)
        self.assertEqual(saved.status_code, 201)
        preset = saved.json
        self.assertEqual(preset['name'], 'Tourney cuts')
        self.assertEqual(preset['spec'], dict(payload['spec'], page=1))
        self.assertEqual(self.client.post(endpoint, json=dict(payload, name='tourney cuts')).status_code, 409)
        self.assertEqual(self.client.post(endpoint, json=dict(payload, spec={'sort': []})).status_code, 400)
        edit = '/api/dev/query/presets/' + preset['id']
        self.assertEqual(self.client.delete(edit, json={'revision': 1}).status_code, 403)
        with self.client.session_transaction() as session:
            session['is_admin'] = True
        changed = self.client.put(edit, json=dict(payload, name='Finals', revision=1))
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json['revision'], 2)
        self.assertEqual(self.client.delete(edit, json={'revision': 1}).status_code, 409)

        with closing(sqlite3.connect(self.db)) as conn:
            dump = sql_dump(conn)
        restored, *_ = prepare_sql(dump, self.folder, 'restored')
        with patch.object(services, 'DB_NAME', str(restored)):
            self.assertEqual(self.client.get(endpoint).json, {'presets': [changed.json]})
        self.assertEqual(self.client.delete(edit, json={'revision': 2}).status_code, 200)
        self.assertEqual(self.client.get(endpoint).json, {'presets': []})
