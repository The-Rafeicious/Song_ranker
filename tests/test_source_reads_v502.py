"""Fill-only snapshots must remain readable after another source is saved."""
import unittest
from unittest.mock import patch
import test_catalog_sources as fixture
from songranker.developer import catalog_sources as sources, metadata_fill
from songranker.storage.database_io import capture

class SourceReadTests(unittest.TestCase):
    setUp=fixture.CatalogSourceTests.setUp
    connect=fixture.CatalogSourceTests.connect
    client=fixture.CatalogSourceTests.client
    result=fixture.CatalogSourceTests.result
    add=fixture.CatalogSourceTests.add
    link=fixture.CatalogSourceTests.link

    def partial(self):
        remote=fixture.apple(trackId=9009,artistId=None,trackViewUrl=None,
            collectionViewUrl=None,previewUrl=None,releaseDate=None,trackTimeMillis=None)
        source=metadata_fill.merge_source(None,sources.observation(remote,'gb'))
        self.assertNotIn('duration_ms',source)
        self.assertNotIn('audio_url',source['metadata'])
        sources.save_source(self.conn,2,dict(source=source,observed_at=1));self.conn.commit()
        return source

    def test_fill_snapshot_projects_optional_fields_without_writing_it(self):
        self.partial();before=capture(self.conn);client=self.client()
        response=client.get('/api/dev/song-sources')
        self.assertEqual(response.status_code,200)
        summary=response.json['songs']['2']
        self.assertEqual(summary['status'],'linked')
        self.assertEqual(summary['source']['track_id'],'9009')
        self.assertEqual(summary['source']['collection_id'],'8001')
        self.assertEqual(summary['source']['track_url'],'')
        self.assertEqual(summary['content_label'],'Explicit')
        self.assertFalse(summary['preview_matches'])
        self.assertEqual(capture(self.conn),before)

    def test_save_then_batch_reload_succeeds_with_an_unrelated_partial_source(self):
        self.partial();client=self.client();row,_=self.result(client)
        saved=self.link(client,1,row)
        self.assertEqual(saved.status_code,200,saved.get_json())
        response=client.get('/api/dev/song-sources')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['songs']['1']['source']['track_id'],'9001')

    def test_relink_replaces_partial_source_with_one_readable_current_source(self):
        self.partial();client=self.client();row,_=self.result(client)
        self.assertEqual(self.link(client,2,row).status_code,200)
        detail=client.get('/api/dev/song-source/2')
        self.assertEqual(detail.status_code,200)
        self.assertEqual(detail.json['current']['track_id'],'9001')
        self.assertEqual(detail.json['history'],[])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM song_sources WHERE song_id=2').fetchone()[0],1)

    def test_optional_source_names_do_not_break_detail_reads(self):
        source=dict(track_id='9010',storefront='gb',explicitness='unknown')
        sources.save_source(self.conn,1,dict(source=source,observed_at=1));self.conn.commit()
        response=self.client().get('/api/dev/song-source/1')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['current']['title'],'Song 1')
        self.assertEqual(response.json['current']['content_label'],'Not explicit')

if __name__=='__main__':unittest.main()
