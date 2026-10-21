-- Frozen schema-12 layout: schema-13 DDL from the attached V2 archive, before source and exact-date additions. No user data.
CREATE TABLE album_shelf_items (
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
    CHECK((answer_slot IS NULL AND answer_position IS NULL) OR (answer_slot IS NOT NULL AND answer_position IS NOT NULL))
);

CREATE TABLE album_shelf_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    started_at REAL NOT NULL,
    completed_at REAL,
    rules_version INTEGER NOT NULL DEFAULT 1 CHECK(rules_version=1)
);

CREATE TABLE albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    cover_url TEXT,
    release_date TEXT
);

CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cover_url TEXT
);

CREATE TABLE challenge_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('trivia','guesser')),
    rules_version INTEGER NOT NULL CHECK(rules_version=2),
    created_at REAL NOT NULL,
    ended_at REAL,
    CHECK(ended_at IS NULL OR ended_at>=created_at)
);

CREATE TABLE elo_guess_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    song1_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    song2_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    elo1 REAL NOT NULL,
    elo2 REAL NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    chosen_slot INTEGER CHECK(chosen_slot IN (1,2)),
    run_id INTEGER REFERENCES challenge_runs(id),
    rules_version INTEGER NOT NULL DEFAULT 1 CHECK(rules_version IN (1,2)),
    streak_before INTEGER,
    target_quantile REAL,
    streak_after INTEGER,
    user_score_after REAL,
    CHECK(elo1 != elo2),
    CHECK((completed_at IS NULL AND chosen_slot IS NULL) OR (completed_at IS NOT NULL AND chosen_slot IS NOT NULL)),
    CHECK((rules_version=1 AND run_id IS NULL) OR
          (rules_version=2 AND run_id IS NOT NULL AND streak_before IS NOT NULL AND streak_before>=0
           AND target_quantile IS NOT NULL AND target_quantile>0 AND target_quantile<=0.6)),
    CHECK(rules_version=1 OR completed_at IS NULL OR
          (streak_after IS NOT NULL AND streak_after>=0 AND user_score_after IS NOT NULL AND user_score_after>=0))
);

CREATE TABLE genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE global_stats (
    key TEXT PRIMARY KEY,
    value INTEGER
);

CREATE TABLE preference_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES preference_events(id) ON DELETE CASCADE,
    request_token TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL CHECK(action IN ('void','restore','replace')),
    winner_id INTEGER NOT NULL,
    loser_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE preference_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    winner_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    loser_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    mode TEXT NOT NULL DEFAULT 'standard',
    created_at DATETIME,
    winner_before REAL,
    winner_after REAL,
    loser_before REAL,
    loser_after REAL,
    offer_token TEXT UNIQUE REFERENCES preference_offers(token) ON DELETE SET NULL,
    origin TEXT NOT NULL DEFAULT 'legacy' CHECK(origin IN ('legacy','ordinary','tournament')),
    rules_version INTEGER NOT NULL DEFAULT 0 CHECK(rules_version>=0),
    winner_snapshot TEXT NOT NULL DEFAULT '{}',
    loser_snapshot TEXT NOT NULL DEFAULT '{}',
    rating_weight REAL NOT NULL DEFAULT 1 CHECK(rating_weight IN (0.5,1)),
    tournament_id INTEGER,
    tournament_match_id INTEGER UNIQUE,
    CHECK((origin='tournament' AND tournament_id IS NOT NULL AND tournament_match_id IS NOT NULL)
       OR (origin!='tournament' AND tournament_id IS NULL AND tournament_match_id IS NULL AND rating_weight=1))
);

CREATE TABLE preference_mode_ratings (
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK(mode IN ('standard','blind')),
    elo REAL NOT NULL DEFAULT 1200,
    matches INTEGER NOT NULL DEFAULT 0 CHECK(matches>=0),
    tournament_matches INTEGER NOT NULL DEFAULT 0 CHECK(tournament_matches BETWEEN 0 AND matches),
    PRIMARY KEY(song_id,mode)
);

CREATE TABLE preference_offers (
    token TEXT NOT NULL PRIMARY KEY,
    owner_hash TEXT NOT NULL,
    song1_id INTEGER NOT NULL,
    song2_id INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('standard','blind')),
    origin TEXT NOT NULL DEFAULT 'ordinary' CHECK(origin IN ('ordinary','tournament')),
    rules_version INTEGER NOT NULL CHECK(rules_version>0),
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','answered','cancelled')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    song1_snapshot TEXT,
    song2_snapshot TEXT,
    CHECK(song1_id!=song2_id),
    CHECK(status!='open' OR (song1_snapshot IS NOT NULL AND song2_snapshot IS NOT NULL))
);

CREATE TABLE preference_rating_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_token TEXT NOT NULL UNIQUE,
    song_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    song_snapshot TEXT NOT NULL,
    after_event_id INTEGER NOT NULL,
    previous_elo REAL NOT NULL,
    new_elo REAL NOT NULL CHECK(new_elo BETWEEN 0 AND 5000),
    reason TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE preference_rating_projection (
    event_id INTEGER PRIMARY KEY REFERENCES preference_events(id) ON DELETE CASCADE,
    winner_before REAL,
    winner_after REAL,
    loser_before REAL,
    loser_after REAL
);

CREATE TABLE preference_rating_seeds (
    song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    elo REAL NOT NULL,
    matches INTEGER NOT NULL,
    highest_elo REAL NOT NULL,
    highest_rank INTEGER NOT NULL
);

CREATE TABLE preference_replay_state (
    id INTEGER PRIMARY KEY CHECK(id=1),
    cutoff_event_id INTEGER NOT NULL,
    legacy_boundary INTEGER NOT NULL,
    baseline_kind TEXT NOT NULL CHECK(baseline_kind IN ('verified_replay','legacy_anchor')),
    rules_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE song_artists (
    song_id INTEGER,
    artist_id INTEGER,
    FOREIGN KEY (song_id) REFERENCES songs (id),
    FOREIGN KEY (artist_id) REFERENCES artists (id),
    PRIMARY KEY (song_id, artist_id)
);

CREATE TABLE song_genres (
    song_id INTEGER,
    genre_id INTEGER,
    FOREIGN KEY (song_id) REFERENCES songs (id),
    FOREIGN KEY (genre_id) REFERENCES genres (id),
    PRIMARY KEY (song_id, genre_id)
);

CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    album_id INTEGER,
    audio_url TEXT,
    elo_score REAL DEFAULT 1200,
    matches_played INTEGER DEFAULT 0,
    highest_elo REAL DEFAULT 1200,
    highest_rank INTEGER DEFAULT 9999,
    track_number INTEGER,
    tournament_wins INTEGER DEFAULT 0,
    FOREIGN KEY (album_id) REFERENCES albums (id)
);

CREATE TABLE tournament_entries (
    tournament_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    PRIMARY KEY (tournament_id, song_id),
    UNIQUE (tournament_id, seed),
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY(song_id) REFERENCES songs(id)
);

CREATE TABLE "tournament_matches" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    match_number INTEGER NOT NULL,
    song1_id INTEGER,
    song2_id INTEGER,
    winner_id INTEGER,
    loser_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    points_awarded REAL NOT NULL DEFAULT 0,
    played_at DATETIME,
    match_type TEXT NOT NULL DEFAULT 'bracket',
    UNIQUE (tournament_id, round_number, match_number),
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY(song1_id) REFERENCES songs(id),
    FOREIGN KEY(song2_id) REFERENCES songs(id),
    FOREIGN KEY(winner_id) REFERENCES songs(id),
    FOREIGN KEY(loser_id) REFERENCES songs(id)
);

CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    size INTEGER NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id INTEGER,
    champion_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at DATETIME,
    updated_at DATETIME,
    completed_at DATETIME,
    current_round INTEGER NOT NULL DEFAULT 1,
    points_version INTEGER NOT NULL DEFAULT 1,
    is_blind BOOLEAN NOT NULL DEFAULT 0,
    playoff_enabled INTEGER NOT NULL DEFAULT 0,
    runner_up_id INTEGER REFERENCES songs(id),
    third_place_id INTEGER REFERENCES songs(id),
    fourth_place_id INTEGER REFERENCES songs(id),
    elo_policy_version INTEGER NOT NULL DEFAULT 0 CHECK(elo_policy_version IN (0,1)),
    elo_weight REAL NOT NULL DEFAULT 0 CHECK(elo_weight IN (0,0.5,1)),
    CHECK((elo_policy_version=0 AND elo_weight=0) OR
          (elo_policy_version=1 AND ((scope_type='global' AND elo_weight=1) OR
          (scope_type IN ('artist','album','tag') AND elo_weight=0.5)))),
    FOREIGN KEY(champion_id) REFERENCES songs(id)
);

CREATE TABLE trivia_adjustments (
    song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    new_attempts_delta INTEGER NOT NULL DEFAULT 0,
    title_correct_delta INTEGER NOT NULL DEFAULT 0,
    artist_correct_delta INTEGER NOT NULL DEFAULT 0,
    album_attempts_delta INTEGER NOT NULL DEFAULT 0,
    album_correct_delta INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE trivia_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    song_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
    album_available INTEGER NOT NULL CHECK(album_available IN (0,1)),
    started_at REAL,
    paused_at REAL,
    paused_seconds REAL NOT NULL DEFAULT 0,
    completed_at REAL,
    title_correct INTEGER CHECK(title_correct IN (0,1)),
    artist_correct INTEGER CHECK(artist_correct IN (0,1)),
    album_correct INTEGER CHECK(album_correct IN (0,1)),
    title_seconds REAL,
    artist_seconds REAL,
    album_seconds REAL,
    user_score_after REAL,
    streak_after INTEGER,
    run_id INTEGER REFERENCES challenge_runs(id),
    rules_version INTEGER NOT NULL DEFAULT 1 CHECK(rules_version IN (1,2)),
    streak_before INTEGER,
    streak_rule TEXT CHECK(streak_rule IN ('any','title_or_album','title_and_album','title')),
    streak_passed INTEGER CHECK(streak_passed IN (0,1)),
    answer_snapshot TEXT,
    CHECK((rules_version=1 AND run_id IS NULL) OR
          (rules_version=2 AND run_id IS NOT NULL AND streak_before IS NOT NULL AND streak_before>=0
           AND streak_rule IS NOT NULL AND answer_snapshot IS NOT NULL)),
    CHECK(rules_version=1 OR completed_at IS NULL OR
           (streak_passed IS NOT NULL AND streak_after IS NOT NULL AND streak_after>=0
            AND user_score_after IS NOT NULL AND user_score_after>=0))
);

CREATE VIEW history AS
    SELECT e.id,e.winner_id,e.loser_id,e.mode,e.created_at,
      p.winner_before,p.winner_after,p.loser_before,p.loser_after
    FROM preference_effective e
    LEFT JOIN preference_rating_projection p ON p.event_id=e.id
    WHERE e.active=1 AND e.origin IN ('legacy','ordinary');

CREATE VIEW mode_exposures AS
    WITH preference_appearances AS (
      SELECT h.winner_id AS song_id,h.mode FROM history h JOIN songs w ON w.id=h.winner_id
        JOIN songs l ON l.id=h.loser_id WHERE h.winner_id!=h.loser_id
      UNION ALL
      SELECT h.loser_id AS song_id,h.mode FROM history h JOIN songs w ON w.id=h.winner_id
        JOIN songs l ON l.id=h.loser_id WHERE h.winner_id!=h.loser_id
    ), counts AS (
      SELECT song_id,mode,COUNT(*) appearances FROM preference_appearances
        WHERE mode IN ('standard','blind') GROUP BY song_id,mode
      UNION ALL SELECT song_id,'public',COUNT(*) FROM preference_appearances GROUP BY song_id
      UNION ALL SELECT song_id,'trivia',MAX(0,new_attempts) FROM trivia_stats
      UNION ALL SELECT e.song_id,'tournament',COUNT(*) FROM tournament_entries e
        JOIN tournaments t ON t.id=e.tournament_id GROUP BY e.song_id
      UNION ALL SELECT song_id,'guesser',COUNT(*) FROM (
        SELECT song1_id song_id FROM elo_guess_rounds WHERE completed_at IS NOT NULL
        UNION ALL SELECT song2_id FROM elo_guess_rounds WHERE completed_at IS NOT NULL
      ) WHERE song_id IS NOT NULL GROUP BY song_id
      UNION ALL SELECT i.song_id,'shelves',COUNT(*) FROM album_shelf_items i
        JOIN album_shelf_rounds r ON r.id=i.round_id WHERE r.completed_at IS NOT NULL
        AND i.song_id IS NOT NULL GROUP BY i.song_id
    ) SELECT c.song_id,c.mode,c.appearances FROM counts c JOIN songs s ON s.id=c.song_id;

CREATE VIEW preference_effective AS
    SELECT e.id,e.offer_token,e.origin,e.rules_version,e.created_at,
      e.rating_weight,e.tournament_id,e.tournament_match_id,
      CASE WHEN c.id IS NULL THEN e.winner_id ELSE c.winner_id END AS winner_id,
      CASE WHEN c.id IS NULL THEN e.loser_id ELSE c.loser_id END AS loser_id,
      CASE WHEN c.id IS NULL THEN e.mode ELSE c.mode END AS mode,
      COALESCE(c.active,1) AS active,COALESCE(c.id,0) AS revision
    FROM preference_events e LEFT JOIN preference_corrections c
      ON c.id=(SELECT MAX(last.id) FROM preference_corrections last WHERE last.event_id=e.id);

CREATE VIEW shelf_album_exposures AS
    SELECT i.album_id,COUNT(DISTINCT i.round_id) AS appearances
    FROM album_shelf_items i JOIN album_shelf_rounds r ON r.id=i.round_id
    JOIN albums a ON a.id=i.album_id WHERE r.completed_at IS NOT NULL GROUP BY i.album_id;

CREATE VIEW trivia_stats AS
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
          FROM totals WHERE new_attempts>0;

CREATE UNIQUE INDEX challenge_active_run
    ON challenge_runs(owner,mode) WHERE ended_at IS NULL;

CREATE INDEX elo_guess_completed ON elo_guess_rounds(completed_at,id);

CREATE UNIQUE INDEX guess_pending_run
    ON elo_guess_rounds(run_id) WHERE run_id IS NOT NULL AND completed_at IS NULL;

CREATE INDEX guess_run_results ON elo_guess_rounds(run_id,id);

CREATE INDEX history_loser ON preference_events(loser_id,id);

CREATE INDEX history_winner ON preference_events(winner_id,id);

CREATE INDEX idx_tournament_matches_loser ON tournament_matches(loser_id);

CREATE INDEX idx_tournament_matches_tournament_round
                ON tournament_matches(tournament_id, round_number, match_number);

CREATE INDEX idx_tournament_matches_winner ON tournament_matches(winner_id);

CREATE INDEX idx_tournaments_status ON tournaments(status);

CREATE INDEX preference_correction_event ON preference_corrections(event_id,id);

CREATE UNIQUE INDEX preference_open_offer
    ON preference_offers(owner_hash,mode,origin) WHERE status='open';

CREATE INDEX preference_override_order ON preference_rating_overrides(after_event_id,id);

CREATE INDEX shelf_completed ON album_shelf_rounds(completed_at,id);

CREATE INDEX song_artists_artist ON song_artists(artist_id,song_id);

CREATE INDEX song_genres_genre ON song_genres(genre_id,song_id);

CREATE INDEX songs_album ON songs(album_id);

CREATE TRIGGER songs_track_position_insert
            BEFORE INSERT ON songs BEGIN
            SELECT RAISE(ABORT,'Track number must be a positive whole number or NULL.')
              WHERE NEW.track_number IS NOT NULL
              AND (typeof(NEW.track_number)!='integer' OR NEW.track_number<1);
            SELECT RAISE(ABORT,'Track number is already used in this album.')
              WHERE NEW.album_id IS NOT NULL AND NEW.track_number IS NOT NULL
              AND EXISTS (SELECT 1 FROM songs s WHERE s.album_id=NEW.album_id
                  AND s.track_number=NEW.track_number );
            END;

CREATE TRIGGER songs_track_position_update
            BEFORE UPDATE OF album_id,track_number ON songs BEGIN
            SELECT RAISE(ABORT,'Track number must be a positive whole number or NULL.')
              WHERE NEW.track_number IS NOT NULL
              AND (typeof(NEW.track_number)!='integer' OR NEW.track_number<1);
            SELECT RAISE(ABORT,'Track number is already used in this album.')
              WHERE NEW.album_id IS NOT NULL AND NEW.track_number IS NOT NULL
              AND EXISTS (SELECT 1 FROM songs s WHERE s.album_id=NEW.album_id
                  AND s.track_number=NEW.track_number AND s.id!=NEW.id);
            END;

CREATE UNIQUE INDEX trivia_pending_run
    ON trivia_rounds(run_id) WHERE run_id IS NOT NULL AND completed_at IS NULL;

CREATE INDEX trivia_rounds_song ON trivia_rounds(song_id,id);

CREATE INDEX trivia_run_results ON trivia_rounds(run_id,id);
