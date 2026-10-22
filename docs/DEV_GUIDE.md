# Developer guide

**v5.2.2.1 · Dev tools**

Open **System Access** on the hosting computer and enter the Dev PIN. Dev replaces
the app header and gives the active tool the full content width. Existing editing
and record tools remain available while their later revamp steps are pending.

## Header

| Control | Action |
| --- | --- |
| Home | Standalone link back to the service overview. |
| Category menus | Four dropdowns: Library, Editing, Records and System. All twenty existing destinations remain available. |
| Lock Dev, centre | Ends the Dev session and returns to the app home page. |
| Search library | Opens Library Explorer with your query. The current explorer is retained for the next revamp steps. |
| ⏻ Stop app | Opens the same backup-and-stop dialog from either app header. Enter the PIN once; a separate Dev login is unnecessary. |

The page menu supports keyboard navigation, Escape and clicking outside to close.
Backup and upload controls live on their dedicated pages. A restore in progress must finish before changing tools.

## Developer home

| Container | Shows |
| --- | --- |
| Library | Clickable songs, artists, releases (including Singles) and tags open the corresponding tables. |
| Database health | Application/schema version, SQLite integrity and foreign-key errors. Click the title for the compact integrity report. |
| Tag Workshop | Compact card linked directly to the tag bench, with tagged-song and available-tag counts. |
| Catalogue coverage | Untagged songs, missing preview URLs and missing Apple source links. These are stored-data checks, not network playback tests. |
| Stored rounds & votes | Stored vote/round/bracket counts, including prepared rounds where those modes store them, plus songs with all four Vibe positions placed. |
| Git sync | Branch, short commit and cached remote status. Click the title for Git controls; opening Home does not fetch a remote. |
| Local backups | Backup count, newest timestamp and live database file size. Click the title for Database & backups. File size excludes transient SQLite sidecar files. |

Database health, Git sync and Local backups share one aligned row on desktop.
Tag Workshop starts the next row as a card beside coverage and stored activity.
Home has no separate action rows.

## Page lookup

| Group | Pages / purpose |
| --- | --- |
| Library | Library Explorer searches all entity types. Songs, artists, albums and tags provide existing record tables and editing actions. |
| Editing | Apple Music adds/reviews source versions; Tag workbench handles single-song queues and reviewed bulk edits; Bulk edits reviews sources/album placement; Fill missing metadata runs bounded reviewed requests. |
| Records | Match history and corrections; Trivia / Elo maintenance; tournament brackets/podiums; Elo Guesser, Album Shelves and Vibe Map maintenance. |
| System | Overall calculator; Selection health; Database backups/inventory/restore and typed resets; Git & exports. |

Detailed source-request rules: [Apple Music](APPLE_MUSIC.md). Vibe edit/delete/reset:
[Vibe Dev maintenance](VIBE_MAP_DEV.md). Storage and recovery:
[Upgrades](UPGRADES.md). API and configuration: [Technical guide](TECHNICAL_GUIDE.md).

## Stop and recovery

Stop remains available only from localhost on the hosting computer, with the normal
`python main.py` launcher. The PIN is checked freshly and rate-limited; using Stop
does not unlock other Dev tools. A successful preparation drains requests, creates
a rotating local backup and, when selected, uploads the Git snapshot. The visible
receipt waits four seconds before acknowledging shutdown. Cancel keeps the app running.

Backup or Git errors keep the server running. Use **Review in Dev** to inspect them.
For a deliberately restored/wiped local save, use **Git & exports → Keep local
database…**, compare both copies and type `KEEP LOCAL`, then upload normally.
See [split recovery](UPGRADES.md#database-sync-and-split-recovery) before replacing data.

## Git & database sync

Opening Git refreshes the remote and compares its committed SQL snapshot with the
**live database**, not the older local SQL export. Refresh status repeats that
check. The page shows the check time and two independent results:

| Result | Meaning / next step |
| --- | --- |
| Code commits | Branch, target, local/remote commits and incoming/local counts. Incoming code requires a restart/update even when the local database is newer. |
| Database matches | Both logical snapshots match. |
| Local data ready to upload | The live database contains the remote changes plus local changes. Use Upload database backup. |
| Remote data is newer | The remote snapshot contains the local changes plus newer facts. Review before deciding which copy to keep. |
| Copies need review | Both have unmatched edits/deletions, or no shared baseline is proved. Compare the per-table added/removed/edited counts and backups. |
| Not freshly checked | A cached result is displayed. It is not proof of the current remote or live data. Refresh before uploading. |

An **Up to date** code status never means that the databases match. Home explicitly
labels its code summary as cached. Shutdown fetches/rechecks independently; it may
find changes made after the page's last check. Upload rechecks again and still
blocks unsafe overwrites, source conflicts and unpublished code commits. The page
shows per-table deltas when a shared baseline is available. No automatic row merge
or force-push is introduced. **Keep local database…** retains its reviewed, typed
confirmation and two-copy backup flow. For a deliberate local reset/restoration,
review both copies and choose that option before normal upload.

Recent outcomes retain the latest operations in a bounded panel. Detailed sync
ancestry/backup rules are in [Upgrades](UPGRADES.md#database-sync-and-split-recovery)
and the [technical guide](TECHNICAL_GUIDE.md). Both pages link to these guides.

## Database & backups

Create backup makes a verified rotating local copy. Full export downloads the
lossless JSON transport. Find a backup by date/name/purpose; Review restore shows
its counts beside the backup list, with a safety copy before replacement. Advanced
resets retain their existing confirmations.

**What is stored** is a read-only SQLite browser, including extension tables, views
and SQLite's internal sequence table. Select an object or filter the object list:

| Tab | Information |
| --- | --- |
| Rows | Paged stored values, with explicit SQLite types. Select a value to read longer text or binary chunks. Integers are represented exactly as text; NULL remains distinct from empty text. |
| Columns | Names, declared types, not-null flags, default expressions, primary-key order and generated/hidden flags. |
| Definition | The stored CREATE statement, foreign-key definitions and index metadata. |

Rows are 25 per page, capped at 50 and reduced for very wide tables. Cell previews
are bounded; the value viewer pages through 4096 characters/bytes at a time. BLOBs
are base64, not executable content. Refresh reads current rows/counts; changes in
another tab may change page offsets. A changed row invalidates its value review.
Tables with primary keys use key order; keyless tables/views use SQLite's current
result order. Each request uses one read transaction, a read-only connection and
a bounded query time. There is no SQL input, edit, save or delete action.

## Tag workbench

**Single song** is the default on a fresh page. The first matching song is selected
without starting audio. Search matches titles, artists, albums, tags and #IDs; the
artist/album selectors narrow by exact catalogue links. Sort by fewest tags first
(the default), most tags, title, artist or album. Tag count supports **Less than**,
**More than** and **Exactly** a number from zero to eight; these comparisons are
strict, so Less than 1 selects untagged songs.

The song queue shows title, artist, album, local track number, current tags and
Apple-link identity. Select a title to edit/listen. The selected card adds artwork,
store, source ID, known content status/duration, source album differences, links
and source review. Missing previews do not prevent tag editing. Selecting another
song stops the previous preview.

Checkboxes start with the song’s actual tags. Tick/untick the desired complete set
and optionally enter new tag names separated by commas. **Save tags & next** saves
only that song, creates genuinely new names atomically, deselects it and selects
the next eligible song from the pre-save queue order. Existing names are reused.
The eight-tag limit includes new names. Unchanged saves can also advance.

**Skip song →** advances without saving; a dirty draft requires explicit discard.
A session pass avoids revisiting saved/skipped songs; at the end, choose a song or
change filters to start another pass. Filter changes retain a dirty current draft
even if it is outside the new filter; a clean draft follows the new queue.

The preview loops automatically, with a seek/progress line for up to 30 seconds.
Dragging to 15 seconds jumps to the middle. Shorter clips use their actual length;
longer clips loop the first 30 seconds. Playback may need a manual Play click when
the browser blocks automatic starts. Tag choices do not rebuild the audio element.

Single saves use the existing server review/apply contract internally. If tags
changed since the song was opened, **Reload song** is required before continuing.
A failed save does not advance. A confirmed save whose catalogue refresh fails
pauses the queue until reloaded. Retrying an unconfirmed apply uses the same signed
review so a lost reply cannot create duplicate links/tags.

**Bulk edit** uses the same compact filters, bounded song queue and adjacent tag
editor. Select several songs with row checkboxes, Select this page or Select all
matches; the selected cards get amber outlines. The editor retains explicit
Add/Remove/Replace operations and paged Before/After review before Save. Its
preview controls are separate from the selected editing scope. Changing modes
with unsaved choices asks before discarding them. Returning to single mode clears bulk-only hidden filters.
