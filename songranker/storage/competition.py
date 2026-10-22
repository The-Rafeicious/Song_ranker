"""One-time catalogue-only V2 -> V3 competition bootstrap. Never edits the source."""

from pathlib import Path
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from songranker.storage.database import initialize_database
from songranker.storage.database_io import DatabaseValidationError, readonly, validate, publish, quote
from songranker.storage.database_schema import SCHEMA_VERSION


CATALOGUE = {
    'albums': ('id','title','cover_url','release_date'),
    'artists': ('id','name','cover_url'),
    'genres': ('id','name','description'),
    'songs': ('id','title','album_id','audio_url','track_number','release_date','release_date_origin'),
    'song_artists': ('song_id','artist_id'),
    'song_genres': ('song_id','genre_id'),
    'song_sources': ('id','song_id','provider','external_id','storefront','collection_id','snapshot','observed_at'),
}


def configured_paths(root):
    root=Path(root)
    configured=os.environ.get('SONG_RANKER_DB')
    legacy=Path(os.environ.get('SONG_RANKER_LEGACY_DB',root/'song_ranker_v2.db'))
    if configured and Path(configured).name=='song_ranker_v2.db':
        legacy=Path(configured)
        target=legacy.with_name('song_ranker_v3.db')
    else:target=Path(configured) if configured else root/'data/song_ranker_v3.db'
    if target.resolve()==legacy.resolve():
        raise DatabaseValidationError('Choose separate V2 source and V3 destination paths.')
    return target,legacy


def catalogue_rows(conn):
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'songs','artists','albums','genres','song_artists','song_genres'}<=tables:
        raise DatabaseValidationError('V2 catalogue tables are missing; source was left unchanged.')
    result={}
    for table,wanted in CATALOGUE.items():
        if table not in tables:continue
        available={r[1] for r in conn.execute('PRAGMA table_info('+quote(table)+')')}
        if not set(wanted[:2])<=available:
            raise DatabaseValidationError('Unsupported '+table+' catalogue; source was left unchanged.')
        columns=[c for c in wanted if c in available]
        condition=' WHERE id IN (SELECT MAX(id) FROM song_sources GROUP BY song_id)' if table=='song_sources' else ''
        rows=[tuple(r) for r in conn.execute('SELECT '+','.join(map(quote,columns))+' FROM '+quote(table)+condition)]
        if table=='song_sources' and 'snapshot' in columns:
            from songranker.storage.source_storage import pack_source
            i=columns.index('snapshot')
            rows=[tuple(pack_source(v) if n==i else v for n,v in enumerate(row)) for row in rows]
        result[table]=(columns,rows)
    return result


def start_competition(target,legacy=None,seed=None):
    """Build privately, verify transfer/reset, then publish without overwriting a V3 DB."""
    target=Path(target).resolve()
    if legacy and target==Path(legacy).resolve():raise DatabaseValidationError('V2 source and V3 destination must be separate files.')
    if target.exists():
        with readonly(target) as conn:
            state=conn.execute("SELECT 1 FROM sqlite_master WHERE name='competition_state'").fetchone()
            if not state or not conn.execute('SELECT 1 FROM competition_state WHERE id=1 AND generation=3').fetchone():
                raise DatabaseValidationError('The V3 destination contains an older competition. Keep it as the V2 source and choose a separate V3 file.')
        initialize_database(target)
        return 'existing'
    target.parent.mkdir(parents=True,exist_ok=True)
    source=Path(legacy).resolve() if legacy and Path(legacy).exists() else Path(seed).resolve() if seed and Path(seed).exists() else None
    backup=None
    with tempfile.TemporaryDirectory(prefix='.v5_transfer_',dir=target.parent) as folder:
        candidate=Path(folder)/'candidate.db'
        initialize_database(candidate)
        if source:
            if source==target:raise DatabaseValidationError('V2 and V3 paths must differ.')
            # Snapshot includes WAL transactions. Source connection is strictly read-only.
            backup_dir=target.parent/'database_backups';backup_dir.mkdir(exist_ok=True)
            prefix='pre_v5_catalogue_seed_' if seed and source==Path(seed).resolve() else 'pre_v5_v2_'
            backup=backup_dir/(prefix+time.strftime('%Y%m%d_%H%M%S')+'_'+os.urandom(4).hex()+'.db')
            with readonly(source) as old:
                validate(old)
                pending_backup=Path(folder)/'source_snapshot.db'
                dest=sqlite3.connect(pending_backup)
                try:old.backup(dest)
                finally:dest.close()
            with readonly(pending_backup) as check:validate(check)
            os.link(pending_backup,backup)  # Only a complete validated archive gets a public backup name.
            with readonly(backup) as old:
                validate(old);rows=catalogue_rows(old)
                source_version=old.execute('PRAGMA user_version').fetchone()[0]
                if source_version>SCHEMA_VERSION:raise DatabaseValidationError('Source needs a newer app; no V3 file was published.')
                sequences=dict(old.execute('SELECT name,seq FROM sqlite_sequence')) if old.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone() else {}
            conn=sqlite3.connect(candidate);conn.execute('PRAGMA foreign_keys=ON')
            try:
                conn.execute('BEGIN IMMEDIATE')
                for table,(columns,records) in rows.items():
                    conn.executemany('INSERT INTO '+quote(table)+'('+','.join(map(quote,columns))+') VALUES('+','.join('?' for _ in columns)+')',records)
                # All carried tracks start equally; additions after the transfer receive timestamps.
                conn.execute('UPDATE song_details SET added_at=0')
                for table,seq in sequences.items():
                    if table in CATALOGUE:
                        current=conn.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(table,)).fetchone()
                        if current:conn.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?',(seq,table))
                report=dict(source=source.name,backup=backup.name,source_schema=source_version,
                    sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),counts={t:len(r) for t,(_,r) in rows.items()},
                    reset='All game results, ratings, attempts, streaks, offers and listening records')
                conn.execute('UPDATE competition_state SET migration_report=? WHERE id=1',(json.dumps(report),))
                conn.commit();conn.row_factory=sqlite3.Row
                validate(conn)
                # Exact values, not just counts. No albums/art/preview/tag or source rewrites.
                for table,(columns,records) in rows.items():
                    actual=[tuple(r) for r in conn.execute('SELECT '+','.join(map(quote,columns))+' FROM '+quote(table))]
                    if sorted(actual,key=repr)!=sorted(records,key=repr):raise DatabaseValidationError('Catalogue verification failed: '+table)
                if conn.execute('SELECT COUNT(*) FROM preference_events').fetchone()[0] or conn.execute('SELECT COUNT(*) FROM songs WHERE elo_score!=1200 OR matches_played!=0 OR highest_elo!=1200 OR tournament_wins!=0').fetchone()[0]:
                    raise DatabaseValidationError('Fresh competition verification failed.')
            finally:conn.close()
        try:publish(candidate,target)
        except DatabaseValidationError:
            # Concurrent startup already won. Reuse only a verified V3 winner.
            if target.exists():return start_competition(target)
            raise
    return 'transferred' if source else 'created'


def bootstrap_sql(target,sql_file):
    """Recover a Git SQL snapshot privately: V3 keeps results, V2 carries catalogue only."""
    target=Path(target).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():return start_competition(target)
    with tempfile.TemporaryDirectory(prefix='.sql_bootstrap_',dir=target.parent) as folder:
        staged=Path(folder)/'restored_snapshot.db'
        initialize_database(staged,sql_file)
        with readonly(staged) as conn:
            is_v3=conn.execute("SELECT 1 FROM sqlite_master WHERE name='competition_state'").fetchone() and conn.execute('SELECT 1 FROM competition_state WHERE id=1 AND generation=3').fetchone()
        if not is_v3:return start_competition(target,staged)
        try:publish(staged,target)
        except DatabaseValidationError:
            if target.exists():return start_competition(target)
            raise
    return 'restored'
