"""Shared transactional result reset. Caller owns locks, backup and commit."""


def reset_vibes(conn,song_id=None):
    where=' WHERE song_id=?' if song_id is not None else ''
    params=(song_id,) if song_id is not None else ()
    conn.execute('DELETE FROM vibe_rounds'+where,params)
    conn.execute("UPDATE song_vibe_positions SET x=NULL,y=NULL,status='unmapped',updated_at=NULL,sample_count=0,not_applicable_count=0"+where,params)
    conn.execute('UPDATE song_vibe_progress SET completed_passes=0'+where,params)


def reset_results(conn,scope):
    if scope=='all':conn.execute('UPDATE competition_state SET started_at=unixepoch() WHERE id=1')
    if scope in ('all','matches'):
        from songranker.modes.preferences import reset_preferences
        reset_preferences(conn)
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_elo_changes'").fetchone():
            conn.execute('DELETE FROM legacy_elo_changes')
    if scope in ('all','trivia'):
        conn.execute('DELETE FROM trivia_rounds')
        conn.execute("DELETE FROM challenge_runs WHERE mode='trivia'")
        conn.execute('DELETE FROM trivia_adjustments')
        conn.execute("UPDATE global_stats SET value=0 WHERE key IN ('trivia_high_score','trivia_high_streak')")
        conn.execute("INSERT INTO global_stats(key,value) VALUES('trivia_scoring_version',2) ON CONFLICT(key) DO UPDATE SET value=2")
    if scope in ('all','tournaments'):
        from songranker.modes.preferences import void_tournament_preferences
        void_tournament_preferences(conn)
        for table in ('tournament_matches','tournament_entries','tournaments'):
            conn.execute(f'DELETE FROM {table}')
        conn.execute('UPDATE songs SET tournament_wins=0')
    if scope in ('all','guesser'):
        conn.execute('DELETE FROM elo_guess_rounds')
        conn.execute("DELETE FROM challenge_runs WHERE mode='guesser'")
    if scope in ('all','shelves'):
        conn.execute('DELETE FROM album_shelf_rounds')
    if scope in ('all','vibe'):
        reset_vibes(conn)
    if scope=='all':
        conn.execute("UPDATE global_stats SET value=CASE WHEN key='trivia_scoring_version' THEN 2 ELSE 0 END")
