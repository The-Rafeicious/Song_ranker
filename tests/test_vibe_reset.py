"""Intentional reset is scoped, backed up, atomic and never repeated on new data."""
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest
from songranker.storage.database_schema import SCHEMA_VERSION

from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture, readonly, validate, rebuild
from songranker.storage.vibe_state import MAPS, LEGACY_MAPS, RADAR_ORDER, seed_definitions
from songranker.vibe_maps import map_definitions
from songranker.modes.vibe_map import radar
from tools.reset_vibe_maps_v1042 import reset_test_vibes


class VibeResetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'old.db'
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
        c.executescript(Path('tests/fixtures/schema_v18.sql').read_text());seed_definitions(c,legacy=True)
        c.execute("INSERT INTO songs(id,title,elo_score) VALUES(1,'Keep this song',1345),(2,'Another',1210)")
        c.execute("INSERT INTO artists(id,name) VALUES(1,'Keep artist')")
        c.execute('INSERT INTO song_artists VALUES(1,1)')
        c.execute("INSERT INTO genres(id,name) VALUES(1,'Keep tag')")
        c.execute('INSERT INTO song_genres VALUES(1,1)')
        c.execute("UPDATE song_vibe_positions SET x=.75,y=-.4,status='placed',updated_at=42,sample_count=3 WHERE song_id=1")
        c.execute('UPDATE song_vibe_progress SET completed_passes=3 WHERE song_id=1')
        c.execute("INSERT INTO vibe_rounds(owner_hash,token,song_id,started_at,draft_status,draft_x,draft_y,draft_at,draft_key) VALUES('owner','old-token',1,41,'placed',.3,.2,42,'old-draft')")
        c.execute('PRAGMA user_version=18');c.commit();self.before=capture(c);c.close()

    def test_reset_only_replaces_old_mode_facts_and_keeps_a_full_backup(self):
        result=reset_test_vibes(self.path)
        self.assertTrue(result['reset']);self.assertEqual(len(result['backups']),1)
        with readonly(self.path) as c:
            validate(c);after=capture(c)
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
            self.assertEqual({r[0] for r in c.execute('SELECT id FROM vibe_maps')},{m[0] for m in MAPS})
            self.assertTrue({m[0] for m in LEGACY_MAPS}.isdisjoint({m[0] for m in MAPS}))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM song_vibe_positions').fetchone()[0],8)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM song_vibe_positions WHERE status!='unmapped' OR sample_count!=0 OR not_applicable_count!=0").fetchone()[0],0)
            self.assertEqual(c.execute('SELECT SUM(completed_passes) FROM song_vibe_progress').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM vibe_rounds').fetchone()[0],0)
        changed={'listening_observations','vibe_maps','song_vibe_positions','song_vibe_progress','vibe_rounds'}
        for name,data in self.before['tables'].items():
            if name not in changed:self.assertEqual(after['tables'][name],data,name)
        with readonly(result['backups'][0]) as c:self.assertEqual(capture(c),self.before)

    def test_rerun_restart_and_plain_sql_restore_keep_new_results(self):
        reset_test_vibes(self.path)
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
        c.execute("UPDATE song_vibe_positions SET x=.123456789,y=.4,status='placed',sample_count=1,updated_at=45 WHERE song_id=1 AND map_id='pace_mood'")
        c.execute('UPDATE song_vibe_progress SET completed_passes=1 WHERE song_id=1');c.commit()
        after=capture(c);plain=self.root/'plain.sql';plain.write_text('\n'.join(c.iterdump()));c.close()
        self.assertFalse(reset_test_vibes(self.path)['reset']);initialize_database(self.path)
        restored=self.root/'restored.db';initialize_database(restored,plain)
        for path in (self.path,restored):
            with readonly(path) as c:self.assertEqual(capture(c),after)
        output=self.root/'rebuilt.db';rebuild(after,output)
        with readonly(output) as c:self.assertEqual(capture(c),after)

    def test_failed_replacement_rolls_back_everything(self):
        with patch('songranker.storage.database_io.replace_contents',side_effect=sqlite3.DatabaseError('injected')):
            with self.assertRaises(sqlite3.DatabaseError):reset_test_vibes(self.path)
        with readonly(self.path) as c:self.assertEqual(capture(c),self.before)
        backups=list((self.root/'database_backups').glob('pre_upgrade_*.db'))
        with readonly(backups[0]) as c:self.assertEqual(capture(c),self.before)

    def test_new_song_slots_present_midpoint_and_radar_order_use_new_definitions(self):
        reset_test_vibes(self.path)
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
        c.execute("INSERT INTO songs(id,title) VALUES(3,'Later import')")
        self.assertEqual(c.execute('SELECT COUNT(*) FROM song_vibe_positions WHERE song_id=3').fetchone()[0],4)
        maps=map_definitions(c);self.assertEqual(maps[-1]['x_center'],'Present')
        for m in maps:
            for key in ('x_low','x_high','y_low','y_high'):self.assertEqual(len(m[key].split()),1)
        points={key:dict(status='placed',x=.6,y=-.4) for key,*_ in MAPS}
        spokes=radar(points)['spokes'];self.assertEqual([s['label'] for s in spokes],[r[2] for r in RADAR_ORDER])
        self.assertEqual({(s['map_id'],s['axis']) for s in spokes},{(m[0],axis) for m in MAPS for axis in ('x','y')})
        c.close()


if __name__=='__main__':unittest.main()
