"""Raw inspection is read only, bounded, exact for types and browser owned."""
import base64
from pathlib import Path
import sqlite3
import unittest
import test_preferences as fixture
from songranker import services
from songranker.developer import dev_system
from songranker.storage.database_io import capture


class DatabaseInspectorTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect

    def client(self):
        client=services.app.test_client()
        with client.session_transaction() as s:s['is_admin']=True
        return client

    def test_types_columns_rows_paging_and_binary_chunks_preserve_all_data(self):
        c=self.conn;c.execute('CREATE TABLE "odd table"(id INTEGER PRIMARY KEY, note TEXT, raw BLOB, absent TEXT, amount REAL)')
        c.execute('INSERT INTO "odd table" VALUES(?,?,?,?,?)',(9223372036854775807,'<script>'+('x'*9000),bytes(range(256))*40,None,1.25));c.commit();before=capture(c)
        client=self.client();r=client.get('/api/dev/database/inspect',query_string={'name':'odd table','limit':1});self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['columns'][0]['pk'],1);row=r.json['rows'][0]
        self.assertEqual(row['cells'][0]['value'],'9223372036854775807');self.assertEqual(row['cells'][3]['type'],'null')
        self.assertTrue(row['cells'][1]['truncated'])
        token=row['review_token'];col=lambda n,start=0:client.get('/api/dev/database/cell',query_string={'review_token':token,'column':n,'start':start})
        self.assertEqual(col(1).json['value'],'<script>'+('x'*4088));self.assertEqual(col(1,4096).json['value'],'x'*4096)
        self.assertEqual(base64.b64decode(col(2).json['value']),bytes(range(256))*16)
        self.assertEqual(client.get('/api/dev/database/inspect',query_string={'name':'odd table','offset':1}).json['rows'],[])
        self.assertEqual(capture(c),before)

    def test_unknown_sql_injection_offsets_auth_and_cross_browser_values_are_rejected(self):
        client=self.client();before=capture(self.conn)
        for name in ['songs; DROP TABLE songs','missing','songs"; DELETE FROM songs;--']:
            self.assertEqual(client.get('/api/dev/database/inspect',query_string={'name':name}).status_code,400)
        self.assertEqual(client.get('/api/dev/database/inspect?name=songs&offset=-1').status_code,400)
        self.assertEqual(services.app.test_client().get('/api/dev/database/inspect?name=songs').status_code,302)
        result=client.get('/api/dev/database/inspect?name=songs').json;token=result['rows'][0]['review_token']
        self.assertEqual(self.client().get('/api/dev/database/cell',query_string={'review_token':token}).status_code,400)
        self.conn.execute("UPDATE songs SET title='Changed' WHERE id=?",(self.conn.execute('SELECT id FROM songs ORDER BY id LIMIT 1').fetchone()[0],));self.conn.commit()
        self.assertEqual(client.get('/api/dev/database/cell',query_string={'review_token':token}).status_code,409)
        self.assertEqual(len(capture(self.conn)['tables']['songs']['rows']),len(before['tables']['songs']['rows']))
        self.assertEqual(client.post('/api/dev/database/inspect',json={'sql':'DELETE FROM songs'}).status_code,405)

    def test_views_without_rowid_generated_columns_and_internal_tables_are_inspectable(self):
        self.conn.executescript('CREATE TABLE custom(a TEXT PRIMARY KEY,b INTEGER,c INTEGER GENERATED ALWAYS AS (b*2)) WITHOUT ROWID; INSERT INTO custom(a,b) VALUES(\'key\',4); CREATE VIEW custom_view AS SELECT * FROM custom;')
        client=self.client()
        for name in ['custom','custom_view','sqlite_sequence']:
            r=client.get('/api/dev/database/inspect',query_string={'name':name});self.assertEqual(r.status_code,200,r.json)
        row=client.get('/api/dev/database/inspect?name=custom').json['rows'][0]
        self.assertEqual(row['cells'][2]['value'],'8')
