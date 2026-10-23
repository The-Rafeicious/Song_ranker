"""Versioned lossless source compression and bounded SQLite storage maintenance."""

import base64
from copy import deepcopy
import json
import logging
from pathlib import Path
import sqlite3
import zlib

PREFIX='srz1:'
MAX_SOURCE_BYTES=1024*1024
# Permanent format-v1 dictionary: schema words and public URL prefixes only.
DICTIONARY=b'album artist title metadata release_date source_track_number track_number disc_count disc_number genres audio_url cover_url collection_id artist_id censored_title collection_explicitness duration_ms explicitness storefront track_id track_url album_url https://music.apple.com/gb/album/ https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview https://is1-ssl.mzstatic.com/image/thumb/Music /300x300bb.jpg /100x100bb.jpg notExplicit explicit cleaned unknown'

def unpack_source(value):
    """Decode bounded plain or dictionary-compressed source JSON, rejecting malformed
    or excessive payloads.
    """
    if not isinstance(value,str):raise ValueError('Source snapshot must be text.')
    try:
        if value.startswith(PREFIX):
            compressed=base64.b64decode(value[len(PREFIX):],validate=True)
            decoder=zlib.decompressobj(zdict=DICTIONARY)
            raw=decoder.decompress(compressed,MAX_SOURCE_BYTES+1)
            if len(raw)>MAX_SOURCE_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError('Invalid or excessive compressed source snapshot.')
        else:raw=value.encode('utf-8')
        if len(raw)>MAX_SOURCE_BYTES:raise ValueError('Source snapshot is too large.')
        result=json.loads(raw)
    except (zlib.error,UnicodeError,TypeError) as error:
        raise ValueError('Cannot read source snapshot; restore a verified backup.') from error
    if not isinstance(result,dict):raise ValueError('Source snapshot must contain an object.')
    return result

def pack_source(value):
    """Encode source metadata losslessly, compressing only when smaller and retaining
    existing valid compressed bytes.
    """
    if isinstance(value,str) and value.startswith(PREFIX):
        unpack_source(value)  # Validate, but retain exact bytes across zlib versions.
        return value
    source=unpack_source(value) if isinstance(value,str) else value
    if not isinstance(source,dict):raise ValueError('Source snapshot must contain an object.')
    raw=json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(raw)>MAX_SOURCE_BYTES:raise ValueError('Source snapshot is too large.')
    encoder=zlib.compressobj(9,zdict=DICTIONARY)
    packed=PREFIX+base64.b64encode(encoder.compress(raw)+encoder.flush()).decode('ascii')
    return packed if len(packed)<len(raw) else raw.decode('utf-8')

def upgrade_state(original):
    """Keep the latest source per song; every other table/value stays untouched."""
    if original['user_version']>15:return original
    state=deepcopy(original)
    data=state['tables'].get('song_sources')
    if data:
        from songranker.storage.database_io import json_bytes
        columns=data['columns'];sid=columns.index('song_id');rid=columns.index('id');snap=columns.index('snapshot')
        rows=data['rows'];rowids=data.get('rowids',[None]*len(rows));latest={}
        for row,rowid in zip(rows,rowids):
            previous=latest.get(row[sid])
            if previous is None or row[rid]>previous[0][rid]:latest[row[sid]]=(row,rowid)
        records=[]
        for row,rowid in latest.values():
            row[snap]=pack_source(row[snap]);records.append((row,rowid))
        records.sort(key=lambda item:(json_bytes(item[0]),item[1] or 0))
        data['rows']=[row for row,_ in records]
        if 'rowids' in data:data['rowids']=[rowid for _,rowid in records]
    state['user_version']=15
    return state

def compact_database(filename,*,force=False,backed_up=False,grow_only=False):
    """Run only on a stopped/private database. SQLite keeps VACUUM atomic."""
    path=Path(filename);conn=sqlite3.connect(path,timeout=5)
    try:
        page=conn.execute('PRAGMA page_size').fetchone()[0]
        used=(conn.execute('PRAGMA page_count').fetchone()[0]-conn.execute('PRAGMA freelist_count').fetchone()[0])*page
        target=2048 if used<4*1024*1024 else 4096
        if not force and (page==target or (grow_only and target<page)):return False
        if not backed_up:
            from songranker.storage.database_io import create_backup
            create_backup(path,'pre_compact')
        journal=conn.execute('PRAGMA journal_mode').fetchone()[0]
        try:
            if journal=='wal':conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('PRAGMA page_size='+str(target))
            conn.execute('VACUUM')
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise sqlite3.DatabaseError('Compacted database failed its integrity check.')
        finally:
            if journal=='wal':conn.execute('PRAGMA journal_mode=WAL')
        return True
    except (sqlite3.Error,OSError) as error:
        logging.getLogger(__name__).warning('Source data is saved; optional SQLite compaction deferred: %s',error)
        return False
    finally:conn.close()
