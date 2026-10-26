"""Verified imports and Singles moves: real HTTP, isolated DBs, mocked Apple only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
import json
import sqlite3
import time
import unittest

import test_preferences as fixture
from songranker.developer import catalog_sources as sources
from songranker.developer import dev
from songranker.developer import dev_catalog, dev_tags
from songranker import services
from songranker.overall import shelf_eligible_ids
from songranker.modes import trivia
from songranker.modes import guesser, shelves
from songranker.storage.database import (migrate, initialize_database)
from songranker.storage.database_io import (capture, readonly, reconcile, write_export, read_export, rebuild)
from songranker.storage.database_schema import SCHEMA_VERSION


def apple(**changes):
    return dict(kind='song',trackId=9001,collectionId=8001,artistId=7001,trackName='New Song',artistName='Artist, One',
        collectionName='New Album',trackExplicitness='explicit',collectionExplicitness='explicit',
        trackCensoredName='N*w Song',trackViewUrl='https://music.apple.com/gb/album/new/8001?i=9001',
        collectionViewUrl='https://music.apple.com/gb/album/new/8001',previewUrl='https://audio-ssl.itunes.apple.com/test/preview.m4a',
        artworkUrl100='https://is1-ssl.mzstatic.com/image/thumb/Music/asset/100x100bb.jpg',trackTimeMillis=213000,
        releaseDate='2020-04-05T00:00:00Z',trackNumber=1,discNumber=1,discCount=1,primaryGenreName='New genre',**changes) if not changes else {**apple(),**changes}


class SourceFieldTests(unittest.TestCase):
    def test_content_flags_are_distinct_and_never_inferred_from_censored_titles(self):
        for value,label in [('explicit','Explicit'),('cleaned','Cleaned'),('notExplicit','Not explicit'),(None,'Not explicit'),('unexpected','Not explicit'),([], 'Not explicit')]:
            source=sources.observation(apple(trackExplicitness=value,trackCensoredName='S***'),'gb')
            self.assertEqual(sources.public_source(source)['content_label'],label)
        self.assertFalse(sources.public_source(sources.observation(apple(trackName='Song (Clean)'), 'gb'))['radio_hint'])
        self.assertTrue(sources.public_source(sources.observation(apple(trackName='Song (Radio Edit)'), 'gb'))['radio_hint'])

    def test_disc_positions_are_not_flattened_and_dates_are_not_guessed(self):
        data=sources.apple_metadata(apple(discNumber=2,discCount=2,trackNumber=3,releaseDate='not a date'))
        self.assertEqual(data['track_number'],3);self.assertEqual(data['disc_number'],2);self.assertEqual(data['source_track_number'],3)
        self.assertEqual(data['release_date'],'')

    def test_store_urls_and_identifiers_are_validated(self):
        for url in ('javascript:alert(1)','https://music.apple.com.evil/a','https://x@music.apple.com/a','https://music.apple.com:123/a'):
            self.assertEqual(sources.store_link(url),'')
        self.assertTrue(sources.store_link('http://itunes.apple.com/album/id1').startswith('https://'))
        for value in (True,False,-1,0,'1.5','1e9',None):self.assertIsNone(sources.identifier(value))
        self.assertEqual(sources.identifier('009001'),'9001')
        self.assertEqual(sources.store_code('GB'),'gb')
        for value in ('g','GBR','1b','éa',[],None):
            with self.assertRaises(ValueError):sources.store_code(value)


class CatalogSourceTests(unittest.TestCase):
    setUp=fixture.PreferenceTests.setUp
    connect=fixture.PreferenceTests.connect
    scalar=fixture.PreferenceTests.scalar
    vote=fixture.PreferenceTests.vote
    offer=fixture.PreferenceTests.offer
    payload=fixture.PreferenceTests.payload

    def client(self):
        client=services.app.test_client()
        with client.session_transaction() as session:session['is_admin']=True
        return client

    def result(self,client,track=None,query='New Song',country='gb'):
        with patch.object(dev,'apple_lookup',return_value={'results':[track or apple()]}) as lookup:
            response=client.get('/api/dev/search_apple',query_string=dict(q=query,country=country))
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(len(response.json),1)
        return response.json[0],lookup.call_args[0][0]

    def add(self,client,row,**data):
        return client.post('/api/dev/add_song',json=dict(source_token=row['source_token'],**data))

    def link(self,client,sid,row,**data):
        current=client.get('/api/dev/song-source/'+str(sid))
        self.assertEqual(current.status_code,200)
        return client.post('/api/dev/song-source/'+str(sid),json=dict(fingerprint=current.json['fingerprint'],source_token=row['source_token'],**data))

    def solo(self,sid=1):
        self.conn.execute("INSERT INTO albums(id,title,cover_url,release_date) VALUES(101,'Old Only','/old-cover.jpg','1998-02-03')")
        self.conn.execute('UPDATE songs SET album_id=101,track_number=3 WHERE id=?',(sid,));self.conn.commit()

    def move(self,client,sid,**data):
        plan=client.get('/api/dev/single/'+str(sid))
        self.assertEqual(plan.status_code,200,plan.get_json())
        with patch.object(services,'create_database_backup',return_value=str(Path(self.temp.name)/'move.db')):
            return client.post('/api/dev/single/'+str(sid),json=dict(fingerprint=plan.json['fingerprint'],**data))

    def test_all_new_developer_routes_require_authentication(self):
        client=services.app.test_client()
        for url in ('/api/dev/song-sources','/api/dev/song-source/1','/api/dev/album-tracks/1','/api/dev/single/1'):
            self.assertEqual(client.get(url).status_code,302)
        self.assertEqual(client.post('/api/dev/single/1',json={}).status_code,302)

    def test_search_requests_a_bounded_explicit_inclusive_store_batch(self):
        row,url=self.result(self.client(),query='Name & Song',country='GB')
        params=parse_qs(urlsplit(url).query)
        self.assertEqual(params['term'],['Name & Song']);self.assertEqual(params['limit'],['100'])
        self.assertEqual(params['explicit'],['Yes']);self.assertEqual(params['country'],['gb'])
        self.assertEqual((row['source']['content_label'],row['source']['duration_ms']),('Explicit',213000))

    def test_link_country_takes_precedence_and_album_results_deduplicate_ids(self):
        client=self.client()
        with patch.object(dev,'apple_lookup',return_value={'results':[{'wrapperType':'collection'},apple(),apple(),apple(trackId=9002)]}) as lookup:
            response=client.get('/api/dev/search_apple',query_string={'q':'https://music.apple.com/us/album/test/8001','country':'gb'})
        self.assertEqual(response.status_code,200);self.assertEqual(len(response.json),2)
        self.assertTrue(all(r['source']['storefront']=='us' for r in response.json))
        self.assertEqual(parse_qs(urlsplit(lookup.call_args[0][0]).query)['id'],['8001'])

    def test_invalid_country_and_invalid_source_entries_do_not_write(self):
        client=self.client()
        with patch.object(dev,'apple_lookup') as lookup:
            self.assertEqual(client.get('/api/dev/search_apple?q=x&country=bad').status_code,400);lookup.assert_not_called()
        with patch.object(dev,'apple_lookup',return_value={'results':[apple(trackId=None),None,{'kind':'music-video','trackName':'Video'}]}):
            response=client.get('/api/dev/search_apple?q=x')
        self.assertEqual(response.json,[]);self.assertEqual(self.scalar('SELECT COUNT(*) FROM song_sources'),0)

    def test_title_matches_remain_unverified_then_become_confirmed_after_linking(self):
        client=self.client();row,_=self.result(client,apple(trackName='Song 1'))
        self.assertEqual(row['library_matches'][0]['kind'],'title_artist')
        self.assertEqual(self.link(client,1,row).status_code,200)
        row,_=self.result(client,apple(trackName='Song 1'))
        self.assertEqual(row['library_matches'][0]['kind'],'source_id')

    def test_signed_offer_owns_metadata_and_preserves_comma_artist_names(self):
        client=self.client();row,_=self.result(client)
        response=self.add(client,row,title='Forged',artist='Fake',source={'explicitness':'cleaned'},genres='Custom')
        self.assertEqual(response.status_code,200,response.get_json());sid=response.json['song_id']
        song=self.conn.execute('SELECT * FROM songs WHERE id=?',(sid,)).fetchone()
        self.assertEqual((song['title'],song['release_date'],song['release_date_origin']),('New Song','2020-04-05','apple'))
        self.assertEqual(self.scalar(f'SELECT COUNT(*) FROM song_artists WHERE song_id={sid}'),1)
        saved=sources.current_source(self.conn,sid)['source'];self.assertEqual(saved['explicitness'],'explicit')
        names=[r[0] for r in self.conn.execute('SELECT g.name FROM genres g JOIN song_genres sg ON sg.genre_id=g.id WHERE sg.song_id=?',(sid,))]
        self.assertEqual(set(names),{'Custom','New genre'})

    def test_forged_and_foreign_browser_tokens_do_not_import(self):
        first=self.client();other=self.client();row,_=self.result(first)
        self.assertEqual(self.add(other,row).status_code,400)
        altered=dict(row,source_token=row['source_token']+'bad')
        self.assertEqual(self.add(first,altered).status_code,400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM songs'),10)

    def test_expired_offers_request_a_new_search(self):
        with patch('time.time',return_value=time.time()-90000):
            client=self.client();row,_=self.result(client)
        response=self.add(client,row);self.assertEqual(response.status_code,400)
        self.assertIn('expired',response.json['message'])

    def test_import_retry_is_one_song_and_one_source_observation(self):
        client=self.client();row,_=self.result(client)
        first=self.add(client,row);again=self.add(client,row)
        self.assertEqual((first.status_code,again.status_code),(200,200))
        self.assertTrue(again.json['already_present']);self.assertEqual(first.json['song_id'],again.json['song_id'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM song_sources'),1)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM songs'),11)

    def test_known_collaboration_respects_commas_without_splitting_unknown_acts(self):
        self.conn.execute("INSERT INTO artists(id,name) VALUES(2,'Other')")
        self.conn.execute('INSERT INTO song_artists VALUES(1,2)');self.conn.commit()
        client=self.client();matched,_=self.result(client,apple(trackName='Song 1',artistName='Artist, One & Other'))
        self.assertEqual(matched['library_matches'][0]['kind'],'title_artist')
        row,_=self.result(client,apple(artistName='Artist, One & Other'))
        response=self.add(client,row);self.assertEqual(response.status_code,200)
        names=[r[0] for r in self.conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=?',(response.json['song_id'],))]
        self.assertEqual(set(names),{'Artist, One','Other'})
        self.assertEqual(sources.artist_names(self.conn,'Unknown & Act'),['Unknown & Act'])

    def test_matching_titles_need_explicit_separate_add_and_do_not_use_artist_prefixes(self):
        client=self.client();row,_=self.result(client,apple(trackName='Song 1'))
        self.assertEqual(self.add(client,row).status_code,409)
        self.assertEqual(self.add(client,row,allow_duplicate=True,placement='single').status_code,200)
        row,_=self.result(client,apple(trackId=9010,trackName='Song 2',artistName='Artist, Onyx'))
        self.assertEqual(row['library_matches'],[])
        self.assertEqual(self.add(client,row).status_code,200)

    def test_multidisc_source_and_single_import_preserve_original_position(self):
        client=self.client();row,_=self.result(client,apple(trackNumber=8,discNumber=2,discCount=2))
        response=self.add(client,row,placement='single');self.assertEqual(response.status_code,200)
        sid=response.json['song_id'];song=self.conn.execute('SELECT s.*,a.title album FROM songs s JOIN albums a ON a.id=s.album_id WHERE s.id=?',(sid,)).fetchone()
        self.assertTrue(song['album'].endswith(' - Single'));self.assertIsNone(song['track_number'])
        self.assertEqual(sources.current_source(self.conn,sid)['source']['metadata']['source_track_number'],8)

    def test_source_only_link_does_not_change_local_metadata_scores_or_dates(self):
        self.vote();client=self.client();before=capture(self.conn);row,_=self.result(client)
        response=self.link(client,1,row);self.assertEqual(response.status_code,200,response.get_json())
        after=capture(self.conn)
        for table in before['tables']:
            if table!='song_sources':self.assertEqual(before['tables'][table],after['tables'][table],table)

    def test_relink_replaces_current_source_and_same_link_retry_is_noop(self):
        client=self.client();first,_=self.result(client);second,_=self.result(client,apple(trackId=9002,trackExplicitness='cleaned'))
        for row in (first,second,first,first):self.assertEqual(self.link(client,1,row).status_code,200)
        history=client.get('/api/dev/song-source/1').json
        self.assertEqual(history['history'],[]);self.assertEqual(history['current']['content_label'],'Explicit')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM song_sources'),1)

    def test_one_source_cannot_be_linked_to_two_current_songs(self):
        client=self.client();row,_=self.result(client);self.link(client,1,row)
        self.assertEqual(self.link(client,2,row).status_code,400)
        self.assertIsNone(sources.current_source(self.conn,2))

    def test_stale_source_review_is_rejected_but_unrelated_votes_are_allowed(self):
        client=self.client();row,_=self.result(client);review=client.get('/api/dev/song-source/1').json
        self.vote()
        response=client.post('/api/dev/song-source/1',json=dict(source_token=row['source_token'],fingerprint=review['fingerprint']))
        self.assertEqual(response.status_code,200)
        review=client.get('/api/dev/song-source/1').json
        self.conn.execute("UPDATE songs SET title='Changed' WHERE id=1");self.conn.commit()
        self.assertEqual(client.post('/api/dev/song-source/1',json=dict(source_token=row['source_token'],fingerprint=review['fingerprint'])).status_code,409)

    def test_refresh_keeps_current_single_placement_and_custom_tags(self):
        self.conn.execute("UPDATE albums SET title='Song 1 - Single',release_date='1990-01-01' WHERE id=1")
        self.conn.commit();self.vote();client=self.client();before=self.conn.execute('SELECT elo_score,matches_played FROM songs WHERE id=1').fetchone()
        row,_=self.result(client)
        with patch.object(dev,'create_database_backup',return_value='backup.db'):
            response=self.link(client,1,row,refresh_metadata=True)
        self.assertEqual(response.status_code,200,response.get_json())
        song=self.conn.execute('SELECT * FROM songs WHERE id=1').fetchone()
        self.assertEqual((song['album_id'],song['track_number'],song['release_date']),(1,1,'2020-04-05'))
        self.assertEqual(tuple(before),tuple(song[k] for k in ('elo_score','matches_played')))
        self.assertEqual(self.conn.execute('SELECT release_date FROM albums WHERE id=1').fetchone()[0],'1990-01-01')
        self.assertTrue(self.conn.execute('SELECT 1 FROM song_genres WHERE song_id=1 AND genre_id=1').fetchone())

    def test_refresh_source_album_cleans_only_unreferenced_empty_album_and_keeps_pending_answers(self):
        self.solo();client=self.client();pending=client.get('/api/trivia/round',headers={'Content-Type':'application/json'}).json
        row,_=self.result(client)
        with patch.object(dev,'create_database_backup',return_value='backup.db'):
            response=self.link(client,1,row,refresh_metadata=True,use_source_album=True)
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertTrue(response.json['album_cleanup']['removed'])
        self.assertFalse(self.conn.execute('SELECT 1 FROM albums WHERE id=101').fetchone())
        again=client.get('/api/trivia/round',headers={'Content-Type':'application/json'}).json
        self.assertEqual(again['token'],pending['token'])

    def test_unchanged_manual_edit_preserves_existing_artist_links_and_song_date(self):
        self.conn.execute("UPDATE songs SET release_date='2001-01-01',release_date_origin='manual' WHERE id=1");self.conn.commit()
        client=self.client();response=client.post('/api/dev/edit_song/1',json=dict(title='Song 1',artist='Artist, One',album='Album',audio_url='preview',genres='Tag',track_number=1))
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM song_artists WHERE song_id=1'),1)
        self.assertEqual(self.conn.execute('SELECT release_date FROM songs WHERE id=1').fetchone()[0],'2001-01-01')

    def test_manual_dates_are_per_song_and_invalid_input_is_atomic(self):
        client=self.client();self.conn.execute("UPDATE albums SET release_date='1990-01-01' WHERE id=1");self.conn.commit()
        payload=dict(title='Song 1',artist='Artist, One',album='Album',release_date='2001-02-03')
        self.assertEqual(client.post('/api/dev/edit_song/1',json=payload).status_code,200)
        self.assertEqual(self.conn.execute('SELECT release_date FROM albums WHERE id=1').fetchone()[0],'1990-01-01')
        payload['release_date']='2001-02-30';before=capture(self.conn)
        self.assertEqual(client.post('/api/dev/edit_song/1',json=payload).status_code,400)
        self.assertEqual(capture(self.conn),before)

    def test_single_preview_is_read_only_and_move_keeps_game_facts_and_date(self):
        self.solo();self.vote();client=self.client();before=capture(self.conn)
        plan=client.get('/api/dev/single/1');self.assertEqual(plan.status_code,200)
        self.assertEqual(capture(self.conn),before)
        result=self.move(client,1);self.assertEqual(result.status_code,200,result.get_json())
        song=self.conn.execute('SELECT * FROM songs WHERE id=1').fetchone()
        self.assertEqual((song['release_date'],song['release_date_origin'],song['track_number']),('1998-02-03','album',None))
        self.assertTrue(result.json['album_cleanup']['removed'])
        after=capture(self.conn)
        for table in ('preference_events','preference_mode_ratings','preference_rating_projection','song_artists','song_genres'):
            self.assertEqual(before['tables'][table],after['tables'][table],table)
        again=self.move(client,1);self.assertTrue(again.json['already_single'])

    def test_song_date_precedes_source_and_album_dates_when_moving(self):
        self.solo();client=self.client();row,_=self.result(client);self.link(client,1,row)
        self.conn.execute("UPDATE songs SET release_date='2000-01-01',release_date_origin='manual' WHERE id=1");self.conn.commit()
        result=self.move(client,1);self.assertEqual(result.status_code,200)
        self.assertEqual(self.conn.execute('SELECT release_date_origin,release_date FROM songs WHERE id=1').fetchone()[:],('manual','2000-01-01'))

    def test_verified_source_date_is_carried_before_album_fallback(self):
        self.solo();client=self.client();row,_=self.result(client);self.link(client,1,row)
        self.assertEqual(self.move(client,1).status_code,200)
        self.assertEqual(self.conn.execute('SELECT release_date_origin,release_date FROM songs WHERE id=1').fetchone()[:],('apple','2020-04-05'))

    def test_missing_dates_remain_unknown_and_shared_albums_are_kept(self):
        client=self.client();result=self.move(client,1)
        self.assertEqual(result.status_code,200);self.assertFalse(result.json['album_cleanup']['removed'])
        self.assertEqual(self.conn.execute('SELECT release_date FROM songs WHERE id=1').fetchone()[0],None)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM songs WHERE album_id=1'),4)

    def test_archive_album_references_survive_a_single_move(self):
        self.solo();self.conn.execute("INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(101,'archive',1,2)")
        for sid in range(1,11):
            slot=1 if sid<=5 else 2
            self.conn.execute('''INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,answer_slot,answer_position)
                VALUES(101,?,?,?,?,?,?,?)''',(sid,sid,101 if slot==1 else 2,slot,(sid-1)%5+1,slot,(sid-1)%5+1))
        self.conn.commit();before=[tuple(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')]
        response=self.move(self.client(),1);self.assertEqual(response.status_code,200)
        self.assertFalse(response.json['album_cleanup']['removed'])
        self.assertEqual(before,[tuple(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')])

    def test_extension_foreign_keys_prevent_empty_album_cleanup(self):
        self.solo();self.conn.execute('CREATE TABLE extra_album_facts(album_id INTEGER REFERENCES albums(id),note TEXT)')
        self.conn.execute("INSERT INTO extra_album_facts VALUES(101,'kept')");self.conn.commit()
        response=self.move(self.client(),1);self.assertEqual(response.status_code,200)
        self.assertFalse(response.json['album_cleanup']['removed'])
        self.assertEqual(self.conn.execute('SELECT note FROM extra_album_facts').fetchone()[0],'kept')

    def test_single_names_do_not_merge_unrelated_same_title_tracks(self):
        self.solo();self.conn.execute("INSERT INTO albums(id,title) VALUES(102,'Song 1 - Single')")
        self.conn.execute('UPDATE songs SET album_id=102 WHERE id=2');self.conn.commit()
        response=self.move(self.client(),1);self.assertEqual(response.status_code,200)
        self.assertNotEqual(response.json['album_id'],102)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM songs WHERE album_id=102'),1)

    def test_stale_single_review_never_moves_a_changed_song(self):
        client=self.client();plan=client.get('/api/dev/single/1').json
        self.conn.execute("UPDATE songs SET title='New title' WHERE id=1");self.conn.commit();before=capture(self.conn)
        response=client.post('/api/dev/single/1',json={'fingerprint':plan['fingerprint']})
        self.assertEqual(response.status_code,409);self.assertEqual(capture(self.conn),before)

    def test_parallel_single_retries_make_one_destination(self):
        self.solo();client=self.client();plan=client.get('/api/dev/single/1').json
        cookie=client.get_cookie(services.app.config['SESSION_COOKIE_NAME']).value;barrier=Barrier(4)
        def run(_):
            c=services.app.test_client();c.set_cookie(services.app.config['SESSION_COOKIE_NAME'],cookie);barrier.wait()
            return c.post('/api/dev/single/1',json={'fingerprint':plan['fingerprint']}).status_code
        with patch.object(services,'create_database_backup',return_value='backup.db'),ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(run,range(4))),[200]*4)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM albums WHERE title='Song 1 - Single'"),1)

    def test_album_inspection_orders_tracks_and_reports_source_unknowns_without_writes(self):
        client=self.client();before=capture(self.conn);result=client.get('/api/dev/album-tracks/1')
        self.assertEqual(result.status_code,200);self.assertEqual([r['id'] for r in result.json['songs']],[1,2,3,4,5])
        self.assertTrue(all(r['source_summary']['content_label']=='Not explicit' for r in result.json['songs']))
        self.assertEqual(capture(self.conn),before)

    def test_source_history_and_dates_survive_export_rebuild_and_sql_restore(self):
        client=self.client();row,_=self.result(client);self.link(client,1,row);self.move(client,1)
        export=Path(self.temp.name)/'all.json';output=Path(self.temp.name)/'rebuilt.db'
        write_export(self.path,export);rebuild(read_export(export),output)
        with readonly(self.path) as a,readonly(output) as b:reconcile(capture(a),capture(b))
        dump=Path(self.temp.name)/'all.sql'
        with readonly(self.path) as a:dump.write_text('\n'.join(a.iterdump()))
        restored=Path(self.temp.name)/'restored.db';initialize_database(restored,dump)
        with readonly(self.path) as a,readonly(restored) as b:reconcile(capture(a),capture(b))

    def test_schema12_upgrade_keeps_legacy_dates_and_source_identity_unknown(self):
        path=Path(self.temp.name)/'twelve.db';conn=sqlite3.connect(path)
        conn.executescript(Path('tests/fixtures/schema_v12.sql').read_text())
        conn.execute("INSERT INTO albums(id,title,release_date) VALUES(1,'Album','2000-01-01')")
        conn.execute("INSERT INTO songs(id,title,album_id,audio_url) VALUES(1,'Old',1,'https://audio-ssl.itunes.apple.com/old.m4a')")
        conn.execute('PRAGMA user_version=12');conn.commit();before=capture(conn)
        dump=Path(self.temp.name)/'twelve.sql';dump.write_text('\n'.join(conn.iterdump()));conn.close()
        migrate(path);restored=Path(self.temp.name)/'twelve-restored.db';initialize_database(restored,dump)
        for target in (path,restored):
            with readonly(target) as conn:
                reconcile(before,capture(conn));self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
                self.assertEqual(tuple(conn.execute('SELECT release_date,release_date_origin FROM songs').fetchone()),(None,None))
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM song_sources').fetchone()[0],0)

    def test_reserved_source_names_fail_closed_without_discarding_extensions(self):
        for ddl in ('CREATE TABLE song_sources(note TEXT)','ALTER TABLE songs ADD COLUMN release_date TEXT'):
            path=Path(self.temp.name)/('collision-'+str(len(ddl))+'.db');conn=sqlite3.connect(path)
            conn.executescript(Path('tests/fixtures/schema_v12.sql').read_text());conn.execute(ddl);conn.execute('PRAGMA user_version=12');conn.commit();before=capture(conn);conn.close()
            with self.assertRaisesRegex(ValueError,'dedicated migration'):migrate(path)
            with readonly(path) as conn:self.assertEqual(capture(conn),before)

    def test_new_assets_load_only_for_developer_page(self):
        client=self.client();page=client.get('/dev/dashboard').get_data(as_text=True)
        self.assertIn('js/dev_catalog.js',page);self.assertIn('css/dev_catalog.css',page)
        public=client.get('/').get_data(as_text=True)
        self.assertNotIn('songranker.developer.dev_catalog.js',public);self.assertNotIn('songranker.developer.dev_catalog.css',public)





class AlbumDiscTests(unittest.TestCase):
    """Multi-disc editing and frozen game facts against isolated databases."""
    setUp = fixture.PreferenceTests.setUp
    connect = fixture.PreferenceTests.connect

    def client(self):
        client = services.app.test_client()
        with client.session_transaction() as session:
            session['is_admin'] = True
        return client

    def test_same_track_number_on_different_discs_and_conflicts_are_atomic(self):
        self.conn.execute("INSERT INTO songs(id,title,album_id,disc_number,track_number) VALUES(11,'Second disc opener',1,2,1)")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE songs SET disc_number=1 WHERE id=11")
        self.conn.rollback()
        for value in (0,-1,True,1.5,[],{}):
            response = self.client().post('/api/dev/bulk_songs',json=dict(song_ids=[11],action='move_album',album_id=1,disc_number=value))
            self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(tuple(self.conn.execute('SELECT disc_number,track_number FROM songs WHERE id=11').fetchone()),(2,1))
        self.assertEqual(sources.track_position_conflicts(self.conn),[])
        self.assertEqual(len(shelves.shelf_pool(self.conn)[1]),6)
        data=dict(albums=[dict(r) for r in self.conn.execute('SELECT * FROM albums')],songs=[dict(r) for r in self.conn.execute('SELECT * FROM songs')])
        self.assertEqual(shelf_eligible_ids(data),set(range(1,12)))

    def test_bulk_combine_discs_keeps_destination_artwork_and_saved_scores(self):
        self.conn.execute("UPDATE albums SET cover_url='preferred-art' WHERE id=1")
        self.conn.execute("UPDATE songs SET elo_score=1337 WHERE id=6")
        self.conn.commit()
        client=self.client()
        response=client.post('/api/dev/bulk_songs',json=dict(song_ids=list(range(6,11)),action='move_album',album_id=1,disc_number=2))
        self.assertEqual(response.status_code,200,response.json)
        rows=client.get('/api/dev/album-tracks/1').json['songs']
        self.assertEqual([(r['disc_number'],r['track_number']) for r in rows],[(d,t) for d in (1,2) for t in range(1,6)])
        self.assertEqual(self.conn.execute('SELECT cover_url FROM albums WHERE id=1').fetchone()[0],'preferred-art')
        self.assertEqual(self.conn.execute('SELECT elo_score FROM songs WHERE id=6').fetchone()[0],1337)
        # Moving into an occupied disc rejects the entire change.
        before=capture(self.conn)
        response=client.post('/api/dev/bulk_songs',json=dict(song_ids=list(range(6,11)),action='move_album',album_id=1,disc_number=1))
        self.assertEqual(response.status_code,400)
        self.assertEqual(capture(self.conn),before)

    def test_round_uses_saved_disc_order_after_catalogue_edit(self):
        # Keep ten tracks across two albums while restarting numbers on disc two.
        for album in (1,2):
            self.conn.execute('UPDATE songs SET track_number=NULL WHERE album_id=?',(album,))
            rows=self.conn.execute('SELECT id FROM songs WHERE album_id=? ORDER BY id',(album,)).fetchall()
            for index,row in enumerate(rows):
                self.conn.execute('UPDATE songs SET disc_number=?,track_number=? WHERE id=?',(1 if index<3 else 2,index+1 if index<3 else index-2,row['id']))
        self.conn.commit()
        client=self.client()
        result=client.post('/api/album-shelves/round',json={'album_count':2})
        self.assertEqual(result.status_code,200,result.json)
        self.assertTrue(all('disc_number' not in s and 'track_number' not in s for s in result.json['songs']))
        items=[dict(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')]
        placements={str(slot):[r['item_slot'] for r in sorted(items,key=shelves.shelf_position) if r['album_slot']==slot] for slot in (1,2)}
        self.conn.execute('UPDATE songs SET track_number=NULL')
        self.conn.execute('UPDATE songs SET disc_number=3,track_number=id')
        self.conn.commit()
        response=client.post('/api/album-shelves/answer',json=dict(token=result.json['token'],placements=placements))
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['points'],30)
        self.assertEqual({a['disc_number'] for a in response.json['answers']},{1,2})
        saved=[dict(r) for r in self.conn.execute('SELECT * FROM album_shelf_items')]
        self.assertTrue(shelves.can_grade(saved,1))
        self.assertEqual(shelves.grade_shelf(saved)['points'],30)
        # An incorrect order across the disc boundary loses relative-order points.
        group=[r for r in saved if r['album_slot']==1]
        group.sort(key=shelves.shelf_position)
        group[0]['answer_position'],group[-1]['answer_position']=group[-1]['answer_position'],group[0]['answer_position']
        self.assertLess(shelves.grade_shelf(saved)['points'],30)

    def test_schema20_sql_restore_defaults_discs_and_preserves_rounds(self):
        old=self.path.parent/'old20.db'
        c=sqlite3.connect(old)
        c.executescript((Path(__file__).with_name('fixtures')/'schema_v20.sql').read_text())
        from songranker.storage.vibe_state import seed_definitions
        seed_definitions(c)
        c.execute("INSERT INTO competition_state VALUES(1,3,1,'{}')")
        c.execute("INSERT INTO preference_replay_state VALUES(1,0,0,'verified_replay',1)")
        c.execute("INSERT INTO albums(id,title) VALUES(91,'Archive')")
        c.execute("INSERT INTO songs(id,title,album_id,track_number) VALUES(92,'Archived song',91,7)")
        c.execute("INSERT INTO album_shelf_rounds(id,token,started_at,completed_at) VALUES(93,'saved',1,2)")
        c.execute('INSERT INTO album_shelf_items(round_id,item_slot,song_id,album_id,album_slot,track_number,answer_slot,answer_position) VALUES(93,1,92,91,1,7,1,1)')
        c.execute('PRAGMA user_version=20');c.commit()
        dump=self.path.parent/'old.sql';dump.write_text('\n'.join(c.iterdump()))
        c.close()
        # Both direct upgrades and SQL dumps with no user_version take the lossless path.
        restored=self.path.parent/'restored.db'
        initialize_database(restored,dump)
        migrate(old)
        for path in (old,restored):
            with readonly(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],22)
                self.assertEqual(tuple(db.execute('SELECT id,disc_number,track_number FROM songs').fetchone()),(92,1,7))
                self.assertEqual(tuple(db.execute('SELECT round_id,disc_number,track_number,answer_position FROM album_shelf_items').fetchone()),(93,1,7,1))
                before=capture(db)
            migrate(path)
            with readonly(path) as db:self.assertEqual(capture(db),before)
        self.assertTrue(list((old.parent/'database_backups').glob('pre_upgrade_*.db')))


if __name__=='__main__':unittest.main()
