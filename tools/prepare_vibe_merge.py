"""One-time test-branch result cleanup. Close the app; preview before --apply."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from songranker.storage.database_io import capture,digest,readonly,sql_dump,validate,quote
from songranker.storage.database_schema import table_columns
from songranker.storage.competition import CATALOGUE
from songranker.storage.competition_reset import reset_results

MARKER='vibe_v11_merge_cleanup'
# Only result-free metadata is retained. All source observations remain intact.
KEEP={**CATALOGUE,'song_details':('song_id','added_at','preview_bad','preview_note','flagged_at')}
RESULT_TABLES=('preference_events','preference_corrections','preference_rating_projection','preference_offers',
    'preference_rating_overrides','trivia_rounds','trivia_adjustments','challenge_runs','tournaments',
    'tournament_entries','tournament_matches','elo_guess_rounds','album_shelf_rounds','album_shelf_items',
    'listening_observations','vibe_rounds')


def catalogue(conn):
    return {table:sorted([list(r) for r in conn.execute('SELECT '+','.join(map(quote,cols))+' FROM '+quote(table))],key=repr)
            for table,cols in KEEP.items()}


def assert_clean(conn):
    for table in RESULT_TABLES:
        if conn.execute('SELECT 1 FROM '+quote(table)+' LIMIT 1').fetchone():raise ValueError('New results exist in '+table+'. This cleanup has already run; no results were erased.')
    if conn.execute("SELECT 1 FROM songs WHERE elo_score!=1200 OR matches_played!=0 OR highest_elo!=1200 OR highest_rank!=9999 OR tournament_wins!=0 LIMIT 1").fetchone():raise ValueError('Song ratings are not reset.')
    if conn.execute("SELECT 1 FROM song_vibe_positions WHERE status!='unmapped' OR sample_count!=0 OR not_applicable_count!=0 LIMIT 1").fetchone():raise ValueError('New Vibe selections exist. This cleanup has already run; no results were erased.')
    if conn.execute('SELECT 1 FROM song_vibe_progress WHERE completed_passes!=0 LIMIT 1').fetchone():raise ValueError('New Vibe passes exist.')
    if conn.execute("SELECT 1 FROM global_stats WHERE key!='trivia_scoring_version' AND value!=0 LIMIT 1").fetchone():raise ValueError('New global records exist.')
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='legacy_elo_changes' AND type='table'").fetchone() and conn.execute('SELECT 1 FROM legacy_elo_changes LIMIT 1').fetchone():raise ValueError('Legacy Elo results remain.')


def export_sql(conn,output):
    """Validate a round trip before atomically replacing the requested Git snapshot."""
    output=Path(output).absolute()
    if output.is_symlink():raise ValueError('Use a regular SQL snapshot path.')
    if not output.parent.is_dir():raise ValueError('The export directory must already exist.')
    content=sql_dump(conn)
    with tempfile.TemporaryDirectory(prefix='.merge_export_',dir=output.parent) as folder:
        staged=Path(folder)/'database_backup.sql'
        with staged.open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        check=sqlite3.connect(':memory:');check.row_factory=sqlite3.Row
        try:
            check.executescript(content);validate(check);assert_clean(check)
            if capture(check)!=capture(conn):raise ValueError('Export round-trip verification failed.')
        finally:check.close()
        os.replace(staged,output)
    return str(output)


def prepare(database,output=None,apply=False,confirmation=''):
    raw=Path(database).absolute()
    if raw.is_symlink():raise ValueError('Choose a regular test database, not a symlink.')
    path=raw.resolve(strict=True)
    if output and Path(output).resolve()==path:raise ValueError('Database and SQL output paths must differ.')
    with readonly(path) as conn:
        conn.execute('BEGIN');validate(conn)
        if conn.execute('PRAGMA user_version').fetchone()[0]!=19:raise ValueError('Update the test branch database before cleanup.')
        known={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if known-set(table_columns())-{'legacy_elo_changes'}:raise ValueError('Unknown extension tables found; review them before cleanup.')
        report=json.loads(conn.execute('SELECT migration_report FROM competition_state WHERE id=1').fetchone()[0])
        if not isinstance(report,dict):raise ValueError('Invalid competition metadata; review it before cleanup.')
        before=capture(conn);kept=catalogue(conn)
        preview=dict(database=str(path),already_prepared=MARKER in report,keep={t:len(rows) for t,rows in kept.items()},
            clear={t:conn.execute('SELECT COUNT(*) FROM '+quote(t)).fetchone()[0] for t in RESULT_TABLES},
            mapped_positions=conn.execute("SELECT COUNT(*) FROM song_vibe_positions WHERE status!='unmapped'").fetchone()[0])
    if not apply:return dict(preview,applied=False,message='Preview only. Close the app before applying.')
    if confirmation!='RESET TEST COMPETITION':raise ValueError('Use --confirmation "RESET TEST COMPETITION" to apply to the test database.')
    if not output:raise ValueError('--export is required when applying, normally database_backup.sql on the test branch.')
    output=Path(output).absolute()
    if output.is_symlink() or not output.parent.is_dir() or (output.exists() and not output.is_file()):raise ValueError('Choose a regular SQL path in an existing directory.')
    backup=None;reset_committed=False
    conn=sqlite3.connect(path,timeout=5);conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON')
    try:
        if MARKER not in report:
            folder=path.parent/'database_backups';folder.mkdir(exist_ok=True)
            backup=folder/('pre_merge_vibe_v11_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.db')
            dest=sqlite3.connect(backup)
            try:conn.backup(dest)
            finally:dest.close()
            with readonly(backup) as check:
                validate(check)
                if capture(check)!=before:raise ValueError('Database changed during preparation. Close the app and retry.')
        conn.execute('BEGIN IMMEDIATE')
        if capture(conn)!=before:raise ValueError('Database changed during preparation. Close the app and retry.')
        if MARKER not in report:
            reset_results(conn,'all');assert_clean(conn);validate(conn)
            if catalogue(conn)!=kept:raise ValueError('Catalogue verification failed; reset rolled back.')
            report[MARKER]=dict(at=time.time(),catalogue_sha256=digest(kept),backup=backup.name)
            conn.execute('UPDATE competition_state SET migration_report=? WHERE id=1',(json.dumps(report),))
            conn.commit();reset_committed=True
            conn.execute('BEGIN IMMEDIATE')
        assert_clean(conn)
        exported=export_sql(conn,output)
        conn.commit()
        return dict(preview,applied=not preview['already_prepared'],
            backup=str(backup) if backup else None,export=exported,message='Ready for review and manual push. No Git commands were run.')
    except Exception as error:
        conn.rollback()
        if reset_committed:raise ValueError('Cleanup committed and the restore backup was kept, but SQL export failed: '+str(error)+'. Keep the app closed and rerun the same command to retry export without another reset.') from error
        raise
    finally:conn.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('--export',help='SQL snapshot to replace after a verified reset.')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--confirmation',default='')
    args=parser.parse_args()
    try:print(json.dumps(prepare(args.database,args.export,args.apply,args.confirmation),indent=2))
    except (ValueError,sqlite3.Error,OSError) as error:parser.exit(1,str(error)+'\n')


if __name__=='__main__':main()
