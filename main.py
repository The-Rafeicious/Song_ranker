from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from difflib import SequenceMatcher
import random
import requests
import re
import subprocess
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "theandwasdwe"
DB_NAME = "song_ranker_v2.db" # Make sure this matches your newly migrated database name
DEV_PIN = "9042"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('dev_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
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
        if not os.path.exists(DB_NAME) and os.path.exists('database_backup.sql'):
            print("No local database found. Restoring from database_backup.sql...")
            conn = sqlite3.connect(DB_NAME)
            try:
                with open('database_backup.sql', 'r', encoding='utf-8') as f:
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
            with open('database_backup.sql', 'w', encoding='utf-8') as f:
                for line in snapshot.iterdump():
                    f.write(f'{line}\n')
        finally:
            snapshot.close()
            source.close()

        subprocess.run(["git", "add", "database_backup.sql"], check=True, timeout=30)
        result = subprocess.run(
            ["git", "commit", "-m", "Auto-sync database update"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr).lower():
            app.logger.error("Database sync commit failed: %s", result.stderr or result.stdout)
            return False
        if "nothing to commit" in (result.stdout + result.stderr).lower():
            # The remote may still be behind, so push any already-created local commit.
            app.logger.info("Database dump unchanged; checking remote sync")

        pushed = subprocess.run(
            ["git", "push", "origin", "main"], capture_output=True,
            text=True, timeout=120
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
            song1_id INTEGER NOT NULL,
            song2_id INTEGER NOT NULL,
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
        'points_version': 'INTEGER NOT NULL DEFAULT 1'
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
        CREATE TABLE IF NOT EXISTS interaction_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            song_id INTEGER,
            related_song_id INTEGER,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            details_json TEXT,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE SET NULL,
            FOREIGN KEY(related_song_id) REFERENCES songs(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS elo_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            winner_id INTEGER, loser_id INTEGER,
            winner_before REAL, winner_after REAL,
            loser_before REAL, loser_after REAL,
            mode TEXT NOT NULL DEFAULT 'standard',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(winner_id) REFERENCES songs(id) ON DELETE SET NULL,
            FOREIGN KEY(loser_id) REFERENCES songs(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL, details TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_interaction_events_type_date ON interaction_events(event_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_elo_history_date ON elo_history(created_at);
    ''')
    ensure_tournament_schema(conn)
    history_columns = {row['name'] for row in conn.execute('PRAGMA table_info(history)')}
    if 'created_at' not in history_columns:
        conn.execute('ALTER TABLE history ADD COLUMN created_at DATETIME')
    conn.execute('INSERT OR IGNORE INTO global_stats (key, value) VALUES ("trivia_high_score", 0)')
    conn.commit()
    conn.close()


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

    with open("database_snapshot.txt", "w", encoding="utf-8") as f:
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


def get_song_full(song_id, conn):
    """Helper function to fetch a single song with its linked relational data."""
    return conn.execute('''
        SELECT s.*, al.cover_url, al.title as album,
               CASE WHEN LOWER(TRIM(COALESCE(al.title, ''))) LIKE '% - single' THEN 1 ELSE 0 END AS album_is_single,
               COALESCE(ts.attempts, 0) as trivia_attempts,
               COALESCE(ts.correct, 0) as trivia_correct,
               (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) as artist,
               (SELECT GROUP_CONCAT(g2.name, ', ') FROM song_genres sg2 JOIN genres g2 ON sg2.genre_id = g2.id WHERE sg2.song_id = s.id) as genres
        FROM songs s
        LEFT JOIN albums al ON s.album_id = al.id
        LEFT JOIN trivia_stats ts ON s.id = ts.song_id
        WHERE s.id = ?
    ''', (song_id,)).fetchone()


def get_matchup(is_blind=False):
    """Unified song selection logic utilizing the relational database."""
    conn = get_db_connection()

    query = '''
            SELECT s.id, \
                   s.title, \
                   s.audio_url, \
                   s.elo_score, \
                   s.matches_played,
                   al.cover_url, \
                   GROUP_CONCAT(a.name, ', ') as artist
            FROM songs s
                     LEFT JOIN albums al ON s.album_id = al.id
                     LEFT JOIN song_artists sa ON s.id = sa.song_id
                     LEFT JOIN artists a ON sa.artist_id = a.id \
            '''
    if is_blind:
        query += ' WHERE s.audio_url IS NOT NULL AND s.audio_url != ""'

    query += ' GROUP BY s.id'
    songs = conn.execute(query).fetchall()
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


def log_interaction(conn, event_type, song_id=None, related_song_id=None, details=None):
    conn.execute('INSERT INTO interaction_events (event_type, song_id, related_song_id, details_json) VALUES (?, ?, ?, ?)',
                 (event_type, song_id, related_song_id, json.dumps(details or {}, ensure_ascii=False)))


def create_database_backup(prefix='song_ranker'):
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(f'Database not found: {DB_NAME}')
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    source = sqlite3.connect(DB_NAME, timeout=30)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close(); source.close()
    return backup_path


# --- CORE ROUTES ---

@app.route('/')
def home():
    conn = get_db_connection()

    # 1. Top 3 Songs
    top_songs = conn.execute('''
        SELECT s.id, s.title, s.elo_score, al.cover_url,
               (SELECT GROUP_CONCAT(a2.name, ', ') 
                FROM song_artists sa2 
                JOIN artists a2 ON sa2.artist_id = a2.id 
                WHERE sa2.song_id = s.id) as artist
        FROM songs s
        LEFT JOIN albums al ON s.album_id = al.id
        ORDER BY s.elo_score DESC
        LIMIT 10
    ''').fetchall()

    # 2. Top 3 Artists
    top_artists = conn.execute('''
                               SELECT a.id,
                                      a.name                         as artist,
                                      a.cover_url,
                                      COUNT(s.id)                    as song_count,
                                      AVG(s.elo_score)               as avg_elo,
                                      1200 + SUM(s.elo_score - 1200) as impact_score
                               FROM artists a
                                        JOIN song_artists sa ON a.id = sa.artist_id
                                        JOIN songs s ON sa.song_id = s.id
                               GROUP BY a.id
                               ORDER BY impact_score DESC
                               LIMIT 10
                               ''').fetchall()

    # 3. Top 3 Albums (excluding singles and placeholders)
    top_albums = conn.execute('''
        SELECT al.id, al.title as album, al.cover_url,
               COUNT(s.id) as song_count,
               AVG(s.elo_score) as avg_elo,
               1200 + SUM(s.elo_score - 1200) as impact_score,
               (SELECT a.name 
                FROM songs s2 
                JOIN song_artists sa ON s2.id = sa.song_id 
                JOIN artists a ON sa.artist_id = a.id 
                WHERE s2.album_id = al.id 
                LIMIT 1) as artist
        FROM albums al
        JOIN songs s ON al.id = s.album_id
        WHERE al.title != 'Unknown Album' 
          AND al.title != '' 
          AND al.title NOT LIKE '% - Single'
        GROUP BY al.id
        ORDER BY impact_score DESC
        LIMIT 10
    ''').fetchall()

    # 4. Trivia Spotlight (Track with highest recognizability with at least 1 attempt)
    trivia_spotlight = conn.execute('''
        SELECT s.id, s.title, al.cover_url,
               (SELECT GROUP_CONCAT(a2.name, ', ') 
                FROM song_artists sa2 
                JOIN artists a2 ON sa2.artist_id = a2.id 
                WHERE sa2.song_id = s.id) as artist,
               ts.attempts, ts.correct,
               ROUND((CAST(ts.correct AS FLOAT) / (ts.attempts * 2)) * 100) as rec_score
        FROM songs s
        JOIN trivia_stats ts ON s.id = ts.song_id
        LEFT JOIN albums al ON s.album_id = al.id
        WHERE ts.attempts > 0
        ORDER BY rec_score DESC, ts.attempts DESC
        LIMIT 1
    ''').fetchone()

    conn.close()

    return render_template(
        'home.html',
        top_songs=top_songs,
        top_artists=top_artists,
        top_albums=top_albums,
        trivia_spotlight=trivia_spotlight
    )


@app.route('/game')
def index():
    conn = get_db_connection()
    if 'song1_id' in session and 'song2_id' in session:
        song1 = get_song_full(session['song1_id'], conn)
        song2 = get_song_full(session['song2_id'], conn)

        if song1 and song2:
            conn.close()
            return render_template('index.html', song1=song1, song2=song2, last_vote=session.get('last_vote'))

    conn.close()
    song1, song2 = get_matchup(is_blind=False)

    if not song1 or not song2:
        return "<h1>Not enough songs in the database. Add at least two!</h1>"

    session['song1_id'] = song1['id']
    session['song2_id'] = song2['id']
    last_vote = session.pop('last_vote', None)

    return render_template('index.html', song1=song1, song2=song2, last_vote=last_vote)


@app.route('/vote', methods=['POST'])
def vote():
    winner_id = request.form['winner_id']
    loser_id = request.form['loser_id']

    conn = get_db_connection()
    winner = get_song_full(winner_id, conn)
    loser = get_song_full(loser_id, conn)

    new_winner_elo, new_loser_elo = calculate_new_elo(winner['elo_score'], loser['elo_score'])
    winner_new_rank = conn.execute('SELECT COUNT(*) + 1 FROM songs WHERE elo_score > ?', (new_winner_elo,)).fetchone()[
        0]

    session['last_vote'] = {
        'winner_title': winner['title'],
        'winner_old': int(winner['elo_score']),
        'winner_new': int(new_winner_elo),
        'winner_change': f"+{int(new_winner_elo - winner['elo_score'])}",
        'loser_title': loser['title'],
        'loser_old': int(loser['elo_score']),
        'loser_new': int(new_loser_elo),
        'loser_change': f"{int(new_loser_elo - loser['elo_score'])}"
    }

    conn.execute('''
                 UPDATE songs
                 SET elo_score      = ?,
                     matches_played = matches_played + 1,
                     highest_elo    = CASE WHEN ? > highest_elo THEN ? ELSE highest_elo END,
                     highest_rank   = CASE WHEN ? < highest_rank OR highest_rank = 9999 THEN ? ELSE highest_rank END
                 WHERE id = ?
                 ''', (new_winner_elo, new_winner_elo, new_winner_elo, winner_new_rank, winner_new_rank, winner_id))

    conn.execute('UPDATE songs SET elo_score = ?, matches_played = matches_played + 1 WHERE id = ?',
                 (new_loser_elo, loser_id))
    conn.execute('INSERT INTO history (winner_id, loser_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (winner_id, loser_id))
    conn.execute('INSERT INTO elo_history (winner_id, loser_id, winner_before, winner_after, loser_before, loser_after, mode) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (winner_id, loser_id, winner['elo_score'], new_winner_elo, loser['elo_score'], new_loser_elo, 'standard'))
    log_interaction(conn, 'vote', winner_id, loser_id, {'mode': 'standard'})

    total_votes = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]
    conn.commit()
    conn.close()

    session.pop('song1_id', None)
    session.pop('song2_id', None)
    return redirect(url_for('index'))


@app.route('/blind')
def blind_mode():
    song1, song2 = get_matchup(is_blind=True)
    if not song1 or not song2:
        return "Not enough songs with audio previews to play Blind Mode."
    return render_template('blind_mode.html', song1=song1, song2=song2)


@app.route('/api/blind_vote', methods=['POST'])
def api_blind_vote():
    data = request.json
    winner_id = data['winner_id']
    loser_id = data['loser_id']

    conn = get_db_connection()
    winner = get_song_full(winner_id, conn)
    loser = get_song_full(loser_id, conn)

    new_winner_elo, new_loser_elo = calculate_new_elo(winner['elo_score'], loser['elo_score'])
    winner_new_rank = conn.execute('SELECT COUNT(*) + 1 FROM songs WHERE elo_score > ?', (new_winner_elo,)).fetchone()[
        0]

    conn.execute('''
                 UPDATE songs
                 SET elo_score      = ?,
                     matches_played = matches_played + 1,
                     highest_elo    = CASE WHEN ? > highest_elo THEN ? ELSE highest_elo END,
                     highest_rank   = CASE WHEN ? < highest_rank OR highest_rank = 9999 THEN ? ELSE highest_rank END
                 WHERE id = ?
                 ''', (new_winner_elo, new_winner_elo, new_winner_elo, winner_new_rank, winner_new_rank, winner_id))

    conn.execute('UPDATE songs SET elo_score = ?, matches_played = matches_played + 1 WHERE id = ?',
                 (new_loser_elo, loser_id))
    conn.execute('INSERT INTO history (winner_id, loser_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (winner_id, loser_id))
    conn.execute('INSERT INTO elo_history (winner_id, loser_id, winner_before, winner_after, loser_before, loser_after, mode) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (winner_id, loser_id, winner['elo_score'], new_winner_elo, loser['elo_score'], new_loser_elo, 'blind'))
    log_interaction(conn, 'vote', winner_id, loser_id, {'mode': 'blind'})
    conn.commit()
    conn.close()

    return jsonify({
        "winner": {"title": winner['title'], "artist": winner['artist'], "cover_url": winner['cover_url'],
                   "elo_change": f"+{int(new_winner_elo - winner['elo_score'])}"},
        "loser": {"title": loser['title'], "artist": loser['artist'], "cover_url": loser['cover_url'],
                  "elo_change": f"{int(new_loser_elo - loser['elo_score'])}"}
    })


# --- TRIVIA MODE ---

@app.route('/trivia')
def trivia_mode():
    conn = get_db_connection()
    high_score_row = conn.execute('SELECT value FROM global_stats WHERE key = "trivia_high_score"').fetchone()
    high_score = high_score_row['value'] if high_score_row else 0

    if 'trivia_score' not in session: session['trivia_score'] = 0
    if 'trivia_streak' not in session: session['trivia_streak'] = 0

    pool = conn.execute('''
                        SELECT s.id, s.audio_url, COALESCE(ts.attempts, 0) as trivia_attempts
                        FROM songs s
                                 LEFT JOIN trivia_stats ts ON s.id = ts.song_id
                        WHERE s.audio_url IS NOT NULL
                          AND s.audio_url != ""
                        ORDER BY trivia_attempts ASC, RANDOM()
                            LIMIT 30
                        ''').fetchall()
    conn.close()

    if not pool:
        return "No songs with audio previews available to play Trivia."

    song = random.choice(pool)
    return render_template('trivia_mode.html', song=song, score=session['trivia_score'],
                           streak=session['trivia_streak'], high_score=high_score)


@app.route('/api/trivia_guess', methods=['POST'])
def api_trivia_guess():
    data = request.json
    song_id = data['song_id']
    time_taken = float(data.get('time_taken', 30.0))
    timeout = data.get('timeout', False)

    conn = get_db_connection()
    song = get_song_full(song_id, conn)

    title_match = False if timeout else is_close_match(data.get('title_guess', ''), song['title'])
    artist_match = False if timeout else is_close_match(data.get('artist_guess', ''), song['artist'])

    correct_count = sum([title_match, artist_match])
    points = 0
    speed_bonus = 0
    game_over = False

    if correct_count > 0:
        points += (correct_count * 100)
        speed_bonus = max(0, int((1.0 - (time_taken / 30.0)) * 100))
        points += speed_bonus
        session['trivia_streak'] = session.get('trivia_streak', 0) + 1
        session['trivia_score'] = session.get('trivia_score', 0) + points
    else:
        game_over = True

    final_score = session.get('trivia_score', 0)
    high_score_row = conn.execute('SELECT value FROM global_stats WHERE key = "trivia_high_score"').fetchone()
    high_score = high_score_row['value'] if high_score_row else 0

    new_high_score = False
    if final_score > high_score:
        conn.execute('UPDATE global_stats SET value = ? WHERE key = "trivia_high_score"', (final_score,))
        high_score = final_score
        new_high_score = True

    if game_over:
        session['trivia_score'] = 0
        session['trivia_streak'] = 0

    cursor = conn.execute('UPDATE trivia_stats SET attempts = attempts + 1, correct = correct + ? WHERE song_id = ?',
                          (correct_count, song_id))
    if cursor.rowcount == 0:
        conn.execute('INSERT INTO trivia_stats (song_id, attempts, correct) VALUES (?, 1, ?)', (song_id, correct_count))
    log_interaction(conn, 'trivia_guess', song_id, details={
        'title_correct': bool(title_match), 'artist_correct': bool(artist_match),
        'correct_fields': int(correct_count), 'points': int(points),
        'time_taken': round(time_taken, 2), 'timeout': bool(timeout)
    })

    conn.commit()
    conn.close()

    return jsonify({
        "actual_title": song['title'],
        "actual_artist": song['artist'],
        "cover_url": song['cover_url'],
        "points_earned": points,
        "speed_bonus": speed_bonus,
        "new_total": final_score,
        "title_correct": title_match,
        "artist_correct": artist_match,
        "game_over": game_over,
        "new_high_score": new_high_score,
        "high_score": high_score
    })


@app.route('/tournament')
def tournament():
    # Pass lists of artists and albums to the frontend so the user can select a specific scope
    conn = get_db_connection()
    artists = [dict(row) for row in
               conn.execute('SELECT id, name FROM artists ORDER BY name COLLATE NOCASE').fetchall()]
    albums = [dict(row) for row in conn.execute(
        'SELECT id, title FROM albums WHERE title != "Unknown Album" AND title NOT LIKE "% - Single" ORDER BY title COLLATE NOCASE').fetchall()]
    conn.close()

    return render_template('tournament.html', artists=artists, albums=albums)


@app.route('/api/generate_bracket')
def api_generate_bracket():
    size = request.args.get('size', 8, type=int)
    scope = request.args.get('scope', 'global')
    scope_id = request.args.get('scope_id', type=int)
    if size not in (8, 16, 32):
        return jsonify({'error': 'Tournament size must be 8, 16, or 32.'}), 400
    if scope not in ('global', 'artist', 'album'):
        return jsonify({'error': 'Invalid tournament scope.'}), 400
    if scope != 'global' and not scope_id:
        return jsonify({'error': 'An artist or album must be selected.'}), 400

    conn = get_db_connection()
    try:
        if scope == 'artist':
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s JOIN song_artists sa ON s.id = sa.song_id
                LEFT JOIN albums al ON s.album_id = al.id
                WHERE sa.artist_id = ? ORDER BY RANDOM() LIMIT ?'''
            params = (scope_id, size)
        elif scope == 'album':
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s LEFT JOIN albums al ON s.album_id = al.id
                WHERE s.album_id = ? ORDER BY RANDOM() LIMIT ?'''
            params = (scope_id, size)
        else:
            query = '''SELECT s.id, s.title, s.audio_url, s.elo_score, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = s.id) AS artist
                FROM songs s LEFT JOIN albums al ON s.album_id = al.id
                ORDER BY RANDOM() LIMIT ?'''
            params = (size,)

        songs = [dict(row) for row in conn.execute(query, params).fetchall()]
        if len(songs) < size:
            return jsonify({'error': f'Not enough tracks found. Needed {size}, found {len(songs)}.'}), 400
        songs.sort(key=lambda song: song['elo_score'], reverse=True)

        cursor = conn.execute('''INSERT INTO tournaments
            (size, scope_type, scope_id, status, created_at, updated_at, current_round, points_version)
            VALUES (?, ?, ?, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 1)''',
            (size, scope, scope_id))
        tournament_id = cursor.lastrowid
        for seed, song in enumerate(songs, start=1):
            conn.execute('INSERT INTO tournament_entries (tournament_id, song_id, seed) VALUES (?, ?, ?)',
                         (tournament_id, song['id'], seed))
        # Mirror tournament.html's standard seeding order so persisted matches match the UI.
        seed_order = _tournament_seed_order(size)
        for i in range(0, size, 2):
            song1 = songs[seed_order[i]]
            song2 = songs[seed_order[i + 1]]
            conn.execute('''INSERT INTO tournament_matches
                (tournament_id, round_number, match_number, song1_id, song2_id)
                VALUES (?, 1, ?, ?, ?)''',
                (tournament_id, (i // 2) + 1, song1['id'], song2['id']))
        conn.commit()
        return jsonify({'tournament_id': tournament_id, 'tracks': songs,
                        'matches': _tournament_matches(conn, tournament_id)})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not create tournament')
        return jsonify({'error': 'Could not create tournament.'}), 500
    finally:
        conn.close()


def _tournament_seed_order(size):
    """Return zero-based track indexes in the same bracket seeding order as tournament.html."""
    bracket = [1]
    rounds = size.bit_length() - 1
    for r in range(rounds):
        seed_sum = (2 ** (r + 1)) + 1
        next_bracket = []
        for seed in bracket:
            next_bracket.extend((seed, seed_sum - seed))
        bracket = next_bracket
    return [seed - 1 for seed in bracket]


def _tournament_matches(conn, tournament_id):
    rows = conn.execute('''SELECT id, tournament_id, round_number, match_number,
        song1_id, song2_id, winner_id, loser_id, status, points_awarded, played_at
        FROM tournament_matches WHERE tournament_id = ?
        ORDER BY round_number, match_number''', (tournament_id,)).fetchall()
    return [dict(row) for row in rows]


def _round_points(size, round_number):
    # Normalize the maximum points for a champion to 7 across bracket sizes.
    return round(7 * (2 ** (round_number - 1)) / (size - 1), 4)


@app.route('/api/tournament_vote', methods=['POST'])
def api_tournament_vote():
    data = request.get_json(silent=True) or {}
    tournament_id = data.get('tournament_id')
    match_id = data.get('match_id')
    winner_id = data.get('winner_id')
    loser_id = data.get('loser_id')
    if not all((tournament_id, match_id, winner_id, loser_id)) or winner_id == loser_id:
        return jsonify({'error': 'tournament_id, match_id, distinct winner_id and loser_id are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament = conn.execute('SELECT size, status FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        match = conn.execute('SELECT * FROM tournament_matches WHERE id = ? AND tournament_id = ?',
                             (match_id, tournament_id)).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({'error': 'Tournament not found.'}), 404
        if tournament['status'] != 'in_progress':
            conn.rollback()
            return jsonify({'error': 'Tournament is not in progress.'}), 409
        if not match:
            conn.rollback()
            return jsonify({'error': 'Match does not belong to this tournament.'}), 404
        if match['status'] != 'pending':
            conn.rollback()
            return jsonify({'error': 'This match has already been recorded.'}), 409
        if {winner_id, loser_id} != {match['song1_id'], match['song2_id']}:
            conn.rollback()
            return jsonify({'error': 'Winner and loser must be the two songs in this match.'}), 400

        points = _round_points(tournament['size'], match['round_number'])
        conn.execute('''UPDATE tournament_matches SET winner_id = ?, loser_id = ?, status = 'completed',
            points_awarded = ?, played_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (winner_id, loser_id, points, match_id))
        log_interaction(conn, 'tournament_vote', winner_id, loser_id, {'tournament_id': int(tournament_id), 'points_awarded': points})
        round_rows = conn.execute('''SELECT * FROM tournament_matches
            WHERE tournament_id = ? AND round_number = ? ORDER BY match_number''',
            (tournament_id, match['round_number'])).fetchall()
        if all(row['status'] == 'completed' or row['id'] == match_id for row in round_rows):
            winners = [winner_id if row['id'] == match_id else row['winner_id'] for row in round_rows]
            if len(winners) > 1:
                next_round = match['round_number'] + 1
                for i in range(0, len(winners), 2):
                    conn.execute('''INSERT OR IGNORE INTO tournament_matches
                        (tournament_id, round_number, match_number, song1_id, song2_id)
                        VALUES (?, ?, ?, ?, ?)''',
                        (tournament_id, next_round, (i // 2) + 1, winners[i], winners[i + 1]))
                conn.execute('UPDATE tournaments SET current_round = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                             (next_round, tournament_id))
            else:
                conn.execute('UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (tournament_id,))
        conn.commit()
        return jsonify({'success': True, 'points_awarded': points,
                        'matches': _tournament_matches(conn, tournament_id)})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not record tournament vote')
        return jsonify({'error': 'Could not save this vote.'}), 500
    finally:
        conn.close()


@app.route('/api/tournaments', methods=['GET'])
def api_tournaments_list():
    conn = get_db_connection()
    try:
        rows = conn.execute('''SELECT t.id, t.size, t.scope_type, t.scope_id, t.status,
            t.champion_id, t.created_at, t.updated_at, t.completed_at,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id AND tm.status = 'completed') AS matches_completed,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id) AS matches_created
            FROM tournaments t ORDER BY CASE t.status WHEN 'in_progress' THEN 0 ELSE 1 END,
            COALESCE(t.updated_at, t.timestamp) DESC''').fetchall()
        return jsonify({'tournaments': [dict(row) for row in rows]})
    finally:
        conn.close()


@app.route('/api/tournaments/<int:tournament_id>', methods=['GET'])
def api_tournament_detail(tournament_id):
    conn = get_db_connection()
    try:
        tournament = conn.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        if not tournament:
            return jsonify({'error': 'Tournament not found.'}), 404
        entries = conn.execute('''SELECT e.seed, s.id, s.title, s.audio_url, s.elo_score,
            al.cover_url, (SELECT GROUP_CONCAT(a.name, ', ') FROM song_artists sa
            JOIN artists a ON a.id = sa.artist_id WHERE sa.song_id = s.id) AS artist
            FROM tournament_entries e JOIN songs s ON s.id = e.song_id
            LEFT JOIN albums al ON al.id = s.album_id
            WHERE e.tournament_id = ? ORDER BY e.seed''', (tournament_id,)).fetchall()
        return jsonify({'tournament': dict(tournament), 'entries': [dict(row) for row in entries],
                        'matches': _tournament_matches(conn, tournament_id)})
    finally:
        conn.close()


@app.route('/tournament_stats')
def tournament_stats_page():
    """Render the dedicated tournament leaderboard and history page."""
    return render_template('tournament_stats.html')


@app.route('/api/tournament_stats', methods=['GET'])
def api_tournament_stats():
    """Tournament-only leaderboard; regular Elo and history are not involved."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT s.id, s.title, al.cover_url,
                (SELECT GROUP_CONCAT(a.name, ', ') FROM song_artists sa
                 JOIN artists a ON a.id = sa.artist_id WHERE sa.song_id = s.id) AS artist,
                (SELECT COUNT(*) FROM tournament_entries te WHERE te.song_id = s.id) AS tournaments_entered,
                (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.winner_id = s.id) AS matches_won,
                (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.loser_id = s.id) AS matches_lost,
                (SELECT COALESCE(SUM(tm.points_awarded), 0) FROM tournament_matches tm
                 WHERE tm.winner_id = s.id) AS tournament_points,
                (SELECT COUNT(*) FROM tournaments t WHERE t.champion_id = s.id AND t.status = 'completed') AS championships
            FROM songs s LEFT JOIN albums al ON al.id = s.album_id
            ORDER BY championships DESC, tournament_points DESC,
                CASE WHEN (SELECT COUNT(*) FROM tournament_matches tm
                           WHERE tm.winner_id = s.id OR tm.loser_id = s.id) = 0 THEN -1.0
                     ELSE CAST((SELECT COUNT(*) FROM tournament_matches tm WHERE tm.winner_id = s.id) AS REAL)
                          / (SELECT COUNT(*) FROM tournament_matches tm
                             WHERE tm.winner_id = s.id OR tm.loser_id = s.id) END DESC,
                tournaments_entered DESC, s.title COLLATE NOCASE
        ''').fetchall()
        result = []
        for row in rows:
            item = dict(row)
            played = item['matches_won'] + item['matches_lost']
            item['matches_played'] = played
            item['win_rate'] = round(item['matches_won'] * 100 / played, 2) if played else None
            item['tournament_points'] = round(item['tournament_points'], 4)
            result.append(item)
        return jsonify({'songs': result})
    finally:
        conn.close()


@app.route('/api/tournament_complete', methods=['POST'])
def api_tournament_complete():
    data = request.get_json(silent=True) or {}
    tournament_id = data.get('tournament_id')
    champion_id = data.get('champion_id')
    if not tournament_id or not champion_id:
        return jsonify({'error': 'tournament_id and champion_id are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        tournament = conn.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,)).fetchone()
        if not tournament:
            conn.rollback()
            return jsonify({'error': 'Tournament not found.'}), 404
        if tournament['status'] == 'completed':
            conn.rollback()
            if tournament['champion_id'] == champion_id:
                return jsonify({'success': True, 'already_completed': True})
            return jsonify({'error': 'Tournament has already been completed.'}), 409
        if tournament['status'] != 'in_progress':
            conn.rollback()
            return jsonify({'error': 'Tournament is not in progress.'}), 409
        pending = conn.execute('''SELECT COUNT(*) FROM tournament_matches
            WHERE tournament_id = ? AND status != 'completed' ''', (tournament_id,)).fetchone()[0]
        final_match = conn.execute('''SELECT winner_id FROM tournament_matches
            WHERE tournament_id = ? ORDER BY round_number DESC, match_number ASC LIMIT 1''',
            (tournament_id,)).fetchone()
        if pending or not final_match or final_match['winner_id'] != champion_id:
            conn.rollback()
            return jsonify({'error': 'All matches must be complete and champion must be the final winner.'}), 409
        conn.execute('''UPDATE tournaments SET champion_id = ?, status = 'completed',
            completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (champion_id, tournament_id))
        conn.execute('UPDATE songs SET tournament_wins = tournament_wins + 1 WHERE id = ?', (champion_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception:
        conn.rollback()
        app.logger.exception('Could not complete tournament')
        return jsonify({'error': 'Could not complete tournament.'}), 500
    finally:
        conn.close()

# --- PUBLIC PAGES & LEADERBOARDS ---

@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    top_songs = conn.execute('''
                             SELECT s.id,
                                    s.title,
                                    s.elo_score,
                                    al.title                   as album,
                                    al.cover_url,
                                    GROUP_CONCAT(a.name, ', ') as artist
                             FROM songs s
                                      LEFT JOIN albums al ON s.album_id = al.id
                                      LEFT JOIN song_artists sa ON s.id = sa.song_id
                                      LEFT JOIN artists a ON sa.artist_id = a.id
                             GROUP BY s.id
                             ORDER BY s.elo_score DESC
                             LIMIT 20
                             ''').fetchall()
    conn.close()
    return render_template('leaderboard.html', songs=top_songs)


@app.route('/artists')
def artists_leaderboard():
    conn = get_db_connection()
    top_artists = conn.execute('''
                               SELECT a.name                         as artist,
                                      a.cover_url                    as sample_cover,
                                      COUNT(s.id)                    as song_count,
                                      AVG(s.elo_score)               as avg_elo,
                                      1200 + SUM(s.elo_score - 1200) as artist_score
                               FROM artists a
                                        JOIN song_artists sa ON a.id = sa.artist_id
                                        JOIN songs s ON sa.song_id = s.id
                               GROUP BY a.id
                               ORDER BY artist_score DESC
                               LIMIT 10
                               ''').fetchall()
    conn.close()
    return render_template('artists_leaderboard.html', artists=top_artists)


@app.route('/albums')
def albums_leaderboard():
    conn = get_db_connection()
    albums_data = conn.execute('''
        SELECT al.title as album, al.cover_url as sample_cover, 
               COUNT(s.id) as song_count, 
               AVG(s.elo_score) as avg_elo, 
               1200 + SUM(s.elo_score - 1200) as album_score,
               GROUP_CONCAT(DISTINCT a.name) as artist
        FROM albums al
        JOIN songs s ON al.id = s.album_id
        LEFT JOIN song_artists sa ON s.id = sa.song_id
        LEFT JOIN artists a ON sa.artist_id = a.id
        WHERE al.title != 'Unknown Album' 
          AND al.title != '' 
          AND al.title NOT LIKE '% - Single'
        GROUP BY al.id 
        ORDER BY album_score DESC 
        LIMIT 10
    ''').fetchall()
    conn.close()
    return render_template('albums_leaderboard.html', albums=albums_data)


@app.route('/api/library', methods=['GET'])
def api_library():
    """Paginated library data for the Search page's browse-all mode.

    type is one of songs, artists, or albums. q is optional and matches names,
    related artists, and album/song metadata where relevant.
    """
    category = request.args.get('type', 'songs').lower().strip()
    query = request.args.get('q', '').strip()
    try:
        limit = max(1, min(int(request.args.get('limit', 60)), 200))
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        return jsonify({'error': 'limit and offset must be integers.'}), 400
    if category not in {'songs', 'artists', 'albums'}:
        return jsonify({'error': 'type must be songs, artists, or albums.'}), 400

    conn = get_db_connection()
    try:
        term = f'%{query}%'
        if category == 'songs':
            where = '''WHERE (? = '' OR s.title LIKE ? OR a.name LIKE ? OR al.title LIKE ?)'''
            params = (query, term, term, term)
            from_sql = '''FROM songs s LEFT JOIN albums al ON al.id = s.album_id
                LEFT JOIN song_artists sa ON sa.song_id = s.id
                LEFT JOIN artists a ON a.id = sa.artist_id'''
            total = conn.execute(f'SELECT COUNT(DISTINCT s.id) {from_sql} {where}', params).fetchone()[0]
            rows = conn.execute(f'''SELECT s.id, s.title, s.elo_score, s.matches_played,
                al.title AS album, al.cover_url,
                (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2
                 JOIN artists a2 ON a2.id = sa2.artist_id WHERE sa2.song_id = s.id) AS artist
                {from_sql} {where} GROUP BY s.id ORDER BY s.elo_score DESC, s.title COLLATE NOCASE
                LIMIT ? OFFSET ?''', params + (limit, offset)).fetchall()
        elif category == 'artists':
            from_sql = '''FROM artists a LEFT JOIN song_artists sa ON sa.artist_id = a.id
                LEFT JOIN songs s ON s.id = sa.song_id'''
            where = "WHERE (? = '' OR a.name LIKE ?)"
            params = (query, term)
            total = conn.execute(f'SELECT COUNT(DISTINCT a.id) {from_sql} {where}', params).fetchone()[0]
            rows = conn.execute(f'''SELECT a.id, a.name, a.cover_url, COUNT(DISTINCT s.id) AS song_count,
                ROUND(AVG(s.elo_score), 1) AS avg_elo {from_sql} {where}
                GROUP BY a.id ORDER BY a.name COLLATE NOCASE LIMIT ? OFFSET ?''',
                params + (limit, offset)).fetchall()
        else:
            from_sql = '''FROM albums al LEFT JOIN songs s ON s.album_id = al.id
                LEFT JOIN song_artists sa ON sa.song_id = s.id LEFT JOIN artists a ON a.id = sa.artist_id'''
            where = '''WHERE al.title != 'Unknown Album' AND al.title != ''
                AND al.title NOT LIKE '% - Single' AND (? = '' OR al.title LIKE ? OR a.name LIKE ?)'''
            params = (query, term, term)
            total = conn.execute(f'SELECT COUNT(DISTINCT al.id) {from_sql} {where}', params).fetchone()[0]
            rows = conn.execute(f'''SELECT al.id, al.title, al.cover_url, al.release_date,
                COUNT(DISTINCT s.id) AS song_count, ROUND(AVG(s.elo_score), 1) AS avg_elo,
                (SELECT a2.name FROM songs s2 JOIN song_artists sa2 ON sa2.song_id = s2.id
                 JOIN artists a2 ON a2.id = sa2.artist_id WHERE s2.album_id = al.id
                 ORDER BY s2.elo_score DESC LIMIT 1) AS artist
                {from_sql} {where} GROUP BY al.id
                ORDER BY al.title COLLATE NOCASE LIMIT ? OFFSET ?''', params + (limit, offset)).fetchall()
        return jsonify({'type': category, 'query': query, 'items': [dict(row) for row in rows],
                        'total': total, 'limit': limit, 'offset': offset,
                        'has_more': offset + len(rows) < total})
    finally:
        conn.close()


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    conn = get_db_connection()

    if query:
        search_term = f"%{query}%"

        # 1. Fetch Albums (Includes albums matching the search, OR albums containing songs/artists matching the search)
        albums = [dict(row) for row in conn.execute('''
                                                    SELECT DISTINCT al.*
                                                    FROM albums al
                                                             LEFT JOIN songs s ON s.album_id = al.id
                                                             LEFT JOIN song_artists sa ON sa.song_id = s.id
                                                             LEFT JOIN artists a ON sa.artist_id = a.id
                                                    WHERE (al.title LIKE ? OR s.title LIKE ? OR a.name LIKE ?)
                                                      AND al.title != "Unknown Album"
                                                      AND al.title NOT LIKE "% - Single"
                                                    ''', (search_term, search_term, search_term)).fetchall()]

        # 2. Fetch Artists (Includes artists matching the search, OR artists linked to matched songs/albums)
        artists = [dict(row) for row in conn.execute('''
                                                     SELECT DISTINCT a.*
                                                     FROM artists a
                                                              LEFT JOIN song_artists sa ON sa.artist_id = a.id
                                                              LEFT JOIN songs s ON sa.song_id = s.id
                                                              LEFT JOIN albums al ON s.album_id = al.id
                                                     WHERE (a.name LIKE ? OR s.title LIKE ? OR al.title LIKE ?)
                                                     ''', (search_term, search_term, search_term)).fetchall()]

        # 3. Fetch Songs (Includes songs matching the search, OR songs linked to matched artists/albums)
        songs = [dict(row) for row in conn.execute('''
                                                   SELECT DISTINCT s.id,
                                                                   s.title,
                                                                   s.elo_score,
                                                                   s.matches_played,
                                                                   al.title                   as album,
                                                                   al.cover_url,
                                                                   (SELECT GROUP_CONCAT(a2.name, ', ')
                                                                    FROM song_artists sa2
                                                                             JOIN artists a2 ON sa2.artist_id = a2.id
                                                                    WHERE sa2.song_id = s.id) as artist
                                                   FROM songs s
                                                            LEFT JOIN albums al ON s.album_id = al.id
                                                            LEFT JOIN song_artists sa ON sa.song_id = s.id
                                                            LEFT JOIN artists a ON sa.artist_id = a.id
                                                   WHERE (s.title LIKE ? OR a.name LIKE ? OR al.title LIKE ?)
                                                   ORDER BY s.elo_score DESC
                                                   ''', (search_term, search_term, search_term)).fetchall()]

        # 4. Check for exact matches to determine the priority order
        exact_artist = conn.execute('SELECT 1 FROM artists WHERE name LIKE ? COLLATE NOCASE',
                                    (query,)).fetchone() is not None
        exact_album = conn.execute('SELECT 1 FROM albums WHERE title LIKE ? COLLATE NOCASE',
                                   (query,)).fetchone() is not None

        if exact_artist:
            sections = [('Artists', artists, 'artist'), ('Albums', albums, 'album'), ('Songs', songs, 'song')]
        elif exact_album:
            sections = [('Albums', albums, 'album'), ('Artists', artists, 'artist'), ('Songs', songs, 'song')]
        else:
            # Default to Song priority
            sections = [('Songs', songs, 'song'), ('Artists', artists, 'artist'), ('Albums', albums, 'album')]

    else:
        sections = []

    conn.close()
    return render_template('search_results.html', query=query, sections=sections)


@app.route('/tiers')
def tier_list():
    conn = get_db_connection()
    songs = conn.execute('''
                         SELECT s.id,
                                s.title,
                                s.elo_score,
                                al.cover_url,
                                (SELECT GROUP_CONCAT(a2.name, ', ')
                                 FROM song_artists sa2
                                          JOIN artists a2 ON sa2.artist_id = a2.id
                                 WHERE sa2.song_id = s.id) as artist
                         FROM songs s
                                  LEFT JOIN albums al ON s.album_id = al.id
                         ORDER BY s.elo_score DESC
                         ''').fetchall()
    conn.close()

    tiers = {
        'S': [s for s in songs if s['elo_score'] >= 1600],
        'A': [s for s in songs if 1400 <= s['elo_score'] < 1600],
        'B': [s for s in songs if 1200 <= s['elo_score'] < 1400],
        'C': [s for s in songs if 1000 <= s['elo_score'] < 1200],
        'D': [s for s in songs if s['elo_score'] < 1000]
    }
    return render_template('tier_list.html', tiers=tiers)


@app.route('/history')
def history():
    conn = get_db_connection()
    # Fetch last 50 matches, ensuring we grab the IDs so we can link to them
    history_data = conn.execute('''
        SELECT h.id, 
               w.id as winner_id, w.title as winner_title, aw.cover_url as winner_cover,
               (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = w.id) as winner_artist,
               l.id as loser_id, l.title as loser_title, al.cover_url as loser_cover,
               (SELECT GROUP_CONCAT(a2.name, ', ') FROM song_artists sa2 JOIN artists a2 ON sa2.artist_id = a2.id WHERE sa2.song_id = l.id) as loser_artist
        FROM history h
        JOIN songs w ON h.winner_id = w.id
        JOIN songs l ON h.loser_id = l.id
        LEFT JOIN albums aw ON w.album_id = aw.id
        LEFT JOIN albums al ON l.album_id = al.id
        ORDER BY h.id DESC
        LIMIT 50
    ''').fetchall()
    conn.close()
    return render_template('history.html', history=history_data)


@app.route('/global_stats')
def global_stats():
    conn = get_db_connection()

    # 1. Core Totals
    total_songs = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    total_artists = conn.execute('SELECT COUNT(*) FROM artists').fetchone()[0]
    total_albums = conn.execute('''
                                SELECT COUNT(*)
                                FROM albums
                                WHERE title != "Unknown Album"
                                  AND title NOT LIKE "% - Single"
                                ''').fetchone()[0]
    total_matches = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]

    # 2. Most Frequent Matchups (Rivalries)
    frequent_matchups = conn.execute('''
                                     SELECT CASE WHEN winner_id < loser_id THEN winner_id ELSE loser_id END as s1_id,
                                            CASE WHEN winner_id < loser_id THEN loser_id ELSE winner_id END as s2_id,
                                            COUNT(*)                                                        as encounters
                                     FROM history
                                     GROUP BY s1_id, s2_id
                                     ORDER BY encounters DESC
                                     LIMIT 5
                                     ''').fetchall()

    matchups_data = []
    for m in frequent_matchups:
        # Join albums for cover_url, and subquery artists for the artist name
        s1 = conn.execute('''
                          SELECT s.id,
                                 s.title,
                                 al.cover_url,
                                 (SELECT GROUP_CONCAT(a.name, ', ')
                                  FROM song_artists sa
                                           JOIN artists a ON sa.artist_id = a.id
                                  WHERE sa.song_id = s.id) as artist
                          FROM songs s
                                   LEFT JOIN albums al ON s.album_id = al.id
                          WHERE s.id = ?
                          ''', (m['s1_id'],)).fetchone()

        s2 = conn.execute('''
                          SELECT s.id,
                                 s.title,
                                 al.cover_url,
                                 (SELECT GROUP_CONCAT(a.name, ', ')
                                  FROM song_artists sa
                                           JOIN artists a ON sa.artist_id = a.id
                                  WHERE sa.song_id = s.id) as artist
                          FROM songs s
                                   LEFT JOIN albums al ON s.album_id = al.id
                          WHERE s.id = ?
                          ''', (m['s2_id'],)).fetchone()

        if s1 and s2:
            matchups_data.append({'s1': s1, 's2': s2, 'encounters': m['encounters']})

    # 3. Fun Superlatives
    # Join albums for cover_url, and subquery artists for the artist name
    most_played = conn.execute('''
                               SELECT s.id,
                                      s.title,
                                      s.matches_played,
                                      al.cover_url,
                                      (SELECT GROUP_CONCAT(a.name, ', ')
                                       FROM song_artists sa
                                                JOIN artists a ON sa.artist_id = a.id
                                       WHERE sa.song_id = s.id) as artist
                               FROM songs s
                                        LEFT JOIN albums al ON s.album_id = al.id
                               ORDER BY s.matches_played DESC
                               LIMIT 1
                               ''').fetchone()

    prolific_artist = conn.execute('''
                                   SELECT a.name as artist, a.cover_url, COUNT(sa.song_id) as track_count
                                   FROM artists a
                                            JOIN song_artists sa ON a.id = sa.artist_id
                                   GROUP BY a.id
                                   ORDER BY track_count DESC
                                   LIMIT 1
                                   ''').fetchone()

    top_genre = conn.execute('''
                             SELECT g.name, COUNT(sg.song_id) as tag_count
                             FROM genres g
                                      JOIN song_genres sg ON g.id = sg.genre_id
                             GROUP BY g.id
                             ORDER BY tag_count DESC
                             LIMIT 1
                             ''').fetchone()

    extra_stats = {
        'genres_count': conn.execute('SELECT COUNT(*) FROM genres').fetchone()[0],
        'songs_never_voted': conn.execute('SELECT COUNT(*) FROM songs WHERE COALESCE(matches_played,0)=0').fetchone()[0],
        'songs_with_audio': conn.execute("SELECT COUNT(*) FROM songs WHERE COALESCE(audio_url,'') != ''").fetchone()[0],
        'average_elo': round(conn.execute('SELECT COALESCE(AVG(elo_score),1200) FROM songs').fetchone()[0]),
        'highest_elo': conn.execute('SELECT id,title,elo_score FROM songs ORDER BY elo_score DESC,title LIMIT 1').fetchone(),
        'lowest_elo': conn.execute('SELECT id,title,elo_score FROM songs ORDER BY elo_score ASC,title LIMIT 1').fetchone(),
        'most_wins': conn.execute('SELECT s.id,s.title,COUNT(h.id) AS wins FROM songs s JOIN history h ON h.winner_id=s.id GROUP BY s.id ORDER BY wins DESC LIMIT 1').fetchone(),
        'trivia_attempts': conn.execute('SELECT COALESCE(SUM(attempts),0) FROM trivia_stats').fetchone()[0],
        'trivia_correct': conn.execute('SELECT COALESCE(SUM(correct),0) FROM trivia_stats').fetchone()[0],
        'tournaments_total': conn.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0],
        'tournaments_completed': conn.execute("SELECT COUNT(*) FROM tournaments WHERE status='completed' OR champion_id IS NOT NULL").fetchone()[0],
        'recent_votes': conn.execute("SELECT COUNT(*) FROM history WHERE created_at >= datetime('now','-7 days')").fetchone()[0],
        'events_tracked': conn.execute('SELECT COUNT(*) FROM interaction_events').fetchone()[0],
        'top_trivia': conn.execute('''SELECT s.id,s.title,ts.attempts,ts.correct,ROUND(100.0*ts.correct/NULLIF(ts.attempts*2,0)) AS accuracy
            FROM trivia_stats ts JOIN songs s ON s.id=ts.song_id WHERE ts.attempts>0 ORDER BY accuracy DESC,ts.attempts DESC LIMIT 1''').fetchone()
    }
    elo_distribution = [dict(r) for r in conn.execute('''SELECT CASE WHEN elo_score < 1000 THEN '< 1000'
        WHEN elo_score < 1100 THEN '1000-1099' WHEN elo_score < 1200 THEN '1100-1199'
        WHEN elo_score < 1300 THEN '1200-1299' WHEN elo_score < 1400 THEN '1300-1399' ELSE '1400+' END AS band,
        COUNT(*) AS count FROM songs GROUP BY band ORDER BY MIN(elo_score)''').fetchall()]
    genre_leaders = [dict(r) for r in conn.execute('SELECT g.name,COUNT(DISTINCT sg.song_id) AS songs FROM genres g JOIN song_genres sg ON sg.genre_id=g.id GROUP BY g.id ORDER BY songs DESC,g.name LIMIT 8').fetchall()]
    top_albums_stats = [dict(r) for r in conn.execute('''SELECT al.id,al.title,al.cover_url,COUNT(s.id) AS songs,ROUND(AVG(s.elo_score)) AS avg_elo
        FROM albums al JOIN songs s ON s.album_id=al.id WHERE al.title != 'Unknown Album' AND al.title NOT LIKE '% - Single'
        GROUP BY al.id HAVING COUNT(s.id)>0 ORDER BY avg_elo DESC,songs DESC LIMIT 5''').fetchall()]
    recent_activity = [dict(r) for r in conn.execute('''SELECT h.id,h.created_at,w.id AS winner_id,w.title AS winner_title,l.id AS loser_id,l.title AS loser_title
        FROM history h LEFT JOIN songs w ON w.id=h.winner_id LEFT JOIN songs l ON l.id=h.loser_id ORDER BY h.id DESC LIMIT 8''').fetchall()]
    conn.close()

    return render_template('global_stats.html',
                           extra_stats=extra_stats, elo_distribution=elo_distribution,
                           genre_leaders=genre_leaders, top_albums_stats=top_albums_stats,
                           recent_activity=recent_activity,
                           total_songs=total_songs,
                           total_artists=total_artists,
                           total_albums=total_albums,
                           total_matches=total_matches,
                           matchups=matchups_data,
                           most_played=most_played,
                           prolific_artist=prolific_artist,
                           top_genre=top_genre)


@app.route('/song/<int:song_id>')
def song_page(song_id):
    conn = get_db_connection()
    song = get_song_full(song_id, conn)

    if not song:
        conn.close()
        return "<h1>Song not found</h1>", 404

    current_rank = conn.execute('SELECT COUNT(*) + 1 FROM songs WHERE elo_score > ?', (song['elo_score'],)).fetchone()[
        0]

    history_data = conn.execute('''
                                SELECT h.id,
                                       w.id                      as winner_id,
                                       w.title                   as winner_title,
                                       wal.cover_url             as winner_cover,
                                       (SELECT GROUP_CONCAT(a.name, ', ')
                                        FROM song_artists sa
                                                 JOIN artists a ON sa.artist_id = a.id
                                        WHERE sa.song_id = w.id) as winner_artist,
                                       l.id                      as loser_id,
                                       l.title                   as loser_title,
                                       lal.cover_url             as loser_cover,
                                       (SELECT GROUP_CONCAT(a.name, ', ')
                                        FROM song_artists sa
                                                 JOIN artists a ON sa.artist_id = a.id
                                        WHERE sa.song_id = l.id) as loser_artist
                                FROM history h
                                         JOIN songs w ON h.winner_id = w.id
                                         LEFT JOIN albums wal ON w.album_id = wal.id
                                         JOIN songs l ON h.loser_id = l.id
                                         LEFT JOIN albums lal ON l.album_id = lal.id
                                WHERE h.winner_id = ?
                                   OR h.loser_id = ?
                                ORDER BY h.id DESC
                                LIMIT 5
                                ''', (song_id, song_id)).fetchall()

    tournament_record = conn.execute('''
        SELECT
            (SELECT COUNT(*) FROM tournament_entries te WHERE te.song_id = ?) AS tournaments_entered,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.winner_id = ?) AS matches_won,
            (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.loser_id = ?) AS matches_lost,
            (SELECT COALESCE(SUM(tm.points_awarded), 0) FROM tournament_matches tm
             WHERE tm.winner_id = ?) AS tournament_points,
            (SELECT COUNT(*) FROM tournaments t WHERE t.champion_id = ? AND t.status = 'completed') AS championships
    ''', (song_id, song_id, song_id, song_id, song_id)).fetchone()
    tournament_appearances = conn.execute('''
        SELECT t.id, t.size, t.status, t.scope_type, t.created_at, t.completed_at,
               t.champion_id,
               (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id
                AND (tm.song1_id = ? OR tm.song2_id = ?)) AS matches_played,
               (SELECT COUNT(*) FROM tournament_matches tm WHERE tm.tournament_id = t.id
                AND tm.winner_id = ?) AS matches_won,
               (SELECT COALESCE(SUM(tm.points_awarded), 0) FROM tournament_matches tm
                WHERE tm.tournament_id = t.id AND tm.winner_id = ?) AS points_earned
        FROM tournament_entries te
        JOIN tournaments t ON t.id = te.tournament_id
        WHERE te.song_id = ?
        ORDER BY COALESCE(t.completed_at, t.updated_at, t.created_at, t.timestamp) DESC, t.id DESC
    ''', (song_id, song_id, song_id, song_id, song_id)).fetchall()

    conn.close()
    return render_template('song_page.html', song=song, current_rank=current_rank,
                           history=history_data, tournament_record=tournament_record,
                           tournament_appearances=tournament_appearances)


@app.route('/artist/<path:artist_name>')
def artist_page(artist_name):
    conn = get_db_connection()
    artist_data = conn.execute('SELECT id, cover_url FROM artists WHERE name = ? COLLATE NOCASE',
                               (artist_name,)).fetchone()

    songs = conn.execute('''
                         SELECT s.*,
                                al.cover_url,
                                al.title                   as album,
                                (SELECT GROUP_CONCAT(a2.name, ', ')
                                 FROM song_artists sa2
                                          JOIN artists a2 ON sa2.artist_id = a2.id
                                 WHERE sa2.song_id = s.id) as artist,
                                (SELECT GROUP_CONCAT(g2.name, ', ')
                                 FROM song_genres sg2
                                          JOIN genres g2 ON sg2.genre_id = g2.id
                                 WHERE sg2.song_id = s.id) as genres
                         FROM songs s
                                  JOIN song_artists sa ON s.id = sa.song_id
                                  JOIN artists a ON sa.artist_id = a.id
                                  LEFT JOIN albums al ON s.album_id = al.id
                         WHERE a.name = ? COLLATE NOCASE
                         ORDER BY s.elo_score DESC
                         ''', (artist_name,)).fetchall()

    albums = []
    if artist_data:
        albums = conn.execute('''
                              SELECT DISTINCT al.*, COUNT(s.id) as song_count
                              FROM albums al
                                       JOIN songs s ON al.id = s.album_id
                                       JOIN song_artists sa ON s.id = sa.song_id
                              WHERE sa.artist_id = ?
                                AND al.title != 'Unknown Album'
                                AND al.title NOT LIKE '% - Single'
                              GROUP BY al.id
                              ORDER BY al.release_date DESC, al.title ASC
                              ''', (artist_data['id'],)).fetchall()

    conn.close()

    if not songs:
        return "Artist not found.", 404

    song_count = len(songs)
    best_song = songs[0]
    worst_song = songs[-1]
    avg_elo = sum(s['elo_score'] for s in songs) / song_count
    impact_score = avg_elo + (song_count * 5)

    pfp_url = artist_data['cover_url'] if artist_data and artist_data['cover_url'] else best_song['cover_url']

    return render_template('artist_page.html',
                           artist_name=artist_name,
                           pfp_url=pfp_url,
                           song_count=song_count,
                           impact_score=impact_score,
                           best_song=best_song,
                           worst_song=worst_song,
                           songs=songs,
                           albums=albums)


@app.route('/album/<path:album_title>')
def album_page(album_title):
    conn = get_db_connection()

    # Get album details
    album_data = conn.execute('SELECT * FROM albums WHERE title = ? COLLATE NOCASE', (album_title,)).fetchone()

    if not album_data:
        conn.close()
        return "Album not found.", 404

    # Fetch all songs on this album, ordered by highest Elo
    songs = conn.execute('''
                         SELECT s.*,
                                (SELECT GROUP_CONCAT(a2.name, ', ')
                                 FROM song_artists sa2
                                          JOIN artists a2 ON sa2.artist_id = a2.id
                                 WHERE sa2.song_id = s.id) as artist
                         FROM songs s
                         WHERE s.album_id = ?
                         ORDER BY s.elo_score DESC
                         ''', (album_data['id'],)).fetchall()
    conn.close()

    if not songs:
        return "No songs found for this album.", 404

    song_count = len(songs)

    # Calculate Impact Score: Average Elo + (Total Songs * 5)
    avg_elo = sum(s['elo_score'] for s in songs) / song_count
    impact_score = avg_elo + (song_count * 5)

    # Use the primary artist of the highest-ranked song to represent the album's artist
    artist_name = songs[0]['artist']

    return render_template('album_page.html',
                           album_name=album_data['title'],
                           cover_url=album_data['cover_url'],
                           release_date=album_data['release_date'] if 'release_date' in album_data.keys() else None,
                           artist_name=artist_name,
                           song_count=song_count,
                           avg_elo=avg_elo,
                           best_song=songs[0],
                           worst_song=songs[-1],
                           impact_score=impact_score,
                           songs=songs)


@app.route('/trivia_stats')
def trivia_stats():
    conn = get_db_connection()

    # Base query for trivia stats
    base_query = '''
                 SELECT s.id, \
                        s.title, \
                        al.cover_url,
                        (SELECT GROUP_CONCAT(a2.name, ', ') \
                         FROM song_artists sa2 \
                                  JOIN artists a2 ON sa2.artist_id = a2.id \
                         WHERE sa2.song_id = s.id)                                   as artist,
                        ts.attempts                                                  as trivia_attempts, \
                        ts.correct                                                   as trivia_correct,
                        ROUND((CAST(ts.correct AS FLOAT) / (ts.attempts * 2)) * 100) as rec_score
                 FROM songs s
                          JOIN trivia_stats ts ON s.id = ts.song_id
                          LEFT JOIN albums al ON s.album_id = al.id
                 WHERE ts.attempts > 0 \
                 '''

    # Split into Top 10 and Bottom 10
    top_stats = conn.execute(base_query + ' ORDER BY rec_score DESC, ts.attempts DESC LIMIT 10').fetchall()
    bottom_stats = conn.execute(base_query + ' ORDER BY rec_score ASC, ts.attempts DESC LIMIT 10').fetchall()

    high_score_row = conn.execute('SELECT MAX(value) FROM global_stats WHERE key = "trivia_high_score"').fetchone()
    high_score = high_score_row[0] if high_score_row and high_score_row[0] else 0

    conn.close()
    return render_template('trivia_stats.html', top_stats=top_stats, bottom_stats=bottom_stats, high_score=high_score)


# --- HELPER FUNCTIONS FOR RELATIONAL DATA ---

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


# --- DEVELOPER AUTHENTICATION ---

@app.route('/dev/login', methods=['GET', 'POST'])
def dev_login():
    if request.method == 'POST':
        pin = request.form.get('pin')
        if pin == DEV_PIN:
            session['is_admin'] = True
            return redirect(url_for('dev_dashboard'))
        return render_template('dev_login.html', error="Invalid PIN")
    return render_template('dev_login.html')


@app.route('/dev/logout')
def dev_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


# --- DEVELOPER DASHBOARD ---

@app.route('/dev/dashboard')
@admin_required
def dev_dashboard():
    conn = get_db_connection()
    raw_songs = conn.execute('''
                             SELECT s.id,
                                    s.title,
                                    s.audio_url,
                                    s.elo_score,
                                    s.matches_played,
                                    al.title                   as album,
                                    al.cover_url,
                                    (SELECT GROUP_CONCAT(a2.name, ', ')
                                     FROM song_artists sa2
                                              JOIN artists a2 ON sa2.artist_id = a2.id
                                     WHERE sa2.song_id = s.id) as artist,
                                    (SELECT GROUP_CONCAT(g2.name, ', ')
                                     FROM song_genres sg2
                                              JOIN genres g2 ON sg2.genre_id = g2.id
                                     WHERE sg2.song_id = s.id) as genres
                             FROM songs s
                                      LEFT JOIN albums al ON s.album_id = al.id
                             ORDER BY artist, s.title
                             ''').fetchall()

    songs = [dict(row) for row in raw_songs]
    artists = [dict(row) for row in conn.execute('SELECT * FROM artists ORDER BY name').fetchall()]
    albums = [dict(row) for row in conn.execute('''
                                                SELECT al.*, COUNT(s.id) as song_count
                                                FROM albums al
                                                         LEFT JOIN songs s ON al.id = s.album_id
                                                GROUP BY al.id
                                                ORDER BY al.title
                                                ''').fetchall()]
    genres = [dict(row) for row in conn.execute('SELECT * FROM genres ORDER BY name').fetchall()]
    conn.close()

    return render_template('dev_dashboard.html', songs=songs, artists=artists, albums=albums, genres=genres)


# --- REAL-TIME API ROUTES FOR THE DASHBOARD ---

@app.route('/api/dev/search_apple')
@admin_required
def api_search_apple():
    """Queries Apple Music for a text search or direct link and returns JSON."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    if "music.apple.com" in query:
        match = re.search(r'[?&]i=(\d+)', query)
        if not match:
            return jsonify({"error": "Invalid link"}), 400
        url = f"https://itunes.apple.com/lookup?id={match.group(1)}"
    else:
        formatted_query = query.replace(" ", "+")
        url = f"https://itunes.apple.com/search?term={formatted_query}&entity=song&limit=10&explicit=Yes"

    try:
        response = requests.get(url, timeout=5).json()
        results = []
        for track in response.get('results', []):
            results.append({
                'title': track.get('trackName', 'Unknown'),
                'artist': track.get('artistName', 'Unknown'),
                'album': track.get('collectionName', ''),
                'cover_url': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
                'audio_url': track.get('previewUrl', '')
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/dev/add_song', methods=['POST'])
@admin_required
def api_add_song():
    """Adds a new song, creating and linking albums/artists in the relational database."""
    data = request.json
    title = data.get('title', '').strip()
    artist = data.get('artist', '').strip()
    album = data.get('album', '').strip()
    if not album:
        album = f"{title} - Single"
    cover_url = data.get('cover_url', '')
    audio_url = data.get('audio_url', '')

    conn = get_db_connection()

    # Check for duplicate track by same title & primary artist
    existing = conn.execute('''
                            SELECT s.id
                            FROM songs s
                                     JOIN song_artists sa ON s.id = sa.song_id
                                     JOIN artists a ON sa.artist_id = a.id
                            WHERE s.title = ? COLLATE NOCASE
                              AND a.name LIKE ?
                            ''', (title, f"%{artist[:10]}%")).fetchone()

    if existing:
        conn.close()
        return jsonify({"status": "error", "message": f"'{title}' by {artist} already exists."}), 400

    # 1. Resolve Album
    album_id = get_or_create_album(conn, album, cover_url)

    # 2. Insert Song
    cursor = conn.execute('''
                          INSERT INTO songs (title, album_id, audio_url, elo_score, matches_played)
                          VALUES (?, ?, ?, 1200, 0)
                          ''', (title, album_id, audio_url))
    song_id = cursor.lastrowid

    # 3. Resolve & Link Artists
    link_artists_to_song(conn, song_id, artist, default_cover=cover_url)

    genres = data.get('genres', '').strip()
    link_genres_to_song(conn, song_id, genres)

    # 4. Initialize Trivia Stats row
    conn.execute('INSERT INTO trivia_stats (song_id, attempts, correct) VALUES (?, 0, 0)', (song_id,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Added '{title}'"})


@app.route('/api/dev/edit_song/<int:song_id>', methods=['POST'])
@admin_required
def api_edit_song(song_id):
    """Updates an existing song and re-links its relational dependencies."""
    data = request.json
    title = data.get('title', '').strip()
    artist = data.get('artist', '').strip()
    album = data.get('album', '').strip()
    cover_url = data.get('cover_url', '')
    audio_url = data.get('audio_url', '')

    # Intercept Apple Music links pasted into the title box
    if "music.apple.com" in title:
        match = re.search(r'[?&]i=(\d+)', title)
        if not match:
            return jsonify({"status": "error", "message": "Invalid Apple Music link."}), 400

        lookup_url = f"https://itunes.apple.com/lookup?id={match.group(1)}"
        try:
            response = requests.get(lookup_url, timeout=5).json()
            if response['resultCount'] > 0:
                track = response['results'][0]
                title = track.get('trackName', 'Unknown')
                artist = track.get('artistName', 'Unknown')
                album = track.get('collectionName', '')
                cover_url = track.get('artworkUrl100', '').replace('100x100bb', '300x300bb')
                audio_url = track.get('previewUrl', '')
            else:
                return jsonify({"status": "error", "message": "Link returned no data."}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if not album:
        album = f"{title} - Single"

    conn = get_db_connection()

    # 1. Update/Link Album
    album_id = get_or_create_album(conn, album, cover_url)

    # 2. Update Core Song Row
    conn.execute('''
                 UPDATE songs
                 SET title     = ?,
                     album_id  = ?,
                     audio_url = ?
                 WHERE id = ?
                 ''', (title, album_id, audio_url, song_id))

    # 3. Refresh Artist Links (remove old associations and apply new ones)
    conn.execute('DELETE FROM song_artists WHERE song_id = ?', (song_id,))
    link_artists_to_song(conn, song_id, artist, default_cover=cover_url)

    genres = data.get('genres', '').strip()
    conn.execute('DELETE FROM song_genres WHERE song_id = ?', (song_id,))
    link_genres_to_song(conn, song_id, genres)

    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('song_edited', json.dumps({'song_id': song_id, 'title': title}, ensure_ascii=False)))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Song updated successfully.",
        "updated_song": {
            "title": title,
            "artist": artist,
            "cover_url": cover_url
        }
    })


@app.route('/api/dev/delete_song/<int:song_id>', methods=['DELETE'])
@admin_required
def api_delete_song(song_id):
    """Deletes a song and redistributes its net Elo impact to the rest of the database."""
    conn = get_db_connection()

    song = conn.execute('SELECT elo_score FROM songs WHERE id = ?', (song_id,)).fetchone()
    if not song:
        conn.close()
        return jsonify({"status": "error", "message": "Song not found."}), 404

    elo_difference = song['elo_score'] - 1200

    conn.execute('DELETE FROM song_artists WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM song_genres WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM trivia_stats WHERE song_id = ?', (song_id,))
    conn.execute('DELETE FROM history WHERE winner_id = ? OR loser_id = ?', (song_id, song_id))
    conn.execute('DELETE FROM songs WHERE id = ?', (song_id,))

    remaining_songs = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    if remaining_songs > 0 and elo_difference != 0:
        adjustment = elo_difference / remaining_songs
        conn.execute('UPDATE songs SET elo_score = elo_score + ?', (adjustment,))

    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('song_deleted', json.dumps({'song_id': song_id}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Song deleted. System Elo conserved."})


@app.route('/api/dev/edit_artist/<int:artist_id>', methods=['POST'])
@admin_required
def api_edit_artist(artist_id):
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE artists SET name = ?, cover_url = ? WHERE id = ?',
                 (data.get('name', '').strip(), data.get('cover_url', ''), artist_id))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('artist_edited', json.dumps({'artist_id': artist_id, 'name': data.get('name', '').strip()}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Artist updated successfully."})


@app.route('/api/dev/delete_artist/<int:artist_id>', methods=['DELETE'])
@admin_required
def api_delete_artist(artist_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_artists WHERE artist_id = ?', (artist_id,))
    conn.execute('DELETE FROM artists WHERE id = ?', (artist_id,))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('artist_deleted', json.dumps({'artist_id': artist_id}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Artist deleted."})


@app.route('/api/dev/edit_album/<int:album_id>', methods=['POST'])
@admin_required
def api_edit_album(album_id):
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE albums SET title = ?, cover_url = ?, release_date = ? WHERE id = ?',
                 (data.get('title', '').strip(), data.get('cover_url', ''), data.get('release_date', ''), album_id))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('album_edited', json.dumps({'album_id': album_id, 'title': data.get('title', '').strip()}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album updated successfully."})


@app.route('/api/dev/delete_album/<int:album_id>', methods=['DELETE'])
@admin_required
def api_delete_album(album_id):
    conn = get_db_connection()
    conn.execute('UPDATE songs SET album_id = NULL WHERE album_id = ?', (album_id,))
    conn.execute('DELETE FROM albums WHERE id = ?', (album_id,))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('album_deleted', json.dumps({'album_id': album_id}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album deleted. Associated songs updated."})

@app.route('/api/dev/edit_genre/<int:genre_id>', methods=['POST'])
@admin_required
def api_edit_genre(genre_id):
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE genres SET name = ? WHERE id = ?', (data.get('name', '').strip(), genre_id))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('genre_edited', json.dumps({'genre_id': genre_id, 'name': data.get('name', '').strip()}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre updated successfully."})

@app.route('/api/dev/delete_genre/<int:genre_id>', methods=['DELETE'])
@admin_required
def api_delete_genre(genre_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_genres WHERE genre_id = ?', (genre_id,))
    conn.execute('DELETE FROM genres WHERE id = ?', (genre_id,))
    conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)', ('genre_deleted', json.dumps({'genre_id': genre_id}, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre deleted."})


@app.route('/api/dev/overview', methods=['GET'])
@admin_required
def api_dev_overview():
    conn = get_db_connection()
    tables = ['songs','artists','albums','genres','history','trivia_stats','tournaments','tournament_entries','tournament_matches','interaction_events','elo_history','admin_audit_log']
    counts = {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}
    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    fk_errors = len(conn.execute('PRAGMA foreign_key_check').fetchall())
    events = [dict(r) for r in conn.execute('SELECT id,event_type,song_id,related_song_id,created_at,details_json FROM interaction_events ORDER BY id DESC LIMIT 12').fetchall()]
    audit = [dict(r) for r in conn.execute('SELECT id,action,details,created_at FROM admin_audit_log ORDER BY id DESC LIMIT 12').fetchall()]
    conn.close()
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    backups=[]
    if os.path.isdir(backup_dir):
        for name in sorted(os.listdir(backup_dir), reverse=True)[:10]:
            full=os.path.join(backup_dir,name)
            if os.path.isfile(full) and name.endswith('.db'):
                backups.append({'name':name,'size':os.path.getsize(full),'modified':datetime.fromtimestamp(os.path.getmtime(full)).isoformat(timespec='seconds')})
    return jsonify({'counts':counts,'integrity':integrity,'foreign_key_errors':fk_errors,'recent_events':events,'recent_audit':audit,'backups':backups})


@app.route('/api/dev/backup', methods=['POST'])
@admin_required
def api_dev_backup():
    try:
        path=create_database_backup('manual')
        conn=get_db_connection(); conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)',('backup_created',os.path.basename(path))); conn.commit(); conn.close()
        return jsonify({'status':'success','message':'Database backup created.','backup':os.path.basename(path)})
    except Exception as exc:
        app.logger.exception('Backup failed'); return jsonify({'status':'error','message':f'Backup failed: {exc}'}),500


@app.route('/api/dev/restore-backup', methods=['POST'])
@admin_required
def api_dev_restore_backup():
    data = request.get_json(silent=True) or {}
    name = os.path.basename(str(data.get('filename', '')))
    if not name.endswith('.db') or not name.startswith(('manual_', 'pre_reset_', 'pre_restore_', 'song_ranker_')):
        return jsonify({'status': 'error', 'message': 'Choose a valid Song Ranker backup file.'}), 400
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), 'database_backups')
    source_path = os.path.join(backup_dir, name)
    if not os.path.isfile(source_path):
        return jsonify({'status': 'error', 'message': 'Backup file not found.'}), 404
    try:
        # Verify the candidate backup before touching the live database.
        check = sqlite3.connect(source_path)
        try:
            result = check.execute('PRAGMA integrity_check').fetchone()[0]
            if result != 'ok':
                return jsonify({'status': 'error', 'message': f'Backup failed integrity check: {result}'}), 400
        finally:
            check.close()
        current_backup = create_database_backup('pre_restore')
        source = sqlite3.connect(source_path, timeout=30)
        destination = sqlite3.connect(DB_NAME, timeout=30)
        try:
            source.backup(destination)
            integrity = destination.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity != 'ok':
                raise sqlite3.DatabaseError(f'Restored database failed integrity check: {integrity}')
        finally:
            destination.close(); source.close()
        conn = get_db_connection()
        conn.execute('INSERT INTO admin_audit_log (action, details) VALUES (?, ?)',
                     ('backup_restored', json.dumps({'restored': name, 'pre_restore_backup': os.path.basename(current_backup)})))
        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': f'Restored {name}. A safety backup was saved as {os.path.basename(current_backup)}.'})
    except Exception as exc:
        app.logger.exception('Backup restore failed')
        return jsonify({'status': 'error', 'message': f'Restore failed: {exc}'}), 500


@app.route('/api/dev/reset-preview', methods=['GET'])
@admin_required
def api_dev_reset_preview():
    conn=get_db_connection()
    keep={k:conn.execute(q).fetchone()[0] for k,q in {
        'songs':'SELECT COUNT(*) FROM songs','artists':'SELECT COUNT(*) FROM artists','albums':'SELECT COUNT(*) FROM albums','genres':'SELECT COUNT(*) FROM genres',
        'song_artist_links':'SELECT COUNT(*) FROM song_artists','song_genre_links':'SELECT COUNT(*) FROM song_genres'}.items()}
    clear={k:conn.execute(q).fetchone()[0] for k,q in {
        'votes_and_history':'SELECT COUNT(*) FROM history','trivia_stats':'SELECT COUNT(*) FROM trivia_stats','tournaments':'SELECT COUNT(*) FROM tournaments',
        'tournament_matches':'SELECT COUNT(*) FROM tournament_matches','interaction_events':'SELECT COUNT(*) FROM interaction_events','elo_history':'SELECT COUNT(*) FROM elo_history'}.items()}
    conn.close(); return jsonify({'keep':keep,'clear':clear})


@app.route('/api/dev/reset-database', methods=['POST'])
@admin_required
def api_dev_reset_database():
    data=request.get_json(silent=True) or {}
    if data.get('confirmation') != 'RESET COMPETITION':
        return jsonify({'status':'error','message':'Type RESET COMPETITION to confirm.'}),400
    try:
        backup_path=create_database_backup('pre_reset')
        conn=get_db_connection(); conn.execute('PRAGMA foreign_keys=ON')
        for table in ('tournament_matches','tournament_entries','tournaments','history','trivia_stats','interaction_events','elo_history'):
            conn.execute(f'DELETE FROM {table}')
        conn.execute('UPDATE songs SET elo_score=1200,matches_played=0,highest_elo=1200,highest_rank=9999,tournament_wins=0')
        conn.execute('UPDATE global_stats SET value=0')
        conn.execute("INSERT INTO global_stats (key,value) VALUES ('trivia_high_score',0) ON CONFLICT(key) DO UPDATE SET value=0")
        conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)',('competition_reset',json.dumps({'backup':os.path.basename(backup_path),'kept_library':True})))
        conn.commit(); conn.close()
        return jsonify({'status':'success','message':'Competition reset. Songs, albums, artists, genres, and their music links were kept.','backup':os.path.basename(backup_path)})
    except Exception as exc:
        app.logger.exception('Database reset failed'); return jsonify({'status':'error','message':f'Reset failed: {exc}'}),500


@app.route('/api/dev/elo-correction', methods=['POST'])
@admin_required
def api_dev_elo_correction():
    data = request.get_json(silent=True) or {}
    try:
        song_id = int(data.get('song_id'))
        new_elo = float(data.get('new_elo'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Enter a valid song ID and numeric Elo value.'}), 400
    reason = str(data.get('reason', '')).strip()
    if not reason:
        return jsonify({'status': 'error', 'message': 'A reason is required for the audit log.'}), 400
    if not 0 <= new_elo <= 5000:
        return jsonify({'status': 'error', 'message': 'Elo must be between 0 and 5000.'}), 400
    conn = get_db_connection()
    song = conn.execute('SELECT id,title,elo_score FROM songs WHERE id=?', (song_id,)).fetchone()
    if not song:
        conn.close(); return jsonify({'status': 'error', 'message': 'Song not found.'}), 404
    details = {'song_id': song_id, 'title': song['title'], 'old_elo': song['elo_score'], 'new_elo': new_elo, 'reason': reason}
    conn.execute('UPDATE songs SET elo_score=? WHERE id=?', (new_elo, song_id))
    conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)', ('manual_elo_correction', json.dumps(details, ensure_ascii=False)))
    conn.commit(); conn.close()
    return jsonify({'status': 'success', 'message': f"Updated {song['title']} from {round(song['elo_score'])} to {round(new_elo)} Elo. The correction was logged."})


@app.route('/api/dev/trivia/<int:song_id>', methods=['POST', 'DELETE'])
@admin_required
def api_dev_edit_trivia(song_id):
    conn = get_db_connection()
    if not conn.execute('SELECT id FROM songs WHERE id=?', (song_id,)).fetchone():
        conn.close(); return jsonify({'status': 'error', 'message': 'Song not found.'}), 404
    if request.method == 'DELETE':
        conn.execute('DELETE FROM trivia_stats WHERE song_id=?', (song_id,))
        conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)', ('trivia_stats_deleted', str(song_id)))
        conn.commit(); conn.close()
        return jsonify({'status': 'success', 'message': 'Trivia statistics deleted for this song.'})
    data = request.get_json(silent=True) or {}
    try:
        attempts = int(data.get('attempts', 0)); correct = int(data.get('correct', 0))
    except (TypeError, ValueError):
        conn.close(); return jsonify({'status': 'error', 'message': 'Attempts and correct must be whole numbers.'}), 400
    if attempts < 0 or correct < 0 or correct > attempts * 2:
        conn.close(); return jsonify({'status': 'error', 'message': 'Values must be non-negative and correct fields cannot exceed twice the attempts.'}), 400
    conn.execute('INSERT INTO trivia_stats (song_id,attempts,correct) VALUES (?,?,?) ON CONFLICT(song_id) DO UPDATE SET attempts=excluded.attempts,correct=excluded.correct', (song_id, attempts, correct))
    conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)', ('trivia_stats_updated', json.dumps({'song_id': song_id, 'attempts': attempts, 'correct': correct})))
    conn.commit(); conn.close()
    return jsonify({'status': 'success', 'message': 'Trivia statistics updated and logged.'})


@app.route('/api/dev/integrity', methods=['GET'])
@admin_required
def api_dev_integrity():
    conn=get_db_connection(); integrity=[r[0] for r in conn.execute('PRAGMA integrity_check').fetchall()]
    fk=[list(r) for r in conn.execute('PRAGMA foreign_key_check').fetchall()]
    duplicates={}
    for table,column in (('songs','title'),('artists','name'),('albums','title')):
        duplicates[table]=[dict(r) for r in conn.execute(f'''SELECT LOWER(TRIM({column})) AS key,COUNT(*) AS count,GROUP_CONCAT(id) AS ids
            FROM {table} GROUP BY LOWER(TRIM({column})) HAVING COUNT(*)>1 ORDER BY count DESC LIMIT 50''').fetchall()]
    conn.close(); return jsonify({'integrity':integrity,'foreign_key_errors':fk,'duplicates':duplicates})


@app.route('/api/dev/activity', methods=['GET'])
@admin_required
def api_dev_activity():
    conn=get_db_connection()
    votes=[dict(r) for r in conn.execute('''SELECT h.id,h.created_at,w.id AS winner_id,w.title AS winner,l.id AS loser_id,l.title AS loser,
        CASE WHEN h.is_tournament_match THEN 'tournament' ELSE 'vote' END AS mode FROM history h
        LEFT JOIN songs w ON w.id=h.winner_id LEFT JOIN songs l ON l.id=h.loser_id ORDER BY h.id DESC LIMIT 100''').fetchall()]
    tournaments=[dict(r) for r in conn.execute('''SELECT t.id,t.size,t.scope_type,t.scope_id,t.champion_id,t.timestamp,t.status,t.created_at,t.completed_at,
        (SELECT COUNT(*) FROM tournament_matches m WHERE m.tournament_id=t.id) AS match_count FROM tournaments t ORDER BY t.id DESC LIMIT 100''').fetchall()]
    conn.close(); return jsonify({'votes':votes,'tournaments':tournaments})


@app.route('/api/dev/tournaments/<int:tournament_id>', methods=['DELETE'])
@admin_required
def api_dev_delete_tournament(tournament_id):
    conn=get_db_connection()
    if not conn.execute('SELECT id FROM tournaments WHERE id=?',(tournament_id,)).fetchone():
        conn.close(); return jsonify({'message':'Tournament not found.'}),404
    conn.execute('DELETE FROM tournament_matches WHERE tournament_id=?',(tournament_id,)); conn.execute('DELETE FROM tournament_entries WHERE tournament_id=?',(tournament_id,)); conn.execute('DELETE FROM tournaments WHERE id=?',(tournament_id,))
    conn.execute('INSERT INTO admin_audit_log (action,details) VALUES (?,?)',('tournament_deleted',str(tournament_id)))
    conn.commit(); conn.close(); return jsonify({'status':'success','message':'Tournament and bracket records deleted.'})


@app.route('/api/dev/sync', methods=['POST'])
@admin_required
def api_sync():
    """Endpoint to trigger a manual database push."""
    success = git_push()
    if success:
        return jsonify({"status": "success", "message": "Database synced to GitHub!"})
    return jsonify({"status": "error", "message": "Failed to sync to GitHub."}), 500

@app.route('/api/dev/export', methods=['POST'])
@admin_required
def api_export():
    """Endpoint to manually trigger a database text export."""
    try:
        export_rankings()
        return jsonify({"status": "success", "message": "Database snapshot saved to txt file!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Export failed: {str(e)}"}), 500

# --- ENTRY POINT ---

if __name__ == "__main__":
    git_pull()
    init_db()
    app.run(debug=True)