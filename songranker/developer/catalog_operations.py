"""Reviewable Singles moves. Catalogue placement never rewrites game facts."""
import hashlib
import json

from songranker.developer.catalog_sources import current_source
from songranker.storage.database_io import quote


def single_title(conn,title,artist,song_id=None):
    """Keep hidden release names unique instead of joining unrelated recordings."""
    for candidate in (f'{title} - Single',f'{title} ({artist}) - Single'):
        rows=conn.execute('SELECT id FROM albums WHERE title=? COLLATE NOCASE',(candidate,)).fetchall()
        if not rows:return candidate
        if len(rows)==1:
            members=[r[0] for r in conn.execute('SELECT id FROM songs WHERE album_id=?',(rows[0]['id'],))]
            if not members or members==[song_id]:return candidate
    # Extremely repetitive names still cannot silently merge unrelated tracks.
    i=2
    while conn.execute('SELECT 1 FROM albums WHERE title=? COLLATE NOCASE',(f'{title} ({artist}, {i}) - Single',)).fetchone():i+=1
    return f'{title} ({artist}, {i}) - Single'


def album_references(conn,album_id,exclude_song=None):
    references=[]
    for table, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        for fk in conn.execute('PRAGMA foreign_key_list('+quote(table)+')'):
            if fk['table']!='albums':continue
            sql='SELECT COUNT(*) FROM '+quote(table)+' WHERE '+quote(fk['from'])+'=?'
            args=[album_id]
            if table=='songs' and exclude_song is not None:sql+=' AND id!=?';args.append(exclude_song)
            count=conn.execute(sql,args).fetchone()[0]
            if count:references.append(dict(table=table,count=count))
    triggers=conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='albums'").fetchone()[0]
    if triggers:references.append(dict(table='custom album rules',count=triggers))
    return references


def remove_empty_album(conn,album_id):
    if album_id is None:return dict(removed=False,reason='No previous album.')
    refs=album_references(conn,album_id)
    if refs:return dict(removed=False,reason='Previous album kept for linked tracks or saved records.',references=refs)
    removed=conn.execute('DELETE FROM albums WHERE id=?',(album_id,)).rowcount
    return dict(removed=bool(removed),reason='Empty previous album removed.' if removed else 'Previous album already removed.')


def single_plan(conn,song_id):
    song=conn.execute('SELECT * FROM songs WHERE id=?',(song_id,)).fetchone()
    if not song:return None
    album=conn.execute('SELECT * FROM albums WHERE id=?',(song['album_id'],)).fetchone()
    artists=[r[0] for r in conn.execute('SELECT a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id WHERE sa.song_id=? ORDER BY a.id',(song_id,))]
    saved=current_source(conn,song_id)
    source=saved['source'] if saved else {}
    day=song['release_date'] or source.get('release_date') or (album['release_date'] if album else '') or ''
    origin=song['release_date_origin'] if song['release_date'] else 'apple' if source.get('release_date') else 'album' if day else None
    title=single_title(conn,song['title'],', '.join(artists) or 'Unknown artist',song_id)
    already=bool(album and album['title'].strip().casefold().endswith(' - single'))
    refs=album_references(conn,album['id'],song_id) if album else []
    target=conn.execute('SELECT * FROM albums WHERE title=? COLLATE NOCASE',(title,)).fetchone()
    metadata={key:song[key] for key in ('id','title','album_id','audio_url','track_number','release_date','release_date_origin')}
    state=dict(song=metadata,album=dict(album) if album else None,artists=artists,source_id=saved['id'] if saved else None,source_revision=saved['snapshot'] if saved else None,
               destination=dict(target) if target else None,references=refs)
    fingerprint=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return dict(song_id=song_id,title=song['title'],artist=', '.join(artists),source_album=dict(album) if album else None,
        destination_title=album['title'] if already else title,release_date=day,release_date_origin=origin,
        already_single=already,cleanup_possible=bool(album and not refs and not already),references=refs,
        fingerprint=fingerprint)
