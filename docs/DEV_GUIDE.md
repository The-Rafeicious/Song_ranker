# Developer guide

**V5.3.1 · Dev workspace**

Open **System Access** on the hosting computer and enter the Dev PIN. Use **Home**,
**Library**, **Mode edits**, and **Tools & systems** to move between tasks. Each
section has a landing page and direct links; task pages show the other destinations
in that section. Every task has its own URL, so refresh and bookmarks return to it.
Old `/dev/dashboard?view=...` bookmarks still work.

## Navigation and workspace

| Control | Purpose |
| --- | --- |
| Home | Site health, library counts, cached Git state, latest backup and attention counts; direct links to all tools. |
| Library | Catalogue tables, Tag Workshop, Apple imports, bulk edits and missing metadata. |
| Mode edits | Voting, Trivia/Elo, tournaments, Guesser, Shelves and Vibe data. |
| Tools & systems | Overall, selection, database inspection, backups/restore, Git, resets, duplicates, exports and guides. |
| Guides | This operator guide or the technical reference, with a table of contents and plain-text download. |
| Lock Dev | End the Dev session and return to the main site. |
| Search library | Search every catalogue entity directly. |
| Stop app | Prepare a backup and optionally upload it before acknowledging shutdown. |

Routine editors open beside the task on a wide screen and above it on a phone.
Fields scroll within that editor; Save and Close remain visible. Read-only value
inspection has no Save button. Unsaved catalogue edits and tag choices require an
explicit **Discard & continue** before changing tasks. **Keep editing** preserves
the draft. Active record/catalogue saves, tag/Vibe operations and restores block
task navigation until they finish.

## Developer home

Library totals open the corresponding catalogue tables. Three aligned summaries
show site health, Git/backups and missing catalogue data. Home reads local/cached
Git status; opening Git sync performs a fresh check. Missing preview URLs indicate
stored coverage, not a network/audio playback test. All Library, Mode edits and
Tools destinations are visible below the summaries.

## Library tasks

| Page | Work |
| --- | --- |
| [Search library](/dev/library/search) | Search songs, artists, releases and tags together. |
| [Songs](/dev/library/songs) | Identity, artists, album/track placement, tags, dates, media, source review, preview quality and deletion. |
| [Artists](/dev/library/artists) | Names, artwork and linked records. |
| [Releases](/dev/library/albums) | Album/Single metadata, track inspection and selected imports. |
| [Tags](/dev/library/tags) | Canonical names, descriptions and memberships. |
| [Tag Workshop](/dev/library/tag-workshop) | Single-song queue and reviewed Add/Remove/Replace bulk tagging. |
| [Apple Music](/dev/library/apple-music) | Search, verify and import selected song/album offers. |
| [Bulk edits](/dev/library/bulk-edits) | Review source links or move selected songs to an album. |
| [Missing metadata](/dev/library/metadata) | Scan, review, then apply fill-only proposals. |

Catalogue tables share search, field filters, displayed columns, order and paging.
Filters and Columns expand in the page. Clear filters and Reset order are separate.
Each table remembers its search/order/filter state for the session, and displayed
columns persist locally. Edit opens the inline workspace; More retains record
maintenance actions. No new metadata replaces existing values without a reviewed
choice. Album import keeps existing matches unchecked and reports partial success.

## Mode edits

Voting exposes saved effective results and corrections. Trivia & Elo provides song
recognition maintenance, reviewed manual Elo correction and saved-vote review.
Tournaments retain bracket/match/placement review. Guesser and Shelves retain saved
record editing. Vibe Map places its bounded song queue beside the editor. Four map selectors
show one coordinate group at a time while retaining changes to every map. Save
submits all map values together with sample counts and completed passes; clearing one map resets its compatible pass state. Saved rules and frozen
answers retain their existing server checks. Whole-mode resets are also available
from **Tools & systems → Reviewed resets**, with the original typed confirmations.

## Tools and guides

Database inspector and Backups & restore are separate pages. Use the inspector for
read-only tables/columns/values, and Backups for recovery. Git sync keeps code and
live-database comparisons distinct. Reviewed resets lists the exact available reset
scopes. Duplicate finder shows exact title/artist matches without automatically
merging or deleting songs. Exports offers the lossless full transport and readable
catalogue report. Overall and Selection health keep their existing diagnostics.

The [technical guide](TECHNICAL_GUIDE.md) explains ownership, APIs, storage, recovery
and configuration. Detailed [Apple Music](APPLE_MUSIC.md), [Vibe maintenance](VIBE_MAP_DEV.md)
and [upgrade/recovery](UPGRADES.md) references remain available there.

## Stop and recovery

Stop remains available only from localhost on the hosting computer, with the normal
`python main.py` launcher. The PIN is checked freshly and rate-limited; using Stop
does not unlock other Dev tools. A successful preparation drains requests, creates
a rotating local backup and, when selected, uploads the Git snapshot. The visible
receipt waits four seconds before acknowledging shutdown. Cancel keeps the app running.

Backup or Git errors keep the server running. Use **Review in Dev** to inspect them.
For a deliberately restored/wiped local save, use **Git sync → Keep local
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

## Backups & restore

Create backup makes a verified rotating local copy. Full export downloads the
lossless JSON transport. Find a backup by date/name/purpose; Review restore shows
its counts beside the backup list, with a safety copy before replacement. Reviewed resets has its own Tools page and retains the existing confirmations.

## Database inspector

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

### Catalogue table details

Songs, Artists, Albums and Tags use the same controls. Search matches words across record fields. Filters opens per-field text filters (and the missing Apple source switch for Songs); Clear filters restores all rows. Order selects a field, the arrow reverses direction, and Reset order returns to ascending ID. Column headings also sort; clicking the active heading reverses it. Columns toggles displayed fields and Default restores the compact set. Search, filters and order remain separate for each table during the browser session; displayed columns persist locally. Open a record by its name, use Edit for its metadata, or More for catalogue-specific maintenance and deletion. The pager shows 30 matches at a time.
