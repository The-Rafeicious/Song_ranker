# V5.1.1.2 — mode retirement and one safe database

## Install

1. Stop the app. Merge this package’s `Song_ranker` folder into your installation.
2. Keep the main database, backups, `instance` settings and Git folder.
3. Delete the obsolete files listed below; an ordinary file merge does not remove them.
4. Launch `python safe_mode.py`, hard-refresh and check footer **V5.1.1.2**.
5. Stop safe mode and run `python main.py` when ready for real play.

## Removed files

Paths are relative to your `Song_ranker` folder. The same list is supplied in
[DELETE_FILES_V5_1_1_2.txt](../DELETE_FILES_V5_1_1_2.txt).

- `songranker/modes/sound_twins.py`
- `songranker/modes/__pycache__/sound_twins.*.pyc` (if present)
- `docs/V5_1_VALIDATION.json` (historical copy retained under `update_logs/validation/`)
- `docs/V5_1_1_VALIDATION.json` (historical copy retained under `update_logs/validation/`)

The shared game/stats templates, controller and CSS remain because Spotlight
and Vibe still use them. This package removes their retired-mode branches.
The frozen `tests/fixtures/schema_v16.sql` intentionally describes the old
schema for migration tests; it is not active storage or gameplay.

## Database change

Sound Twins is retired. Schema 17 removes its choices table/trigger, completed
and pending rounds/items, mode listening and derived exposure entries. All
catalogue values and other mode results remain, including Spotlight and Vibe.
The standard migration first creates a verified `database_backups/pre_upgrade_*.db`
backup. Safe launch upgrades only its copy; the main database changes on normal
launch. JSON rebuilds and SQL restores apply the same selective retirement.
Old mode URLs return 404. Historical release logs and validation are retained
as records of earlier versions. Overall remains calibration 7: Spotlight keeps
its adaptive preference contribution; Vibe retains zero quality weight.

## Safe testing without accumulating runs

`python safe_mode.py` creates a copy once, then reopens that same test database.
Restart and browser refresh preserve test answers and edits. The latest valid
marked old run for the same source is adopted automatically; other marked old
runs for that source are removed. Unmarked folders, other sources and backups
are not pruned. The stable directory is `data/safe_mode/run_<source-path hash>/`
(or beneath `SONG_RANKER_SAFE_DIR`).

To load the main database’s latest songs into that same location, stop the app
and run:

```sh
python safe_mode.py --refresh-safe-mode
```

Refresh intentionally clears safe test answers/edits. It never writes those
answers into the main database. A failed source copy preserves the prior safe
database. Git remains disabled in safe mode. The main database’s existing
launcher lock, read-only source and managed write protections remain in place.

## Colour and navigation

Vibe Map now uses vivid red `#FF3B3B` throughout its game, dedicated stats,
Home card, menus and activity. The navbar spectrum removes the retired accent
and ends with Vibe. The Stats dropdown is a roomy single column with a separate
line per destination and no internal scrolling.

See [current validation](VALIDATION.md), [database reference](DATABASE.md),
[technical guide](TECHNICAL_GUIDE.md) and [style guide](PAGE_STYLE.md).
