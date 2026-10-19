"""Offline schema adapters for recovery and historical fixtures; current DDL has one owner."""


def ensure_mode_schema(conn, *, legacy=False):
    objects = {r['name']: r['type'] for r in conn.execute(
        "SELECT name,type FROM sqlite_master WHERE type IN ('table','view')")}
    if objects.get('trivia_stats') == 'view':
        conn.execute('DROP VIEW trivia_stats')
    # Only detailed V3.2 results and their sparse manual corrections remain.
    from songranker.storage.database_schema import create_objects
    create_objects(conn, names={'trivia_adjustments'})
    missing_rounds = 'trivia_rounds' not in objects
    if missing_rounds and not legacy:
        create_objects(conn, names={'challenge_runs', 'challenge_active_run'})
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
    # A pre-8 database without detailed Trivia has no quiz facts to transport.
    # Let the final canonical rebuild create the current empty tables/view.
    if not (legacy and missing_rounds):
        create_objects(conn, names={'trivia_rounds', 'trivia_rounds_song', 'trivia_stats'})
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


from songranker.storage.database_schema import create_objects


def ensure_special_schema(conn, *, legacy=False):
    missing = not conn.execute("SELECT 1 FROM sqlite_master WHERE name='elo_guess_rounds'").fetchone()
    if missing and not legacy:
        create_objects(conn, names={'challenge_runs', 'challenge_active_run'})
    names={'album_shelf_rounds', 'album_shelf_items', 'shelf_completed'}
    if not (legacy and missing):
        names.update({'elo_guess_rounds', 'elo_guess_completed'})
    create_objects(conn, names=names)
