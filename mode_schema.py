"""V3.2 mode schema. Trivia summaries are views, not duplicate result logs."""


def ensure_mode_schema(conn):
    objects = {r['name']: r['type'] for r in conn.execute(
        "SELECT name,type FROM sqlite_master WHERE type IN ('table','view')")}
    if objects.get('trivia_stats') == 'table':
        if objects.get('trivia_legacy') == 'table':
            if conn.execute('SELECT COUNT(*) FROM trivia_legacy').fetchone()[0]:
                raise ValueError('Both legacy trivia tables contain data; migration stopped safely.')
            conn.execute('DROP TABLE trivia_legacy')
        conn.execute('ALTER TABLE trivia_stats RENAME TO trivia_legacy')
    conn.execute('''CREATE TABLE IF NOT EXISTS trivia_legacy (
        song_id INTEGER PRIMARY KEY REFERENCES songs(id),
        attempts INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0)''')
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(trivia_legacy)')}
    for name in ('new_attempts_delta', 'title_correct_delta', 'artist_correct_delta',
                 'album_attempts_delta', 'album_correct_delta'):
        if name not in cols:
            conn.execute(f'ALTER TABLE trivia_legacy ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0')
    conn.execute('''CREATE TABLE IF NOT EXISTS trivia_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        song_id INTEGER REFERENCES songs(id) ON DELETE CASCADE,
        album_available INTEGER NOT NULL CHECK(album_available IN (0,1)),
        started_at REAL, paused_at REAL, paused_seconds REAL NOT NULL DEFAULT 0,
        completed_at REAL,
        title_correct INTEGER CHECK(title_correct IN (0,1)),
        artist_correct INTEGER CHECK(artist_correct IN (0,1)),
        album_correct INTEGER CHECK(album_correct IN (0,1)),
        title_seconds REAL, artist_seconds REAL, album_seconds REAL,
        user_score_after REAL, streak_after INTEGER)''')
    conn.execute('CREATE INDEX IF NOT EXISTS trivia_rounds_song ON trivia_rounds(song_id,id)')
    conn.execute('''CREATE VIEW IF NOT EXISTS trivia_stats AS
        WITH recent AS (
          SELECT song_id,COUNT(*) AS new_attempts,
            SUM(COALESCE(title_correct,0)) AS title_correct,
            SUM(COALESCE(artist_correct,0)) AS artist_correct,
            SUM(album_available) AS album_attempts,
            SUM(COALESCE(album_correct,0)) AS album_correct
          FROM trivia_rounds WHERE completed_at IS NOT NULL GROUP BY song_id
        ), totals AS (
          SELECT s.id AS song_id,COALESCE(l.attempts,0) AS legacy_attempts,
            COALESCE(l.correct,0) AS legacy_correct,
            COALESCE(r.new_attempts,0)+COALESCE(l.new_attempts_delta,0) AS new_attempts,
            COALESCE(r.title_correct,0)+COALESCE(l.title_correct_delta,0) AS title_correct,
            COALESCE(r.artist_correct,0)+COALESCE(l.artist_correct_delta,0) AS artist_correct,
            COALESCE(r.album_attempts,0)+COALESCE(l.album_attempts_delta,0) AS album_attempts,
            COALESCE(r.album_correct,0)+COALESCE(l.album_correct_delta,0) AS album_correct
          FROM songs s LEFT JOIN trivia_legacy l ON l.song_id=s.id
          LEFT JOIN recent r ON r.song_id=s.id
        ) SELECT *,legacy_attempts+new_attempts AS attempts,
          legacy_correct+title_correct+artist_correct+album_correct AS correct,
          2*(legacy_attempts+new_attempts)+album_attempts AS available_points,
          new_attempts AS title_attempts,new_attempts AS artist_attempts
          FROM totals WHERE legacy_attempts+new_attempts>0''')
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(history)')}
    if 'is_tournament_match' in cols:
        conn.execute("UPDATE history SET mode='legacy_tournament' WHERE is_tournament_match=1")
        conn.execute('ALTER TABLE history DROP COLUMN is_tournament_match')
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(tournament_matches)')}
    if 'match_type' not in cols:
        conn.execute("ALTER TABLE tournament_matches ADD COLUMN match_type TEXT NOT NULL DEFAULT 'bracket'")
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(tournaments)')}
    for name, declaration in [('playoff_enabled','INTEGER NOT NULL DEFAULT 0'),
                              ('runner_up_id','INTEGER REFERENCES songs(id)'),
                              ('third_place_id','INTEGER REFERENCES songs(id)'),
                              ('fourth_place_id','INTEGER REFERENCES songs(id)')]:
        if name not in cols:
            conn.execute(f'ALTER TABLE tournaments ADD COLUMN {name} {declaration}')
    if not conn.execute("SELECT 1 FROM global_stats WHERE key='trivia_scoring_version'").fetchone():
        conn.execute("INSERT OR IGNORE INTO global_stats(key,value) SELECT 'trivia_legacy_high_score',value FROM global_stats WHERE key='trivia_high_score'")
        conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_high_score',0) ON CONFLICT(key) DO UPDATE SET value=0")
        conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_scoring_version',2)")
    conn.execute("INSERT OR IGNORE INTO global_stats(key,value) VALUES('trivia_high_streak',0)")
