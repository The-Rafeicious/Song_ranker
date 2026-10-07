import sqlite3
import re
import os

OLD_DB = 'song_ranker.db'
NEW_DB = 'song_ranker_v2.db'


def create_new_schema(conn):
    """Builds the new relational table structure."""
    conn.executescript('''
                       CREATE TABLE albums
                       (
                           id           INTEGER PRIMARY KEY AUTOINCREMENT,
                           title        TEXT NOT NULL,
                           cover_url    TEXT,
                           release_date TEXT
                       );

                       CREATE TABLE artists
                       (
                           id        INTEGER PRIMARY KEY AUTOINCREMENT,
                           name      TEXT NOT NULL,
                           cover_url TEXT
                       );

                       CREATE TABLE genres
                       (
                           id   INTEGER PRIMARY KEY AUTOINCREMENT,
                           name TEXT NOT NULL UNIQUE
                       );

                       CREATE TABLE songs
                       (
                           id             INTEGER PRIMARY KEY, -- Enforcing exact old ID to preserve history
                           title          TEXT NOT NULL,
                           album_id       INTEGER,
                           audio_url      TEXT,
                           elo_score      REAL    DEFAULT 1200,
                           matches_played INTEGER DEFAULT 0,
                           highest_elo    REAL    DEFAULT 1200,
                           highest_rank   INTEGER DEFAULT 9999,
                           track_number   INTEGER,
                           FOREIGN KEY (album_id) REFERENCES albums (id)
                       );

                       CREATE TABLE song_artists
                       (
                           song_id   INTEGER,
                           artist_id INTEGER,
                           FOREIGN KEY (song_id) REFERENCES songs (id),
                           FOREIGN KEY (artist_id) REFERENCES artists (id),
                           PRIMARY KEY (song_id, artist_id)
                       );

                       CREATE TABLE song_genres
                       (
                           song_id  INTEGER,
                           genre_id INTEGER,
                           FOREIGN KEY (song_id) REFERENCES songs (id),
                           FOREIGN KEY (genre_id) REFERENCES genres (id),
                           PRIMARY KEY (song_id, genre_id)
                       );

                       CREATE TABLE trivia_stats
                       (
                           song_id  INTEGER PRIMARY KEY,
                           attempts INTEGER DEFAULT 0,
                           correct  INTEGER DEFAULT 0,
                           FOREIGN KEY (song_id) REFERENCES songs (id)
                       );

                       CREATE TABLE history
                       (
                           id        INTEGER PRIMARY KEY AUTOINCREMENT,
                           winner_id INTEGER,
                           loser_id  INTEGER,
                           FOREIGN KEY (winner_id) REFERENCES songs (id),
                           FOREIGN KEY (loser_id) REFERENCES songs (id)
                       );

                       CREATE TABLE global_stats
                       (
                           key   TEXT PRIMARY KEY,
                           value INTEGER
                       );
                       ''')


def migrate_data():
    if os.path.exists(NEW_DB):
        os.remove(NEW_DB)

    old_conn = sqlite3.connect(OLD_DB)
    old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(NEW_DB)

    create_new_schema(new_conn)

    # Dictionary caches to prevent duplicate entries and map text to new IDs
    album_map = {}
    artist_map = {}

    print("Migrating songs, artists, and albums...")
    old_songs = old_conn.execute('SELECT * FROM songs').fetchall()

    for song in old_songs:
        # 1. Process Album (Handling empty albums gracefully)
        album_title = song['album'].strip() if song['album'] else "Unknown Album"
        if album_title not in album_map:
            cursor = new_conn.execute('INSERT INTO albums (title, cover_url) VALUES (?, ?)',
                                      (album_title, song['cover_url']))
            album_map[album_title] = cursor.lastrowid
        album_id = album_map[album_title]

        # 2. Insert Song (Preserving the exact original ID)
        new_conn.execute('''
                         INSERT INTO songs (id, title, album_id, audio_url, elo_score, matches_played, highest_elo,
                                            highest_rank)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                         ''', (song['id'], song['title'], album_id, song['audio_url'],
                               song['elo_score'], song['matches_played'], song['highest_elo'], song['highest_rank']))

        # 3. Process Artists (Splitting by comma, &, and, feat., ft.)
        # This regex ignores case and handles varied spacing
        artist_string = song['artist'].strip()
        split_artists = re.split(r', |\s+feat\.\s+|\s+ft\.\s+|\s+&\s+|\s+and\s+', artist_string, flags=re.IGNORECASE)

        for artist_name in split_artists:
            artist_name = artist_name.strip()
            if not artist_name:
                continue

            if artist_name not in artist_map:
                # We reuse the track's cover_url as a placeholder for the artist profile picture
                cursor = new_conn.execute('INSERT INTO artists (name, cover_url) VALUES (?, ?)',
                                          (artist_name, song['cover_url']))
                artist_map[artist_name] = cursor.lastrowid

            artist_id = artist_map[artist_name]

            # 4. Link Song to Artist in Junction Table
            new_conn.execute('INSERT OR IGNORE INTO song_artists (song_id, artist_id) VALUES (?, ?)',
                             (song['id'], artist_id))

        # 5. Extract Trivia Stats into isolated table
        new_conn.execute('INSERT INTO trivia_stats (song_id, attempts, correct) VALUES (?, ?, ?)',
                         (song['id'], song['trivia_attempts'], song['trivia_correct']))

    print("Migrating match history...")
    old_history = old_conn.execute('SELECT * FROM history').fetchall()
    for match in old_history:
        new_conn.execute('INSERT INTO history (id, winner_id, loser_id) VALUES (?, ?, ?)',
                         (match['id'], match['winner_id'], match['loser_id']))

    print("Migrating global stats...")
    old_stats = old_conn.execute('SELECT * FROM global_stats').fetchall()
    for stat in old_stats:
        new_conn.execute('INSERT INTO global_stats (key, value) VALUES (?, ?)',
                         (stat['key'], stat['value']))

    new_conn.commit()
    old_conn.close()
    new_conn.close()
    print(f"Migration complete! Your new relational database is saved as '{NEW_DB}'.")


if __name__ == "__main__":
    migrate_data()