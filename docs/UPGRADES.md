# Upgrades and recovery

Current operating guidance for the generation-3 competition, schema 20.
Patch-by-patch installation notes are **expired / no longer necessary**; their
feature history is consolidated in [V5.0](../update_logs/V5_0_UPDATE.md) and
[V5.1](../update_logs/V5_1_UPDATE.md). v5.1.2 includes a backed-up schema migration.

- [Routine updates](#routine-updates)
- [First competition transfer](#first-competition-transfer)
- [Schema and storage changes](#schema-and-storage-changes)
- [Tags and catalogue policy](#tags-and-catalogue-policy)
- [Backups and controlled stop](#backups-and-controlled-stop)
- [Database sync and split recovery](#database-sync-and-split-recovery)
- [Recovery](#recovery)
- [Historical storage measurements](#historical-storage-measurements)

## Routine updates

1. Stop the app on each computer before updating source. Keep the live database,
   backups, `instance/session_secret` and Git metadata.
2. Pull/review the intended branch, then run `python main.py`. The normal launcher
   updates source before Flask imports, bootstraps/migrates the database, compares
   committed remote data, then starts Waitress.
3. Read the startup outcome and verify catalogue totals. Hard-refresh open tabs.
   A failed migration or uncertain sync needs review, not deletion of the live file.
4. Use the new code with upgraded databases. Older code may refuse a newer schema;
   source rollback alone does not roll back database structure.

`APP_VERSION` is `5.2.1`; Vibe reports `Vibe-Map-v1.1`.
The documentation release labels v5.1.0/v5.1.1 do not change the runtime footer.
Install dependencies from `requirements.txt`; configuration is in the
[technical guide](TECHNICAL_GUIDE.md#configuration).

## First competition transfer

Default paths are `song_ranker_v2.db` for the optional old source and
`data/song_ranker_v3.db` for the live competition. Set `SONG_RANKER_DB` for another
active destination and `SONG_RANKER_LEGACY_DB` for a custom V2 source. The exact
old `song_ranker_v2.db` setting maps to a separate sibling V3 destination.

An existing verified V3 file wins. Otherwise startup considers the V2 source,
a committed SQL backup, an optional catalogue seed, then an empty catalogue.
Generation-3 SQL restores results as well as catalogue data; pre-V5 sources
transfer catalogue only. First transfer takes a complete V2 safety snapshot and
verifies exact IDs, song metadata, albums/artists/tags, links, current source
observations and ID high-water marks before publishing a fresh V3 competition.
Elo/peaks begin at 1200; results, attempts and streaks start fresh.
The old source is left intact. Ordinary restarts and later code upgrades do not
repeat this transfer/reset.

Old package-specific song totals and optional “Optimized_database_copy” downloads
are **expired references**, not a reason to replace newer local data. The schema
and catalogue present on your installation determine current counts.

## Schema and storage changes

| Schema | Change | Existing-data handling |
| --- | --- | --- |
| 14 | Generation-3 competition baseline. | One-time V2 catalogue-only transfer when creating a new competition. |
| 15 | Compressed current Apple source snapshots and page-size policy. | Verified pre-upgrade backup; current source retained losslessly, superseded observations removed by that historical migration. Later source saves replace the current row. |
| 16 | Eight-tag maximum and database write guards. | Retain earliest eight stored attachments on over-limit songs; tag definitions/results stay. Rowid order, with deterministic tag-ID fallback for rowid-free imports. |
| 17 | Four required Vibe slots per song. | Add description tables and links without assigning invented points. |
| 18 | Vibe progress and browser-round state. | Compact running averages/counts rather than an unbounded attempt log. |
| 19 | Generation-2 Vibe map meanings. | Back up and reset incompatible generation-1 Vibe test data once; catalogue and other modes remain. Current schema-19 placements are retained. |

Use normal backed-up migrations. `tools/reset_vibe_maps_v1042.py` is a
**historical compatibility helper**, no longer necessary on schema 19; it is not
a general reset command. The optional `tools/prepare_vibe_merge.py` is a different,
explicit test-results cleanup tool, documented in [Vibe Dev maintenance](VIBE_MAP_DEV.md).
It is not part of startup or a routine main-branch update.

## Tags and catalogue policy

Each song supports eight distinct tags, including Apple's supplied genre.
Workbench Add checks the resulting union; Replace checks the replacement set;
Remove can target any number. Selected tags remain removable at capacity.
Typed new names count too. Review and apply recheck saved memberships; overflow
fails atomically rather than silently trimming a new edit.

Suggested complementary tags below are optional ideas retained from the original
audit, **not automatically created or assigned**. Existing tags may already
cover them; a song need not fill every slot.

| Suggested tag | Use it for | Distinction from existing tags |
| --- | --- | --- |
| `moving-on` | Actively letting go while it may still hurt. | `better-off` describes feeling happier after the split. |
| `self-acceptance` | Making peace with yourself, flaws included. | A softer counterpart to `self-hate`, rather than the defiance of `strong`. |
| `growing-up` | Identity, independence and new responsibilities. | `changing` currently describes changes within a relationship. |
| `regret` | Wishing you had acted or spoken differently. | More specific than looking back in `retrospective`. |
| `escapism` | Imagining or seeking a way out of everyday life. | Separates escape and fantasy from `rebel` defiance. |
| `dreamy` | Floating vocals, hazy textures and spacious production. | Describes sound rather than `low-pop` intensity or `electronic` instrumentation. |
| `tension` | Sustained unease, anticipation or unresolved pressure. | `build-up` describes the rise into a powerful chorus. |
| `grief` | Processing bereavement or a lasting absence. | Covers loss beyond romantic `heart-ache` or general `sad`. |

Use these where they add meaning; a song does not need to fill all eight slots.
The existing `crush`/`flirt`/`falling-in-love` and `past-love`/`hung-up` groups
already cover their areas well, so extra near-duplicates are less useful.


## Backups and controlled stop



- Ordinary edits do not create backups: single/bulk source changes, source metadata
  refreshes, tag edits, Single moves, missing-information fills, deletes and resets.
  Their existing review, validation and transaction safeguards remain.
- **Create backup**, **Stop app**, and the explicitly labelled **Back up & restore**
  action share three slots: `rolling_1.db`, `rolling_2.db`, `rolling_3.db` in the
  active database's sibling `database_backups/` folder. Each new request replaces
  the oldest slot after a complete, verified SQLite snapshot is ready.
- Update/migration recovery archives remain separate. They protect the original
  data when startup upgrades its structure or storage. Ordinary restarts with no
  database change do not add such an archive.
- Existing backups are left untouched. This patch does not silently delete old
  files; the three-slot policy applies to the new rotating files. Full export
  downloads and Git commit history are independent of these three slots.

Use **Create backup** before edits if you want a restore point. SQLite snapshots
include committed WAL data. A failed snapshot/validation/replacement preserves
all previous rotating slots.

### Stop from the website

The **Stop app** button is in the developer dashboard's top action bar, accessible
from every developer view on the hosting computer. Enter the developer PIN again,
even if already signed in. The dialog shows the current Git branch and destination.
Git upload defaults on when configured; without Git, it clearly offers local-only
shutdown. No PIN is saved in the job or retained in the active form.

After **Back up & stop app**:

1. New app actions are paused and active requests/DB connections finish.
2. A rotating local backup is created and verified.
3. If selected, the app uploads `database_backup.sql` through the existing Git
   flow. This publishes only the database snapshot, not unrelated code edits.
4. Local-backup and Git outcomes appear together. After four visible seconds,
   the browser acknowledges them and the normal launcher shuts down.

**Cancel stop** or closing the dialog keeps the app running. If the local backup
or requested Git push fails, the app stays running and displays the error, keeping
any successful local backup. Missing browser acknowledgement times out after two
minutes and resumes the app. A Git snapshot already current on the remote is
reported as unchanged rather than claiming a new push.

The server stops; the browser retains the final receipt so you can close the tab.
Browsers generally do not allow a website to close a tab it did not open. Restart
with `python main.py` when needed. Closing the terminal is not the website's
backup-and-stop workflow.

Website shutdown is intentionally supported by the normal, single-process
Waitress launcher. An externally managed WSGI/Gunicorn host shows the feature as
unavailable; it must be stopped using its own process manager. Local-only System
Access restrictions and same-origin request protection continue to apply.


## Database sync and split recovery

The normal launcher checks an existing database after code/bootstrap, including
a manual Git pull. Do not decide freshness from file dates or song counts.



The comparison uses the fetched, committed upstream SQL blob, not the worktree
file’s timestamp, file size or song count. The snapshot is restored privately,
validated and upgraded using the current schema before comparison. It must be
a V3 competition. Future/invalid schemas, foreign-key errors and corrupt SQL
do not replace local data.

A per-device sync receipt binds a known SQL blob/commit to this database path,
repository, branch and remote target. Confirmed device-bound upload/startup records can
recover a missing receipt. For installations upgrading from older releases,
the app also searches up to 32 SQL-changing ancestor commits for an exact
logical match with the old local database, including deleted-ID high-water
marks. A shallow/older history or an unmatched local edit can prevent this
initial recovery; the app then retains both copies for review. A pre-V5 SQL
ancestor may supply a catalogue-only V5-transfer witness if it exactly matches
the local fresh competition; the current remote must still be a full V3 backup.

Stored rows are compared by primary key, plus sequence high-water marks and
schema/extension objects. Hidden rowids remain identities for unkeyed extension
tables; junction-table rowids do not make a re-saved relationship into new data.
Only competition install time/provenance are treated as device-local metadata.
Ratings, results, offers, sources, notes, tag links and other game/catalogue
facts participate in the comparison.

The common baseline identifies additions, edits **and removals**. A remote
snapshot can supersede local data only if it already includes every local
change; local-only deletion must also be present remotely. Equal counts do not
prove equality. Different songs independently assigned the same ID conflict.

| Outcome | Startup | Upload |
| --- | --- | --- |
| Same logical database | Record/refresh shared baseline. | No duplicate commit for an unchanged SQL file. |
| Remote includes all local changes plus newer changes | Archive local DB, recheck under a write lock, install remote transactionally. | Block; restart first. |
| Only local changes remain | Keep local data. | Publish the verified local snapshot. |
| Both have changes the other lacks | Keep local; save an incoming candidate backup for review. | Block. |
| Baseline cannot be recovered / snapshot cannot be validated | Keep local; provide a review copy when the incoming snapshot is valid. | Block until resolved. |

Initial historical matching can identify a stale older snapshot, but no new
version can reconstruct edits/deletions that were never checkpointed anywhere.
If either computer has unuploaded independent work, compare both backups before
choosing a replacement. Ongoing receipts and confirmed upload history supply
the deletion baseline for subsequent computer switches.

### If the databases have split

The startup log and Dev Git panel identify a database conflict separately from
code commit state. The local database is left active; a validated remote copy
is listed under Dev → **Database & backups** as
`incoming_git_<blob>.db`, with purpose “Incoming Git database — compare before
restore”. This file is never silently used as the live database.

Create a local backup/export and inspect both copies. If the remote copy is the
intended complete library, use the existing **Review → Back up & restore**
workflow for that incoming file, then restart / Check remote to confirm it
matches. A restore replaces the entire database; its review and safety backup
remain in place. If both copies contain unique work, retain/export both while
reconciling that work deliberately. There is no guessed row union, force-push,
automatic rebase or silent choice between colliding song/result IDs.

### Safety and hosting scope

Automatic replacements create non-rotating `pre_git_database_…db` archives;
requested/shutdown backups retain their existing three-slot rotation. A new
local write detected during preparation cancels replacement. The final write
uses `BEGIN IMMEDIATE`; validation/rebuild failure rolls the transaction back.
A completed upload or restore is still reported as successful if saving its
local receipt/outcome log fails afterwards.

Database receipt/status files live in Git’s private `song_ranker_sync` directory
and are not uploaded as catalogue data. Normal app edits do not create extra
backups. Opening Dev status is local-only; **Check remote** fetches and compares
without replacing live data. **Upload** fetches and rechecks before publishing.

Automatic adoption runs only in the stopped, normal launcher after code re-exec
and database bootstrap, before Waitress starts. WSGI imports retain their
Git-free startup contract; externally managed/multi-worker servers need stopped
maintenance for database replacement. Shutdown upload guards also apply there.

See [validation](VALIDATION.md) for test scope and limits.

## Recovery

Keep the original database and the safety archive. Dev → Database & backups
reviews a V3 backup and the current live state before **Back up & restore**.
Restore replaces the whole database; it is not a row merge. Reload old game tabs
after restoring. A pre-V5 archive is a transfer/recovery source, not a normal
V3 full-restore candidate.

For offline work, stop the app and use `python -m songranker.developer.db_tools --help`.
Audit, export, compare, rebuild and restore use the shared lossless transport;
recovered files are written separately. Inspect the recovered copy before
choosing it as active. See [hosting and recovery](TECHNICAL_GUIDE.md#hosting-and-recovery).

For future test-mode promotion, keep production data separate. A clean test
snapshot can be a catalogue seed; do not substitute it for a main database whose
results you intend to retain. [Vibe maintenance/promotion](VIBE_MAP_DEV.md) marks
its pre-integration procedure as historical.

## Historical storage measurements

**Expired benchmark / not a current database-size promise.** On the original
V5.0.2.1 attachment, the current-source/codec/page review reduced 897,024 bytes
to 573,440 (36.07%), with 241 source rows becoming 232. Catalogue totals were
517 songs / 155 releases / 67 artists / 54 tags. Other table values and latest
source fields were verified unchanged. The optional attachment is no longer
needed for installation; migrate your latest database normally.

Repeated JSON keys/URL prefixes compress well; main metadata URLs remain
readable. A 2 KiB page candidate beat the 1 KiB candidate for that sample, while
larger histories favour 4 KiB pages; used space can trigger the existing 4 MiB
page-policy threshold. Live results and source contents determine actual size.

## v5.1.2: keep local and remove listening storage

Schema 20 removes only legacy listening observations and their index. Startup
keeps a pre-migration backup. Existing scores, Vibe placements and catalogue links
remain intact; restoring an older backup runs the same migration.

For an intentional local reset or restored save, open Dev → System → Git and
choose **Keep local database…**. Review local/remote counts, type `KEEP LOCAL`,
and apply. Both databases are backed up; the live database stays unchanged.
Use normal upload afterwards. If source is behind, restart to update code first;
the reviewed database choice survives that restart. This does not force-push or
resolve diverged source commits. Any newer remote data needs a new review.

## v5.2.0 Dev navigation

No database migration. Hard-refresh tabs after upgrading. Stop is now available
from either header with one fresh PIN and no separate Dev login; localhost and
normal-launcher requirements remain. Existing bookmarks and tool URLs still work.
