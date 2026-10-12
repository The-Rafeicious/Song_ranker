# Song Ranker V3.3

New modes update for **V3.2.7.1**. Current schema: **8**.

## Install

1. Stop Song Ranker and keep a copy of your existing project/database.
2. Copy the supplied `Song_ranker` folder contents over your existing project,
   replacing matching files. Keep your own `song_ranker_v2.db`, backups and settings.
3. Run `python -m pip install -r requirements.txt` if dependencies are missing.
4. Start `python main.py`. The app backs up and upgrades the existing database.
5. Hard-refresh the browser. Shared assets now use version `3.3`.

No replacement database is included. Existing Elo, votes, trivia, brackets,
catalogue metadata and profile-title positions are retained. Root-level old
changelogs can remain on your laptop; current notes are now in `update_logs/`.

## Major additions

- **Elo Guesser** is the third tab beside non-blind and blind voting. It uses
  red-orange, frozen Elo comparisons, 1 point per correct answer and current/best
  streaks. It never calls the voting save endpoint or changes song ratings.
- **Album Shelves** is a separate darker-purple page. It selects exactly ten
  tracks from two or three proper albums, allowing uneven distributions and
  artists to match or differ. Missing/duplicate track positions and singles are
  excluded; track-number gaps are valid.
- Shelves support drag/drop, selectors, up/down buttons and focused-row arrow
  keys. Checking requires each offered track exactly once. Correct albums earn
  1 point; relative order earns up to 2 more. A singleton shelf has no order
  points and the available-score denominator adjusts accordingly.
- Optional ten-second previews cycle through available tracks, highlight the
  selected/playing row and loop back to the first. Playback starts from the
  button or a track control; it is not automatic. Buffering and failures use
  existing preview safeguards. Moving rows does not interrupt playback.
- Both modes have detailed stats/history and song/artist/album rankings with
  top/bottom twenty. Guesser rankings offer accuracy, correct picks and exposure;
  Shelves offers points, percentage earned, album membership and track order.

## Page and navigation changes

- Mode Rankings is a coloured dropdown linking to separate Recognisability,
  Tournament, Elo Guesser and Album Shelves rankings. Tournament retains first,
  second, third, podiums, match wins and points. Existing performance URLs still
  work for bookmarks; the new navigation/profile links use separate mode pages.
- Home retains existing cards/banners and adds both new mode cards and record
  summaries. Global stats adds Guesser accuracy/best streak and Shelves points,
  rounds and perfect results.
- Song, artist, album and tag profiles gain compact knowledge panels. Current
  catalogue relationships pool track results; an artist collaboration counts
  once within each artist. Ordinary wins/recognisability/podiums are unchanged.
- Dev gains New mode records, recent-result search, individual round deletion
  and separate Guesser/Shelves resets. Deletion/reset creates a database backup.
  Reset all competition data now includes the new modes. Old scope resets leave
  the new modes intact.
- Shared colours, side glows, score cards, entity links and responsive controls
  include both new accents. Song/artist/album titles remain beside artwork.
- `version.py` is the single version source. Every page footer shows **V3.3**
  below System Access; shared assets use the same cache version.
- The main README is now a current project guide. These version-specific notes
  and future hotfix notes belong in `update_logs/` with an index.

## Storage and protections

Schema 8 adds **three tables**: `elo_guess_rounds`, `album_shelf_rounds` and
`album_shelf_items`. The migration is automatic, backed up and repeatable.

Only question-time answer facts, submitted selections/positions and timing are
saved. Scores, percentages and streaks are derived. There are no new audit logs,
duplicated artwork/audio/name snapshots or persistent summary counters. Pending
questions older than a day are discarded when their mode creates a new round.

Tokens are bound to the browser session. The server validates offered IDs and
complete unique placements, grades saved facts, and prevents repeat submissions.
Deleted songs/albums preserve completed historical scoring but lose active links;
an unanswered question with deleted records must be replaced. The ordinary vote
endpoint explicitly rejects a Guesser mode label.

## Verification

Backend tests cover existing features, schema preservation, frozen answers,
streaks, independent saves/resets, malformed/duplicate input, missing metadata,
singles, skipped track positions and uneven shelf sizes. Interface checks cover
mode switching, ordering, ten-second preview event cycling, rankings and page
integrations. All test databases are copies or temporary files.

A graphical browser render and real Apple playback were unavailable for these
checks; media events are mocked. Existing request throttling/429 safeguards are
retained and no live Apple requests are needed to create either new mode.
