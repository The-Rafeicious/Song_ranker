import sqlite3
import requests
import re

DB_NAME = "song_ranker.db"


def get_song_data(title, artist, album=""):
    """Silently fetches cover art and audio without an interactive menu."""
    query = f"{title} {artist} {album}".strip().replace(" ", "+")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=10&explicit=Yes"

    try:
        response = requests.get(url, timeout=5).json()
        if response.get('resultCount', 0) > 0:
            results = response['results']
            best_track = results[0]

            for track in results:
                if track.get('trackExplicitness') == 'explicit':
                    best_track = track
                    break

            artwork_url = best_track['artworkUrl100'].replace('100x100bb', '300x300bb')
            audio_url = best_track.get('previewUrl', "")
            return artwork_url, audio_url
    except Exception as e:
        print(f"  -> Error fetching {title}: {e}")

    return "https://via.placeholder.com/320/2a2a2a/ffffff?text=No+Cover", ""


def get_song_by_link(url):
    """Fetches exact track data using an Apple Music URL ID."""
    match = re.search(r'[?&]i=(\d+)', url)
    if not match:
        print("  -> Error: Could not find track ID in the link.")
        return None

    track_id = match.group(1)
    lookup_url = f"https://itunes.apple.com/lookup?id={track_id}"

    try:
        response = requests.get(lookup_url, timeout=5).json()
        if response['resultCount'] > 0:
            track = response['results'][0]
            title = track.get('trackName', 'Unknown Title')
            artist = track.get('artistName', 'Unknown Artist')
            album = track.get('collectionName', '')
            artwork_url = track['artworkUrl100'].replace('100x100bb', '300x300bb')
            audio_url = track.get('previewUrl', "")
            return title, artist, album, artwork_url, audio_url
    except Exception as e:
        print(f"  -> Error fetching link: {e}")

    print("  -> API failed to return data for this ID.")
    return None


def add_song_loop(conn):
    print("\n--- CONTINUOUS ADD MODE ---")
    print("Paste Apple Music links one after another.")
    print("Type 'm' to return to the Main Menu manually.")

    while True:
        title_input = input("\nEnter Apple Music link (or 'm' for menu): ").strip()
        if title_input.lower() == 'm' or title_input.lower() == 'q':
            break
        if not title_input:
            continue

        if "music.apple.com" in title_input:
            print("  -> Link detected. Fetching...")
            result = get_song_by_link(title_input)
            if not result: continue
            title, artist, album, cover_url, audio_url = result
        else:
            # Fallback to manual text entry if they don't use a link
            title = title_input
            artist = input("Enter artist name: ").strip()
            if not artist: continue
            album = input("Enter album name (optional): ").strip()
            print("  -> Fetching data from Apple Music...")
            cover_url, audio_url = get_song_data(title, artist, album)

        existing = conn.execute('SELECT id FROM songs WHERE title = ? AND artist = ?', (title, artist)).fetchone()
        if existing:
            print(f"  -> '{title}' by {artist} already exists in your database!")
            continue

        conn.execute('''
            INSERT INTO songs (title, artist, album, cover_url, audio_url, elo_score, matches_played)
            VALUES (?, ?, ?, ?, ?, 1200, 0)
        ''', (title, artist, album, cover_url, audio_url))
        conn.commit()
        print(f"  -> Successfully added '{title}' by {artist}!")


def search_songs(conn):
    print("\n--- SEARCH / QUERY ---")
    query = input("Enter an artist, song, or album to search: ").strip()

    results = conn.execute('''
        SELECT id, title, artist, album, elo_score, matches_played 
        FROM songs 
        WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
        ORDER BY elo_score DESC
    ''', (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()

    if not results:
        print("  -> No matches found.")
        return

    print(f"\nFound {len(results)} matches (Sorted by highest Elo):")
    print(f"{'ID':<4} | {'Elo':<6} | {'Matches':<7} | {'Track'}")
    print("-" * 75)
    for row in results:
        album_display = f" [{row[3]}]" if row[3] else ""
        print(f"{row[0]:<4} | {int(row[4]):<6} | {row[5]:<7} | {row[1]} by {row[2]}{album_display}")
    print()


def delete_song(conn):
    print("\n--- DELETE SONG ---")
    song_id = input("Enter the exact ID of the song to delete (or 'q' to cancel): ").strip()
    if song_id.lower() == 'q': return

    song = conn.execute('SELECT title, artist FROM songs WHERE id = ?', (song_id,)).fetchone()
    if not song:
        print("  -> Song ID not found.")
        return

    confirm = input(f"Are you sure you want to delete '{song[0]} by {song[1]}'? (y/n): ").strip().lower()
    if confirm == 'y':
        conn.execute('DELETE FROM songs WHERE id = ?', (song_id,))
        conn.execute('DELETE FROM history WHERE winner_id = ? OR loser_id = ?', (song_id, song_id))
        conn.commit()
        print("  -> Song successfully deleted.")
    else:
        print("  -> Deletion canceled.")


def edit_song(conn):
    print("\n--- EDIT SONG ---")
    search_input = input("Enter Song ID OR type the track name to search (or 'q' to cancel): ").strip()
    if search_input.lower() == 'q': return

    # If the user typed text instead of a number, search for the ID
    if not search_input.isdigit():
        results = conn.execute('''
            SELECT id, title, artist, album 
            FROM songs 
            WHERE title LIKE ? OR artist LIKE ?
        ''', (f"%{search_input}%", f"%{search_input}%")).fetchall()

        if not results:
            print("  -> No songs found matching that text.")
            return

        if len(results) == 1:
            song_id = str(results[0][0])
            print(f"  -> Found match: [{song_id}] {results[0][1]} by {results[0][2]}")
        else:
            print("\nMultiple matches found:")
            for r in results:
                print(f"[{r[0]}] {r[1]} by {r[2]}")
            song_id = input("\nEnter the exact ID from the list above: ").strip()
    else:
        song_id = search_input

    song = conn.execute('SELECT title, artist, album FROM songs WHERE id = ?', (song_id,)).fetchone()
    if not song:
        print("  -> Song ID not found.")
        return

    current_album = song[2] if song[2] else ""
    print(f"\nEditing: {song[0]} by {song[1]}")
    print("Press Enter to keep current value, or type a new one.")

    new_title = input(f"New Title or Apple Link [{song[0]}]: ").strip()
    if "music.apple.com" in new_title:
        print("  -> Link detected. Replacing track data...")
        result = get_song_by_link(new_title)
        if not result: return
        title, artist, album, cover_url, audio_url = result

        conn.execute('''
            UPDATE songs SET title=?, artist=?, album=?, cover_url=?, audio_url=? WHERE id=?
        ''', (title, artist, album, cover_url, audio_url, song_id))
        conn.commit()
        print(f"  -> Successfully updated to '{title}' by {artist}.")
        return

    new_artist = input(f"New Artist [{song[1]}]: ").strip()
    new_album = input(f"New Album [{current_album}]: ").strip()

    final_title = new_title if new_title else song[0]
    final_artist = new_artist if new_artist else song[1]
    final_album = new_album if new_album else current_album

    force_fetch = input("Re-fetch cover/audio from Apple silently? (y/n): ").strip().lower()

    if final_title != song[0] or final_artist != song[1] or final_album != current_album or force_fetch == 'y':
        print("  -> Updating data...")
        cover_url, audio_url = get_song_data(final_title, final_artist, final_album)

        conn.execute('''
            UPDATE songs SET title=?, artist=?, album=?, cover_url=?, audio_url=? WHERE id=?
        ''', (final_title, final_artist, final_album, cover_url, audio_url, song_id))
        conn.commit()
        print("  -> Song updated successfully.")
    else:
        print("  -> No changes made.")


def main_menu():
    conn = sqlite3.connect(DB_NAME)
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
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN album TEXT')
    except sqlite3.OperationalError:
        pass
    conn.commit()

    while True:
        print("\n=== SONG RANKER DATABASE MANAGER ===")
        print("1. Add songs (Continuous Loop Mode)")
        print("2. Search / Query songs")
        print("3. Edit a song (Fix wrong tracks)")
        print("4. Delete a song")
        print("5. Exit")

        choice = input("Select an option (1-5): ").strip()
        if choice == '1':
            add_song_loop(conn)
        elif choice == '2':
            search_songs(conn)
        elif choice == '3':
            edit_song(conn)
        elif choice == '4':
            delete_song(conn)
        elif choice == '5':
            break
        else:
            print("Invalid choice.")
    conn.close()


if __name__ == "__main__":
    main_menu()