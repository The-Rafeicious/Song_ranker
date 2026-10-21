# Promoting Vibe Map code without the test database

Keep testing on `New-modes-test`. Do not merge that branch's database snapshot
into main: it may contain experimental placements, skipped maps and broken runs.
The eventual production change should promote reviewed source commits only.
Nothing in Vibe-Map-v1.0.4 performs a merge or copies a database.

## During testing

1. Close the production app and make a normal backup of its current database.
2. Use separate working folders/checkouts for main and `New-modes-test`.
3. Set `SONG_RANKER_DB` to an explicit separate file for the test checkout before
   launching it. Confirm Dev's active database path. Do not point both checkouts
   at the same SQLite file or reuse an upgraded test database with older main code.
4. Keep each checkout's Git upstream on its own branch. Closing the test app can
   upload its test snapshot to the test branch; that does not make it production.

The existing Git startup/shutdown system still reconciles/uploads backups.
A separate database path alone does not disable that system or prevent someone
from accidentally promoting its SQL snapshot. Keep the separate checkout and
branch as well, and review the eventual code PR's file list.

## When the mode is ready

Recommended: make an integration branch from up-to-date main, then cherry-pick
only the reviewed feature code commits in order. Resolve ordinary source conflicts
there and open a PR into main. Feature PR commits that contain only code/tests/docs
can be picked directly; do not blindly pick snapshot/backup commits or a squash
commit that also includes test data. If history is mixed, recreate the reviewed
source changes as a clean code-only commit on the integration branch.

Include Python, templates, CSS, JavaScript, tests, docs and **schema/migration
source**. `data/schema.sql` and `tests/fixtures/schema_*.sql` are source and must
be included when needed. Do not exclude every SQL file.

Exclude `database_backup.sql`, live `*.db`/`*.sqlite*` files, SQLite sidecars,
rolling backups, instance runtime state and generated exports/rankings from the
promotion. If seed/catalogue data changed on the test branch, review it separately;
it must not silently replace the production catalogue. Check the PR file list and
diff against main explicitly before merging. Do not use a full branch merge that
brings an experimental SQL backup along, then rely on startup to sort it out.

Before running the new main code, close both apps, retain a fresh production
backup, confirm main's tracked snapshot is the correct production snapshot and
confirm its Git upstream is main. Start against the existing production database;
the normal backed-up migration adds the required tables/columns without copying
test placements. The new mode begins unmapped in production. Test-round state,
means and counters are intentionally left behind in the test checkout.

Run CI and a disposable-copy upgrade check on the integration branch before
promoting it. Keep the old production backup for rollback: older app code cannot
open a database upgraded to a newer schema. A source rollback alone does not
roll back a database migration.

V1.0.4.2 advances to schema 19 and intentionally clears generation-1 test Vibe
Map data once. Include that migration and its definition keys when promoting
code. This does not authorise importing a test database into production.
