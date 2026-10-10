from flask import Flask, redirect, url_for, session
from functools import wraps
from difflib import SequenceMatcher
import random
import re
import subprocess
import sqlite3
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.secret_key = os.environ.get('SONG_RANKER_SECRET', 'theandwasdwe')
DB_NAME = os.environ.get('SONG_RANKER_DB', str(ROOT / 'song_ranker_v2.db'))
DEV_PIN = os.environ.get('SONG_RANKER_PIN', '9042')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('dev_login'))
        return f(*args, **kwargs)
    return decorated_function


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def git_pull():
    """Pull application updates without ever overwriting an existing local database.

    The SQL dump is a portable backup, not a reason to replace a live database at
    startup. This prevents a pull from deleting votes or unfinished tournaments.
    """
    try:
        print("Pulling latest code and backup from GitHub...")
        subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            capture_output=True, text=True, check=True, timeout=120
        )
        if not os.path.exists(DB_NAME) and (ROOT / 'database_backup.sql').exists():
            print("No local database found. Restoring from database_backup.sql...")
            conn = sqlite3.connect(DB_NAME)
            try:
                with open(ROOT / 'database_backup.sql', 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.commit()
            finally:
                conn.close()
        elif os.path.exists(DB_NAME):
            print("Keeping existing local database; remote SQL backup will not overwrite it.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        details = getattr(e, 'stderr', None) or str(e)
        print(f"Git pull skipped/failed; continuing with local files: {details}")
    except OSError as e:
        print(f"Database restore failed: {e}")


def git_push():
    """Write a consistent SQLite dump and push it as the manual sync operation."""
    try:
        if not os.path.exists(DB_NAME):
            app.logger.error("Cannot sync: local database %s does not exist", DB_NAME)
            return False

        # SQLite's backup API gives us a stable snapshot even if a connection is open.
        source = sqlite3.connect(DB_NAME, timeout=30)
        snapshot = sqlite3.connect(':memory:')
        try:
            source.backup(snapshot)
            with open(ROOT / 'database_backup.sql', 'w', encoding='utf-8') as f:
                for line in snapshot.iterdump():
                    f.write(f'{line}\n')
        finally:
            snapshot.close()
            source.close()

        subprocess.run(["git", "add", "database_backup.sql"], check=True, timeout=30, cwd=ROOT)
        result = subprocess.run(
            ["git", "commit", "-m", "Auto-sync database update"],
            capture_output=True, text=True, timeout=30, cwd=ROOT
        )
        if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr).lower():
            app.logger.error("Database sync commit failed: %s", result.stderr or result.stdout)
            return False
        if "nothing to commit" in (result.stdout + result.stderr).lower():
            # The remote may still be behind, so push any already-created local commit.
            app.logger.info("Database dump unchanged; checking remote sync")

        pushed = subprocess.run(
            ["git", "push", "origin", "main"], capture_output=True,
            text=True, timeout=120, cwd=ROOT
        )
        if pushed.returncode != 0:
            app.logger.error("Database sync push failed: %s", pushed.stderr or pushed.stdout)
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, sqlite3.Error) as e:
        app.logger.exception("Database sync failed: %s", e)
        return False


def ensure_tournament_schema(conn):
    """Create/upgrade tournament tables without changing regular Elo history."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS tournament_entries (
            tournament_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            seed INTEGER NOT NULL,
            PRIMARY KEY (tournament_id, song_id),
            UNIQUE (tournament_id, seed),
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        );
        CREATE TABLE IF NOT EXISTS tournament_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            match_number INTEGER NOT NULL,
            song1_id INTEGER,
            song2_id INTEGER,
            winner_id INTEGER,
            loser_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            points_awarded REAL NOT NULL DEFAULT 0,
            played_at DATETIME,
            UNIQUE (tournament_id, round_number, match_number),
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY(song1_id) REFERENCES songs(id),
            FOREIGN KEY(song2_id) REFERENCES songs(id),
            FOREIGN KEY(winner_id) REFERENCES songs(id),
            FOREIGN KEY(loser_id) REFERENCES songs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_tournament_matches_tournament_round
            ON tournament_matches(tournament_id, round_number, match_number);
        CREATE INDEX IF NOT EXISTS idx_tournament_matches_winner ON tournament_matches(winner_id);
        CREATE INDEX IF NOT EXISTS idx_tournament_matches_loser ON tournament_matches(loser_id);
    ''')
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(tournaments)')}
    additions = {
        'status': "TEXT NOT NULL DEFAULT 'completed'",
        'created_at': 'DATETIME',
        'updated_at': 'DATETIME',
        'completed_at': 'DATETIME',
        'current_round': 'INTEGER NOT NULL DEFAULT 1',
        'points_version': 'INTEGER NOT NULL DEFAULT 1',
        'is_blind': 'BOOLEAN NOT NULL DEFAULT 0'
    }
    for name, declaration in additions.items():
        if name not in columns:
            conn.execute(f'ALTER TABLE tournaments ADD COLUMN {name} {declaration}')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)')
    # Older records remain completed historical tournaments.
    conn.execute("UPDATE tournaments SET status = 'completed' WHERE champion_id IS NOT NULL AND status IS NULL")
    conn.execute("UPDATE tournaments SET created_at = COALESCE(created_at, timestamp, CURRENT_TIMESTAMP)")
    conn.execute("UPDATE tournaments SET completed_at = COALESCE(completed_at, timestamp) WHERE champion_id IS NOT NULL")


def init_db():
    """Initializes the relational database structure if it doesn't exist."""
    from database import migrate
    migrate(DB_NAME)
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cover_url TEXT,
            release_date TEXT
        );

        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cover_url TEXT
        );

        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            album_id INTEGER,
            audio_url TEXT,
            elo_score REAL DEFAULT 1200,
            matches_played INTEGER DEFAULT 0,
            highest_elo REAL DEFAULT 1200,
            highest_rank INTEGER DEFAULT 9999,
            track_number INTEGER,
            tournament_wins INTEGER DEFAULT 0,
            FOREIGN KEY(album_id) REFERENCES albums(id)
        );

        CREATE TABLE IF NOT EXISTS song_artists (
            song_id INTEGER,
            artist_id INTEGER,
            FOREIGN KEY(song_id) REFERENCES songs(id),
            FOREIGN KEY(artist_id) REFERENCES artists(id),
            PRIMARY KEY (song_id, artist_id)
        );

        CREATE TABLE IF NOT EXISTS song_genres (
            song_id INTEGER,
            genre_id INTEGER,
            FOREIGN KEY(song_id) REFERENCES songs(id),
            FOREIGN KEY(genre_id) REFERENCES genres(id),
            PRIMARY KEY (song_id, genre_id)
        );

        CREATE TABLE IF NOT EXISTS trivia_stats (
            song_id INTEGER PRIMARY KEY,
            attempts INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            winner_id INTEGER,
            loser_id INTEGER,
            is_tournament_match BOOLEAN DEFAULT 0,
            mode TEXT NOT NULL DEFAULT 'standard',
            FOREIGN KEY(winner_id) REFERENCES songs(id),
            FOREIGN KEY(loser_id) REFERENCES songs(id)
        );
        
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            size INTEGER NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id INTEGER,
            champion_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(champion_id) REFERENCES songs(id)
        );

        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY,
            value INTEGER
        );

    ''')
    ensure_tournament_schema(conn)
    history_columns = {row['name'] for row in conn.execute('PRAGMA table_info(history)')}
    if 'created_at' not in history_columns:
        conn.execute('ALTER TABLE history ADD COLUMN created_at DATETIME')
    if 'mode' not in history_columns:
        conn.execute("ALTER TABLE history ADD COLUMN mode TEXT NOT NULL DEFAULT 'standard'")
    conn.execute('INSERT OR IGNORE INTO global_stats (key, value) VALUES ("trivia_high_score", 0)')
    conn.commit()
    conn.close()
    migrate(DB_NAME)


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


def calculate_new_elo(winner_elo, loser_elo, k_factor=32):
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))
    new_winner_elo = winner_elo + k_factor * (1 - expected_winner)
    new_loser_elo = loser_elo + k_factor * (0 - expected_loser)
    return new_winner_elo, new_loser_elo


def is_close_match(guess, actual, threshold=0.75):
    if not guess or not actual:
        return False
    g = guess.lower().strip()
    a = actual.lower().strip()
    return SequenceMatcher(None, g, a).ratio() >= threshold


SONG_SELECT = "SELECT s.*, al.cover_url, al.title as album,\n               CASE WHEN LOWER(TRIM(COALESCE(al.title, ''))) LIKE '% - single' THEN 1 ELSE 0 END AS album_is_single,\n               COALESCE(ts.attempts, 0) as trivia_attempts,\n               COALESCE(ts.correct, 0) as trivia_correct,\n               (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) as artist,\n               (SELECT GROUP_CONCAT(g2.name, ', ') FROM song_genres sg2 JOIN genres g2 ON sg2.genre_id = g2.id WHERE sg2.song_id = s.id) as genres\n        FROM songs s\n        LEFT JOIN albums al ON s.album_id = al.id\n        LEFT JOIN trivia_stats ts ON s.id = ts.song_id"

def fetch_songs(conn, *, song_id=None, audio_only=False):
    """Consistent song, artist, release and trivia metadata in one query."""
    conditions, parameters = [], []
    if song_id is not None:
        conditions.append('s.id=?')
        parameters.append(song_id)
    if audio_only:
        conditions.append("COALESCE(s.audio_url, '') != ''")
    where=' WHERE '+' AND '.join(conditions) if conditions else ''
    return conn.execute(SONG_SELECT+where,parameters).fetchall()


def get_song_full(song_id, conn):
    songs=fetch_songs(conn,song_id=song_id)
    return songs[0] if songs else None


def fetch_match_history(conn, song_id=None, limit=50):
    """Fetch match rows with both linked songs and their artists in one shared query.

    Passing a song ID scopes results to matches involving that song; omitting it
    returns the site's recent match feed. Mode is stored on history itself.
    """
    return conn.execute('''
        SELECT h.id, h.mode, h.created_at,
               w.id AS winner_id, w.title AS winner_title, wal.cover_url AS winner_cover,
               (SELECT GROUP_CONCAT(a.name, ', ')
                FROM song_artists sa JOIN artists a ON a.id = sa.artist_id
                WHERE sa.song_id = w.id) AS winner_artist,
               l.id AS loser_id, l.title AS loser_title, lal.cover_url AS loser_cover,
               (SELECT GROUP_CONCAT(a.name, ', ')
                FROM song_artists sa JOIN artists a ON a.id = sa.artist_id
                WHERE sa.song_id = l.id) AS loser_artist
        FROM history h
        JOIN songs w ON h.winner_id = w.id
        LEFT JOIN albums wal ON wal.id = w.album_id
        JOIN songs l ON h.loser_id = l.id
        LEFT JOIN albums lal ON lal.id = l.album_id
        WHERE (? IS NULL OR h.winner_id = ? OR h.loser_id = ?)
        ORDER BY h.id DESC
        LIMIT ?
    ''', (song_id, song_id, song_id, max(1, min(int(limit), 500)))).fetchall()


def get_matchup(is_blind=False):
    """Unified song selection logic utilizing the relational database."""
    conn = get_db_connection()

    songs = fetch_songs(conn, audio_only=is_blind)
    conn.close()

    if len(songs) < 2:
        return None, None

    elos = sorted([s['elo_score'] for s in songs])
    mid = len(elos) // 2

    if mid > 0:
        bottom_avg = sum(elos[:mid]) / mid
        top_avg = sum(elos[mid:]) / (len(elos) - mid)
        threshold = max((top_avg - bottom_avg) * 0.25, 50)
    else:
        threshold = 50

    def pick_weighted(pool):
        weights = [1.0 / (s['matches_played'] + 1) for s in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    song1 = pick_weighted(songs)
    pool2 = [s for s in songs if s['id'] != song1['id'] and abs(s['elo_score'] - song1['elo_score']) <= threshold]

    if not pool2:
        songs_except_1 = [s for s in songs if s['id'] != song1['id']]
        songs_except_1.sort(key=lambda x: abs(x['elo_score'] - song1['elo_score']))
        pool2 = songs_except_1[:15]

    song2 = pick_weighted(pool2)
    return song1, song2


def create_database_backup(prefix='song_ranker'):
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(f'Database not found: {DB_NAME}')
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db")
    source = sqlite3.connect(DB_NAME, timeout=30)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close(); source.close()
    return backup_path


def get_or_create_album(conn, album_title, cover_url=None):
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

    return album_id


def link_artists_to_song(conn, song_id, artist_string, default_cover=None):
    """Splits an artist string and links each artist via the song_artists junction table."""
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

    split_genres = [g.strip() for g in genre_string.split(',') if g.strip()]
    for name in split_genres:
        genre_row = conn.execute('SELECT id FROM genres WHERE name = ? COLLATE NOCASE', (name,)).fetchone()
        if genre_row:
            genre_id = genre_row['id']
        else:
            cursor = conn.execute('INSERT INTO genres (name) VALUES (?)', (name,))
            genre_id = cursor.lastrowid

        conn.execute('INSERT OR IGNORE INTO song_genres (song_id, genre_id) VALUES (?, ?)', (song_id, genre_id))


