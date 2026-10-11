# Song Ranker V3.2.6

This is a patch for V3.2.5.1. Stop the app, copy **all** files in this ZIP's
`Song_ranker` folder over the existing project, then run `python main.py` and
hard-refresh your browser. Keep your own database and backups; neither is in
this ZIP. No extra packages are needed.

The first start backs up schema 6 and adds `genres.description` (schema 7).
Descriptions start blank. This upgrade does not populate track numbers or dates,
reset scores, or add request/audit tables. V3.3 mode ideas remain separate.

## Fill missing metadata

Open **Dev → Editing → Fill missing metadata**. Choose the Apple store, scan,
review the release dates and download the text report. **Back up & fill matched
blanks** applies the verified proposals. You can stop a scan; completed matches
remain reviewable. The last scan lives in memory until another scan or an app
restart, so download the report before then. Download again after applying to
get the filled results rather than the dry-run proposals.

Only these fields can change:

- `songs.track_number`, when blank.
- `albums.release_date`, when blank.

Existing values, names, preview URLs, artwork, artists, tags and scores are
preserved. Real album track positions are used: gaps are valid and never get
renumbered. Album release dates come from the verified Apple collection, not an
individual song's original release date.

Checks include exact title/artist matching after spacing and typography
normalization, the same Apple artwork asset, a unique release and track match,
valid dates and positive track positions, and no occupied or duplicated slots.
Artwork sizing and CDN host differences are ignored; different artwork assets
are rejected. Editions, live versions and remasters are not merged. Multi-disc
positions, custom/non-Apple artwork and uncertain results are left for manual
review. This deliberately prefers blanks to questionable data.

A local name ending ` - Single` gets track 1 without a track-number search, only
when that local release contains exactly one song and the slot is free. Missing
release dates still need a lookup. This also works for an album song deliberately
filed locally as a single: its local album title is preserved, and the report
identifies the actual Apple collection used for the date. Multiple-track singles
are flagged instead of receiving duplicate track 1 positions.

Applying rechecks the scanned library metadata under a database write lock. If
names, artists, album links, artwork, preview links or target values changed,
it refuses the whole apply and asks for a new scan. Voting/trivia can continue
because those scores are not metadata targets. A consistent pre-fill backup is
created in `database_backups/pre_metadata_fill_*.db`. All accepted changes are
committed together; write failures roll back the entire batch.

The text report contains every album's release-date outcome (filled/proposed,
kept or failed), track-number failures only, and a track-success count. It does
not print hundreds of successful song rows. Remote errors, including HTTP 429,
stop further Apple requests and flag unfinished lookups. Local single positions
can still be proposed without network access.

The Dev scan shares V3.2.5.1's cache and request gate: up to 12 upstream calls
per minute, spaced by at least 5 seconds. Album searches are grouped, so songs
in the same album share the lookup. The scan runs in the background; it can take
several minutes. This uses the free iTunes Search/Lookup API without a developer
account or token. Apple documents an approximate 20-call/minute search limit,
subject to change: https://performance-partners.apple.com/search-api

### Standalone program

Alternatively, stop the web app and run this from the project folder:

```bash
python fill_missing_metadata.py --database song_ranker_v2.db
```

This is a read-only dry run and creates a timestamped text report. To fill
verified blanks, with a backup:

```bash
python fill_missing_metadata.py --database song_ranker_v2.db --apply
```

Use `--country us` for a different store, or `--report my_report.txt` for a new
report filename. An existing report is never overwritten and a missing database
is never silently created. The CLI rescans on each run; do not run it alongside
the web app or other metadata scripts, since separate processes have separate
rate gates. Ctrl+C ends it without applying the unfinished plan.

## Dev and tags

- Sidebar groups: Library, Editing, Records and System. Groups collapse; the
  active group opens automatically. On desktop the workspace expands to 1840px
  and keeps the sidebar near the edge. Mobile uses a stacked layout.
- Song editing includes a searchable existing-tag picker with exact stored
  spelling and tag info. Typed/new tags remain available.
- Apple Music adding has an **Extra tags for new songs** picker. Selected extras
  are appended to each added song, alongside the source genre; the keep-results
  setting continues to work.
- Edit **Tags → Edit → Tag info** to describe a tag (up to 2,000 characters).
  The description appears on its public tag page and in Dev's tag table, and
  can be searched in the pickers. Existing descriptions survive name-only API
  edits. Displayed descriptions are escaped plain text.
- Bulk edits keep the existing album moves and add/remove-tag actions. Search
  accepts several words in any order, and exact album/artist/tag filters narrow
  the song list. **Selected only** shows the entire selection across searches.
  Destination albums show their artists, song counts and current track positions
  inline; tags show their descriptions. Existing track-conflict checks remain.
- Column visibility, sorting, per-column filters, truncation and record editors
  remain available on the wider data tables.

## Verification

Automated checks use copies or temporary databases. Matching, false matches,
existing values, occupied slots, deliberate singles, rollback guards, reports,
backups, CLI usage and authenticated endpoints are covered. Interface checks
exercise tag descriptions/selection, bulk filters, metadata review and the
existing voting, trivia, rankings, profile and preview controls with simulated
media. No live Apple batch was applied to the supplied database; live catalogue
availability and browser playback still depend on Apple and your laptop.
