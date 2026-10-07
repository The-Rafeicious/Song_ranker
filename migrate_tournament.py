import sqlite3

def migrate():
    # Connect to your active database file
    conn = sqlite3.connect('song_ranker_v2.db')
    cursor = conn.cursor()

    # 1. Create the new tournaments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            size INTEGER NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id INTEGER,
            champion_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(champion_id) REFERENCES songs(id)
        );
    ''')
    print("Ensured 'tournaments' table exists.")

    # 2. Add 'tournament_wins' to the songs table
    try:
        cursor.execute('ALTER TABLE songs ADD COLUMN tournament_wins INTEGER DEFAULT 0;')
        print("Added 'tournament_wins' to songs.")
    except sqlite3.OperationalError:
        # If the column already exists, SQLite throws an error. We catch it and move on safely.
        print("'tournament_wins' already exists in songs.")

    # 3. Add 'is_tournament_match' to the history table
    try:
        cursor.execute('ALTER TABLE history ADD COLUMN is_tournament_match BOOLEAN DEFAULT 0;')
        print("Added 'is_tournament_match' to history.")
    except sqlite3.OperationalError:
        print("'is_tournament_match' already exists in history.")

    conn.commit()
    conn.close()
    print("Database migration complete!")

if __name__ == '__main__':
    migrate()