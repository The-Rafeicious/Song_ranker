# Historical validation reports

These are step-by-step records, retained without replacing their historical
counts. Use [current validation](VALIDATION.md) for the current release.

# V4.1.5 — Dev, Shelves and first-round preference integration

Cumulative source-only patch over completed V4.0/V4.1, schema 13. The supplied
DB remains unchanged, SHA-256
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Prior reports remain in [validation history](VALIDATION_HISTORY.md).

## Completed checks

- **491 Python tests pass**, including six new first-round integration cases.
  They verify combined event counts, exact origin/Blind/Non-blind breakdowns,
  full/half results, source histories, public/selection exposure, Overall evidence
  for first-round-only tracks and actual Standard/Blind selector inputs.
- Retry saves count once. An ordinary mode correction moves its counts to the
  correct stream; voided tournaments remove their preference evidence/history.
  Later rounds and legacy points-only brackets do not invent Elo vote events.
  Raw ordinary counters remain compatible while combined read projections and
  selection health reflect active first rounds. Reader captures make no writes.
- Existing preferences, rating replay, backups/recovery, metadata, stats, Impact,
  modes and security suites pass. Historical ordinary-only report expectations
  are updated for the user's new combined-results requirement; raw storage
  expectations are retained.
- **1,733 JavaScript assertions pass in all 16 suites**. The 146 new assertions
  use actual modules and controlled media/clocks. Dev cases retain category
  search/artist-column conditions, sort direction, paging and session reload,
  clamp after changed data, clear filters and keep Explorer navigation state.
- At both Standard and Quick speed, Shelf tests check intermediate count-up
  values on the cover, every saved point gain/subtotal, unchanged total until an
  album completes, exactly one subtotal transfer and authoritative final score.
  Computed overlay stacking is above positioned cover image layers. Existing
  reduced-motion/audio/visibility/cancellation gameplay checks still pass.
- Profile tests scope first-round histories to linked tracks, count each event
  once even when both participants belong to the collection, retain source mode
  and influence and include combined track appearances. Primary data remains
  visible; bounded histories use native details.
- **165 live app checks pass** using Waitress/jsdom and disposable copied data:
  all 19 Dev sections, six stats pages, full history and a song history. Real
  local requests/assets complete without script errors. Computed search grids,
  unclipped fields/natural button widths and the source-dialog layout are
  checked. A saved disposable first round appears in history and both of its
  participants contribute to live selection-health counts.
- Updated Python/JavaScript syntax, cumulative ZIP CRC/overlay, documentation
  links and original-DB equality checks pass. No user data, keys, backups, QA
  dependencies or schema changes are packaged.

## Limits and reproduction

DOM/computed-style checks use jsdom and do not render browser paint. Desktop/
phone visual layout and real media/Windows hosting remain installation checks.
No external Apple requests or user Git remote are used; live saves affect only
an isolated QA copy. Stored public Elo, tournament points and Impact formulas
are unchanged; preference statistics/Overall inputs now include round-one Elo.

Install normal requirements and run `python -m unittest discover -s tests`.
Install jsdom as a test-only dependency and run all `tests/test_*.js` with Node.
Use a disposable `SONG_RANKER_DB` for startup/live checks.


# V4.1.4 — proportional Impact validation

Cumulative source-only update over completed V4.0/V4.1. Schema remains 13.
The supplied database is unchanged, SHA-256
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Prior reports remain in [validation history](VALIDATION_HISTORY.md).

## Completed checks

- **485 Python tests pass**, including eight new Impact tests. All prior
  preferences, source/metadata, stats, scoring, selection, security and backup
  regressions pass. API reads are compared with full before/after captures.
- New policy checks cover equal-quality groups of different sizes, focused
  quality versus broad near-average tags, live median calibration as peers grow,
  proper-album calibration excluding Singles, duplicates, empty/invalid ratings
  and unavailable empty collections. Forty cross-language cases compare all
  Python/browser policy fields to nine decimal places.
- Stage simulations cover flat and developed Elo spreads at scales 0, .01, .25,
  1, 4 and 100, with shifted baselines. Impact stays within the library Elo range
  and transforms linearly with the ratings. It has no fixed maximum, percentile
  re-spacing or track-count sum multiplier. This is a breadth factor, not a
  statistical uncertainty estimate.
- **1,587 JavaScript assertions pass across all 15 suites**, including twenty-two
  new assertions against the actual site rebuild and its consumers. Cases check
  new ranking order, no broad-tag inflation, duplicate links, live priors, decimal
  display, main-board/home/profile agreement, empty record access with no rank,
  flat collections and unchanged song ratings.
- Read-only analysis of the supplied 507-song snapshot gives artist Impact
  range 1181.25–1222.12, proper albums 1180.32–1213.53 and tags 1187.76–1214.53.
  Previously tags ranged 434.97–2011.70. The typical peer sizes are 2, 6 and 9.5
  tracks respectively; the baseline is 1200. Snapshot examples: pop 1203.17,
  catchy 1210.90, chorus 1214.53. Live databases use their own current values.
- **148 live integration checks pass** using Waitress, jsdom and a disposable copy: the three main
  boards' top twenty scores/order agree with server projections; home artist/
  album shelves, three entity profiles and tag search agree on displayed values.
  Local requests/assets complete with no script errors. This is endpoint/DOM
  verification, not rendered browser paint.
- Updated Python/JavaScript syntax, ZIP CRC, documentation links and cumulative
  overlays from V4.0/all previous V4.1 patches pass. The package contains source
  and notes only, without user data, secrets, backups or QA dependencies.

## Reproduce and limits

Run `python -m unittest discover -s tests`; install jsdom as a test-only dependency
and run each `tests/test_*.js`. Read-only real-data comparison:

```sh
python tools/validate_v414_impact.py --database PATH_TO_DB
```

Use a disposable `SONG_RANKER_DB` for startup/live checks. No user database,
external service or remote Git repository is modified. Browser paint, physical
phone/audio and Windows hosting remain installation checks. Public song Elo,
Overall and mode scoring/selection are outside this calculation-only change.


# V4.1.3 — expanded missing-metadata validation

Cumulative source-only patch over the completed V4 app, including all prior
V4.1 changes. Schema remains 13. Tests use disposable databases and mocked Apple
responses. The supplied DB remains byte-identical, SHA-256
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Prior reports remain in [validation history](VALIDATION_HISTORY.md).

## Completed checks

- **477 Python tests pass** with full test discovery, including twelve new
  metadata cases. All existing schema, source/import, stats, selection, scoring,
  security, backup/recovery and game tests continue to pass.
- Exact song dates come from matched tracks independently of the collection's
  album date. Dry-run scanning makes no writes or backup. Source identities,
  links, duration and disc/source-track facts are proposed with the new dates.
- Full pre-write backup captures equal the original database capture. Only the
  allowed song/album fields and source observations change; every other table
  and protected column is compared. Local art, preview URLs, album/artist/tag
  links and game/rating facts remain equal. Existing dates, positions, known
  flags and advisory source URLs are preserved. Prior source rows stay intact.
- Repeated scans apply no changes or additional backup. Stale date/source edits
  reject apply. A simulated second-source failure rolls back all dates, positions
  and source writes, retaining an exact pre-write recovery backup.
- Tests cover both directions of removed Single/EP suffixes, retained Deluxe
  text, wrong artist/art, ambiguous releases and conflicting saved identities.
  Multi-disc metadata can fill dates/source facts while local positions remain
  unresolved. Explicit, Cleaned and default Not explicit displays are checked.
- Authenticated scan status, new-field counts, apply/reapply refusal and text
  reports are tested through actual Flask endpoints. Full source plans remain
  server-side. No external Apple request or live user metadata fill is performed.
- **1,565 JavaScript assertions pass in all 14 suites**. The seventeen new cases
  use the actual metadata UI closure and cover new-field-only Apply enablement,
  exact dates, escaped names, collapsed review groups, unresolved counts, one
  token-only save, report link, refreshed source summaries, failed-save retry
  and disabled no-op plans. Prior gameplay/audio/stats/Dev suites pass unchanged.
- Updated Python/JavaScript syntax and cumulative ZIP CRC/overlay/document-link
  checks pass. Install overlays from completed V4.0 or any prior V4.1 patch reach
  the current sources; no data, keys, backups or QA dependencies are included.

## Limits and reproduction

Apple responses are deterministic fixtures; upstream search/store availability
and real returned matches were not exercised. Ambiguous/unverified entries stay
blank and are reported for review. Browser DOM checks use jsdom rather than
rendered browser paint; this patch retains the existing layout and controls.

Install normal requirements, then run `python -m unittest discover -s tests`.
Install jsdom as a test-only dependency and run each `tests/test_*.js` with Node.
Always use a disposable `SONG_RANKER_DB` for startup experiments. Existing V4.1.2
live integration evidence is retained in the historical report.


# V4.1.2 — stats, Elo history and selection-health validation

Cumulative source-only patch over the completed V4 app, including V4.1.0/.1.
Schema remains 13. Tests use disposable/copied data. The supplied DB SHA-256 is
unchanged: `d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Previous reports remain in [validation history](VALIDATION_HISTORY.md).

## Completed checks

- **465 Python tests pass** via full discovery. This covers all existing
  preference/correction/replay, split Elo, tournament, challenge, selection,
  grading, stats, Dev, recovery/export and security suites, plus eight focused
  v4.1.2 reporting/diagnostic cases.
- New checks cover saved tournament before/after Elo, retry deduplication,
  full/half influence and Blind/Non-blind filtering, clamped pagination,
  corrected/voided events, separate collection history feeds and unchanged
  ordinary vote totals. Global/Voting reports retain their ordinary denominators.
- Read-only selector snapshots match the production exposure formula, normalize
  active weights, relax previous-pair exclusions in tiny pools, mark unavailable
  pools, retain eligibility counts and never create runs/questions. The new
  endpoint enforces local admin access, excludes private owner/tokens and uses
  no-store caching. Existing fixed SELECT-count checks include the new reports.
- UTC trend tests cover both date boundaries, zero dates, invalid/undated/future
  times, incomplete results, equal/missing-rating denominators and pooled field
  accuracy rather than averages of daily percentages. Existing Shelf grading
  and dashboard tests exercise the shared track-order denominator.
- **1,548 JavaScript assertions pass across all 13 suites**: Developer Catalogue
  121, Controls 30, System 88, Tags 111, Gameplay 307, V4.1.1 Gameplay 48,
  Mode Rankings 347, Overall 96, Preference Admin 29, Profiles 99, Round Flow 63,
  Search 80 and V4.1.2 Stats 29. These use actual modules with controlled media,
  clocks and network fixtures under jsdom.
- New DOM cases cover combined embedded history beyond the first 50 matches,
  mode/source intersections before limits, saved fractional deltas, tournament
  links/weights/replay notes, escaped names, empty states and accessible filters.
  The health inspector covers paging/search/focus, unknown coverage, exact
  weight labels, album links, error/retry and stale refresh/navigation responses.
- **149 live app integration checks pass** with Waitress and a disposable copy
  of the supplied data: all 19 Dev sections, all six stats dashboards, filtered
  public history and a song embed. A disposable first-round result is saved and
  appears in both history displays. Real local endpoint/assets, no script/request
  errors, exact 14-day tables/plots, current values and baseline-last CSS order
  are checked. No user data, external Apple service or Git remote is modified.
- Python compile and JavaScript syntax checks pass. The cumulative ZIP passes
  CRC, documentation-link and overlay checks against V4.0 and both earlier V4.1
  patches. It contains edited/new source files and notes only, with no data,
  private key, backup, QA environment or runtime dependency changes.

## Limits

Live integration here checks endpoints and DOM behaviour using jsdom; it does
not render browser paint or prove pixel layout. Responsive CSS was reviewed,
but actual desktop/phone layout, real preview/background media and Windows
hosting remain installation checks. Existing media tests use controlled players.

The new health page reports current URL presence and runtime eligibility, not
upstream preview availability. Pair/entry/album shares are labelled for their
actual draw stage; frozen pending questions remain unchanged.

## Reproduce

Install normal requirements and run `python -m unittest discover -s tests`.
Install jsdom as a test-only dependency and run each `tests/test_*.js` with Node.
Use an isolated `SONG_RANKER_DB` for any startup/live test. QA dependencies,
temporary databases and live-test scripts are excluded from the distribution.


# V4.1.1 — mode presentation and preview validation

Source-only gameplay update over the completed V4 app. Schema remains 13.
The cumulative V4.1 patch retains V4.1.0 Dev changes. All database checks use
isolated/copied data. The supplied DB SHA-256 remains
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Previous reports remain in [validation history](VALIDATION_HISTORY.md).

## Completed checks

- **99 Python tests pass**: independent/split Elo and tournament persistence,
  challenge rules, final-release offer/game entry points and existing game/preview
  endpoint regressions (`test_split_elo`, `test_challenges`, `test_final_release`,
  `test_patch_v3342`, `test_patch_v33421`). The new receipt test checks full/half
  scopes, Blind/Non-blind mode, exact before/after values and stable retries
  after another vote changes current ratings. Later/bronze/legacy results expose
  no invented Elo receipt. Existing rollback/concurrent retry checks pass.
- **628 JavaScript assertions pass**: Gameplay 307, Round Flow 63, V4.1.1 Gameplay
  48, Tag Workbench 111 and Profiles 99, with actual modules under jsdom and
  deterministic media/network/clocks.
- New gameplay cases cover ordered points → Elo at both speeds, unchanged
  later/bronze/legacy pacing, saved fractional values, matching countdown length,
  one save, blind anonymity, uninterrupted audio at the stage boundary, manual
  pause retention and cancellation of pending stages by manual Next.
- Actual voting/tournament page closures retain playing audio across visibility
  changes. Podium previews keep advancing, workbench playback continues, and
  manual pauses survive return. A mid-result fade waits while hidden. Trivia
  audio and clock continue together, explicit Pause works, hidden expiry finishes
  once, no hidden next round starts, and closing settings does not pause Trivia.
- All five game templates load with one settings disclosure in navbar controls,
  one pacing module and current cache version. Updated scripts/CSS load; public
  home/rankings/stats exclude game settings/pacing. Node syntax and Python compile
  checks pass. The patch is CRC/hash checked and its overlay matches the intended
  source files while preserving the supplied DB byte for byte.

## Limits

These are endpoint, DOM and controlled-media tests. Browser paint, actual media
playback/background policies, physical phones and Windows hosting were not
verified here. Browser/OS suspension can still stop background media. No live
Apple request or user Git remote was used. No scoring formula, selector,
K factor, grade, database schema or runtime dependency was changed.

## Reproduce

Run the five named Python suites together after importing them, or run the full
`python -m unittest discover -s tests`. Install jsdom as a test-only dependency
and run `tests/test_gameplay.js`, `tests/test_round_flow.js`,
`tests/test_gameplay_v411.js`, `tests/test_dev_tags.js` and
`tests/test_profiles.js` with Node. Use an isolated `SONG_RANKER_DB` for startup
checks. QA dependencies, temporary DBs, browser binaries and generated reports
are excluded from the distribution.


# V4.1.0 — developer dashboard validation

UI-only update over V4.0.0, database schema 13. All data tests use isolated or
copied databases. The supplied database SHA-256 remains
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
No schema, game score, selection algorithm or data API changes are included.
Previous full-release results are retained in
[validation history](VALIDATION_HISTORY.md).

## Checks completed

- **91 Python tests pass** across Developer System, Tag Workbench, Catalogue
  Sources and final-release game-page/offer smoke tests. Load these suites
  together so Flask's registered routes are imported before the first request.
- **378 JavaScript assertions pass:** Developer Catalogue 121, Tag Workbench
  110, Developer System 88, Preference Admin 29 and new Developer Controls 30.
- The new controls suite exercises native form values, pointer and keyboard
  selection, accent-insensitive search, escaped labels, no matches, clearing,
  focus return, Escape, disabled controls, removed/recreated controls and editor
  dialog placement. Short lists retain their native select.
- **81 live integration checks pass** with actual app scripts under jsdom and
  a real local Waitress server on a copied 507-song database. All 18 developer
  sections load and their page/API requests succeed. Checks cover record
  editors, every grouped song action, source review, actual artist filtering,
  active-filter counts/reset, bulk pickers, list/editor order and absence of
  developer scripts from the public home page.
- All edited JavaScript parses. The patch is compared by file hashes with the
  original archive, CRC checked and overlaid on a fresh copy. The source DB is
  unchanged. Only changed/new source, tests and documentation ship.

## Practical limits

There is no successful browser-paint, physical-phone or Windows-host test in
this environment. Chromium could not start here. DOM checks and scoped
responsive CSS are not pixel-layout evidence. Actual Apple network lookups,
remote Git operations and real audio playback are outside this UI patch's QA.
Try the dashboard on your installation after restarting and hard-refreshing.

## Reproduce targeted regressions

Install the ordinary runtime requirements and make jsdom available to Node.
Run `node tests/test_dev_controls.js`, `node tests/test_dev_catalog.js`,
`node tests/test_dev_tags.js`, `node tests/test_dev_system.js` and
`node tests/test_preference_admin.js`. For the Python selection, use a loader
that imports all four suites before running them:

```python
import sys, unittest
sys.path.insert(0, 'tests')
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in (
    'test_dev_system', 'test_tag_workbench', 'test_catalog_sources',
    'test_final_release'))
assert unittest.TextTestRunner().run(suite).wasSuccessful()
```

Use an isolated `SONG_RANKER_DB` for app startup checks. Test dependencies,
transient servers/databases, browser binaries and QA reports are not bundled.


# V4.0.0 — final validation

**All eight implementation steps complete · schema 13.** Tests use isolated or
copied databases; the supplied and working-source DB remain byte-for-byte
unchanged. Full-app data is the untouched original snapshot, not a QA playthrough.
Earlier step reports are preserved in [validation history](VALIDATION_HISTORY.md).

## Automated regressions

**456 Python tests pass.** Coverage includes schema 8–13 migration/startup,
complete typed export/rebuild/SQL round trips, extension objects/implicit row IDs/
BLOBs/exact floats/high-water marks, restore verification/rollback/concurrency,
host/origin/login safeguards, all mode grades/statistics/selection, frozen
challenge rules, persisted offers/retry receipts/corrections, independent Elo,
source/Single/tag operations, and dashboard/review/download APIs.

Twenty-nine Git cases run actual disposable repositories/local bare remotes:
SQL-only commits preserving unrelated staging; failed hooks/pushes/lost replies;
retry/no duplicate; incoming/behind/diverged/conflict states; changed/ambiguous
credentials-redacted targets; missing Git/network/deadlines/OS lock; pre-update
backups, protected files, dirty SQL archive/rollback; bytecode removal and actual
CLI re-execution before loading updated modules. No real user remote is touched.

The five final-release endpoint cases confirm game-only pacing assets and that
prepared ordinary/Guesser/Trivia/Shelf questions resume exactly, add no completed
exposure, retain the saved streak, do not start Trivia's clock and reuse the
pending Shelf token without a fresh discard.

**1,338 JavaScript assertions pass** with actual scripts under jsdom, controlled
clocks and HTTP/native-media mocks:

| Suite | Assertions |
| --- | ---: |
| Gameplay | 307 |
| Round flow / final pacing | 61 |
| Mode Rankings | 347 |
| Overall | 96 |
| Profiles | 99 |
| Search | 80 |
| Preference Admin | 29 |
| Developer Catalogue | 121 |
| Tag Workbench | 110 |
| Developer System | 88 |

Pacing checks cover browser persistence/default/corrupt settings, one prepared
slot, token reuse, no duplicate draw, superseded response/abort, TTL, disabled/
hidden/Save Data/2G/offline behaviour, network deadline/fallback, suspended timer
remaining duration, navigation/return, failed save, slow next keeping results,
Quick progression across all modes, blind-bracket anonymity, per-album score
transfers and unchanged Trivia answer time. Existing grade, reveal, preview,
retry, workbench and responsive DOM contracts remain covered.

## Supplied-data and distribution checks

- The 507-song source copy upgrades to schema 13 with **427 original preference
  events and classic Trivia best 221** retained. Original source/working DB
  SHA-256 stays `d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
- Inventory is read-only, with all 25 tables/five views exposed and extension
  labels preserved. Full JSON export/rebuild, binary backup download and
  schema-8 reviewed restore reconcile all stored facts/view results/IDs. New
  activity after review is rejected; a new review restores exactly.
- Full 507-song SQL upload/restoration through a local bare Git remote retains
  every stored cell, hidden row ID, view/sequence and unrelated staged code.
  Repeating unchanged data makes no extra commit. Pending ordinary, Trivia and
  Guesser questions recover after data transport and restoration.
- Both ZIPs are CRC/hash checked. Their source/data overlay is compared against
  the original 106 supplied files and explicit manifest entries. A clean
  V3.4.13 cumulative upgrade and the complete-app extraction reach schema 13.
  All game/public entry points and Dev assets/downloads load. Actual mocked
  Apple source/Single/tag edits save once and survive a fresh process; pending
  challenge progress and signed reviewed recovery survive that restart too.
- A real local Waitress process serves the unpacked completed app over loopback.
  HTTP pages/assets and persisted next-offer/retry behaviour pass across an
  actual server stop/restart with the same browser cookie/key. This process
  uses only disposable data, with private hosting settings and no user remote.
- Documentation checks cover internal file links, current version/step status,
  all canonical stored-column names, schema object counts and package exclusions.
  Public pages do not load Dev/pacing modules unnecessarily.

The completed-app package intentionally includes the original supplied database;
the upgrade package includes no DB/data dump/key/backup. Runtime caches, temporary
repositories/databases, generated QA reports and optional dependencies ship in neither.

## Environment and practical limits

Python 3.12, SQLite 3.53, Flask 3.1, Waitress 3.0 and Git 2.51 on the Linux test
host, with Node/jsdom for browser logic. No live Apple lookup, actual media,
rendered browser/phone or Windows host was tested. DOM viewport/CSS checks are
not pixel layout or autoplay evidence. A final installation play-test should
exercise each mode, Quick/Standard, previews/volume, phone navigation and Dev
backup/export with the user's host/browser. Automatic hidden-tab Trivia pause
also depends on the server connection succeeding.

Selectors, K32, grading and points did not change in the final step. The accepted
step-5/6 simulation evidence remains documented in the
[offline experiment kit](../tools/selection_lab/README.md); it is not claimed rerun
by unrelated UI tests. Full field/recovery limits are in
[docs/DATABASE.md](DATABASE.md), with code/contracts in the
[technical guide](TECHNICAL_GUIDE.md).

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python db_tools.py audit --db song_ranker_v2.db
```

Use an isolated `SONG_RANKER_DB` when importing the app for QA. Run each
`tests/test_*.js` file with Node and jsdom available. Test dependencies are not
runtime requirements. Never run experimental bootstrap/recovery against the live
DB; maintenance CLI output files must have new names.


# V4.0.0.2 — step 2 validation

Cumulative over V3.4.13 and the step-1 foundation. All writes use isolated or
copied databases. The supplied and working-source database remain byte-for-byte
unchanged. No database, SQL data dump, backup, private key or test dependency is
included in the patch.

- **226 Python tests pass**: the previous 201 plus 25 preference tests. New
  cases cover persisted/resumed offers, owner binding, server-owned mode/pair/
  rules, unoffered/malformed submissions, identical receipt retries, later
  metadata edits, transactional failure/rollback, eight simultaneous retries,
  simultaneous opposite choices and concurrent offer creation.
- Corrections cover void/restore/replacement, mode changes without double counts,
  replay of subsequent votes, preservation of original snapshots, stale revision/
  fingerprint rejection, repeat correction keys, manual rating override order/
  retry protection, preference reset and event-ID high-water marks. Song removal
  retains offer order and corrected identities even after both songs are removed.
- Frozen Guesser grading remains unchanged after preference corrections. Mode
  exposure tests distinguish pending/completed questions, bracket entries and
  saved shelf-album membership. Current-schema exports/rebuilds retain pending
  offers, corrections, overrides and original retry receipts.
- **711 JavaScript assertions pass**: 178 gameplay (including persisted tokens
  and lost-response recovery), 26 Dev correction-controller assertions, 80 profile,
  80 Search and 347 mode-ranking checks. Dev cases include pagination, active/
  voided records, restore, double activation, request keys/revisions, stale-error
  handling, escaped long names/notes, protected legacy anchors and empty states.
  Scoped CSS has wrapping controls, one-column phone fields, 44 px actions and
  16 px inputs. These are DOM/static responsive checks, not a browser paint test.

## Supplied database and cumulative upgrade

The 507-song / 427-vote snapshot passes both **schema 8 → 10 directly** and
**schema 9 → 10**. Every original vote ID and all nine original stored cells
remain intact in preference_events. No historical offer or mode is invented.
All other stored facts/high-water marks reconcile. The complete original
collection projection/Overall inputs and actual Guesser/Shelves grading are
identical after upgrade; new exposure fields are checked separately.

The supplied baseline is verified_replay, with a zero cutoff. A separate
schema-9 fixture with an unrecorded old Elo change uses a truthful legacy anchor,
retains that value, protects old edits and still permits replayable new votes.
Existing classic peak/Trivia records are retained. Repeated startup leaves the
migrated file byte-for-byte unchanged.

**28 populated read-only page/API routes return HTTP 200.** Dev preferences and
record-detail APIs also pass. Dev controller/styles load only on Dev. On the
copied full snapshot, a new vote plus repeated retries creates one event; void
returns the original complete public projection exactly, restore/replacement
retains one active event, and every public song count matches shared exposure.
Original quiz grades remain unchanged throughout. Export/rebuild after these
operations reconciles all source facts, projections, offers and view results.

Original snapshot facts retained: 507 songs, 65 artists, 151 releases, 54 tags,
522 artist links, 1023 tag links, 427 ordinary preferences, 289 Trivia rounds,
8 tournaments/144 entries/144 matches, 43 Guesser rounds and 43 Shelves rounds/
430 saved items. These totals are evidence for the attached snapshot, not
hardcoded migration requirements.

## Environment and limits

Python 3.12.14 / SQLite 3.53.1 / Flask 3.1.3 / Waitress 3.0.2, with Node/jsdom
for UI logic. A headless Chromium executable was unavailable and its download
failed; no rendered browser/phone layout or real audio check is claimed. Final
on-device play/paint/audio checks remain a V4 release gate. Multi-process manual
recovery remains intentionally offline. No real Git remote was accessed.

Reproduce after normal project requirements are installed:

```bash
python -m unittest discover -s tests -v
python db_tools.py audit --db song_ranker_v2.db
```

JavaScript QA additionally uses jsdom (test dependency only): run the five
`tests/test_*.js` files. Exact schema/field/reference and recovery rules live in
[docs/DATABASE.md](DATABASE.md). Earlier validation below is historical.

---

# V4.0.0.1 — database foundation validation

All database writes for this release use temporary/copied databases. The
supplied V3.4.13 database and working-source database remain byte-for-byte
unchanged. The patch contains no database, SQL dump, backup or private key.

- **201 Python tests pass: 175 existing and 26 new foundation tests.** These
  cover transactional migration/rollback, exact value/row-ID/view reconciliation,
  deleted-ID sequences, pending rounds, actual Trivia/Guesser/Shelves grading,
  extension tables/indexes/views/triggers/BLOBs, unsupported/generated columns,
  future schemas, flat databases, invalid SQL and broken references, existing
  database precedence, output collision refusal, export checksums, committed WAL
  data, live restore rollback, Dev authentication/inventory, multi-process
  restore refusal and local maintenance concurrency/timeouts.
- Startup tests check script ordering (pull → bootstrap → serve) and WSGI
  ordering (bootstrap without Git/server startup).
- The supplied 507-song database was copied, upgraded 8 → 9, exported, rebuilt
  into a new compact file and recovered from its pre-upgrade backup. Every
  stored value/row ID, view result and available sequence high-water mark
  reconciled. The complete collection projection, including Overall inputs,
  and actual Guesser/Shelves grading summaries were identical before/after.
  Repeated startup left the upgraded file byte-for-byte unchanged.
- **28 populated read-only page/API routes returned HTTP 200**, including all
  game pages, reporting/ranking pages, entity profiles and collection/Overall
  JSON routes. They left the copied database facts unchanged.
- Fresh creation and SQL restoration without Git passed. Corrupt SQL, attached
  database SQL, bad references and newer schema markers cannot publish an empty
  replacement database. A concurrent write during upgrade preparation aborts
  the upgrade without losing that write.

Snapshot totals preserved (not hardcoded migration requirements):

| Stored data | Rows |
| --- | ---: |
| Songs / artists / releases / tags | 507 / 65 / 151 / 54 |
| Artist links / tag links | 522 / 1023 |
| Ordinary vote history | 427 |
| Trivia rounds, including pending | 289 |
| Tournaments / entries / matches | 8 / 144 / 144 |
| Elo Guesser rounds | 43 |
| Shelves rounds / saved items | 43 / 430 |
| Global record/rules values / manual Trivia adjustment rows | 3 / 0 |

Runtime: Python 3.12.14, SQLite 3.53.1, Flask 3.1.3 and Waitress 3.0.2 on the
Linux test host. No templates, CSS, JavaScript, selection algorithms, game
points, public Elo rules or dependency requirements are changed by this patch.
Browser/phone/audio interaction and a Windows-hosted process were not exercised;
this step's rendering checks use Flask clients. Existing security tests pass.
Multi-process recovery is intentionally offline, not protected by the local
single-process gate. No real Git remote was pulled, pushed or committed.

Reproduce backend checks after installing the normal project requirements:

```bash
python -m unittest discover -s tests -v
python db_tools.py audit --db song_ranker_v2.db
```

The full column dictionary, exact transport/recovery commands and upgrade/rollback
instructions are in [docs/DATABASE.md](DATABASE.md). The previous release
checks below are historical; their DOM assertion counts were not rerun here.

---

# V3.4.8 validation

All test writes use copied or isolated in-memory databases. The supplied and
working source databases remain byte-for-byte unchanged.

- **147 project tests pass**, including **27 new Shelves reporting tests**.
  Coverage includes shared-grader agreement, gapped track numbers, correct
  album versus ordering errors, misplaced counterparts, genuine zero results,
  singleton denominators, complete history beyond thirty rounds, paging/deep
  links, pending/token exclusion, rolling windows/future dates, perfect streaks,
  pooled comparison rates, frozen facts after catalogue changes, deleted
  identities, duplicate collaborators/tags, actual round feasibility, metadata
  eligibility, every played album's pagination, practice eligibility,
  incomplete/unsupported data, escaping, read-only queries and connection cleanup.
  The previous mode-report and LAN-security tests remain in the passing suite.
- **36,875 DOM/data/responsive assertions pass** across populated, empty,
  long-name, legacy and paginated states at **1200/1100/1050/844/760/700/600/
  430/390/360/320 px**. These cover all twelve full-row sections, shared type/
  corners/padding, aubergine glows, mauve page tone, joined dividers, primary
  ordering rates, semantic entity/outcome colours, six equal art constraints,
  artist circles, bounded/unknown accessible bars, ellipses/full text, 44 px
  action/detail targets, title/format/shelf stacking, native expansions,
  optional placement, album pagination and selected older round history.
- **1,584 style properties match V3.4.7** across Elo Guesser, Recognisability,
  Tournament and Home at 1200/390/320 px. Displayed data/text and entity links
  match too. Every retained shared mode CSS rule/declaration is unchanged;
  cleanup removes only 53 obsolete stats-only selectors and their retired
  baseline selector. New page rules are scoped to the Shelves dashboard.
- **124 controlled audio/controller assertions pass**, including pair warmup,
  cache cleanup, readiness-gated fades, rapid switches, podium/album/artist
  queues, Shelves reveals and Trivia handoffs. No new player, preview fetch or
  cache behavior was added to the stats page.
- **15 seeded picker comparisons match V3.4.7** for automatic/two-/three-album
  requests after extracting the existing eligibility query. Its conditions and
  random selection behavior are preserved.
- **44 PC/simulated-phone page/API/asset reads return HTTP 200**, including
  both paginated lists, malformed/out-of-range queries, selected/missing rounds,
  other dashboards, rankings and new/shared assets. These reads leave the QA
  database unchanged. A separate allowed-phone round creation/answer/report
  flow completes correctly at **30/30**, opens its saved round and retains
  the phone's Dev-access denial. All templates and seven JavaScript files parse.
- An independent saved-fact calculation reconciles the supplied snapshot to
  **32 completed rounds, 320 track appearances, 48 played albums, 782/1018
  correct ordering comparisons, 763.63/955 available points**. Current feasible
  coverage has **50 albums / 400 tracks**. The 955-point denominator correctly
  retains older singleton shelves instead of assuming 32 × 30 points.
- The report performs **nine SELECTs in one caller-owned snapshot**. Totals
  use all completed history; only displayed album/history lists are paginated.
  No schema, stored counter, scoring, Overall, ranking API, preview or hosting
  policy change is included. Requirements are unchanged.

Responsive checks use jsdom with viewport media rules selected and known
shared/page CSS tokens expanded where variable support is incomplete. They
check DOM, computed styles and disclosure interactions, not native paint/layout.
Native Chromium exits before startup in this runtime; exact painted wrapping,
shadows and screenshots could not be verified. No physical phone, Safari/
Android audio, firewall/Wi-Fi path or upstream media playback was tested.

Apply edited/new files over **V3.4.7**, restart and hard-refresh computer/phone
browsers. Keep the database, backups and private instance key. Grouped V3.4.8
notes/data definitions are in `update_logs/V3_4_UPDATE.md`; the accepted layout
reference is in `README_PAGE_STYLE.md`.


## V3.4.9

- `node tests/test_mode_rankings.js`: 215 assertions passed. Exercises all four
  special boards across Songs/Artists/Albums and both ranges, 20-row limits,
  proper-album filtering, primary metric normalisation, click handling, shared
  metadata delegation, Overall's four categories, sparse records and empty data.
- Existing Python suite: 147 tests passed with isolated fixtures. No production
  game/scoring/backend changes are included.
- Flask smoke checks: all five ranking routes return 200 and load the shared
  ranking/baseline CSS. Collection and Overall APIs return real JSON successfully
  using a copied database.
- JavaScript syntax checks passed for ui.js, site.js, special_modes.js and
  overall.js. Reviewed shared responsive grid/type/art constraints and added
  mode-scoped context/score wrapping and wrapping 44px category links.
- Native browser paint, actual viewport overflow and physical phone interaction
  were not verified: the browser executable is unavailable. Responsive rules were
  reviewed, not claimed as on-device or screenshot-tested.
- Packaged only changed/new files. Supplied database bytes match the input ZIP.


## V3.4.9.1

- 347 Node ranking assertions passed, now including all four categories for
  every special board, tag point pooling and points-based top/bottom order.
- Existing 147 Python tests passed; both edited JavaScript files pass syntax checks.
- Active category colours are provided by the shared navigation renderer and
  scoped glow rules. Existing wrapping/44px category targets remain intact.
- Native browser/physical-phone visuals remain unverified.
- Database bytes remain identical to the supplied V3.4.8 archive; no database
  or scoring/backend files are in this patch.


## V3.4.10

- `node tests/test_search.js`: 50 assertions passed for achievement thresholds,
  sample minimums, pooled rates, podium priority, whole-badge fitting at narrow
  and wide widths, restoration/max-three behavior, forty-card pagination,
  all four card categories, escaping, proper-album exclusion, tag scope/deep
  links, name/rating sort, clear-tag behavior, keyboard submit and empty states.
- Existing `test_mode_rankings.js`: 347 assertions passed. Existing Python suite:
  147 tests passed. Edited/new JavaScript files pass syntax checks.
- Flask checks: Search, Search deep links, Recognisability rankings, standard
  rankings and Home return 200; search.js/search.css are scoped to Search.
  Header HTML and the catalogue matching function match the supplied baseline.
- Reviewed card-grid responsive rules, cover constraints, wrapping scores,
  ellipses, category controls, focus styles and the single-row badge fitter.
  Search CSS braces balance. Removed obsolete search-only list/badge rules.
- Native browser paint, actual DOM viewport overflow and physical-phone visuals
  remain unverified because no browser executable is available. Width-fitting
  tests use explicit badge-width fixtures, not native rendered font measurements.
- Database bytes match the supplied V3.4.8 ZIP. Game, scoring, audio and security
  files are unchanged. Delivery contains only changed/new files.


## V3.4.10.1

- 62 Search assertions passed: >=90% badge boundaries, minimum samples,
  pooled results, stable shuffled pagination with all 50 fixture IDs once,
  category round trips, query-triggered rating sort, empty-query Random reset,
  explicit URL sorts, dropdown synchronisation, result-count placement and the
  existing badge/card/filter/sort behavior. Shuffle tests use a fixed random
  source for reproducible expectations, not assertions about a chance outcome.
- 347 ranking assertions and the existing 147 Python tests passed.
- search.js syntax check passed. Reviewed native select focus/touch styling and
  three-column / two-row / phone toolbar rules; Search CSS braces balance.
- Browser/physical-phone paint and actual font/viewport layout remain unverified.
- Patch contains seven changed files; supplied database matches V3.4.8 bytes.
  No header, matching, game/scoring/audio/security files were edited.


## V3.4.10.2

- 80 Search assertions passed, including the existing random/query/pagination
  and badge checks plus custom popup opening, focus/ARIA state, option selection,
  arrow/Home/End/letter navigation, Enter/Space, Escape/Tab, outside click/focus,
  focus restoration and upward-position logic using explicit viewport fixtures.
- 347 ranking assertions and 147 existing Python tests passed. search.js syntax
  check passed; Search CSS braces balance. Reviewed scoped popup styling and
  checked the surrounding panel rules do not clip it with overflow.
- Browser paint, native assistive technology and physical-phone interaction
  remain unverified; keyboard/focus/viewport checks use DOM fixtures.
- Seven edited files packaged. Database bytes still match the supplied V3.4.8
  archive; no game/scoring/audio/security or header files changed.


## V3.4.11

- 65 profile assertions passed: all five summary panels for all entity types,
  populated/empty states, points/rates, entity-specific rankings, valid bracket
  links, initially collapsed details, escaping, immutable input, preview labels,
  tag title placement, collaborator text, queue initial state and Overall
  placement/breakdown/error paths below key stats.
- All 777 saved-data entity summaries render without NaN/undefined figures using
  a copied database. All four real entity routes load profiles.js/profiles.css
  before site.js; Home/Search/Global Stats/standard rankings do not load them.
- Existing 80 Search assertions, 347 ranking assertions and 147 Python tests
  passed. Edited/new JavaScript passes syntax checks; profile CSS braces balance.
- Nine audio/controller functions (including preview restart, attach/bind,
  play/pause, queue advancement and track marking) match the supplied baseline.
  Only queue info markup and profile composition were changed around them.
- Reviewed 320–430 px phone rules, tablet/landscape stacking, image constraints,
  separate score columns, 44/48 px controls, wrapping labels and native details.
  Native browser/phone paint, overflow and physical audio playback remain
  unverified; profile DOM tests use fixtures, not actual browser screenshots.
- Thirteen changed/new files packaged. Supplied database bytes remain unchanged.
  No backend/scoring/security or dependency files changed.


## V3.4.11.1

- 80 profile assertions passed, including open mode/history/gallery data,
  preserved Overall dropdown, cover-caption placement/content, relevance-sorted
  tag counts with deduplication, two-row fitting/restoration and song/tag
  exceptions. Existing 80 Search and 347 ranking assertions passed.
- 44 colour cascade checks passed at 320/430/768/1440 px using the actual
  stylesheet order and selector matching, covering all mode metric values,
  rate values and the Blind inset. This verifies the legacy pink declaration
  loses to the explicit section-colour rule; it is not a browser screenshot test.
- Existing 147 Python tests passed. Edited JavaScript passes syntax checks;
  profile CSS braces balance. Nine core audio/controller functions still match
  the supplied baseline.
- Browser paint, actual rendered tag wrapping, screen-reader behavior and
  physical-phone playback remain unverified. Tag row tests use layout fixtures;
  a ResizeObserver and fixed two-row CSS fallback handle browser layout.
- Eight edited files packaged. Supplied database bytes remain unchanged; no
  backend, scoring, security or dependency files changed; audio-controller logic is unchanged.


## V3.4.12

- Full Python suite: 165 tests passed (18 new voting-report tests). Fixtures
  cover both modes/other-mode exclusion, bad pairs, saved before/after ratings,
  equal ratings and upset denominators, gaps, zero-sum deltas, missing/invalid
  snapshots, deleted tracks, reversed pairs, sample minimums, pooled collection
  rates, singles/unknown albums, chronological runs, UTC/future/undated activity,
  lifetime totals over 100 rows, history filtering/pagination, SELECT-only reads,
  legacy schemas without rating columns, non-finite/current rating boundaries,
  escaping and populated/empty/missing-track template rendering.
- Copied supplied data reconciles to 419 votes: 251 Non-blind, 168 Blind; all 419
  have complete usable rating snapshots. There are 98 lower-rated wins among
  283 unequal-Elo votes, 136 level-Elo votes and 419 surviving tracks voted.
  Current rating bands sum to the number of finite catalogue ratings.
- All five tested Voting Stats history-query states return 200. Home, Global
  Stats, a mode board, a song profile and Search still return 200 and do not load
  voting_stats.css. The new page is linked from navigation/profile voting panels.
- 805 selector/cascade checks passed on actual rendered page markup across
  320/360/390/430/640/900/1440 px rules. They verify orange/mint metric colours
  and agreement of all six artwork dimensions. Reviewed the shared record
  reflow, stacked compact VS rows, count/label wrapping and 44 px actions.
- Existing 80 profile, 80 Search and 347 ranking assertions passed. Edited
  JavaScript passes syntax checks. Nine audio/controller functions still match
  the supplied baseline; game, scoring, audio-controller and security logic are unchanged.
- Native browser screenshots, actual font/viewport overflow, assistive technology
  and physical-phone interaction remain unverified. CSS checks use a selector
  engine/media-rule evaluation, not browser paint.
- Fourteen changed/new files packaged. Database bytes match the supplied V3.4.8
  archive; the page reads a caller-owned snapshot and adds no schema or counters.


## V3.4.12.1

- Reproduced the populated `/history` failure on a copy of the supplied data:
  Jinja raised `UndefinedError: 'sqlite3.Row object' has no attribute
  'winner_song'`. The History query returned the old flat shape while the
  existing shared VS-row template required nested song metadata.
- Full Python suite: **175 tests passed**, including ten History regressions.
  Coverage includes populated Non-blind/Blind rows, newest-first ordering,
  saved Elo/deltas rather than current ratings, empty state, correct escaped
  song/album/artist links, artist commas/duplicates, missing metadata, partial
  snapshots, legacy history without snapshot columns, song scope, limits,
  deleted tracks, 1,000 distinct tracks under a 999-variable SQLite limit,
  SELECT-only reads, allowed-phone/denied-device access and connection cleanup.
- Twelve copied-data page reads return HTTP 200: History, Voting Stats, Global
  Stats, Home, Search and a song profile for both loopback and the configured
  phone address. History renders fifty rows, both modes and saved Elo. A denied
  device still receives 403; the allowed phone still cannot access Dev login.
- The integration copy is byte-for-byte unchanged after these reads. The source
  database also matches the supplied V3.4.8 ZIP. No database, private key,
  dependency, security, template, CSS or JavaScript files are in this patch.
- Phone checks use Flask's simulated direct-client address; physical Wi-Fi or
  phone-browser behavior was not tested. No presentation changes are included.

Apply the eight edited/new files over **V3.4.12**, restart and refresh History.


## V3.4.13

- **175 Python tests pass** on isolated databases. Existing **347 ranking,
  80 Search and 80 profile assertions pass**. All edited/new JavaScript parses.
- New **173 gameplay assertions** use real game scripts with jsdom, explicit
  HTTP/media fixtures and a controlled clock. Cover blind identity hiding,
  duplicate-vote protection, saved Elo/deltas, manual/automatic next cancellation,
  bracket size/type eligibility and unchanged API parameters, failed-start retry,
  custom menu keyboard/focus/outside/viewport behavior, Trivia start/pause/reveal,
  non-drag shelf placement/order, two/three album reveal order, per-album points,
  deferred main-score updates, zero/fractional points, cancellation during rows
  and transfers, reduced motion, escaped links and final saved totals.
  Run `node tests/test_gameplay.js` with jsdom available to Node (QA only).
- **2,832 selector/cascade checks pass** across thirteen rendered game states at
  320/360/390/430/700/760/1050/1440 px. They use the actual stylesheet order and
  verify semantic link/value/outcome colours, equal child-art constraints, Trivia
  square cover dimensions, pair-game stacking, matching red/green position type,
  mode primary buttons and touch/menu sizes. No shared existing CSS was changed.
- **124 controlled audio/controller assertions pass**: 84 engine/queue/reveal/
  Trivia checks and 40 pair/cache/artist checks. The old test harness was adapted
  to load the current profile renderer. Playback engines and audio handoff
  functions are unchanged; count-up gained an optional cancellation guard.
- **34 computer/simulated-phone page and asset reads return HTTP 200**. New game
  assets/body scope are present only on the five play routes and absent from
  Home, Search, History, Voting Stats, rankings and profiles. Allowed-phone Dev
  denial and disallowed-device denial remain 403. These reads leave the copied
  database byte-for-byte unchanged; the source matches the supplied V3.4.8 ZIP.
- Browser paint, actual wrapping/viewport overflow, native assistive technology,
  physical-phone controls and audio playback remain unverified: no working
  browser executable is available. DOM, timing and media checks use fixtures;
  CSS checks evaluate selectors/media rules rather than painted layout.
- Thirteen edited/new files packaged over V3.4.12.1. No database/private key,
  backend, requirements, scoring, security or preview-engine files are included.


## V4.0.0.3 — step 3 (schema 11)

This patch includes steps 1–3 cumulatively. All app tests use isolated temporary
databases; the supplied 507-song source and working database remain unchanged.

- **250 Python tests pass**, including 24 new stream/tournament integration tests.
  Cover independent known-value ratings, public-only overrides, historical
  anchors, corrected modes/void/restore, unknown/missing/self-pair exclusions,
  prospective global/restricted/blind brackets, later/bronze exclusion, frozen
  server influence, concurrent retries, conflict handling, atomic failure after
  source/public updates, bracket deletion/reset reversal, historical source
  retention, schema-10 pending offers/corrections, extension collision refusal
  and complete export/rebuild. Existing 226 regressions remain included.
- **740 JS assertions pass:** Gameplay 185, Dev preference review 29, Profiles 99,
  Search 80 and Mode Rankings 347. New fixtures check paired track means/counts,
  single-mode/unplayed states, signed gaps, protected tournament review and
  full/half/points-only captions while preserving hidden blind identities.
- The supplied snapshot migrated directly **8→11, 9→11 and 10→11**. Reconciliation
  preserved every original table value/row ID/sequence and old view contract,
  with explicit expected mapping for the new effective-view columns. Public
  collection/Overall inputs and frozen special-mode grades remain exact.
- All **427** raw ordinary vote records are intact. Independent reference
  calculations match **259 Non-blind / 168 Blind** votes from 1200; each mode's
  ratings sum to its baseline mass. The sample has only one track reaching the
  display minimum of three votes in each mode; sparse comparison lists are correct.
  No old tournament event is inserted; all eight old brackets have frozen policy 0.
- **28 read routes** return 200 on populated copied data. A newly created complete
  8-track bracket saved four preference events; later rounds and bronze saved
  none. Retries retained results; ordinary history stayed at 427. Replaying
  mixed events was exact. Deleting that bracket restored the original public
  and independent projections. Export/rebuild reconciled all current state.
- Read-only shadow analysis used the supplied 427 ordinary votes plus 72 first
  rounds (36 restricted). All-full vs restricted-half: max rating movement
  42.0002605 vs 31.3882333; mean absolute movement 4.2426374 vs 3.2299252. A
  100-repeat pair stress check yielded spans 616.7772482 vs 490.1446856.
  Zero-sum and one first-round appearance per entrant/bracket checks passed.
  These are sensitivity checks, not proof that a rating estimates unbiased taste.
- Canonical schema: **23 stored tables, 5 views, 15 explicit indexes, 2 triggers**.
  No dependency, existing tournament point, selector, challenge or Overall
  calculation change. Updated the complete stored-field dictionary.

Reproduce from the app folder with an isolated `SONG_RANKER_DB` and valid test
secret: `python -m unittest discover -s tests`; run each `tests/test_*.js` with
Node/jsdom available (QA only). Shadow check:
`python tools/validate_v4_elo.py /path/to/backup.db` (read-only).

No real Chromium/Safari/Android paint or audio check was performed in this
step. JS fixtures use fake media and DOM checks. The user plans to play-test
when all stages are installed; combined desktop/phone/audio checks remain a
release gate. This patch preserves the existing responsive components and
style tokens and adds no stylesheet/dependency.


## V4.0.0.4 — step 4 (schema remains 11)

- **264 Python tests pass.** Retained all earlier foundation/preference/game
  regressions and updated superseded percentile-display expectations to direct
  composite/rank behaviour. Fourteen new Overall tests cover close/large gaps,
  population-independent display for unchanged composites, exact tied ranks,
  sub-rounding precision, unchanged song contributions, collection confidence,
  mixed allocations, neutral unrepresented tracks, unknown/ineligible modes,
  full balance reconciliation, metadata and API/details/refresh agreement.
  Uniform-growth assertions use 12-place float tolerance, consistent with the
  existing composite test; changing counts proportionally can introduce ~1e-14
  arithmetic differences that the old percentile display hid.
- **836 JS assertions pass:** Overall 96, Gameplay 185, Dev preference review 29,
  Profiles 99, Search 80 and Mode Rankings 347. Overall fixtures check shared
  values across Home/Global/profile/ranking/Dev, category controls, reversed
  Bottom standings, exact tie labels, score-vs-weight-vs-points-vs-evidence,
  collection neutral share, unknown vs real zero, escaped text, retry states,
  native disclosure clicks and the narrow-screen CSS rules.
- Compared all **777** entities in a copied supplied snapshot with the step-3
  calculator. All original composites, features, mode/metric weights, evidence,
  collection priors and category orders were bit-for-bit equal. The new
  presentation fields never feed the calculation. Each measured eligible score
  now equals its composite. All collection effective weights sum to 100 and
  mode/neutral points sum to the composite (floating tolerance 1e-10).
- Supplied-snapshot direct ranges: Songs 34.9761671–75.8136049 (482 tested),
  Artists 48.9936798–56.7466819 (59), Albums 45.9617370–56.5363149 (62),
  Tags 49.6013431–56.1915036 (54). All four previously spanned 2–98%.
- API summary/details and authenticated refresh agree. Eleven relevant read
  routes return 200. Repeated Overall calculations/requests leave the copied
  schema-11 database bytes unchanged. Original/working database hashes still
  match the supplied source. Cumulative migration/recovery tests remain included.
- No schema or dependency changes in this step. VERSION=4 identifies the new
  read-only Overall presentation/calibration metadata. Legacy rank percentile
  API diagnostics are retained; no screen uses them as the displayed score.

Node/jsdom fixtures check DOM, interaction and responsive rule structure; no
Chromium/Safari/Android layout paint or real audio was tested. The existing
phone/desktop/audio release gate remains for the combined upgrade. Run the
Python suite with an isolated SONG_RANKER_DB/valid test secret, and all six
`tests/test_*.js` files with Node/jsdom available (QA only).


## V4.0.0.5 — step 5 (schema remains 11)

- **305 Python tests pass**, including 41 new pure selector/endpoint tests. The
  existing schema, recovery, preferences, split Elo, Overall and detailed-mode
  regressions remain included. New coverage checks the exact below-average
  distribution, positive exploration base, flat/large/skewed counts, count
  translation/replication, live spread fallbacks, affine Elo invariance, recency
  relaxation, invalid/tied ratings, frozen Guesser answers, entry-based tournament
  counts, serial concurrent creation, scope/preview filtering, Shelf feasibility,
  automatic format choice, completed-only exposure and classic streak preservation.
  Pending/repeated/rejected submissions do not add exposure.
- **836 existing JS assertions pass:** Overall 96, Gameplay 185, preference review
  29, Profiles 99, Search 80 and Mode Rankings 347. Game payload shapes, frontend
  controllers and UI layouts are retained; no frontend asset changed in this step.
- **1,205 checks** passed in the optional deployed simulation run: the original
  705 prototype checks plus 500 production/prototype parity checks with changing
  counts and recency. Original eight-seed workloads include 354,400 questions and
  3,200 bracket draws. Deployed statistics match the accepted report within 1e-10.
  Standard/Blind variation fell 37.68%/37.91%; Trivia 33.31%; tournament entries
  37.14%; Shelf albums 61.47%; within-album tracks 30.00%. These are exposure
  balance measures, not measured preference accuracy or UI satisfaction.
- Reproduced growth, imbalance, evolving K32, pool replication, rating rescaling,
  flat/tied/small pools, invalid distributions and feasibility fallbacks. The
  progressive Guesser/Trivia stages in the kit remain offline checks for step 6;
  runtime classic Guesser uses target 0.60 and Trivia keeps its original streak
  condition. Existing scoring/records and K32 remain unchanged.
- On the actual copied 507-song snapshot: completed 30 Standard and 30 Blind
  votes, generated all four scopes with eligible entries, checked full/half
  first-round effects, and completed ten rounds each of Guesser, Trivia and
  Shelves. All completed appearance deltas matched. Pending rounds resumed,
  preference retries returned original receipts and Guesser used frozen ratings.
  Each Shelf question had ten unique tracks, feasible albums and unchanged
  perfect-answer grading. Old 427 preference facts and original completed game
  rows remained exact. Export/rebuild reconciled all state and yielded identical
  seeded preference draws and Shelf recency history.
- Runtime selectors depend only on the standard library and existing shared
  views. NumPy 2.3.5 is pinned only for the optional simulation kit, tested on
  Python 3.12. No schema, selector counter, grading or points migration is added.
  Legacy fixed distances/window are retained only in the offline reference.

The source and working databases remain untouched; all app writes used isolated
copies. No real browser/phone paint or audio test was performed. Existing DOM
regressions remain useful but the combined release play-test is still required.


## V4.0.0.6 — step 6 (schema 12)

All writes use isolated databases or a temporary copy of the supplied snapshot.
The original and working-source DB bytes are unchanged. This cumulative patch
contains no database, SQL data dump, private key, backup or test dependency.

- **336 Python tests** pass, including 31 new challenge/rule tests. Coverage
  includes 9→10 and 24→25 boundaries, artist points with a failed requirement,
  no-album fallback, frozen answers/artist variants/eligibility/targets, modern
  retry/conflict behavior and independent browser/mode progress. Four concurrent
  tabs receive one pending question and save one result in each quiz mode.
- Existing classic pending questions finish under their original rules; cookie
  counters never seed a modern run. Classic bests stay separate from progressive
  records in games, Home, detailed stats and Global Stats. A saved 221 is retained.
  Trivia/Guesser reports make bounded read-only queries (10/8 respectively).
- Schema-11 upgrade, SQL dumps without the version pragma, current export/rebuild
  and saved pending-question recovery pass. Reserved-column/table collisions fail
  without changing stored data. Pre-8 relational upgrades also handle absent quiz
  tables without manufacturing partly upgraded run objects. Existing foundation
  tests cover 8/9/10, future-schema refusal and transactional upgrade failure.
- Modern Trivia results and pending frozen answers survive track removal. Partial
  deletion of progressive quiz history is refused; explicit per-mode resets clear
  the affected results/runs together and preserve the other mode. Malformed JSON,
  paused grading/finish and foreign-browser submissions do not add results.
- **958 JavaScript assertions** pass: Gameplay 307, Overall 96, Preference Admin
  29, Profiles 99, Search 80 and Mode Rankings 347. Challenge DOM checks exercise
  320/360/390/430/568/768/1280 px configurations, no-album fields, distinct classic
  records, artist success with streak failure, missing-identity text, lost finish
  response retry and explicit next/restart controls. Existing audio/reveal mocks
  and reduced-motion behavior remain covered. No device paint or real Safari/
  Android/audio playback was performed; the combined step-8 play-test remains.
- The deployed pure rule/selector helpers pass **19,200 progressive draws** across
  eight seeds and six streak levels, plus **100 affine rating checks**. On the
  fixed 507-song fixture, median raw gap changes 29.83→15.33→14.32→3.81→2.36→1.50
  at streaks 0/10/25/50/100/250. All 400-question batches covered at least 419 tracks.
  The live policy retains exploration; it does not promise each next pair is
  closer or establish that a user knows the ranking. The separate 284-row Trivia
  backtest gives classic/progressive bests 220/46, without rewriting saved 221.
- An actual HTTP play-through on a temporary supplied-data copy completed 60
  ordinary votes, one first-round vote in each of four tournament scopes, 30
  Trivia questions, 21 Guesser answers and ten Shelves rounds. Both Shelf formats,
  first-round Elo influence, exposure deltas, ordinary receipts and frozen answers
  pass. All 427 original vote rows and original completed game facts remain exact.
  Full export/rebuild preserves data, seeded draws and both pending challenge tokens.

The optional standard-library experiment is
`python tools/selection_lab/run_challenges.py`. The step-5 1,205-check full selector
benchmark remains documented above; this step changes its progressive target
caller rather than retuning its exposure/kernel policies. Clean patch-overlay,
CRC, direct upgrade and all game endpoint checks are repeated for distribution.


## V4.0.0.7.1 — step 7A (schema 13)

This is cumulative over V3.4.13, including steps 1–6 and the import/source/album
part of step 7. Tag workbench and dashboard/Git changes remain for 7B/7C.
All app writes used isolated databases, temporary supplied-data copies or a
temporary distribution overlay. Both original DB files retain their original
SHA-256 bytes; no database, SQL data dump, backup, key or dependency is shipped.

- **373 Python tests pass**, including 37 new catalogue tests. Coverage includes
  distinct advisory/censored/radio facts, valid IDs/links/store/discs/dates,
  signed result ownership/expiry/tampering, confirmed versus unverified matches,
  whole artist names/known collaborations, repeat/conflicting adds, source-only
  saves and opt-in refresh, local placement/custom tag retention, observation
  history, stale reviews, auth and malformed payloads. Singles checks cover date
  priority/origin, unique destinations, safe cleanup/FK extensions/custom rules,
  four concurrent retries, rollback, no-op moves and unchanged game facts.
- Schema-12 migration and current export/rebuild preserve catalogue/source
  observations and unknown legacy dates. Pragma-less SQL dump recognition,
  reserved object collision refusal, ID high-water marks, 8–12 upgrade ordering,
  backups, rollback and earlier foundation regressions remain covered.
- **1,079 JavaScript assertions pass:** 121 new developer catalogue assertions
  plus Gameplay 307, Overall 96, Preference Admin 29, Profiles 99, Search 80 and
  Mode Rankings 347. The actual Dev module and site controller run together in
  jsdom: hidden matches/counts, confirmed flags, batching, duplicate activation,
  tags/query retention, separate source opt-ins, source-only default, Enter,
  per-song date editing, album inspection/manual previews and stale/failed saves.
  A lookup can finish after changing panels; an older Add cannot close a newer
  dialog or clear a new query. New controls are exercised at 320/360/390/430/
  568/768/1280 px configurations. These are DOM checks, not browser paint tests.
- On a temporary copy of the supplied **507-song** database, 8→13 creates no
  invented source IDs/song dates. Linking alone changes no other table. An
  explicit metadata refresh keeps album/position and all game facts. Two real
  catalogue tracks move to Singles with Apple-date and album-date fallback;
  song IDs remain stable, necessary old albums remain, FK checks pass and backups
  exist. All **427** original preference rows and classic Trivia best **221**
  remain exact. Ordinary/Trivia/Guesser pending payloads remain unchanged through
  these edits; full export/rebuild reconciles every cell and resumes those offers.
- The packaged files are CRC-checked and overlaid on the untouched V3.4.13 source.
  A cold startup upgrades directly to 13; public collection/stats and all game
  entry points work. A new process resumes exact pending challenge offers and
  saved progress, retains the reviewed source and copied song date, and leaves
  classic best 221 intact. Original source files are checked against the attached
  ZIP; the patch includes only changed/new files and its manifest.

Apple responses were mocked; no live Apple lookup, real browser/device paint,
Safari/Android interaction or real preview playback was performed. The combined
step-8 device/audio release check remains. Selector policies/grading did not
change in 7A; the earlier selector simulations are retained, not claimed rerun.


## V4.0.0.7.2 — step 7B (schema remains 13)

This cumulative patch includes steps 1–6 and 7A/7B over V3.4.13. All writes use
isolated fixtures, a temporary supplied-data copy or a temporary distribution
overlay. The original/source DB files retain their original SHA-256 bytes.
No database, SQL data dump, key, backup or QA dependency is included.

- **403 Python tests pass**, including 30 new tag tests. They cover exact
  Before/After sets, read-only review, add/remove/replace/empty set, preserved
  unrelated memberships and every other table, normalized name reuse, ambiguity,
  description/ID retention, new definitions, malformed requests, local auth/origin
  restrictions, signed owner/expiry/tampering and client-field substitution.
  Four concurrent tabs save one change/definition/backup. Unchanged/repeated
  outcomes make no backup. Selected metadata/membership changes conflict; game
  activity and unrelated tag metadata do not. Backup or mid-write failure rolls
  everything back. A 1,015-song selection exercises chunked reads and de-duplication.
  Full export/rebuild and actual Dev restoration of a real tag backup pass.
- **1,189 JavaScript assertions pass:** Tag Workbench 110, Developer Catalogue
  121, Gameplay 307, Overall 96, Preference Admin 29, Profiles 99, Search 80 and
  Mode Rankings 347. Tests run the actual site, workbench and shared preview
  modules in jsdom, mocking HTTP/native media. Coverage includes combined filters,
  all-match/page/hidden selections, tag-description search, exact single scope,
  reviewed bulk targets, new tags, review pagination/invalidation, duplicate save
  activation, lost-response retry, recovered new target IDs, stale rejection,
  dirty-draft discard, failed-refresh messaging and off-panel request completion.
  Old bulk-tag controls reach review. Query/choices/review/save retain the active
  player; clearing filters does too. Missing/blocked/ended previews, manual
  resume/stop/next, release on leaving and no autoplay/loop/advance are exercised.
  Controls/Before/After are checked at 320/360/390/430/568/768/1280 px DOM settings.
- On a temporary **507-song** supplied-data copy, reviewed additions tag **50**
  previously untagged tracks; a separate pending-Trivia song gets a replacement;
  **25** selected tracks lose only the QA tag. A different browser changes a
  reviewed song and the stale save is refused without another mutation. Exact
  expected memberships pass after every operation. All non-tag table cells,
  mode exposures and per-song Overall composites remain unchanged, including
  **427** original vote rows and classic best **221**. Ordinary/Trivia/Guesser
  offers resume unchanged. Four real pre-tag backups exist; a saved retry makes
  none. Full export/rebuild reconciles every cell and supports pending recovery
  plus a signed already-matching retry with the same session/key. FK checks pass.
- Distribution is CRC-checked and overlaid on the unchanged V3.4.13 source.
  Cold startup upgrades 8→13; all game/public-stat entry points and Dev assets
  load. Mocked Apple source/Single work still passes. A real reviewed bulk tag
  change saves once; a fresh process retains exact memberships/source/date facts,
  resumes both challenge offers/progress, and reconciles the prior tag token
  without another backup. The original source files match the attached ZIP.

No live Apple lookup, real audio, browser paint, Safari/Android or on-device test
was performed. DOM viewport checks cannot establish pixel layout/audio behavior.
The step-8 combined device/audio check remains. Selectors, K32 and grading were
not changed; prior simulation results are retained rather than claimed rerun.


## V4.0.0.7.3 — step 7C (current, schema 13)

Cumulative steps 1–7 over V3.4.13. Writes use isolated fixtures and copied source
or distribution databases. Source/working DB SHA-256 remains unchanged. No user
DB, SQL data dump, backup, key, Git metadata or test dependency ships in the ZIP.

- **451 Python tests pass**: the previous 403 plus **29 Git** and **19 developer
  system/recovery** cases. Git uses actual local repositories and bare remotes:
  local-only status, incoming checks, snapshot-only commits with unrelated staged
  edits, failed hooks/pushes, lost replies, retry/no duplicate, pending code,
  behind/diverged/merge states, target changes, missing Git/network/deadlines,
  destination ambiguity/redaction, OS lock, guarded fast-forward/pre-backup,
  protected incoming files, local edits, SQL archive/rollback and cache removal.
  An actual CLI subprocess updates and executes before importing new modules.
  SQL round trips retain sparse hidden row IDs/composite keys, exact floats,
  NUL text, BLOBs, quoted extension names, sequences and trigger effects.
- System HTTP cases verify host-only auth/origins, complete read-only inventory,
  extensions/projections/views, backup listing/path/link safety, exact downloads,
  complete typed JSON export with pending offers/BLOBs, signed owner/expiry/
  tampering/task/target reviews, stale live/backup refusal, pre-restore backup,
  exact pending recovery, legacy compatibility and multi-worker refusal.
- **1,277 JavaScript assertions pass**: Developer System **88**, Tag Workbench
  110, Developer Catalogue 121, Gameplay 307, Overall 96, Preference Admin 29,
  Profiles 99, Search 80, Mode Rankings 347. Actual scripts run in jsdom with
  HTTP/native-media mocks. Dashboard checks cover default/bookmarked tasks,
  shortcuts/filters, no remote fetch on entry, no autoplay, inventory/backup
  search/paging/escaping, busy/double-click controls, blocked Git states,
  failed-push retry, signed target use, restore count review/cancel/stale/success,
  safety-backup messaging, catalogue/source refresh, navigation guard, late
  request suppression and status retry. Desktop/tablet/phone DOM configurations
  and CSS breakpoints/wrapping/touch targets are checked; these are not paint tests.
- On a disposable **507-song** copy, schema-8 backup review/restore reconciles
  the entire upgraded state. A new edit after review is refused; a fresh review
  restores exactly. All pending ordinary/Trivia/Guesser offers resume. Full JSON
  export/rebuild and binary download are exact. The full real catalogue uploads
  to a local bare remote; its SQL restores every stored cell/implicit row ID,
  view and sequence exactly while unrelated staged code remains staged. Retrying
  unchanged data makes no commit. Original **427** preferences and classic best
  **221** are retained. Only temporary local Git targets are used.
- Distribution CRC/file hashes, original-source attachment comparison, cold
  schema 8→13 cumulative upgrade, all game/public entry points and Dev assets
  pass. Existing Apple-source/Single and tag work still pass. A fresh process
  retains source/date/tag facts and challenge offers, plus the current restore
  review; signed reviewed restoration succeeds after that restart.

No live Apple request, real preview playback, rendered browser/device or Windows
host was tested. The final device/audio/paint check remains for step 8. Selectors,
K32, grading and points did not change; earlier selection simulation results are
retained rather than claimed rerun. Exact recovery/Git limits and target policies
are in [docs/DATABASE.md](DATABASE.md).
