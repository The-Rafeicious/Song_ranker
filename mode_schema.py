"""V3.2.4 mode schema. Trivia summaries are views, not duplicate result logs."""


def ensure_mode_schema(conn):
    objects = {r['name']: r['type'] for r in conn.execute(
        "SELECT name,type FROM sqlite_master WHERE type IN ('table','view')")}
    if objects.get('trivia_stats') == 'view':
        conn.execute('DROP VIEW trivia_stats')
    # Only detailed V3.2 results and their sparse manual corrections remain.
    conn.execute('''CREATE TABLE IF NOT EXISTS trivia_adjustments (
        song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
        new_attempts_delta INTEGER NOT NULL DEFAULT 0,
        title_correct_delta INTEGER NOT NULL DEFAULT 0,
        artist_correct_delta INTEGER NOT NULL DEFAULT 0,
        album_attempts_delta INTEGER NOT NULL DEFAULT 0,
        album_correct_delta INTEGER NOT NULL DEFAULT 0)''')
    if objects.get('trivia_legacy') == 'table':
        old_columns = {r['name'] for r in conn.execute('PRAGMA table_info(trivia_legacy)')}
        deltas = ('new_attempts_delta','title_correct_delta','artist_correct_delta',
                  'album_attempts_delta','album_correct_delta')
        if set(deltas) <= old_columns:
            columns = ','.join(deltas)
            conn.execute(f'INSERT OR IGNORE INTO trivia_adjustments(song_id,{columns}) '
                         f'SELECT song_id,{columns} FROM trivia_legacy WHERE '+
                         ' OR '.join(f'{name}!=0' for name in deltas))
        conn.execute('DROP TABLE trivia_legacy')
    if objects.get('trivia_stats') == 'table':
        conn.execute('DROP TABLE trivia_stats')
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
          SELECT s.id AS song_id,COALESCE(r.new_attempts,0)+COALESCE(l.new_attempts_delta,0) AS new_attempts,
            COALESCE(r.title_correct,0)+COALESCE(l.title_correct_delta,0) AS title_correct,
            COALESCE(r.artist_correct,0)+COALESCE(l.artist_correct_delta,0) AS artist_correct,
            COALESCE(r.album_attempts,0)+COALESCE(l.album_attempts_delta,0) AS album_attempts,
            COALESCE(r.album_correct,0)+COALESCE(l.album_correct_delta,0) AS album_correct
          FROM songs s LEFT JOIN trivia_adjustments l ON l.song_id=s.id
          LEFT JOIN recent r ON r.song_id=s.id
        ) SELECT *,new_attempts AS attempts,
          title_correct+artist_correct+album_correct AS correct,
          2*new_attempts+album_attempts AS available_points,
          new_attempts AS title_attempts,new_attempts AS artist_attempts
          FROM totals WHERE new_attempts>0''')
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
        conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_high_score',0) ON CONFLICT(key) DO UPDATE SET value=0")
        conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_scoring_version',2)")
    conn.execute("INSERT OR IGNORE INTO global_stats(key,value) VALUES('trivia_high_streak',0)")

    conn.execute("DELETE FROM global_stats WHERE key='trivia_legacy_high_score'")
