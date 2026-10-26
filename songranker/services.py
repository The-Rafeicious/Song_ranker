from flask import Flask, redirect, url_for, session
from functools import wraps
from difflib import SequenceMatcher
import re
import sqlite3
import os
from pathlib import Path
import weakref
from songranker.storage.database_access import gate
from songranker.paths import ROOT
from songranker.lan_security import configure_security
from songranker.version import APP_VERSION
from songranker.storage.competition import configured_paths

app = Flask(__name__,template_folder=str(ROOT/'templates'),static_folder=str(ROOT/'static'))
configure_security(app, ROOT)

@app.context_processor
def project_version():
    """Expose application and Vibe data versions to the shared template context."""
    from songranker.storage.vibe_state import VIBE_MAP_VERSION
    return dict(app_version=APP_VERSION, vibe_version=VIBE_MAP_VERSION)

DB_PATH, LEGACY_DB_PATH = configured_paths(ROOT)
DB_NAME = str(DB_PATH)
DEV_PIN = os.environ.get('SONG_RANKER_PIN', '9042')

def admin_required(f):
    """Wrap a Dev handler so unauthenticated browsers are redirected to the PIN
    login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """Require the current browser's admin session before invoking the wrapped
        Dev handler.
        """
        if not session.get('is_admin'):
            return redirect(url_for('dev_login'))
        return f(*args, **kwargs)
    return decorated_function


class _AppConnection(sqlite3.Connection):
    def close(self):
        """Close SQLite and release its maintenance-gate lease even when closing
        raises.
        """
        try:
            super().close()
        finally:
            lease = getattr(self, '_maintenance_lease', None)
            if lease is not None:
                lease()


def get_db_connection():
    """Open the configured app database with foreign keys, row objects and a
    maintenance-gate lease.
    """
    gate.enter_connection()
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30, factory=_AppConnection)
        conn._maintenance_lease = weakref.finalize(conn, gate.leave_connection)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    except BaseException:
        if 'conn' in locals():
            conn.close()
        else:
            gate.leave_connection()
        raise








def init_db():
    """Restore before creating anything, then apply the single versioned schema."""
    from songranker.storage.competition import start_competition, bootstrap_sql
    with gate.maintenance():
        if not Path(DB_NAME).exists() and os.environ.get('SONG_RANKER_LEGACY_DB') and not LEGACY_DB_PATH.exists():
            raise ValueError('The configured V2 source is missing; no fresh database was created.')
        if not Path(DB_NAME).exists() and not LEGACY_DB_PATH.exists() and (ROOT/'database_backup.sql').exists():
            bootstrap_sql(DB_NAME,ROOT/'database_backup.sql')
            return
        start_competition(DB_NAME, LEGACY_DB_PATH, ROOT / 'data/catalogue_seed.db')


def activate_elo_policy():
    """Back up and activate adaptive Elo after startup database reconciliation."""
    from songranker.storage.database import activate_adaptive_elo
    with gate.maintenance():
        report = activate_adaptive_elo(DB_NAME)
    if report:
        app.logger.warning('Adaptive Elo replay complete: %s events; rollback backup: %s',
                           report['events'], report['backup'])
    return report


def export_rankings():
    """Exports a comprehensive database snapshot to a text file."""
    conn = get_db_connection()
    all_songs = conn.execute('''
                             SELECT s.title,
                                    s.elo_score,
                                    s.highest_elo,
                                    s.highest_rank,
                                    s.matches_played,
                                    al.title                   as album,
                                    COALESCE(ts.attempts, 0)   as t_attempts,
                                    COALESCE(ts.correct, 0)    as t_correct,
                                    GROUP_CONCAT(a.name, ', ') as artist
                             FROM songs s
                                      LEFT JOIN albums al ON s.album_id = al.id
                                      LEFT JOIN song_artists sa ON s.id = sa.song_id
                                      LEFT JOIN artists a ON sa.artist_id = a.id
                                      LEFT JOIN trivia_stats ts ON s.id = ts.song_id
                             GROUP BY s.id
                             ORDER BY s.elo_score DESC
                             ''').fetchall()
    conn.close()

    with open(ROOT / "database_snapshot.txt", "w", encoding="utf-8") as f:
        f.write("--- SONG RANKER DATABASE SNAPSHOT ---\n\n")

        # Define table headers and column widths
        header = f"{'Rank':<5} | {'Elo':<6} | {'Peak Elo':<9} | {'Peak Rank':<10} | {'Matches':<7} | {'Recog %':<7} | {'Track Title':<35} | {'Artist':<25} | {'Album'}\n"
        f.write(header)
        f.write("-" * 140 + "\n")

        for rank, song in enumerate(all_songs, 1):
            elo = int(song['elo_score'])
            peak_elo = int(song['highest_elo']) if song['highest_elo'] else elo
            peak_rank = song['highest_rank'] if song['highest_rank'] and song['highest_rank'] != 9999 else rank

            # Calculate Recognizability %
            attempts = song['t_attempts']
            if attempts > 0:
                recog = f"{int((song['t_correct'] / (attempts * 2)) * 100)}%"
            else:
                recog = "N/A"

            # Truncate long text strings to keep the table cleanly aligned
            title = (song['title'][:32] + '...') if len(song['title']) > 35 else song['title']
            artist = (song['artist'][:22] + '...') if song['artist'] and len(song['artist']) > 25 else (
                        song['artist'] or 'Unknown')
            album = song['album'] or 'Single / Unknown'

            f.write(
                f"{rank:<5} | {elo:<6} | {peak_elo:<9} | {peak_rank:<10} | {song['matches_played']:<7} | {recog:<7} | {title:<35} | {artist:<25} | {album}\n")

    with open("current_elo_rankings.txt", "w", encoding="utf-8") as f:
        f.write("--- CURRENT ELO RANKINGS ---\n\n")
        f.write(f"{'Rank':<5} | {'Elo':<6} | {'Matches':<7} | {'Track'}\n")
        f.write("-" * 65 + "\n")
        for rank, song in enumerate(all_songs, 1):
            elo = int(song['elo_score'])
            f.write(f"{rank:<5} | {elo:<6} | {song['matches_played']:<7} | {song['title']} by {song['artist']}\n")




def is_close_match(guess, actual, threshold=0.75):
    """Compare trimmed case-insensitive answer text using the configured
    sequence-similarity threshold.
    """
    if not guess or not actual:
        return False
    g = guess.lower().strip()
    a = actual.lower().strip()
    return SequenceMatcher(None, g, a).ratio() >= threshold


SONG_SELECT = "SELECT s.*, al.cover_url, al.title as album,\n               CASE WHEN LOWER(TRIM(COALESCE(al.title, ''))) LIKE '% - single' THEN 1 ELSE 0 END AS album_is_single,\n               COALESCE(ts.attempts, 0) as trivia_attempts,\n               COALESCE(ts.correct, 0) as trivia_correct, COALESCE(ts.available_points,0) as available_points,\n               (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) as artist,\n               (SELECT GROUP_CONCAT(g2.name, ', ') FROM song_genres sg2 JOIN genres g2 ON sg2.genre_id = g2.id WHERE sg2.song_id = s.id) as genres\n        FROM songs s\n        LEFT JOIN albums al ON s.album_id = al.id\n        LEFT JOIN trivia_stats ts ON s.id = ts.song_id"

def fetch_songs(conn, *, song_id=None, audio_only=False):
    """Consistent song metadata plus batched, independent Vibe Map placements."""
    conditions, parameters = [], []
    if song_id is not None:
        conditions.append('s.id=?')
        parameters.append(song_id)
    if audio_only:
        conditions.append("COALESCE(s.audio_url, '') != ''")
    where=' WHERE '+' AND '.join(conditions) if conditions else ''
    from songranker.vibe_maps import with_vibe_maps
    return with_vibe_maps(conn, conn.execute(SONG_SELECT+where,parameters))


def get_song_full(song_id, conn):
    """Hydrate one catalogue song through the shared song query, returning no result
    when absent.
    """
    songs=fetch_songs(conn,song_id=song_id)
    return songs[0] if songs else None


def fetch_match_history(conn, song_id=None, limit=50, *, offset=0, mode='all', origin='all'):
    """Fetch recent matches with the rich song records used by shared VS rows.

    Passing a song ID scopes results to matches involving that song; omitting it
    returns the site's recent match feed. Saved Elo belongs to each match, while
    linked song/album/artist metadata comes from the current catalogue. Older
    history without rating snapshots falls back to explicitly labelled current
    Elo in the template. This reader never changes the database.
    """
    from songranker.catalog import versus_metadata
    from songranker.catalog import source_sql
    from songranker.catalog import filters
    mode, origin = filters(mode, origin)

    rows = [dict(row) for row in conn.execute(f'''
        SELECT h.*,
               w.title AS winner_title, w.elo_score AS winner_elo, wal.cover_url AS winner_cover,
               wal.id AS winner_album_id, wal.title AS winner_album_title,
               l.title AS loser_title, l.elo_score AS loser_elo, lal.cover_url AS loser_cover,
               lal.id AS loser_album_id, lal.title AS loser_album_title
        FROM {source_sql(conn)} h
        JOIN songs w ON h.winner_id = w.id
        LEFT JOIN albums wal ON wal.id = w.album_id
        JOIN songs l ON h.loser_id = l.id
        LEFT JOIN albums lal ON lal.id = l.album_id
        WHERE (? IS NULL OR h.winner_id = ? OR h.loser_id = ?)
          AND (?='all' OR h.mode=?) AND (?='all' OR (?='tournament')=(h.origin='tournament'))
          AND h.winner_id!=h.loser_id
        ORDER BY h.id DESC
        LIMIT ? OFFSET ?
    ''', (song_id, song_id, song_id, mode, mode, origin, origin, max(1, min(int(limit), 500)), max(0,int(offset))))]

    # Read actual relationships instead of splitting comma-delimited artist
    # names. Batch only the displayed tracks, below SQLite's legacy bind limit.
    song_ids = sorted({row[side + '_id'] for row in rows for side in ('winner', 'loser')})
    artists = {sid: [] for sid in song_ids}
    for start in range(0, len(song_ids), 500):
        batch = song_ids[start:start + 500]
        for artist in conn.execute('''
            SELECT DISTINCT sa.song_id, a.id, a.name
            FROM song_artists sa JOIN artists a ON a.id = sa.artist_id
            WHERE sa.song_id IN (''' + ','.join('?' for _ in batch) + ')', batch):
            artists[artist['song_id']].append(dict(artist))

    songs = {}
    for row in rows:
        for side in ('winner', 'loser'):
            sid = row[side + '_id']
            if sid not in songs:
                album = dict(id=row[side + '_album_id'], title=row[side + '_album_title'],
                             cover_url=row[side + '_cover'])
                songs[sid] = dict(id=sid, title=row[side + '_title'], elo_score=row[side + '_elo'],
                                  **versus_metadata(album, artists[sid]))
            row[side + '_song'] = songs[sid]
            row[side + '_artist'] = ', '.join(a['name'] for a in songs[sid]['artist_links'])
            row.setdefault(side + '_before', None)
            row.setdefault(side + '_after', None)
    return rows




def create_database_backup(prefix='song_ranker'):
    """Save the configured live database through the shared rotating-backup policy."""
    from songranker.storage.database_io import create_rolling_backup
    return str(create_rolling_backup(DB_NAME))


def get_or_create_album(conn, album_title, cover_url=None, release_date=None):
    """Retrieves an existing album or creates one, updating artwork if missing."""
    title_clean = album_title.strip() if album_title else "Unknown Album"
    album_row = conn.execute('SELECT id, cover_url FROM albums WHERE title = ? COLLATE NOCASE',
                             (title_clean,)).fetchone()

    if album_row:
        album_id = album_row['id']
        if cover_url and not album_row['cover_url']:
            conn.execute('UPDATE albums SET cover_url = ? WHERE id = ?', (cover_url, album_id))
    else:
        cursor = conn.execute('INSERT INTO albums (title, cover_url) VALUES (?, ?)', (title_clean, cover_url))
        album_id = cursor.lastrowid

    if release_date:
        conn.execute("UPDATE albums SET release_date=? WHERE id=? AND COALESCE(release_date,'')=''",(release_date,album_id))
    return album_id


def link_artists_to_song(conn, song_id, artist_string, default_cover=None, *, artist_names=None):
    """Splits an artist string and links each artist via the song_artists junction table."""
    if artist_names is not None:
        split_artists=artist_names
    elif conn.execute('SELECT 1 FROM artists WHERE name=? COLLATE NOCASE',(artist_string.strip(),)).fetchone():
        split_artists=[artist_string]
    else:
        split_artists = re.split(r', |\s+feat\.\s+|\s+ft\.\s+|\s+&\s+|\s+and\s+', artist_string, flags=re.IGNORECASE)

    for name in split_artists:
        name_clean = name.strip()
        if not name_clean:
            continue

        artist_row = conn.execute('SELECT id FROM artists WHERE name = ? COLLATE NOCASE', (name_clean,)).fetchone()
        if artist_row:
            artist_id = artist_row['id']
        else:
            cursor = conn.execute('INSERT INTO artists (name, cover_url) VALUES (?, ?)', (name_clean, default_cover))
            artist_id = cursor.lastrowid

        conn.execute('INSERT OR IGNORE INTO song_artists (song_id, artist_id) VALUES (?, ?)', (song_id, artist_id))


def link_genres_to_song(conn, song_id, genre_string):
    """Splits a genre string and links each tag via the song_genres junction table."""
    if not genre_string:
        return

    from songranker.storage.tag_limits import tag_names, check_count
    split_genres = tag_names(genre_string)
    existing = {r[0].casefold() for r in conn.execute('SELECT g.name FROM song_genres sg JOIN genres g ON g.id=sg.genre_id WHERE sg.song_id=?',(song_id,))}
    check_count(len(existing | {name.casefold() for name in split_genres}))
    for name in split_genres:
        genre_row = conn.execute('SELECT id FROM genres WHERE name = ? COLLATE NOCASE', (name,)).fetchone()
        if genre_row:
            genre_id = genre_row['id']
        else:
            cursor = conn.execute('INSERT INTO genres (name) VALUES (?)', (name,))
            genre_id = cursor.lastrowid

        conn.execute('INSERT OR IGNORE INTO song_genres (song_id, genre_id) VALUES (?, ?)', (song_id, genre_id))
