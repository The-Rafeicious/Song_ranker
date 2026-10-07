from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from difflib import SequenceMatcher
import random
import requests
import re
import subprocess
import sqlite3
import os

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
    """Pulls the latest SQL dump and rebuilds the local database if changes are found."""
    try:
        print("Pulling latest data from GitHub...")
        result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, check=True)

        if "Already up to date." not in result.stdout and os.path.exists('database_backup.sql'):
            print("Updates found. Rebuilding local database...")

            if os.path.exists(DB_NAME):
                os.remove(DB_NAME)

            conn = sqlite3.connect(DB_NAME)
            with open('database_backup.sql', 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.close()

    except subprocess.CalledProcessError as e:
        print(f"Git pull failed: {e}")

def git_push():
    """Converts the database to a text file and pushes it to GitHub."""
    try:
        conn = sqlite3.connect(DB_NAME)
        with open('database_backup.sql', 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line)
        conn.close()

        subprocess.run(["git", "add", "database_backup.sql"], check=True)

        result = subprocess.run(
            ["git", "commit", "-m", "Auto-sync database update"],
            capture_output=True, text=True
        )

        if "nothing to commit" in result.stdout:
            return True

        subprocess.run(["git", "push", "origin", "main"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

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
            FOREIGN KEY(winner_id) REFERENCES songs(id),
            FOREIGN KEY(loser_id) REFERENCES songs(id)
        );

        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY, 
            value INTEGER
        );
    ''')
    conn.execute('INSERT OR IGNORE INTO global_stats (key, value) VALUES ("trivia_high_score", 0)')
    conn.commit()
    conn.close()


def export_rankings():
    """Exports the current Elo leaderboard to a text file."""
    conn = get_db_connection()
    all_songs = conn.execute('''
                             SELECT s.title,
                                    s.elo_score,
                                    s.matches_played,
                                    GROUP_CONCAT(a.name, ', ') as artist
                             FROM songs s
                                      LEFT JOIN song_artists sa ON s.id = sa.song_id
                                      LEFT JOIN artists a ON sa.artist_id = a.id
                             GROUP BY s.id
                             ORDER BY s.elo_score DESC
                             ''').fetchall()
    conn.close()

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
    conn.execute('INSERT INTO history (winner_id, loser_id) VALUES (?, ?)', (winner_id, loser_id))

    total_votes = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]
    conn.commit()
    conn.close()

    if total_votes % 10 == 0:
        export_rankings()

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
    conn.execute('INSERT INTO history (winner_id, loser_id) VALUES (?, ?)', (winner_id, loser_id))
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

    conn.close()

    return render_template('global_stats.html',
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

    conn.close()
    return render_template('song_page.html', song=song, current_rank=current_rank, history=history_data)


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
                           artist_name=artist_name,
                           song_count=song_count,
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
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Artist updated successfully."})


@app.route('/api/dev/delete_artist/<int:artist_id>', methods=['DELETE'])
@admin_required
def api_delete_artist(artist_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_artists WHERE artist_id = ?', (artist_id,))
    conn.execute('DELETE FROM artists WHERE id = ?', (artist_id,))
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
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album updated successfully."})


@app.route('/api/dev/delete_album/<int:album_id>', methods=['DELETE'])
@admin_required
def api_delete_album(album_id):
    conn = get_db_connection()
    conn.execute('UPDATE songs SET album_id = NULL WHERE album_id = ?', (album_id,))
    conn.execute('DELETE FROM albums WHERE id = ?', (album_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Album deleted. Associated songs updated."})

@app.route('/api/dev/edit_genre/<int:genre_id>', methods=['POST'])
@admin_required
def api_edit_genre(genre_id):
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE genres SET name = ? WHERE id = ?', (data.get('name', '').strip(), genre_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre updated successfully."})

@app.route('/api/dev/delete_genre/<int:genre_id>', methods=['DELETE'])
@admin_required
def api_delete_genre(genre_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM song_genres WHERE genre_id = ?', (genre_id,))
    conn.execute('DELETE FROM genres WHERE id = ?', (genre_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Genre deleted."})


@app.route('/api/dev/sync', methods=['POST'])
@admin_required
def api_sync():
    """Endpoint to trigger a manual database push."""
    success = git_push()
    if success:
        return jsonify({"status": "success", "message": "Database synced to GitHub!"})
    return jsonify({"status": "error", "message": "Failed to sync to GitHub."}), 500


# --- ENTRY POINT ---

if __name__ == "__main__":
    git_pull()
    init_db()
    app.run(debug=True)