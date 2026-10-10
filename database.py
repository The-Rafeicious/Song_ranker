"""One-time, backed-up migration to a single vote record per match."""
from pathlib import Path
from datetime import datetime
import sqlite3

SCHEMA_VERSION = 4

def migrate(filename):
    path = Path(filename)
    if not path.exists(): return
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        song_columns={r['name'] for r in conn.execute('PRAGMA table_info(songs)')}
        if 'songs' in tables and 'album_id' not in song_columns:
            raise sqlite3.DatabaseError('This is the older flat-schema database. Use song_ranker_v2.db; the older database is kept separately.')
        if 'history' not in tables or conn.execute('PRAGMA user_version').fetchone()[0] >= SCHEMA_VERSION:
            return
        # sqlite backup captures a consistent snapshot, including older schemas.
        directory = path.parent / 'database_backups'
        directory.mkdir(exist_ok=True)
        backup = directory / ('pre_upgrade_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
        destination = sqlite3.connect(backup)
        try: conn.backup(destination)
        finally: destination.close()
        conn.execute('BEGIN IMMEDIATE')
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(history)')}
        for name, declaration in [('created_at','DATETIME'),('mode',"TEXT NOT NULL DEFAULT 'unknown'"),
                                  ('winner_before','REAL'),('winner_after','REAL'),('loser_before','REAL'),('loser_after','REAL')]:
            if name not in columns: conn.execute(f'ALTER TABLE history ADD COLUMN {name} {declaration}')
        if 'elo_history' in tables:
            consumed = set()
            for row in conn.execute('SELECT * FROM elo_history ORDER BY id').fetchall():
                candidates = conn.execute('SELECT * FROM history WHERE winner_id=? AND loser_id=? AND winner_before IS NULL ORDER BY id',
                                          (row['winner_id'], row['loser_id'])).fetchall()
                exact = [h for h in candidates if h['created_at'] and h['created_at'] == row['created_at']]
                target = exact[0] if exact else (candidates[0] if len(candidates)==1 and not candidates[0]['created_at'] else None)
                if target:
                    # Existing history labels are authoritative. Only legacy unknown
                    # rows receive the explicitly recorded Elo entry's mode.
                    conn.execute('UPDATE history SET winner_before=?,winner_after=?,loser_before=?,loser_after=?,created_at=COALESCE(created_at,?), mode=CASE WHEN mode=\'unknown\' THEN ? ELSE mode END WHERE id=?',
                        (row['winner_before'],row['winner_after'],row['loser_before'],row['loser_after'],row['created_at'],row['mode'],target['id']))
                    consumed.add(row['id'])
            unmatched = [dict(r) for r in conn.execute('SELECT * FROM elo_history') if r['id'] not in consumed]
            if unmatched:
                # Do not guess a pairing for ambiguous old votes. Keep only the
                # unmatched legacy values, instead of retaining a duplicate log.
                conn.execute('CREATE TABLE legacy_elo_changes AS SELECT * FROM elo_history WHERE 0')
                for row in unmatched:
                    conn.execute('INSERT INTO legacy_elo_changes VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
        for table in ('admin_audit_log','interaction_events','elo_history'):
            conn.execute(f'DROP TABLE IF EXISTS {table}')
        if 'trivia_stats' in tables:
            conn.execute('DELETE FROM trivia_stats WHERE attempts=0 AND correct=0')
        if 'tournament_matches' in tables:
            columns={r['name']:r for r in conn.execute('PRAGMA table_info(tournament_matches)')}
            if columns['song1_id']['notnull'] or columns['song2_id']['notnull']:
                # Archived brackets keep their structure when a song is deleted.
                # Nullable references avoid dangling IDs or deleting whole brackets.
                schema=conn.execute("SELECT sql FROM sqlite_master WHERE name='tournament_matches'").fetchone()[0]
                indexes=[r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='tournament_matches' AND sql IS NOT NULL")]
                sequence=conn.execute("SELECT seq FROM sqlite_sequence WHERE name='tournament_matches'").fetchone()
                schema=schema.replace('CREATE TABLE tournament_matches','CREATE TABLE tournament_matches_slim',1)
                schema=schema.replace('song1_id INTEGER NOT NULL','song1_id INTEGER').replace('song2_id INTEGER NOT NULL','song2_id INTEGER')
                conn.execute(schema)
                names=','.join('"'+name+'"' for name in columns)
                conn.execute(f'INSERT INTO tournament_matches_slim ({names}) SELECT {names} FROM tournament_matches')
                conn.execute('DROP TABLE tournament_matches')
                conn.execute('ALTER TABLE tournament_matches_slim RENAME TO tournament_matches')
                if sequence:
                    conn.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='tournament_matches'",(sequence[0],))
                for index in indexes:conn.execute(index)
        conn.execute('CREATE INDEX IF NOT EXISTS history_winner ON history(winner_id,id)')
        conn.execute('CREATE INDEX IF NOT EXISTS history_loser ON history(loser_id,id)')
        conn.execute('CREATE INDEX IF NOT EXISTS songs_album ON songs(album_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS song_artists_artist ON song_artists(artist_id,song_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS song_genres_genre ON song_genres(genre_id,song_id)')
        conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        conn.commit()
        conn.execute('VACUUM')
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()
