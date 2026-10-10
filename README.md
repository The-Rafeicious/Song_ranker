# Song Ranker — approved V3 implementation

## Run locally

Unzip the project, open a terminal in the `Song_ranker` folder, then run:

```sh
python -m pip install -r requirements.txt
python main.py
```

Open http://127.0.0.1:5000. Your existing System Access PIN still works.

When installing this over your existing project, keep your own live
`song_ranker_v2.db` if you have added votes or tracks since uploading the ZIP.
The first startup migrates that database after saving a safety backup.
Stop the app before replacing files. Keep the new Python modules and the
entire `templates` and `static` folders together.

## Changes

- Approved V3 colours, navigation, scrolling home shelves, song details,
  separate rankings, search and developer dashboard.
- Rankings heading and category links centred; no tier-list link on those
  pages. The tier list remains available from the main navigation.
- Voting shows Elo only after a committed vote. Blind votes reveal the artwork,
  title, artists and proper album in the same cards.
- Cover-art playback, shared volume, outside-click/Escape dismissal and
  proper album metadata in voting. Singles stay in the library and out of album
  counts, album rankings and voting's album line.
- Related song/artist/album/tag search, editable records, Apple Music imports,
  retained suggestions, column filters, sorting, pagination, selectable columns
  and 32-character table labels with full-value hover text.
- Trivia, tournaments, resume, tournament statistics, histories, genres,
  artist/album pages, tier list, backup, restore, reset, corrections, exports
  and Git sync remain available.

## Code

`main.py` is the entry point. `services.py` contains shared database access,
metadata queries, Elo calculation, backups and exports. `catalog.py` handles
library projections and impact scores. `pages.py`, `games.py` and `dev.py`
contain their respective routes. `database.py` owns the versioned migration.

Artist and album impact is consistently `1200 + sum(song Elo - 1200)`.
Each song contributes once, including collaborations.

The application reads its database relative to its own folder rather than the
terminal's current directory. Optional environment overrides are
`SONG_RANKER_DB`, `SONG_RANKER_PIN` and `SONG_RANKER_SECRET`.
Git sync uses the existing `origin/main` configuration. Startup pulls updates
when this project folder is an existing Git checkout, and keeps local database
files. Restart after an update to load changed Python modules.

## Database

The included active database preserves the supplied 389 songs, 51 artists,
114 releases (57 proper albums), one regular match, four tournaments,
64 entries, 60 bracket matches and the existing trivia totals.

A vote now writes its mode, timestamp and before/after Elo into `history` once.
The generic interaction log, admin audit log and duplicate Elo log are removed.
Unused zero-attempt trivia rows are removed; new imports do not create them.
Tournament entries and matches remain separate because they support results,
resume and archives. Rating counters and peaks are kept because old history
is incomplete. Song deletion retains completed bracket structure and protects
unfinished brackets from becoming unplayable.

The migration runs once and does not overwrite existing match-mode labels.
Ambiguous old Elo entries, if encountered, are kept separately instead of being
assigned to the wrong vote. Restores validate and migrate a temporary copy
before replacing the live database, and save a pre-restore backup.

`database_backups` contains the original pre-reset backup and a pre-upgrade copy
of the uploaded active database. `legacy_data/song_ranker.db` is the older
flat-schema database with 186 songs and 701 history records; it is preserved
separately and is not silently merged into the active database.
Historical command-line tools are retained in `legacy_tools` for reference.

## Validation

See `VALIDATION.md`. To rerun the backend tests:

```sh
python tests/test_app.py
```

The test suite works on temporary copies and never changes your live database.
Apple Music search, streamed artwork and preview audio require internet access.
