"""Real schema-16 retirement and restore: only the removed mode loses facts."""
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from songranker import services, pages
from songranker.modes import judgement_pages, judgement_api
from songranker.storage.database import migrate
from songranker.storage.database_io import capture, readonly, reconcile, rebuild, sql_dump
from songranker.storage.mode_retirement import upgrade_state


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'old.db'
        c = sqlite3.connect(self.path)
        c.executescript((Path(__file__).parent/'fixtures/schema_v16.sql').read_text())
        c.execute('PRAGMA user_version=16')
        c.execute("INSERT INTO albums(id,title) VALUES(1,'Retained album')")
        for sid in range(1, 5):
            c.execute('INSERT INTO songs(id,title,album_id,audio_url) VALUES(?,?,1,?)', (sid, 'Track '+str(sid), 'preview/'+str(sid)))
        for rid, mode in enumerate(('spotlight','vibe','twins'), 1):
            c.execute('INSERT INTO judgement_rounds(id,token,owner_hash,mode,created_at) VALUES(?,?,?,?,1)', (rid,str(rid)*32,'a'*64,mode))
            for slot in range(1 if mode == 'vibe' else 4):
                c.execute('INSERT INTO judgement_items VALUES(?,?,?,?,?)', (rid,slot,slot+1,slot+1,json.dumps(dict(title='Track '+str(slot+1),artist='Artist'))))
            if mode == 'spotlight':c.executemany('INSERT INTO spotlight_allocations VALUES(?,?,3)',[(rid,s) for s in range(4)])
            elif mode == 'vibe':c.execute("INSERT INTO vibe_placements VALUES(?,'mood',1,4)",(rid,))
            else:c.execute('INSERT INTO twins_choices VALUES(?,2)',(rid,))
            c.execute("UPDATE judgement_rounds SET status='answered',closed_at=2,answer_hash=? WHERE id=?",('b'*64,rid))
            c.execute('INSERT INTO listening_observations(mode,reference,song_key,song_id,seconds,decision_ms,recorded_at) VALUES(?,?,1,1,3,4000,2)', (mode,str(rid)))
        # A pending retired offer is removed too, without lowering future IDs.
        c.execute("INSERT INTO judgement_rounds(id,token,owner_hash,mode,created_at) VALUES(500,? ,?,'twins',1)", ('z'*32,'c'*64))
        c.execute('CREATE TABLE extension_notes(id INTEGER PRIMARY KEY, note TEXT)')
        c.execute("INSERT INTO extension_notes VALUES(70,'Keep this exactly')")
        c.commit();self.before=capture(c);c.close()

    def check_retired(self, path):
        with readonly(path) as c:
            after=capture(c);reconcile(self.before,after)
            self.assertEqual(after['user_version'],17)
            self.assertNotIn('twins_choices',after['tables'])
            self.assertNotIn('twins_open_answer',{o['name'] for o in after['objects']})
            self.assertEqual([r[0] for r in c.execute('SELECT mode FROM judgement_rounds ORDER BY id')],['spotlight','vibe'])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM listening_observations WHERE mode='twins'").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mode_exposures WHERE mode='twins'").fetchone()[0],0)
            expected=upgrade_state(self.before)
            for name in expected['tables']:
                self.assertEqual(expected['tables'][name],after['tables'][name],name)
            self.assertGreaterEqual(after['sequences']['judgement_rounds'],500)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_live_migration_is_selective_backed_up_and_idempotent(self):
        migrate(self.path);self.check_retired(self.path)
        backups=list(self.path.parent.glob('database_backups/pre_upgrade_*.db'))
        self.assertEqual(len(backups),1)
        with readonly(backups[0]) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM twins_choices').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM judgement_rounds').fetchone()[0],4)
        migrate(self.path)
        self.assertEqual(len(list(self.path.parent.glob('database_backups/pre_upgrade_*.db'))),1)

    def test_export_rebuild_and_versionless_sql_restore_also_retire(self):
        output=Path(self.tmp.name)/'rebuilt.db';rebuild(self.before,output);self.check_retired(output)
        with readonly(self.path) as c:dump=sql_dump(c).replace('PRAGMA user_version=16;','')
        restored=Path(self.tmp.name)/'dump.db'
        with sqlite3.connect(restored) as c:
            c.executescript(dump)
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],0)
        migrate(restored);self.check_retired(restored)

    def test_removed_urls_are_unavailable_and_navigation_has_no_retired_mode(self):
        migrate(self.path)
        with patch.object(services,'DB_NAME',str(self.path)):
            client=services.app.test_client()
            for url in ('/sound_twins','/sound_twins_stats','/api/sound-twins/stats','/api/twins/stats'):
                self.assertEqual(client.get(url).status_code,404,url)
            for suffix in ('round','answer'):
                self.assertEqual(client.post('/api/sound-twins/'+suffix,json={}).status_code,404)
            for url in ('/','/global_stats','/vibe_map','/vibe_map_stats'):
                page=client.get(url);self.assertEqual(page.status_code,200)
                self.assertNotIn(b'Sound Twins',page.data);self.assertNotIn(b'sound_twins',page.data)
            self.assertEqual({m['key'] for m in client.get('/api/mode-updates').json['modes']},{'spotlight','vibe'})
            self.assertEqual(client.get('/api/mode-updates').json['modes'][1]['color'],'#FF3B3B')


if __name__=='__main__':unittest.main()
