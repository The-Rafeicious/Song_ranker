-- Frozen pre-preference-replay layout, recovered from attached git commit 8eb97b4. DDL only, no user data.
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
            CHECK((answer_slot IS NULL AND answer_position IS NULL) OR
                  (answer_slot IS NOT NULL AND answer_position IS NOT NULL))
        );

CREATE TABLE album_shelf_rounds (
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            started_at REAL NOT NULL,
            completed_at REAL,
            rules_version INTEGER NOT NULL DEFAULT 1 CHECK(rules_version=1)
        );

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

CREATE TABLE elo_guess_rounds (
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

CREATE TABLE genres
                       (
                           id   INTEGER PRIMARY KEY AUTOINCREMENT,
                           name TEXT NOT NULL UNIQUE
                       , description TEXT NOT NULL DEFAULT '');

CREATE TABLE global_stats
                       (
                           key   TEXT PRIMARY KEY,
                           value INTEGER
                       );

CREATE TABLE history
                       (
                           id        INTEGER PRIMARY KEY AUTOINCREMENT,
                           winner_id INTEGER,
                           loser_id  INTEGER, created_at DATETIME, mode TEXT NOT NULL DEFAULT 'standard', winner_before REAL, winner_after REAL, loser_before REAL, loser_after REAL,
                           FOREIGN KEY (winner_id) REFERENCES songs (id),
                           FOREIGN KEY (loser_id) REFERENCES songs (id)
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
                           track_number   INTEGER, tournament_wins INTEGER DEFAULT 0,
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
                played_at DATETIME, match_type TEXT NOT NULL DEFAULT 'bracket',
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL DEFAULT 'completed', created_at DATETIME, updated_at DATETIME, completed_at DATETIME, current_round INTEGER NOT NULL DEFAULT 1, points_version INTEGER NOT NULL DEFAULT 1, is_blind BOOLEAN NOT NULL DEFAULT 0, playoff_enabled INTEGER NOT NULL DEFAULT 0, runner_up_id INTEGER REFERENCES songs(id), third_place_id INTEGER REFERENCES songs(id), fourth_place_id INTEGER REFERENCES songs(id),
            FOREIGN KEY(champion_id) REFERENCES songs(id)
        );

CREATE TABLE trivia_adjustments (
        song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
        new_attempts_delta INTEGER NOT NULL DEFAULT 0,
        title_correct_delta INTEGER NOT NULL DEFAULT 0,
        artist_correct_delta INTEGER NOT NULL DEFAULT 0,
        album_attempts_delta INTEGER NOT NULL DEFAULT 0,
        album_correct_delta INTEGER NOT NULL DEFAULT 0);

CREATE TABLE trivia_rounds (
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
        user_score_after REAL, streak_after INTEGER);

CREATE INDEX idx_tournaments_status ON tournaments(status);

CREATE INDEX idx_tournament_matches_tournament_round
                ON tournament_matches(tournament_id, round_number, match_number);

CREATE INDEX idx_tournament_matches_winner ON tournament_matches(winner_id);

CREATE INDEX idx_tournament_matches_loser ON tournament_matches(loser_id);

CREATE INDEX history_winner ON history(winner_id,id);

CREATE INDEX history_loser ON history(loser_id,id);

CREATE INDEX songs_album ON songs(album_id);

CREATE INDEX song_artists_artist ON song_artists(artist_id,song_id);

CREATE INDEX song_genres_genre ON song_genres(genre_id,song_id);

CREATE INDEX trivia_rounds_song ON trivia_rounds(song_id,id);

CREATE INDEX elo_guess_completed ON elo_guess_rounds(completed_at,id);

CREATE INDEX shelf_completed ON album_shelf_rounds(completed_at,id);

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
