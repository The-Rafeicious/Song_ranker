# Developer guide

**V5.5.0 · Dev workspace**

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

Catalogue tables keep Search, Filters and Columns together. Open Filters, choose
a field and match (contains, exact, blank, filled or a numeric range), then type
or choose a saved value and press Enter. Remove individual filter chips or Clear
filters; Reset order is separate. Columns expands a checklist in the page.
Choose 15/30/60/100 rows, jump to a page, or use Previous/Next above or below the
table. Vertical scrolling belongs to the page; wide tables scroll horizontally.
Each table remembers its session search/order/filter/page-size state; displayed
columns persist locally. Edit opens the inline workspace. More opens record actions
within the screen and supports arrow keys and Escape.

Missing metadata starts with a local blank-field audit. Scan first recovers verified
saved Apple facts, then looks online for remaining dates, disc/track positions,
preview URLs, names/titles, album artwork and genuine artist artwork. Review shows
new values and their evidence before Fill matched blanks. Existing values, local
release placements, song tags and results remain unchanged. Ambiguous identities
or unavailable artist pictures require manual review. An empty release has no
tracks to verify its date. Album import keeps existing matches unchecked and
reports partial success.

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

## Albums, discs and artwork

One album can contain multiple discs. Song **Disc number** defaults to 1;
**Track number** is its position within that disc. Disc 1 track 1 and disc 2
track 1 are different slots. Blanks and gaps in track numbers remain allowed.

To combine existing split discs:

1. In Releases, open the disc-2 record's tracks and choose **Move / combine tracks**.
   This opens Bulk edits with its songs selected and the album-move action ready.
2. Choose the album record/artwork to keep, enter **Destination disc = 2** and
   leave **Clear selected track numbers** unchecked. Apply the move. Conflicting
   disc/track pairs reject the entire change; scores, tags and source links stay.
3. Rename the destination (for example, *Quarter Life Crisis (Deluxe)*) in Releases.
   An empty old album can remain if saved results refer to it; do not delete it
   merely to tidy a historical reference. Saved Shelves results keep their old facts.

For *locket*, tracks 12–14 are bonus tracks on the same disc: move them to the
chosen record with disc 1 if you want one album shelf. Standard and deluxe
editions may also remain separate. Album artwork can be edited independently of
Apple source metadata; choosing another cover does not require another album.
There is no automatic edition/title matching or disc-title parsing.

Album Shelves uses one shelf per album, ordered by disc then track. Disc/track
answers appear only during reveal; their saved values also appear in history.
Imports retain Apple's disc and within-disc track numbers. Missing metadata
reviews show verified disc/track proposals; ambiguous matches still need manual editing.

## Git & database sync

Opening Git refreshes the remote and compares its committed SQL backup with the
**live database**. Refresh status repeats the check; Upload always checks again.
Code ahead/behind and database safety are independent.

| Comparison | Action |
| --- | --- |
| Local and remote hashes match | No duplicate backup commit. |
| Remote hash matches the accepted baseline | Local edits/deletions upload without another choice. |
| Last remote backup was uploaded by this device | Trust the current local database, including intentional resets or restores. |
| Another/unidentified device changed the remote backup | Compare the copies before keeping either one. No automatic database replacement. |
| Invalid/missing previously accepted snapshot | Keep local data and review the remote problem. |

Device numbers start at **1**, then **2**, **3**, and so on when each new
installation first uploads. A random local identity and private host fingerprint keep the number stable;
copying `.git` onto another host creates a different identity. Computer/user names
and credentials are not added to backups. Moving the live
DB to a different configured path counts as a separate installation identity.
The SQL header contains its backup commit time (UTC) and device number.

**Compare databases…** shows the last remote device/time/commit, full local,
remote and accepted-baseline SHA-256 hashes, catalogue/mode counts and changed
records per table. “Only local”, “Only remote” and “Different values” compare
whole rows by identity; schema and ID high-water differences are also included.
Expand the per-table details when counts alone do not explain a difference.

Choose **Keep this device’s local database** and type `KEEP LOCAL`, or **Use the
reviewed remote database** and type `USE REMOTE`. Switching choices clears the
confirmation. Keep local archives both copies and accepts that exact remote as
the baseline, allowing Upload immediately. Use remote takes a safety backup and
transactionally replaces the live database; open game tabs should be reloaded.
Any local/remote change invalidates the choice. Unique work in both copies is
never combined automatically; retain both copies while reconciling deliberately.

Upload builds a SQL-only commit on the freshly fetched remote, so incoming code
and unpublished local code commits do not block a safe database backup. It does
not publish local code/staged files or install incoming code. A concurrent remote
change rejects the upload; Refresh/retry performs a fresh comparison. A failed
push keeps a private pending commit and reuses it when the compared state is
unchanged. Startup code updates still require a safe fast-forward/clean code.
Every app-managed pull compares databases first and rechecks after bootstrap;
it leaves the live database active when another device's data needs review.
Manual terminal Git commands are outside these app checks.

**Compact Git storage** shows Git object sizes and repacks without expiring Git
history, reflogs or recoverable objects. Existing plain SQL safety copies inside
`.git/song_ranker_sync` move to verified `.sql.gz` files under
`database_backups/git_snapshots` beside the configured live DB. New SQL safety
copies use the same compressed location; identical contents are reused. Neither
live databases nor existing database backups are deleted. SQL backups remain
plain text in Git so Git can delta-compress their history. Matching logical hashes
avoid timestamp-only backup commits. New clones can use `git clone --single-branch
--no-tags <repository>` to avoid fetching unrelated branches/tags.

Recent outcomes show the latest operations. Details are in the
[technical guide](TECHNICAL_GUIDE.md#git-database-reconciliation) and
[recovery guide](UPGRADES.md#database-sync-and-split-recovery).

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

## Guide formatting and missing dependencies

Git code updates do not install Python packages. If the Markdown renderer is
unavailable, both in-app guides remain readable as escaped, wrapping plain text
and show the repair command. From the project folder, using the same Python
interpreter that runs Song Ranker, run `python -m pip install -r requirements.txt`,
then restart the app. Plain-text downloads remain available as well.

Album Shelves previews load on play, with no future-track preload. Selecting a
track restarts the ten-second sample rotation from that track. Seeking and
buffering respect the remaining sample time. Normal rotation uses about six new
clips/minute, below the existing shared 18/minute limit; rapid skips may still
reach it. Completed previews reuse the ten-track, ten-minute memory cache.
