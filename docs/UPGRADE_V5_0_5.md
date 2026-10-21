# V5.0.5 — laptop / desktop database sync

## What caused the stale laptop

Earlier startup code fast-forwarded Git and downloaded `database_backup.sql`,
but an existing `data/song_ranker_v3.db` always won. SQL recovery only ran when
the live file was missing. Pulling the code before launch therefore did not
bring an existing laptop database up to date. SQL backup validity and loading
that backup into an existing database are separate operations.

The repository backup at commit `2d3638a35eb02fd2745cfd64d6389abe71dcf67f` was
validated read-only for this release: **1,003 songs, 199 releases including
Singles, 80 artists and 64 tags**, schema 16. Fresh SQL bootstrap reproduced
every stored value exactly. No live user database or repository SQL was
modified during validation. Later uploads may have newer totals.

## Apply this update

1. Stop the app on both computers before replacing code. Preserve their live
   databases, `instance` folder, backups and Git metadata.
2. Apply/pull V5.0.5 on both computers. On the stale laptop, run the normal
   `python main.py` launcher. Manual Git pulls before launch are supported.
3. Read the database startup outcome, then check the song total. A safe update
   reports the old/new song totals and its safety archive. No schema change or
   new dependency is required.
4. Between computers, use Dev → **Stop app**, leave Git upload selected, enter
   the PIN and wait for the uploaded-backup receipt before changing computers.
   A browser-tab close, process kill, failed push or local-only stop does not
   confirm a remote database upload.

Older app versions do not have the new upload guard. Update both computers
before another shutdown upload; a client still running old code cannot enforce
this protocol. If an old client has already uploaded a stale snapshot, retain
the prior Git backup commits and local archives for comparison.

Do not delete the laptop database or force-push an old laptop backup to make
the counts match. The normal launcher now handles the separate database check.

## How the decision is made

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

## If the databases have split

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

## Safety and hosting scope

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
