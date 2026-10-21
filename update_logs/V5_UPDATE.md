# V5 update log

## V5.0.5 — safe cross-computer database sync

21 October 2026 · schema 16 retained.

- Fix the stale-laptop path: normal startup now checks the committed remote
  database after code/schema initialization, including after a manual Git pull.
- Validate SQL candidates, track per-device shared baselines and compare actual
  stored rows, edits, removals, high-water marks and extension objects.
- Archive and transactionally adopt a safe newer remote snapshot. Detect local
  writes during preparation and roll back replacement failures.
- Keep both copies on a split, expose the incoming candidate in backup review
  and block stale/conflicting uploads, including shutdown uploads.
- Report database status separately from code Git status; retain confirmed
  success if only a later local receipt/status write fails.
- Verify the repository snapshot restores all 1,003 songs and every stored value.

See [installation, baseline limits and split recovery](../docs/UPGRADE_V5_0_5.md).

## V5.0.4.3.1 — search collection counts and contained achievements

21 October 2026 · schema 16 unchanged.

- Give album and artist results a separate green song-count line. Keep album
  artist links without repeating the count in their metadata.
- Add a purple proper-album count to artists with qualifying releases, excluding
  Singles and counting each release once across linked songs.
- Bound achievement rows to the card width and one 28 px line, preserving
  whole-badge fitting, priority, the three-badge maximum and resize restoration.
- Update the shared version, README and style rules. Restart and hard-refresh.

Validation: 84 search DOM/fitting checks pass using the real frontend module
and controlled badge measurements at 390/1280 viewport settings. Cover count
pluralisation, Singles exclusion, links, metadata, sorting/query/pagination
retention and long/high-percentage badge fitting at multiple row widths.
JavaScript syntax and diff whitespace checks pass. Browser painting and actual
responsive geometry were not verified.

## V5.0.4.3 — cleaner search cards

21 October 2026 · schema 16 unchanged.

- Remove repeated Song/Album/Artist/Tag badges above search result titles.
- Add a gold attached-tag count below each song’s metadata, including zero
  and singular counts, so lightly tagged songs are easy to spot.
- Space result copy consistently across all four categories and phone layouts.
- Update the README, shared style guidance and asset-cache version.

Validation: 54 search DOM checks pass at 390/1280 viewport settings, plus
JavaScript syntax and diff whitespace checks. Browser painting and measured
responsive geometry were not verified.

Restart and hard-refresh to load the updated search assets.

## V5.0.4.2 — eight tags per song

21 October 2026 · database schema 16.

- Limit each song to eight tags in the song editor and tag workbench, including
  typed names and each song’s final bulk selection. Keep removals available.
- Enforce the policy in server review/save and database insert/update guards.
- Back up and trim existing excess memberships once during migration, keeping
  the earliest eight saved links. Preserve definitions and competition data.
- Add migration, rollback, API and selection-limit regressions and propose eight
  complementary tags based on the current saved catalogue.

See [upgrade notes and tag suggestions](../docs/UPGRADE_V5_0_4_2.md).

## V5.0.4.1 — profile page revamp

20 October 2026 · schema 15 unchanged.

- Restore matching rounded hero artwork/player layers and circular artists.
- Use shared compact mode records across song, artist, album and tag pages;
  move useful breakdowns inline and remove extra explanations and disclosures.
- Keep Overall Mode balance dropdown with figures only.
- Add centred Show more controls after six tag albums and thirty collection
  songs, preserving active previews and complete collection playback queues.
- Add 137 passing profile DOM assertions and update the profile style rules.

See [installation and validation](../docs/UPGRADE_V5_0_4_1.md).

## V5.0.2.1 — storage follow-up

19 October 2026 · cumulative V5 patch, database schema 15.

- Measured the supplied 897,024-byte database and reduced its verified copy to
  573,440 bytes (36.07%). All 517 songs, 155 albums, 67 artists, 54 tags, catalogue
  links, exact URLs and every current source field are preserved.
- Replaced source history with one current source per song. Migration keeps the
  latest row, archives the complete original first and removes nine superseded
  rows in the supplied file. Future relinks update one row; review fingerprints
  still detect changes. The previous-source disclosure is removed.
- Added versioned lossless source compression with plain-JSON compatibility,
  bounded decoding and no extra dependency. The private analysis download exposes
  decoded current observations for readable analysis.
- Repacked small databases with 2 KiB pages. A larger growing database can move
  to 4 KiB pages at startup; optional compaction defers on busy/error conditions.
  Match/correction facts, listening, preview annotations and pending state remain.
- Preserved V3 competition/results; no new competition or V2 retransfer. Generic
  JSON/SQL export, restore and extension verification remain supported.

See [installation and storage review](../docs/UPGRADE_V5_STORAGE.md).

## V5.0.2 — source reads and accurate save feedback

19 October 2026 · schema 14 unchanged; cumulative patch for V5.

- Reproduced a successful source POST followed by a 500 on the dashboard summary:
  fill-only snapshots omit blank optional fields, while the reader required them.
  Source/history projections now accept those snapshots, and preview comparisons
  tolerate missing source previews. Existing observations are read without rewriting.
- Source receipts immediately update the local source cache. The Edit summary
  refreshes in place, including when its read finishes after the form opens;
  unsaved form fields remain untouched. Source detail reads also update the cache.
- A confirmed save remains successful if a subsequent catalogue/summary refresh
  fails. It shows a separate reload notice. Actual rejected saves still show
  errors and keep the review open. Missing preview comparisons are not shown as
  a known mismatch while a refresh is pending.
- Preserved the V5.0.1 import fix and existing database/results. No reimport,
  source relinking, database migration, reset or file removal is required.

Validation: 525 Python tests, 2,052 JavaScript assertions in 18 suites, 38 live
source checks and a restart with all saved sources/results retained. See
[installation](../docs/UPGRADE_V5_0_2.md) and [validation](../docs/VALIDATION.md).

## V5.0.1 — Apple source persistence

19 October 2026 · focused patch for V5.0.0, schema 14 unchanged.

- Fixed the flat-metadata add path that could ignore supplied Apple source fields
  and save an unlinked song. IDs/URLs are now verified against the Apple response
  and saved with the song; client explicitness cannot override the verified fact.
- Empty source offers and explicitly marked Apple imports without identity now
  fail before writing. A source-write failure rolls back the song and its links.
- Add and Source responses return the saved source ID and recording details.
  The Dev client confirms these before showing success; duplicate adds return
  the existing source receipt instead of creating another song.
- Added optional Apple ID/link columns with the existing filters/sorts. Kept them
  off by default, retained Apple content labels, and refreshed source summaries
  after song edits. The version bump refreshes cached scripts.
- Documented source-only repair for songs already added without a link. Existing
  V3 competition results and all current catalogue data are retained. No database
  or schema migration is included in this patch.

See [V5.0.1 installation and repair](../docs/UPGRADE_V5_0_1.md) and
[validation](../docs/VALIDATION.md).

## V5.0.0 — fresh competition and organised application

18 October 2026 · full release based on V4.1.6.

- Added a new V3 competition database, schema 14. First startup snapshots V2,
  transfers exact catalogue metadata/links/IDs and resets all competition results.
  Existing V3 restarts retain new results. Full package includes a catalogue-only
  seed; the upgrade includes no database. Original V2 is left intact.
- Added private-build verification, no-overwrite publication, concurrent-start
  handling and generation-aware SQL/bootstrap recovery. Normal V5 restore refuses
  old V2 archives; complete originals remain available for recovery.
- Preserved K32, independent Blind/Non-blind Elo and full/half first-round policy.
  Later tournament rounds retain points-only influence. Current stats omit old
  Classic-record captions and show fresh empty states without invented rates.
- Refined mean-based catch-up, reduced uniform exploration to 8%, added a bounded
  fading recent-addition bonus and modestly tighter stage-relative opponent
  closeness. No high-K placement or forced spread.
- Added stage-relative health labels, current exposure mean/dispersion, Elo-spread
  reference ranges and live per-pool policy values. Precise probabilities remain.
- Added accepted-decision listening samples for all five modes, one shared browser
  tracker, idempotent bounded server writes, shared stats/profile summaries and
  private analysis export. Mode resets also clear relevant measurements.
- Added a private bad-preview flag/note under Dev Song Actions. It does not appear
  on public pages or automatically remove a song from games.
- Grouped backend modules into storage/modes/reports/developer packages, kept one
  root launcher and canonical schema, combined small schema adapters and removed
  superseded install/fill notes/scripts and old snapshot-based experiment runners. Full obsolete-path list is provided.
- Rewrote the main and technical guides, generated a current field dictionary and
  moved notes into docs/. Historical update logs remain in this folder.

Validation: 511 Python tests; 2,037 JavaScript assertions in 18 suites; 571 live
app checks; 48,000 simulated preference draws. See [validation](../docs/VALIDATION.md)
for exact scope and physical-device limits. Install/recovery are in the
[V5 patch guide](../docs/UPGRADE_V5.md).


## V5.0.3 — source choices and bulk review

- Source selection: five initial results and ten collapsed additional versions.
- Bulk tag editing/filter removed; Tag & preview workbench remains its owner.
- Bulk source review filters missing/linked sources, searches per song or reuses
  an optional album/EP/Single link, and supports choose/next, skip and revisit.
- One atomic, backed-up group save; no automatic matching or metadata refresh.
- Correct misassigned source pairs together, reject stale/conflicting choices
  without partial writes, and retain one current source with stable IDs.
- Schema 15 and all V5 competition data retained. No files deleted.


## V5.0.3.1 — rotating requested backups and controlled stop

- Removed automatic backups from source/tag edits, Singles moves, metadata fills,
  deletes and resets; reviews, validation and atomic writes retained.
- Requested and shutdown backups rotate through three verified atomic slots;
  update archives and existing backups remain separate and untouched.
- Added top-bar Stop app with fresh PIN and reviewed optional Git database upload.
- Drain requests, save local backup, push Git, show receipts for four seconds,
  then acknowledge and gracefully stop the normal single-process launcher.
- Failure, cancellation or missing acknowledgement leaves the app running.
- Schema 15 retained, no competition reset, no files deleted.


## V5.0.3.2 — faster source selection feedback

- Show selected feedback and a marked source-choice button.
- Collapse alternatives, scroll to confirmation and focus the next action.
- Retain the option to reopen choices; no automatic save or queue advance.
- Align bulk filter controls, especially Apple source versus artist/album pickers,
  plus action and optional release-link label spacing.
- Retain schema 15, three-slot requested backup policy and shutdown workflow.
  No files deleted.

## V5.0.3.3 — Apple album imports

- Album-link search opens a track checklist; untick exclusions before saving.
- Reuses verified song imports, reports partial failures and protects saved identities.
- Removes trailing - EP from new local Apple album metadata; retains raw source names.
- Documents Apple adding and requests across developer areas in docs/APPLE_MUSIC.md.
- Schema 15 retained. Python/browser regression suites were not run in this session.

## V5.0.3.3.1 — album Add button fix

- Fix four single-element selectors in the album-save handler to use the shared
  list selector. The previous handler threw before sending any save request.
- Restore checked-track submission, control disabling, confirmation/close on
  success and saved-track exclusion when retrying a partial failure.
- Add browser regression cases for exclusions, empty selection, double activation,
  successful catalogue addition/confirmation/close and partial-failure retry.
- Validation: JavaScript syntax checks and eight focused handler checks passed;
  the same isolated harness reproduced the original pre-request failure.
  Full jsdom/browser and Python suites were not run: execution host unavailable.
- No database or schema changes. Restart and hard-refresh to load V5.0.3.3.1.


## V5.0.4 — developer polish

- Audit the complete Dev backend and all nineteen interface views.
- Consolidate catalogue entity mutations, validation, connection cleanup and
  inventory/backup discovery. Fix the technical-guide download target.
- Extract metadata tasks and record lists from the shared page script; group
  developer assets in a readable include and remove obsolete frontend fallbacks.
- Add tool search, bounded bulk/history/tournament lists, choice-list counts,
  better selection feedback, shared-picker focus/reset handling and one dialog
  error owner. Distinguish saved changes from follow-up refresh failures.
- Retain source/tag review, Git/shutdown and backup safeguards; remove outdated
  Classic-record UI and automatic-backup wording. No schema/scoring changes.
- [Upgrade, per-tool audit and validation limits](../docs/UPGRADE_V5_0_4.md).




