from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from difflib import SequenceMatcher
import random
import requests
import re
import subprocess
import sqlite3
import os


def git_pull():
    """Pulls the latest SQL dump and rebuilds the local database if changes are found."""
    try:
        print("Pulling latest data from GitHub...")
        result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, check=True)

        # If the pull downloaded new data, rebuild the binary .db file
        if "Already up to date." not in result.stdout and os.path.exists('database_backup.sql'):
            print("Updates found. Rebuilding local database...")

            # Delete the outdated binary file
            if os.path.exists('song_ranker.db'):
                os.remove('song_ranker.db')

            # Rebuild it from the fresh text dump
            conn = sqlite3.connect('song_ranker.db')
            with open('database_backup.sql', 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.close()

    except subprocess.CalledProcessError as e:
        print(f"Git pull failed: {e}")


def git_push():
    """Converts the database to a text file and pushes it to GitHub."""
    try:
        # 1. Convert the binary database into a text-based SQL file
        conn = sqlite3.connect('song_ranker.db')
        with open('database_backup.sql', 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line)
        conn.close()

        # 2. Stage only the text backup file for GitHub
        subprocess.run(["git", "add", "database_backup.sql"], check=True)

        result = subprocess.run(
            ["git", "commit", "-m", "Auto-sync database update"],
            capture_output=True, text=True
        )

        # 3. Push if there are actual changes
        if "nothing to commit" in result.stdout:
            return True

        subprocess.run(["git", "push", "origin", "main"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

app = Flask(__name__)
app.secret_key = "theandwasdwe"
DB_NAME = "song_ranker.db"
DEV_PIN = "9042"  # Change this to whatever 4-digit PIN you want

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


def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            cover_url TEXT,
            audio_url TEXT,
            elo_score REAL DEFAULT 1200,
            matches_played INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            winner_id INTEGER,
            loser_id INTEGER
        )
    ''')

    # Safely add the new tracking columns to existing databases
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN album TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN highest_elo REAL DEFAULT 1200')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN highest_rank INTEGER DEFAULT 9999')
    except sqlite3.OperationalError:
        pass

    # Safely add the new tracking columns to existing databases
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN trivia_attempts INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN trivia_correct INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def export_rankings():
    """Exports the current Elo leaderboard to a text file."""
    conn = get_db_connection()
    all_songs = conn.execute('''
        SELECT title, artist, elo_score, matches_played 
        FROM songs 
        ORDER BY elo_score DESC
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
    """Calculates the new Elo ratings for both tracks."""
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))

    new_winner_elo = winner_elo + k_factor * (1 - expected_winner)
    new_loser_elo = loser_elo + k_factor * (0 - expected_loser)

    return new_winner_elo, new_loser_elo

def is_close_match(guess, actual, threshold=0.75):
    """Returns True if the guess is at least 75% similar to the actual answer."""
    if not guess or not actual:
        return False
    # Strip spaces and make lowercase for comparison
    g = guess.lower().strip()
    a = actual.lower().strip()
    return SequenceMatcher(None, g, a).ratio() >= threshold


@app.route('/')
def home():
    conn = get_db_connection()

    # Fetch #1 Track
    top_song = conn.execute('''
        SELECT title, artist, cover_url 
        FROM songs 
        ORDER BY elo_score DESC 
        LIMIT 1
    ''').fetchone()

    # Fetch #1 Artist (Highest Impact Score) and grab their best track's cover art
    top_artist = conn.execute('''
            SELECT artist, 
                   (SELECT cover_url FROM songs s2 WHERE s2.artist = songs.artist ORDER BY elo_score DESC LIMIT 1) as cover_url,
                   (AVG(elo_score) + (COUNT(id) * 5)) as impact_score
            FROM songs 
            GROUP BY artist 
            ORDER BY impact_score DESC 
            LIMIT 1
        ''').fetchone()

    # Fetch #1 Album (Highest Impact Score, ignoring empty albums)
    top_album = conn.execute('''
            SELECT album, artist, cover_url,
                COUNT(id) as song_count, 
                AVG(elo_score) as avg_elo, 
                1200 + SUM(elo_score - 1200) as impact_score
            FROM songs 
            WHERE album IS NOT NULL AND album != '' 
            GROUP BY album 
            ORDER BY impact_score DESC 
            LIMIT 1
        ''').fetchone()

    conn.close()

    return render_template('home.html', top_song=top_song, top_artist=top_artist, top_album=top_album)

@app.route('/game')
def index():
    conn = get_db_connection()

    if 'song1_id' in session and 'song2_id' in session:
        song1 = conn.execute('SELECT * FROM songs WHERE id = ?', (session['song1_id'],)).fetchone()
        song2 = conn.execute('SELECT * FROM songs WHERE id = ?', (session['song2_id'],)).fetchone()

        if song1 and song2:
            conn.close()
            return render_template('index.html', song1=song1, song2=song2)

    # 1. Widen the net for Song 1:
    # Pick from the 40 least-played songs instead of just the bottom 5.
    pool1 = conn.execute('''
        SELECT * FROM songs 
        ORDER BY matches_played ASC, RANDOM() 
        LIMIT 40
    ''').fetchall()

    if not pool1:
        conn.close()
        return "<h1>Database is empty. Please add songs!</h1>"

    song1 = random.choice(pool1)

    # 2. Widen the Elo range for Song 2:
    # Look at the 60 closest songs instead of 15 to break the Elo bubble.
    pool2 = conn.execute('''
        SELECT * FROM songs 
        WHERE id != ? 
        ORDER BY ABS(elo_score - ?) ASC 
        LIMIT 60
    ''', (song1['id'], song1['elo_score'])).fetchall()

    conn.close()

    if not pool2:
        return "<h1>Not enough songs in the database. Add at least two!</h1>"

    # 3. Add more variety to the final opponent selection:
    # Pick randomly from the 15 least-played competitors in that widened pool (instead of just 3).
    pool2_sorted = sorted(pool2, key=lambda x: x['matches_played'])
    song2 = random.choice(pool2_sorted[:15])

    session['song1_id'] = song1['id']
    session['song2_id'] = song2['id']

    last_vote = session.pop('last_vote', None)

    return render_template('index.html', song1=song1, song2=song2, last_vote=last_vote)


@app.route('/vote', methods=['POST'])
def vote():
    winner_id = request.form['winner_id']
    loser_id = request.form['loser_id']

    conn = get_db_connection()

    winner = conn.execute('SELECT title, elo_score FROM songs WHERE id = ?', (winner_id,)).fetchone()
    loser = conn.execute('SELECT title, elo_score FROM songs WHERE id = ?', (loser_id,)).fetchone()

    new_winner_elo, new_loser_elo = calculate_new_elo(winner['elo_score'], loser['elo_score'])

    # Calculate winner's new rank globally
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

    # Update winner, saving new all-time highs if applicable
    conn.execute('''
        UPDATE songs 
        SET elo_score = ?, matches_played = matches_played + 1,
            highest_elo = CASE WHEN ? > highest_elo THEN ? ELSE highest_elo END,
            highest_rank = CASE WHEN ? < highest_rank OR highest_rank = 9999 THEN ? ELSE highest_rank END
        WHERE id = ?
    ''', (new_winner_elo, new_winner_elo, new_winner_elo, winner_new_rank, winner_new_rank, winner_id))

    # Update loser
    conn.execute('''
        UPDATE songs 
        SET elo_score = ?, matches_played = matches_played + 1 
        WHERE id = ?
    ''', (new_loser_elo, loser_id))

    conn.execute('INSERT INTO history (winner_id, loser_id) VALUES (?, ?)', (winner_id, loser_id))

    total_votes = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]
    conn.commit()
    conn.close()

    if total_votes % 10 == 0:
        export_rankings()

    session.pop('song1_id', None)
    session.pop('song2_id', None)

    return redirect(url_for('index'))


@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    # Fetch the top 20 songs ordered by Elo score
    top_songs = conn.execute('''
        SELECT id, title, artist, album, cover_url, elo_score 
        FROM songs 
        ORDER BY elo_score DESC 
        LIMIT 20
    ''').fetchall()
    conn.close()

    return render_template('leaderboard.html', songs=top_songs)


@app.route('/artists')
def artists_leaderboard():
    conn = get_db_connection()

    # Calculate the Total Impact Score and grab one cover image per artist
    top_artists = conn.execute('''
        SELECT artist, 
               COUNT(id) as song_count, 
               AVG(elo_score) as avg_elo, 
               1200 + SUM(elo_score - 1200) as artist_score,
               MAX(cover_url) as sample_cover
        FROM songs 
        GROUP BY artist 
        ORDER BY artist_score DESC 
        LIMIT 10
    ''').fetchall()

    conn.close()

    return render_template('artists_leaderboard.html', artists=top_artists)


@app.route('/search')
def search():
    # Grab the query from the URL (e.g., /search?q=maisie)
    query = request.args.get('q', '').strip()
    conn = get_db_connection()

    if query:
        search_term = f"%{query}%"
        # Search across title, artist, and album, sorted by highest Elo
        results = conn.execute('''
            SELECT id, title, artist, album, cover_url, elo_score, matches_played
            FROM songs
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
            ORDER BY elo_score DESC
        ''', (search_term, search_term, search_term)).fetchall()
    else:
        results = []

    conn.close()
    return render_template('search_results.html', query=query, songs=results)

@app.route('/albums')
def albums_leaderboard():
    conn = get_db_connection()
    # Calculate Impact Score and group by Album, excluding empty albums
    albums_data = conn.execute('''
        SELECT album, artist, 
               COUNT(id) as song_count, 
               AVG(elo_score) as avg_elo, 
               1200 + SUM(elo_score - 1200) as album_score,
               MAX(cover_url) as sample_cover
        FROM songs 
        WHERE album != '' AND album IS NOT NULL
        GROUP BY album 
        ORDER BY album_score DESC 
        LIMIT 20
    ''').fetchall()
    conn.close()

    return render_template('albums_leaderboard.html', albums=albums_data)


@app.route('/tiers')
def tier_list():
    conn = get_db_connection()
    songs = conn.execute('''
        SELECT title, artist, cover_url, elo_score 
        FROM songs 
        ORDER BY elo_score DESC
    ''').fetchall()
    conn.close()

    # Group songs into dictionary arrays based on their Elo thresholds
    tiers = {
        'S (1600+)': [],
        'A (1400+)': [],
        'B (1200+)': [],
        'C (1000+)': [],
        'D (<1000)': []
    }

    for song in songs:
        score = song['elo_score']
        if score >= 1600: tiers['S (1600+)'].append(song)
        elif score >= 1400: tiers['A (1400+)'].append(song)
        elif score >= 1200: tiers['B (1200+)'].append(song)
        elif score >= 1000: tiers['C (1000+)'].append(song)
        else: tiers['D (<1000)'].append(song)

    return render_template('tier_list.html', tiers=tiers)


@app.route('/history')
def match_history():
    conn = get_db_connection()
    # Join the history table with the songs table twice to get winner and loser details
    history_data = conn.execute('''
        SELECT h.id, 
               w.title as winner_title, w.artist as winner_artist, w.cover_url as winner_cover,
               l.title as loser_title, l.artist as loser_artist, l.cover_url as loser_cover
        FROM history h
        JOIN songs w ON h.winner_id = w.id
        JOIN songs l ON h.loser_id = l.id
        ORDER BY h.id DESC 
        LIMIT 50
    ''').fetchall()
    conn.close()

    return render_template('history.html', history=history_data)


@app.route('/song/<int:song_id>')
def song_page(song_id):
    conn = get_db_connection()
    song = conn.execute('SELECT * FROM songs WHERE id = ?', (song_id,)).fetchone()

    if not song:
        conn.close()
        return "<h1>Song not found</h1>", 404

    # Calculate current live rank
    current_rank = conn.execute('SELECT COUNT(*) + 1 FROM songs WHERE elo_score > ?', (song['elo_score'],)).fetchone()[
        0]

    # Fetch last 5 matches involving this exact track
    history_data = conn.execute('''
        SELECT h.id, 
               w.id as winner_id, w.title as winner_title, w.artist as winner_artist, w.cover_url as winner_cover,
               l.id as loser_id, l.title as loser_title, l.artist as loser_artist, l.cover_url as loser_cover
        FROM history h
        JOIN songs w ON h.winner_id = w.id
        JOIN songs l ON h.loser_id = l.id
        WHERE h.winner_id = ? OR h.loser_id = ?
        ORDER BY h.id DESC 
        LIMIT 5
    ''', (song_id, song_id)).fetchall()

    conn.close()

    return render_template('song_page.html', song=song, current_rank=current_rank, history=history_data)


# --- BLIND AUDITION MODE ---

@app.route('/blind')
def blind_mode():
    conn = get_db_connection()
    # Only pull songs that actually have an audio preview
    songs = conn.execute(
        'SELECT * FROM songs WHERE audio_url IS NOT NULL AND audio_url != "" ORDER BY RANDOM() LIMIT 2').fetchall()
    conn.close()

    if len(songs) < 2:
        return "Not enough songs with audio previews to play Blind Mode."

    return render_template('blind_mode.html', song1=songs[0], song2=songs[1])


@app.route('/api/blind_vote', methods=['POST'])
def api_blind_vote():
    """Processes the vote silently and returns the identities for the reveal modal."""
    data = request.json
    winner_id = data['winner_id']
    loser_id = data['loser_id']

    conn = get_db_connection()
    winner = conn.execute('SELECT * FROM songs WHERE id = ?', (winner_id,)).fetchone()
    loser = conn.execute('SELECT * FROM songs WHERE id = ?', (loser_id,)).fetchone()

    new_winner_elo, new_loser_elo = calculate_new_elo(winner['elo_score'], loser['elo_score'])
    winner_new_rank = conn.execute('SELECT COUNT(*) + 1 FROM songs WHERE elo_score > ?', (new_winner_elo,)).fetchone()[
        0]

    # Update Database
    conn.execute('''
        UPDATE songs 
        SET elo_score = ?, matches_played = matches_played + 1,
            highest_elo = CASE WHEN ? > highest_elo THEN ? ELSE highest_elo END,
            highest_rank = CASE WHEN ? < highest_rank OR highest_rank = 9999 THEN ? ELSE highest_rank END
        WHERE id = ?
    ''', (new_winner_elo, new_winner_elo, new_winner_elo, winner_new_rank, winner_new_rank, winner_id))

    conn.execute('UPDATE songs SET elo_score = ?, matches_played = matches_played + 1 WHERE id = ?',
                 (new_loser_elo, loser_id))
    conn.execute('INSERT INTO history (winner_id, loser_id) VALUES (?, ?)', (winner_id, loser_id))
    conn.commit()
    conn.close()

    # Return the reveal data to the frontend
    return jsonify({
        "winner": {"title": winner['title'], "artist": winner['artist'], "cover_url": winner['cover_url'],
                   "elo_change": f"+{int(new_winner_elo - winner['elo_score'])}"},
        "loser": {"title": loser['title'], "artist": loser['artist'], "cover_url": loser['cover_url'],
                  "elo_change": f"{int(new_loser_elo - loser['elo_score'])}"}
    })


# --- TRIVIA MINI-GAME ---

@app.route('/trivia')
def trivia_mode():
    # Initialize the user's running score in their session
    if 'trivia_score' not in session:
        session['trivia_score'] = 0

    conn = get_db_connection()
    song = conn.execute(
        'SELECT id, audio_url FROM songs WHERE audio_url IS NOT NULL AND audio_url != "" ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()

    return render_template('trivia_mode.html', song=song, score=session['trivia_score'])


@app.route('/api/trivia_guess', methods=['POST'])
def api_trivia_guess():
    """Checks the guess, updates the recognizability stats, and returns the result."""
    data = request.json
    song_id = data['song_id']

    conn = get_db_connection()
    song = conn.execute('SELECT title, artist, cover_url FROM songs WHERE id = ?', (song_id,)).fetchone()

    # Check guesses against actual data (75% accuracy threshold)
    title_match = is_close_match(data.get('title_guess', ''), song['title'])
    artist_match = is_close_match(data.get('artist_guess', ''), song['artist'])

    points = 0
    if title_match: points += 1
    if artist_match: points += 1

    session['trivia_score'] = session.get('trivia_score', 0) + points

    # Update global recognizability stats for this song
    conn.execute(
        'UPDATE songs SET trivia_attempts = trivia_attempts + 1, trivia_correct = trivia_correct + ? WHERE id = ?',
        (points, song_id))
    conn.commit()
    conn.close()

    return jsonify({
        "actual_title": song['title'],
        "actual_artist": song['artist'],
        "cover_url": song['cover_url'],
        "points_earned": points,
        "new_total": session['trivia_score'],
        "title_correct": title_match,
        "artist_correct": artist_match
    })

@app.route('/trivia_stats')
def trivia_stats():
    conn = get_db_connection()
    # Calculate recognizability percentage. Only show songs with at least 1 attempt.
    stats_data = conn.execute('''
        SELECT id, title, artist, cover_url, trivia_attempts, trivia_correct,
               (CAST(trivia_correct AS FLOAT) / (trivia_attempts * 2)) * 100 as rec_score
        FROM songs
        WHERE trivia_attempts > 0
        ORDER BY rec_score DESC, trivia_attempts DESC
    ''').fetchall()
    conn.close()

    return render_template('trivia_stats.html', stats=stats_data)

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
    # Fetch all songs and instantly convert the sqlite3.Row objects to standard dictionaries
    raw_songs = conn.execute('SELECT * FROM songs ORDER BY artist, title').fetchall()
    songs = [dict(row) for row in raw_songs]
    conn.close()

    return render_template('dev_dashboard.html', songs=songs)


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
    """Silently adds a new song to the database."""
    data = request.json
    title = data.get('title')
    artist = data.get('artist')
    album = data.get('album', '')
    cover_url = data.get('cover_url', '')
    audio_url = data.get('audio_url', '')

    conn = get_db_connection()
    existing = conn.execute('SELECT id FROM songs WHERE title = ? AND artist = ?', (title, artist)).fetchone()

    if existing:
        conn.close()
        return jsonify({"status": "error", "message": f"'{title}' by {artist} already exists."}), 400

    conn.execute('''
        INSERT INTO songs (title, artist, album, cover_url, audio_url, elo_score, matches_played)
        VALUES (?, ?, ?, ?, ?, 1200, 0)
    ''', (title, artist, album, cover_url, audio_url))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Added '{title}'"})


@app.route('/api/dev/edit_song/<int:song_id>', methods=['POST'])
@admin_required
def api_edit_song(song_id):
    """Updates an existing song's metadata, with auto-fetch for Apple Music links."""
    data = request.json
    title = data.get('title', '')
    artist = data.get('artist', '')
    album = data.get('album', '')
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

    conn = get_db_connection()
    conn.execute('''
        UPDATE songs 
        SET title = ?, artist = ?, album = ?, cover_url = ?, audio_url = ? 
        WHERE id = ?
    ''', (title, artist, album, cover_url, audio_url, song_id))
    conn.commit()
    conn.close()

    # Return the final applied data so the frontend can refresh the table row
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
    """Deletes a song and scrubs its match history."""
    conn = get_db_connection()
    conn.execute('DELETE FROM songs WHERE id = ?', (song_id,))
    conn.execute('DELETE FROM history WHERE winner_id = ? OR loser_id = ?', (song_id, song_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Song deleted."})

@app.route('/api/dev/sync', methods=['POST'])
@admin_required
def api_sync():
    """Endpoint to trigger a manual database push."""
    success = git_push()
    if success:
        return jsonify({"status": "success", "message": "Database synced to GitHub!"})
    return jsonify({"status": "error", "message": "Failed to sync to GitHub."}), 500

if __name__ == "__main__":
    git_pull()
    init_db()
    app.run(debug=True)