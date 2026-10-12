"""V3.3 independent knowledge results; current stats are derived, not copied."""

def ensure_special_schema(conn):
    schema='''
        CREATE TABLE IF NOT EXISTS elo_guess_rounds (
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            song1_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
            song2_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
            elo1 REAL NOT NULL,
            elo2 REAL NOT NULL,
            started_at REAL NOT NULL,
            completed_at REAL,
            chosen_slot INTEGER CHECK(chosen_slot IN (1,2)),
            CHECK(elo1 != elo2),
            CHECK((completed_at IS NULL AND chosen_slot IS NULL) OR
                  (completed_at IS NOT NULL AND chosen_slot IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS elo_guess_completed ON elo_guess_rounds(completed_at,id);
        CREATE TABLE IF NOT EXISTS album_shelf_rounds (
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            started_at REAL NOT NULL,
            completed_at REAL,
            rules_version INTEGER NOT NULL DEFAULT 1 CHECK(rules_version=1)
        );
        CREATE TABLE IF NOT EXISTS album_shelf_items (
            round_id INTEGER NOT NULL REFERENCES album_shelf_rounds(id) ON DELETE CASCADE,
            item_slot INTEGER NOT NULL CHECK(item_slot BETWEEN 1 AND 10),
            song_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
            album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
            album_slot INTEGER NOT NULL CHECK(album_slot BETWEEN 1 AND 3),
            track_number INTEGER NOT NULL CHECK(track_number>0),
            answer_slot INTEGER CHECK(answer_slot BETWEEN 1 AND 3),
            answer_position INTEGER CHECK(answer_position BETWEEN 1 AND 10),
            PRIMARY KEY(round_id,item_slot),
            UNIQUE(round_id,song_id),
            CHECK((answer_slot IS NULL AND answer_position IS NULL) OR
                  (answer_slot IS NOT NULL AND answer_position IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS shelf_completed ON album_shelf_rounds(completed_at,id);
    '''
    for statement in schema.split(';'):
        if statement.strip():conn.execute(statement)
