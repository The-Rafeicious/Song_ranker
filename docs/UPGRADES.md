# Upgrades and recovery

Current operating guidance for the generation-3 competition, schema 22.
Patch-by-patch installation notes are **expired / no longer necessary**; their
feature history is consolidated in [V5.0](../update_logs/V5_0_UPDATE.md) and
[V5.1](../update_logs/V5_1_UPDATE.md). v5.1.2 includes a backed-up schema migration.

- [Routine updates](#routine-updates)
- [Adaptive Elo activation](#adaptive-elo-activation-v540)
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

`APP_VERSION` is `5.5.7`; Vibe reports `Vibe-Map-v1.1`.
The documentation release labels v5.1.0/v5.1.1 do not change the runtime footer.
Install dependencies from `requirements.txt`; configuration is in the
[technical guide](TECHNICAL_GUIDE.md#configuration).

## Adaptive Elo activation (V5.4.0)

On the first launch with a policy-1 database, startup creates an integrity-checked
SQLite archive beside the live database, in
`database_backups/pre_adaptive_elo_<timestamp>.db`. It includes committed WAL data.
The startup log prints its full path. This historical archive is never rotated
out by the three-slot rolling backup policy.

After normal Git database reconciliation, and before requests are served, the app
replays saved effective matches in event-ID order. Corrections, voids, weighted
first-round tournament results and manual overrides retain their meaning. Public
and independent mode ratings are rebuilt, along with full-history peaks. Missing
legacy history is never invented: protected anchor values/cutoffs remain.
Catalogue, tags, other game results and immutable original vote receipts stay intact.

The completion marker and all projections commit together. Later launches skip
activation. A backup, replay or validation failure stops startup and leaves the
old ratings and marker intact; fix the failure and restart to retry. A restored
older snapshot with a policy-1 marker will be activated on its next startup.

To return to the old calculation, stop the app, keep a separate backup of any
newer votes, restore the printed pre-adaptive archive using the existing recovery
workflow, and run the pre-V5.4.0 source. Returning only the source or only the
archive does not provide a consistent rollback. Starting V5.4.0 with that old
archive will activate adaptive Elo again. The archive restores the whole database
to that point in time; it does not merge later votes.

## Artist/album tournament Elo removal (V5.5.0)

The first launch archives affected databases to
`database_backups/pre_tournament_scope_<timestamp>.db` before removing existing
artist/album first-round Elo influence. The startup log prints the path. Original
votes remain saved as facts with void corrections; tournament matches, points,
placements, catalogue and other modes are retained. Public/independent Elo and
preference evidence replay without those events. Tags retain half influence and
whole-library tournaments retain full influence.

The retirement is transactional and runs only while affected policy flags/events
remain. Failure stops startup with previous data intact. To roll back, stop the
app, preserve any newer work separately, and restore the archive together with
pre-V5.5.0 source. Restoring it under V5.5.0 will retire the selective Elo again on
startup. Schema stays 21, using the existing points-only tournament policy.

## Album Shelves flags (V5.5.5)

Schema 22 adds `albums.shelves_excluded`, defaulting all existing albums to included.
The normal startup migration creates an integrity-checked pre-upgrade backup before
publishing the new schema. Saved rounds and historical results retain their facts;
no albums or songs are merged or removed. Upgrade every device before sharing
schema-22 snapshots, since older apps reject newer schemas.

Use Dev → Library → Albums → Edit → **Exclude from Album Shelves** for grouped or
placeholder releases that should stay ordinary albums but never enter new Shelves
questions. The setting is reversible and is carried in normal backups/Git sync.

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
| 22 | Per-album Shelves exclusion. | Verified pre-upgrade backup; existing albums remain included, saved rounds/results unchanged. |
| 14 | Generation-3 competition baseline. | One-time V2 catalogue-only transfer when creating a new competition. |
| 15 | Compressed current Apple source snapshots and page-size policy. | Verified pre-upgrade backup; current source retained losslessly, superseded observations removed by that historical migration. Later source saves replace the current row. |
| 16 | Eight-tag maximum and database write guards. | Retain earliest eight stored attachments on over-limit songs; tag definitions/results stay. Rowid order, with deterministic tag-ID fallback for rowid-free imports. |
| 17 | Four required Vibe slots per song. | Add description tables and links without assigning invented points. |
| 18 | Vibe progress and browser-round state. | Compact running averages/counts rather than an unbounded attempt log. |
| 19 | Generation-2 Vibe map meanings. | Back up and reset incompatible generation-1 Vibe test data once; catalogue and other modes remain. Current schema-19 placements are retained. |

Use normal backed-up migrations. Historical one-time Vibe reset/merge-cleanup
helpers were removed in V5.3; routine code updates never reset current results.
Use the explicit reviewed Dev controls when an intentional reset is needed.

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

V5.3.2 compares the live database and fetched remote SQL using canonical SHA-256
hashes before every app-managed pull/push and again after startup bootstrap.
Code ahead/behind is independent of database safety. Code may fast-forward while
an incoming database is flagged; the live DB is retained until an explicit choice.

| Database condition | Policy |
| --- | --- |
| Equal logical hashes | Record the shared baseline; no duplicate backup commit. |
| Remote hash equals accepted baseline | Upload local changes without intervention. |
| Last snapshot writer is this registered device | Trust the current local copy, including deliberate edits/deletions/resets. |
| Another/unidentified writer changed remote data | Keep local active, save a validated incoming review copy, require a choice. |
| Accepted remote snapshot removed, corrupt or unsupported | Keep local data; resolve/review the remote before upload. |

Hashes cover all stored facts, extension/schema objects and ID high-water marks;
installation start/provenance are excluded. Counts/timestamps alone never decide
which database wins. Existing V1 receipts upgrade on acceptance. Confirmed history
or an exact match among 32 older SQL snapshots may recover an initial baseline;
unknown work remains a review, including on a shallow clone with insufficient history.

Open **Dev → Tools & systems → Git sync → Compare databases…**. Inspect numbered
devices, backup commit time, full local/remote/baseline hashes, mode/catalogue counts
and per-table differences. Choose **Keep local** (`KEEP LOCAL`) or **Use remote**
(`USE REMOTE`). The exact compared hashes/target are bound to the current browser;
any intervening change requires a fresh review. Keeping local archives both copies
and permits Upload immediately. Using remote makes a non-rotating
`pre_git_database_…db` safety copy and replaces the whole database transactionally.
The incoming copy also appears in Backups & restore as `incoming_git_<blob>.db`.
There is no row union or automatic cross-device adoption. Keep/export both copies
if each contains unique work that needs deliberate reconciliation.

Device numbers start at 1 and allocate on each new installation's first successful
upload. Keep `.git/song_ranker_sync` to retain its random identity and receipts.
A changed DB path/new clone receives its own identity; no hostname is exposed.
A registry in each backup commit preserves assignments even when an older device
uploads again. The SQL comment header shows only commit time and device number.

Uploads add only a SQL commit atop the latest remote code; they do not publish
local code/staging or install incoming code. Both hashes and the expected remote
head are rechecked before publication. Changed remotes reject a push, preserving
the pending commit and snapshot for a fresh comparison/retry. Matching retries
reuse their pending commit; lost replies reconcile by database hash. A failed
upload never requires deleting/recreating `.git` or the live database.

### Git storage

**Compact Git storage** repacks objects while keeping unreachable recovery objects
and all history/reflogs. It verifies and moves old plain SQL safety copies from
`.git/song_ranker_sync` to compressed, content-deduplicated `.sql.gz` archives under
`database_backups/git_snapshots` beside the live DB. New SQL archives use that
location. No live DB, database backup or source history is deleted; existing remote
history is not rewritten. Matching hashes avoid timestamp-only backup commits.

### Safety and hosting scope

Code fast-forward still refuses staged/local code edits, merge/rebase work and
incoming private/database files. A live write during replacement preparation
cancels it; final replacement uses a maintenance gate and `BEGIN IMMEDIATE` with
rollback. Completed uploads/replacements stay successful if subsequent local
receipt/history writes fail. Ordinary edits do not create extra backups; requested
and shutdown backups retain their three-slot policy.

Status reads are cached/local-only. Opening Git performs a fresh remote comparison.
WSGI imports remain Git-free, and multi-worker replacement requires stopped offline
maintenance. Stop app still uses a fresh PIN, a local backup, independently checked
Git outcome and explicit acknowledgement before shutdown.

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

For an intentional local reset or restored save, open Dev → Tools & systems →
Git sync → **Compare databases…**. Review the copies and type `KEEP LOCAL`. Both
databases are backed up; the live database stays unchanged and can upload
immediately even with incoming code. The current hash/device policy above
supersedes the earlier ahead/behind upload restriction.

## v5.2.0 Dev navigation

No database migration. Hard-refresh tabs after upgrading. Stop is now available
from either header with one fresh PIN and no separate Dev login; localhost and
normal-launcher requirements remain. Existing bookmarks and tool URLs still work.

## V5.3.3 multi-disc upgrade

Schema 21 adds disc number 1 to existing songs and saved Shelves items. It keeps
album IDs, track numbers, answers, results and relationships intact and uses the
normal pre-upgrade backup/transactional rebuild. SQL restores recognize the old
schema-20 layout even when the dump omits `PRAGMA user_version`.

No real catalogue album records are merged automatically. Use the album/disc
workflow in [the Dev guide](DEV_GUIDE.md#albums-discs-and-artwork) after reviewing
the intended destination and its artwork. Keep older computers updated to V5.3.3
before sharing new schema-21 snapshots; older apps reject newer schemas.

## V5.3.4 guide dependency recovery

The guide reader no longer returns HTTP 500 when the `Markdown` package is
missing or cannot be imported. It shows safely escaped text and an installation
instruction instead. Git updates change source files; they never run pip. After
updating code, install `requirements.txt` using the app's Python interpreter and
restart to enable formatted headings, tables and contents links. Schema remains 21.
