"""V5.1 facts, opportunity statistics, adaptive calibration and HTTP isolation."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import random
import sqlite3
import tempfile
import unittest

from songranker import services, overall, pages
from songranker.modes import games, special_modes, trivia, judgement_api
from songranker.developer import dev, dev_system
from songranker.catalog import collection
from songranker.storage.database import initialize_database, migrate
from songranker.storage.database_io import capture, readonly, reconcile, write_export, read_export, rebuild, sql_dump
from songranker.modes.judgements import get_offer, save_answer, JudgementError, RETENTION_SECONDS
from songranker.modes.judgement_selection import diagnostics
from songranker.reports.judgement_stats_data import build_judgement_stats, spotlight_records
from songranker.modes.shared_spotlight import support
from songranker.modes.preferences import get_offer as vote_offer, save_vote


def fixture(path, *, schema15=False):
    if schema15:
        c=sqlite3.connect(path)
        c.executescript((Path(__file__).parent/'fixtures/schema_v15.sql').read_text())
        c.execute("INSERT INTO competition_state VALUES(1,3,1,'{}')")
        c.execute("INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',1)")
    else:
        initialize_database(path);c=sqlite3.connect(path)
    c.execute("INSERT INTO albums(id,title) VALUES(1,'Example album')")
    c.execute("INSERT INTO artists(id,name) VALUES(1,'Artist A'),(2,'Artist B')")
    c.execute("INSERT INTO genres(id,name,description) VALUES(1,'sad-pop','Bright sound, sad words'),(2,'bridge','Big bridge')")
    for sid in range(1,13):
        c.execute('INSERT INTO songs(id,title,album_id,audio_url,track_number) VALUES(?,?,?,?,?)',(sid,'Song '+str(sid),1,'preview/'+str(sid),sid))
        c.execute('INSERT INTO song_artists VALUES(?,?)',(sid,1 if sid<8 else 2))
        c.execute('INSERT INTO song_genres VALUES(?,1)',(sid,))
    c.commit();c.close()


class ModeUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'test.db';fixture(self.db)
        self.c=self.connect();self.addCleanup(self.c.close)
        for obj in (services,dev):
            p=patch.object(obj,'DB_NAME',str(self.db));p.start();self.addCleanup(p.stop)
        self.client=services.app.test_client()

    def connect(self):
        c=sqlite3.connect(self.db,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

    def offer(self,mode='spotlight',owner='one'):
        return get_offer(self.c,owner,mode,random.Random(4))

    def answer(self,mode='spotlight',owner='one',**fields):
        offer=self.offer(mode,owner)
        default={'allocations':[5,4,2,1]} if mode=='spotlight' else {'maps':[dict(map='mood',x=2,y=1)]}
        return save_answer(self.c,owner,mode,dict(token=offer['token'],**(fields or default)))

    def scalar(self,sql):return self.c.execute(sql).fetchone()[0]

    def test_refresh_resumes_one_offer_with_distinct_frozen_slots(self):
        first=self.offer()
        for _ in range(20):self.assertEqual(self.offer(),first)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM judgement_rounds'),1)
        self.assertEqual(len({s['id'] for s in first['songs']}),4)
        self.assertEqual([s['slot'] for s in first['songs']],[0,1,2,3])
        self.assertFalse({'elo_score','highest_elo'} & first['songs'][0].keys())

    def test_budget_validates_types_sum_size_and_mode_fields(self):
        offer=self.offer()
        invalid=[[3,3,3,True],[3,3,3,3.0],[3,3,3,2],[13,0,0,-1],[6,6],['3',3,3,3],[float('nan'),4,4,4]]
        for points in invalid:
            with self.subTest(points=points),self.assertRaises(JudgementError):
                save_answer(self.c,'one','spotlight',dict(token=offer['token'],allocations=points))
        with self.assertRaises(JudgementError):save_answer(self.c,'one','spotlight',dict(token=offer['token'],allocations=[3]*4,choice=1))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM spotlight_allocations'),0)

    def test_equal_shares_neutral_zero_and_extreme_support_are_preserved(self):
        self.assertEqual(support(3),.5);self.assertEqual(support(0),0);self.assertEqual(support(12),1)
        self.assertGreater(support(10),support(7))
        self.answer(allocations=[3]*4)
        self.assertTrue(all(r['mean_support']==.5 for r in spotlight_records(self.c).values()))

    def test_spotlight_does_not_invent_votes_or_change_public_elo(self):
        before=[tuple(r) for r in self.c.execute('SELECT id,elo_score,matches_played FROM songs')]
        self.answer()
        self.assertEqual(before,[tuple(r) for r in self.c.execute('SELECT id,elo_score,matches_played FROM songs')])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM preference_events'),0)
        self.assertEqual(self.scalar("SELECT SUM(appearances) FROM mode_exposures WHERE mode='spotlight'"),4)

    def test_receipt_is_idempotent_and_conflicting_answer_is_rejected(self):
        o=self.offer();payload=dict(token=o['token'],allocations=[12,0,0,0])
        a=save_answer(self.c,'one','spotlight',payload);b=save_answer(self.c,'one','spotlight',payload)
        self.assertFalse(a['replayed']);self.assertTrue(b['replayed']);self.assertEqual(a['id'],b['id'])
        with self.assertRaises(JudgementError):save_answer(self.c,'one','spotlight',dict(payload,allocations=[0,12,0,0]))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM spotlight_allocations'),4)

    def test_concurrent_retries_commit_one_receipt_and_one_listening_set(self):
        o=self.offer();payload=dict(token=o['token'],allocations=[3]*4,
            listening=dict(version=1,decision_ms=5000,songs=[dict(song_id=s['id'],seconds=2) for s in o['songs']]))
        def submit(_):
            c=self.connect()
            try:return save_answer(c,'one','spotlight',payload)['replayed']
            finally:c.close()
        with ThreadPoolExecutor(max_workers=5) as pool:out=list(pool.map(submit,range(8)))
        self.assertEqual(out.count(False),1);self.assertEqual(self.scalar('SELECT COUNT(*) FROM listening_observations'),4)

    def test_owner_and_mode_cannot_be_changed(self):
        o=self.offer()
        for owner,mode,fields in [('other','spotlight',dict(allocations=[3]*4)),('one','vibe',dict(maps=[dict(map='mood',x=1,y=1)]))]:
            with self.assertRaises(JudgementError):save_answer(self.c,owner,mode,dict(token=o['token'],**fields))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM judgement_rounds WHERE status='answered'"),0)

    def test_sql_close_guard_rejects_incomplete_or_cross_mode_facts(self):
        o=self.offer();rid=o['id']
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("UPDATE judgement_rounds SET status='answered',closed_at=created_at+1,answer_hash=? WHERE id=?",('a'*64,rid))
        self.c.rollback()
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO vibe_placements VALUES(?,'mood',1,2)",(rid,))
        self.c.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("INSERT INTO judgement_rounds(token,owner_hash,mode,status,created_at,closed_at,answer_hash) VALUES(?,?,'spotlight','answered',1,2,?)",('x'*43,'y'*64,'z'*64))
        self.c.rollback()

    def test_three_maps_are_independent_and_missing_axes_are_not_zero(self):
        a=self.answer('vibe',maps=[dict(map='mood',x=0,y=4),dict(map='craft',x=3,y=2)])
        self.assertEqual(len(a['maps']),2)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM vibe_placements'),2)
        stats=build_judgement_stats(self.c,'vibe')['details']
        self.assertEqual(next(m for m in stats['maps'] if m['key']=='sound')['placements'],0)
        self.assertAlmostEqual(diagnostics(self.c,'vibe')['mean'],2/3/12)
        next_offer=self.offer('vibe');self.assertEqual(len(next_offer['suggested_maps']),3)

    def test_vibe_rejects_bad_or_duplicate_maps_and_oversized_themes(self):
        o=self.offer('vibe')
        for maps in [[],[dict(map='unknown',x=1,y=1)],[dict(map='mood',x=True,y=1)],
                     [dict(map='mood',x=1,y=5)],[dict(map='mood',x=1,y=1)]*2]:
            with self.subTest(maps=maps),self.assertRaises(JudgementError):save_answer(self.c,'one','vibe',dict(token=o['token'],maps=maps))
        with self.assertRaises(JudgementError):save_answer(self.c,'one','vibe',dict(token=o['token'],maps=[dict(map='mood',x=1,y=1)],themes=[1,1]))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM vibe_placements'),0)

    def test_themes_are_optional_annotations_and_do_not_edit_catalogue(self):
        before=list(self.c.execute('SELECT * FROM song_genres'))
        self.answer('vibe',maps=[dict(map='sound',x=4,y=0)],themes=[2])
        self.assertEqual(before,list(self.c.execute('SELECT * FROM song_genres')))
        self.answer('vibe',maps=[dict(map='mood',x=1,y=1)],themes=[])
        self.answer('vibe')
        stats=build_judgement_stats(self.c,'vibe')['details']
        self.assertEqual(stats['theme_reviewed_rounds'],2)
        self.assertEqual(stats['themes'][0]['reviewed_round_share'],50)

    def test_removed_tag_is_archived_and_retry_remains_idempotent(self):
        o=self.offer('vibe');payload=dict(token=o['token'],maps=[dict(map='mood',x=1,y=1)],themes=[2])
        save_answer(self.c,'one','vibe',payload)
        self.c.execute('DELETE FROM genres WHERE id=2');self.c.commit()
        r=save_answer(self.c,'one','vibe',payload)
        self.assertTrue(r['replayed']);self.assertIsNone(r['themes'][0]['id']);self.assertEqual(r['themes'][0]['label'],'bridge')

    def test_skip_does_not_create_evidence_and_abandoned_storage_is_pruned(self):
        get_offer(self.c,'ancient','spotlight',now=1)
        self.answer(skip=True)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM mode_exposures WHERE mode='spotlight'"),0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM spotlight_allocations'),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM judgement_rounds WHERE owner_hash='nonexistent'"),0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM judgement_rounds'),1)

    def test_deleted_song_keeps_history_but_drops_current_projection(self):
        o=self.offer();self.answer();sid=o['songs'][0]['id']
        self.c.execute('DELETE FROM song_artists WHERE song_id=?',(sid,));self.c.execute('DELETE FROM song_genres WHERE song_id=?',(sid,))
        self.c.execute('DELETE FROM songs WHERE id=?',(sid,));self.c.commit()
        s=build_judgement_stats(self.c,'spotlight')
        archived=next(s for s in s['history'][0]['songs'] if s['song_key']==sid)
        self.assertIsNone(archived['id']);self.assertEqual(archived['title'],f'Song {sid}')
        self.assertNotIn(sid,spotlight_records(self.c));self.assertFalse(self.c.execute('PRAGMA foreign_key_check').fetchall())

    def test_pending_song_loss_regenerates_offer_and_no_previews_disables_modes(self):
        o=self.offer();sid=o['songs'][0]['id'];self.c.execute('UPDATE songs SET audio_url=NULL WHERE id=?',(sid,));self.c.commit()
        n=self.offer();self.assertNotEqual(n['token'],o['token']);self.assertNotIn(sid,[s['id'] for s in n['songs']])
        self.c.execute('UPDATE songs SET audio_url=NULL');self.c.commit()
        with self.assertRaises(JudgementError):self.offer('vibe')

    def test_read_projections_never_write_or_expose_receipt_tokens(self):
        for mode in ('spotlight','vibe'):self.answer(mode)
        before=capture(self.c)
        for mode in ('spotlight','vibe'):
            report=build_judgement_stats(self.c,mode);diagnostics(self.c,mode)
            self.assertNotIn('token',report['history'][0]);self.assertIn('listening_data',report)
        self.assertEqual(before,capture(self.c))

    def test_fresh_rates_are_unknown_but_coverage_is_zero(self):
        for mode in ('spotlight','vibe'):
            s=build_judgement_stats(self.c,mode);self.assertEqual(s['summary']['rounds'],0);self.assertEqual(s['summary']['coverage'],0)
            self.assertIsNone(s['listening_data']['mean'])

    def test_adaptive_weights_move_to_unseen_and_new_songs_without_repair(self):
        self.answer();before=diagnostics(self.c,'spotlight')
        played=[p for p in before['probabilities'] if p['exposure']]
        unseen=[p for p in before['probabilities'] if not p['exposure']]
        self.assertGreater(unseen[0]['base_probability'],played[0]['base_probability'])
        self.c.execute("INSERT INTO songs(id,title,audio_url) VALUES(99,'New song','preview')");self.c.commit()
        after=diagnostics(self.c,'spotlight');self.assertEqual(after['eligible'],13)
        self.assertAlmostEqual(sum(r['base_probability'] for r in after['probabilities']),1)
        self.assertGreater(next(r for r in after['probabilities'] if r['song_id']==99)['base_probability'],played[0]['base_probability'])

    def test_partial_listening_is_unknown_and_retry_cannot_replace_measured_time(self):
        o=self.offer();payload=dict(token=o['token'],allocations=[3]*4,listening=dict(version=1,decision_ms=5000,songs=[dict(song_id=o['songs'][0]['id'],seconds=1)]))
        save_answer(self.c,'one','spotlight',payload);self.assertEqual(self.scalar('SELECT COUNT(*) FROM listening_observations'),0)
        payload['listening']['songs']=[dict(song_id=s['id'],seconds=2) for s in o['songs']]
        save_answer(self.c,'one','spotlight',payload);self.assertEqual(self.scalar('SELECT COUNT(*) FROM listening_observations'),0)

    def test_exports_and_canonical_rebuild_retain_all_new_facts_and_ids(self):
        for mode in ('spotlight','vibe'):self.answer(mode)
        self.offer('spotlight',owner='pending')
        target=Path(self.tmp.name)/'rebuilt.db';export=Path(self.tmp.name)/'all.json'
        before=capture(self.c);write_export(self.db,export);rebuild(read_export(export),target)
        with readonly(target) as c:reconcile(before,capture(c));self.assertEqual(before,capture(c))
        raw=sql_dump(self.c);c=sqlite3.connect(':memory:');c.executescript(raw);c.row_factory=sqlite3.Row
        self.assertEqual(capture(c),before);c.close()

    def test_v15_upgrade_preserves_catalogue_results_extensions_and_backup(self):
        path=Path(self.tmp.name)/'old.db';fixture(path,schema15=True)
        c=sqlite3.connect(path);c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE note(value BLOB)');c.execute("INSERT INTO note(rowid,value) VALUES(77,X'00FF')");c.commit()
        before=capture(c);c.close();original=path.read_bytes();migrate(path)
        with readonly(path) as c:reconcile(before,capture(c));self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],17)
        backup=next((path.parent/'database_backups').glob('pre_upgrade_*.db'))
        with readonly(backup) as c:self.assertEqual(capture(c),before)
        first=path.read_bytes();migrate(path);self.assertEqual(path.read_bytes(),first)

    def test_http_contract_ownership_origin_pagination_and_validation(self):
        a=self.client.post('/api/shared-spotlight/round',json={});self.assertEqual(a.status_code,200)
        token=a.json['token'];payload=dict(token=token,allocations=[3]*4)
        other=services.app.test_client();self.assertEqual(other.post('/api/shared-spotlight/answer',json=payload).status_code,403)
        self.assertEqual(self.client.post('/api/shared-spotlight/answer',json=payload,headers={'Origin':'https://elsewhere.invalid'}).status_code,403)
        self.assertEqual(self.client.post('/api/shared-spotlight/answer',json=payload).status_code,200)
        self.assertTrue(self.client.post('/api/shared-spotlight/answer',json=payload).json['replayed'])
        self.assertEqual(self.client.get('/api/shared-spotlight/stats?page_size=51').status_code,400)
        self.assertEqual(self.client.get('/api/shared-spotlight/stats?page=100').json['history_page'],1)
        self.assertEqual(self.client.get('/api/mode-updates').json['vibe']['max_themes'],8)

    def test_overall_pref_family_is_capped_and_context_does_not_fake_quality(self):
        o=vote_offer(self.c,'vote','standard',lambda:tuple(services.get_song_full(s,self.c) for s in (1,2)))
        save_vote(self.c,'vote',dict(token=o['token'],winner_id=1,loser_id=2,mode='standard',rules_version=1))
        before=overall.evaluate(collection(True))
        self.answer('vibe')
        after=overall.evaluate(collection(True))
        self.assertEqual([r['score'] for r in before['entities']['songs']],[r['score'] for r in after['entities']['songs']])
        self.assertTrue(all(m['score_weight']==0 for m in after['calibration']['context_modes']))
        self.answer('spotlight');fresh=overall.evaluate(collection(True),details=True)
        self.assertAlmostEqual(sum(m['weight'] for m in fresh['calibration']['modes']),100)
        self.assertEqual(len(fresh['calibration']['families']),5)
        self.assertIn('spotlight',next(f for f in fresh['calibration']['modes'] if f['key']=='spotlight')['key'])
        self.assertEqual(fresh['calibration']['metrics']['spotlight_support']['appearances'],4)

    def test_mode_reset_cascades_facts_and_keeps_other_modes_and_library(self):
        for mode in ('spotlight','vibe'):self.answer(mode)
        with self.client.session_transaction() as session:session['is_admin']=True
        r=self.client.post('/api/dev/reset-history/vibe',json={'confirmation':'RESET VIBE'});self.assertEqual(r.status_code,200)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM vibe_placements'),0);self.assertEqual(self.scalar('SELECT COUNT(*) FROM spotlight_allocations'),4)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM songs'),12)


if __name__=='__main__':unittest.main()
