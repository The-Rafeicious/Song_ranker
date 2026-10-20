# V5.1.1.1 display hotfix validation

**268 Python tests and 466 JavaScript assertions passed** on this package.
The gameplay suite now has 88 assertions; the three developer suites retain
167 catalogue, 99 system and 112 tag-workbench assertions. The added checks
cover escaped/encoded proper album links, Standard Vote's Singles/Unknown
policy, shared cover structure and centre-overlay play/pause state.

All five changed stylesheets parse successfully. The Home layout's obsolete
five-card rules were removed from `special_modes.css`, while `home.css` now
owns automatic four/two/one-column placement. Navigation's new stylesheet is
loaded before the approved final baseline. Python and JavaScript syntax,
documentation links, release hashes and archive contents are checked at packaging.
These CSS/DOM checks do not substitute for visual browser or physical-device QA.

A full Waitress/DOM smoke test verified eight Home cards with the expected
emojis, album links and centre-overlay play/pause in all three new modes with
all shared scripts loaded. Each mode saved a real test decision and its stats
page displayed the saved history. No JavaScript errors or duplicate player
toggles occurred. The safe-mode source fixture stayed byte-for-byte unchanged.

This patch changes no canonical schema, backend mode rules, selectors, Overall
formula or safe-mode implementation. The archive is a cumulative code-only update.

---

## Retained V5.1.1 page-release validation

# V5.1.1 validation

**268 Python tests and 456 JavaScript assertions passed.** These are the tests
present in this package: 14 new page/report cases and 78 new gameplay assertions,
plus the 254 Python cases and 378 developer DOM assertions retained from V5.1.
All new tests use disposable fixtures; no synthetic decisions are distributed.

The new Python cases render all six real templates, both empty and populated;
verify no database writes during reads, cache policy and asset/navigation links;
check history bounds, Vibe map filtering, reviewed/unknown tags, HTML escaping,
removed song identities, renamed tag links and Global Stats integration.

The new JavaScript suite executes `ui.js` and `judgement_game.js` with controlled
HTTP, pacing and media boundaries. It covers exact Spotlight budgets, zeroes,
fractions and rapid double saves; independent optional Vibe grids, arrow/tab
keys, clearing, the eight-tag cap and reviewed-empty semantics; Twins choice,
none and skip; frozen listening/answer retries, unconfirmed saves across refresh,
draft resumption, no autoplay, audio-node preservation and late response rejection.

The underlying selection, schema and Overall algorithms are unchanged. The
600-round adaptive simulation below is the measured V5.1 baseline, not a new
V5.1.1 simulation claim. Source catalogue bytes remain protected; release
packaging excludes live databases, snapshots, safe runs, secrets and test output.

## Complete HTTP and DOM smoke

A real Waitress server ran against a safe copy of the supplied 535-song catalogue.
With all shared/page scripts loaded, the DOM harness completed and advanced a
Spotlight split, a two-table Vibe review and a Twins no-match decision, then
opened each populated dedicated stats page with ten-item history. No JavaScript
errors were captured. The source database's bytes remained exact. The harness
used native-fetch/media adapters; this is not a browser-paint or sound test.
The measured summary is [V5_1_1_VALIDATION.json](V5_1_1_VALIDATION.json).

## Reproduce V5.1.1

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
node tests/test_judgement_game.js
node tests/test_dev_catalog.js
node tests/test_dev_system.js
node tests/test_dev_tags.js
python tools/test_v51_backend.py
```

Node DOM suites require jsdom installed outside the app source. The final command
always enables safe mode. Automated DOM checks validate controls/state rather
than pixel layout or physical-device playback. Local headless Chromium could
not launch in this execution environment, and the separate cloud browser could
not reach the local preview server, so a visual browser-paint check is not claimed.
Windows hosting and real phone/audio checks remain installation checks.

---

## Retained V5.1.0 backend validation

# V5.1.0 validation

This release reruns the **254 Python tests present in this package**, including
37 new mode/safe-mode cases. The three supplied DOM suites pass **378 JavaScript
assertions** (167 catalogue, 99 developer-system, 112 tag-workbench). The changed
Overall script also passes JavaScript syntax checking. These are current counts;
the larger historical counts retained below are inherited notes, not fresh
V5.1 claims for harnesses absent from the supplied archive.

## Database and safety checks

- Upgraded a disposable copy of the supplied schema-15 catalogue to schema 16.
  All old values, implicit row IDs, view results and ID high-water marks
  reconcile; 535 songs, 67 artists, 155 albums and 54 tags remain. SQLite reports
  integrity OK and no foreign-key errors. The source archive/database is untouched.
- The empty new schema adds **51,200 bytes (50 KiB)** to this 722,944-byte snapshot.
  The migrated copy has zero new judgement rows: no example answers are seeded.
- Tested concurrent retries, exact point budgets, independent optional maps,
  nullable similarity choices, absent/partial listening, browser ownership,
  origin checks, invalid fields, deletion, resets, JSON and SQL round trips,
  repeated migration and preserved sparse extension row IDs.
- Exercised the real safe-mode app bootstrap, new endpoints, Overall and the
  visible safe banner in subprocesses. Main bytes/schema remain unchanged;
  writes and backups occur only in the test copy. Committed WAL is copied
  without changing source DB/WAL bytes. Managed writes reject original and
  hardlink aliases; attached databases are denied.
- Verified launcher mutual exclusion, Git tasks blocked before invoking Git,
  fresh snapshots and three-run retention, missing/corrupt sources and explicit
  safe flag parsing. File locking was exercised on Linux; the Windows msvcrt
  branch is included but was not run on Windows.
- Verified that descriptor judgments alone do not alter Overall quality scores.
  Spotlight contributes one observation per song within the same capped
  preference family. Nominal shares sum to 100 and actual shares remain adaptive.

The supplied test files referenced missing historical SQL fixtures. They were
restored as schema-only definitions: the pre-replay layout from the attached
8eb97b4 Git snapshot, the pre-source schema-12 layout from its schema-13 archive,
and the actual supplied schema-15 registry. They contain no user rows. Existing
startup tests now include the protection step and new backend-module registration.

## Adaptive selection exercise

600 synthetic rounds in disposable fixtures: 200 for each mode. Each starts
with 12 songs, adds four after round 100 and continues without resetting weights.
All current tracks are reached. The four new songs catch up automatically:

| Mode | Final mean exposure | New-song mean exposure | Coverage | Fixture bytes added |
| --- | ---: | ---: | ---: | ---: |
| spotlight | 50.000 | 50.250 | 100% | 161,792 |
| vibe | 4.167 | 3.333 | 100% | 96,256 |
| twins | 50.000 | 49.250 | 100% | 141,312 |

Vibe exposure is complete-map equivalents, so its single-table turns contribute
one third each. The measured fixture growth is about 0.5-0.8 KiB per round,
including ordinary page/index overhead and the four added songs, without optional
listening samples. This is a fixture measurement, not a fixed storage guarantee.
The full report is [V5_1_VALIDATION.json](V5_1_VALIDATION.json). Synthetic test
results and test copies are excluded from the download.

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python tools/test_v51_backend.py
```

The last command always uses a fresh safe copy. DOM tests require Node and
jsdom, installed outside the app source, then run the three `tests/test_dev_*.js`
files. No new mode gameplay screens or physical-device audio/paint are claimed
in this backend release. HTTP/DOM checks do not substitute for those later UI
checks. Packaging checks cover Python/JavaScript syntax, registry version,
manifest hashes, ZIP CRC, excluded live/private files and extracted safe startup.

---

## Inherited V5.0.3.x validation notes

# V5.0.3.2 validation

Based on the completed V4 app plus V4.1.6. V5 uses a new generation-3 database,
initially schema 14, now schema 15. The supplied V2 database remains unchanged, SHA-256:
`d9d06fc85a2786968f50219549a0eb4598c4284686e98fafb4b1a7beae695e68`.
Earlier reports are retained in [validation history](../../docs/VALIDATION_HISTORY.md).

## V5.0.3.2 source confirmation and alignment

167 developer-catalogue JavaScript assertions pass, including selected feedback,
collapsed alternatives, retained pressed state, confirmation focus and no early
save. The catalogue suite also exercises single/bulk source editing, failure
recovery, staging/skip/revisit, and DOM contracts at seven widths. Developer
controls, developer-system and V4.1.5 UI regression suites pass separately.
These are DOM/behavior checks, not physical-device browser paint assertions.

A real Waitress/HTML/script bulk-source check with mocked Apple confirms the
new selected/collapsed/focused state and a subsequent successful group save.
Restart retains current sources, database integrity and foreign keys. The
supplied database remains unchanged. Cumulative packaging checks validate
syntax, document links, checksums/CRC and repeated extracted-app startup.
Backend behavior is unchanged; the prior 550-test Python validation is retained
below for the underlying V5.0.3.1 implementation.

## V5.0.3.1 requested backups and shutdown

**550 Python tests pass**, including eight new rotation/shutdown cases: five
requests retain only the latest three slots, old archives stay untouched, failed
atomic replacement retains all slots, pending requests drain, PIN is required
even for administrators, new writes are blocked during stop, owner/job-bound UI
acknowledgement is required, Git failure retains the local backup and app, cancel
and timeout resume the app, and externally managed WSGI hosts cannot be stopped.
Earlier tests now verify routine source/tag/metadata/delete edits create no
backup. Explicit manual backup/restore still reconciles every field.

**2,090 JavaScript assertions pass in 18 suites.** The stop UI tests cover the
always-available developer header action, masked fresh PIN and incorrect-PIN
feedback, visible Git destination, explicit reviewed request, backup/Git receipts
before acknowledgement, four-second display pause and unsupported WSGI state.

**10 live real-launcher checks pass** with actual HTML/scripts, real Waitress,
an isolated supplied-database copy and a disposable local bare Git remote. An
incorrect PIN leaves the app running. Correct PIN creates the local slot and
pushes the SQL snapshot; both success receipts appear while the server still
serves pages. Browser acknowledgement then produces a clean process exit (0).
The remote commit matches local HEAD and contains only `database_backup.sql`.
Restored SQL, the shutdown backup and live DB compare exactly. The original
attachment is unchanged. This does not claim physical-device browser paint or
user-remote credentials were tested.

The cumulative ZIP also passes syntax, document-link, hash/CRC and extracted
full-app overlay checks, including repeated startup and catalogue preservation.
No active database, secret, Git repository or backup is shipped. Earlier reports
below describe their own releases' backup policies; V5.0.3.1 supersedes per-edit
backup creation.

## V5.0.3 source review

**542 Python tests pass**, including eight new bulk-source transaction tests:
complete pre-edit backup, unchanged catalogue/game tables, stale-item rejection,
external identity conflicts, corrected pair swaps with stable row IDs, duplicate
song/track/token validation, session ownership, admin/size bounds and rollback
when the backup cannot be created.

**2,079 JavaScript assertions pass in 18 suites.** Source tests exercise five
initial choices plus ten collapsed extras, the fifteen-choice cap, source-state
filtering, queue advance/skip/revisit, duplicate staging, close/resume/discard,
failed-save retry, explicit signed per-song requests and successful refresh.
Shared album/EP/Single search results are reused, reordered for each title and
never automatically assigned. Bulk tag UI tests now verify its removal while
the separate tag workbench remains fully covered.

**19 live HTTP/jsdom checks pass** against Waitress and a disposable copy of the
supplied database, using the actual loaded HTML/scripts and mocked Apple only.
The real source queue selects two recordings, commits them together, shows a
successful backup receipt and retains the correct advisory flags. Songs,
albums, artists, tags and history compare exactly before/after. A second process
retains both source records, one row per song, SQLite integrity and foreign keys.
No live database or original attachment was modified. These are DOM/HTTP checks;
physical-device browser layout and live Apple availability are not asserted.

The release ZIP is checked for syntax, document links, file hashes/CRC and a
cumulative overlay onto the original full V5 app. Repeated startup against a
copy of the supplied schema-14 database retains its entire catalogue and latest
source values through the included schema-15 storage upgrade. No active database,
secret or backup is bundled. No files are deleted by this patch.

## V5.0.2.1 storage follow-up

**534 Python tests pass**, including nine compression/current-source cases.
They check lossless Unicode/URL round trips, plain-JSON compatibility, corrupt/
truncated streams, current-only migration with a complete pre-upgrade backup,
unchanged non-source tables, unique source constraints, in-place updates/stale
reviews, complete export/rebuild, protected invalid/extension-referenced sources,
and growth from 2 KiB to 4 KiB pages. Source-history assertions now reflect the
explicit one-current-source requirement. Separate WAL compaction checks retain
all values and restore WAL mode.

**2,052 JavaScript assertions pass in 18 suites.** **41 live source checks pass**
against Waitress/jsdom using an isolated copy of the supplied database. They cover
all decoded sources, an incomplete observation, actual import/source changes,
Edit summaries, a saved vote, and readable current sources in the analysis export.
A second process retains the vote and current sources. Apple responses are mocked.

The supplied database is **897,024 bytes**; the verified optimized copy is
**573,440 bytes** (36.07% smaller). All 517 songs, 155 albums, 67 artists, 54 tags,
532 artist links and 1,045 tag links are retained. All non-source table values
match exactly; every field/URL/ID/time of the 232 latest source observations
matches the original. Only nine obsolete observations are removed. The original
attachment SHA-256 remains
`356c6b10b3b408b41c114c6cc242faa041f3f6f10a78db26be76d142b542984c`.
The full supplied-data JSON rebuild and SQL restore reconcile every table and
all 232 decoded current sources. Integrity and foreign-key checks pass.

Page-size/compression candidates and a representative 10,000-vote storage
scenario informed the small/large page policy. These are measured examples, not
a guaranteed reduction for every future database. The optimized deliverable is
the supplied catalogue copy and contains none of the isolated live-test writes.

## V5.0.2 source reads and save status

**525 Python tests pass.** Four new regressions cover fill-generated snapshots
with omitted optional fields, successful save followed by a working batch read,
partial historical observations after relinking, and missing optional names.
Reads retain exact stored snapshots. The V5.0.1 failure was reproduced as a source
POST returning 200 followed by a summary GET returning 500 (`track_url` missing).

**2,052 JavaScript assertions pass in 18 suites.** The catalogue suite adds live
Edit-summary updates without losing unsaved text, and a confirmed save followed
by an injected 500 refresh. The latter retains the confirmed source, closes the
save dialog and shows a saved/reload notice. Existing rejected-save checks still
require an error and an open dialog.

**38 live Waitress/jsdom checks pass**, including an existing fill-generated
partial observation, actual source changes, success feedback and agreement with
the Edit summary. A new process retains the saved vote and all four observations.
Apple responses/media are mocked. The package overlay also checks preservation
of every stored V3 value, including existing results/listening/private flags.

## V5.0.1 source persistence

- **521 Python tests pass**, including ten new source-fix regressions. Flat Apple
  identities/links are verified and persisted; blank offers, missing/mismatched
  identities and failed source inserts leave the database unchanged. Signed and
  duplicate imports return saved source receipts. Reopened connections and Dev
  summaries retain the ID, URL and advisory label. Source-only repair preserves
  every other table; unmarked explicitness keeps the Not explicit default.
- **2,046 JavaScript assertions pass in 18 suites.** The Dev catalogue checks now
  reject missing offers/unconfirmed source receipts and cover optional saved-ID/
  link columns, filtering and safe external links. Existing layout/game checks
  remain in the suite.
- **34 live Waitress/jsdom checks pass.** Actual search/add/reload requests retain
  Apple ID, URL, explicitness and observation time; flat imports use the server's
  advisory fact rather than a forged client label. A Source-only repair keeps
  every public song/rating/listening value. Reloaded table columns read the
  persisted observation. Only the Apple response/media are mocked.
- A second process retains the saved match and all three source observations;
  integrity and foreign-key checks pass. These writes use isolated QA databases.

This is a schema-14 code patch over V5.0.0. The original first-release migration
and broader V5 validation are recorded below. Automated DOM checks do not replace
real-device visual/audio testing or prove current Apple service availability.

## Automated regression checks — V5.0.0 baseline

**511 Python tests pass.** The release adds 14 V5 cases alongside the retained
preference, scoring, replay, metadata, recovery, security and report suites.

- Catalogue transfer verifies exact songs/artists/albums/tags/source facts and
  relationships, ID high-water marks, 1200 baselines, zero old game/analysis rows
  and a complete old-results backup. The source is byte-for-byte unchanged.
- Repeated and simultaneous first starts publish one complete competition.
  A failed destination publish retains the old source and completed archive.
  Existing results/additions survive restart, including after archiving the V2
  source. Non-V3 destination data is refused. Exact V2 filename configuration
  maps to a distinct V3 target.
- SQL bootstrap preserves a generation-3 competition and resets older snapshot
  results through catalogue transfer. V2 archives cannot be restored over a V3
  competition through the normal Dev restore endpoint.
- Accepted Standard/Blind, Tournament, Trivia, Guesser and Shelves answers store
  listening only for actual offered tracks. Retry inserts once. Partial, foreign,
  duplicate, nonfinite or excessive measurements stay unmeasured and do not
  change a valid game result. Recognition reports map Trivia samples correctly.
- Preview flags require Dev authentication, validate input and remain absent
  from public collection data. Private exports include flags and observations;
  flags do not change public metadata or eligibility.
- New-track support is bounded and decays; exploration remains positive and
  normalised. Stage policy changes smoothly and health follows current mean/
  dispersion. Existing full/half preference evidence and saved Elo semantics pass.
- Package-import/launcher/Git re-exec fixtures follow the new module layout.
  Read-query bounds were updated only for the explicit extra analysis reads.

**2,037 JavaScript assertions pass in 18 suites.** Tests use actual feature
modules with controlled media/clocks and cover existing gameplay, timing,
reduced motion, tab visibility, Shelf counters, Dev search state, history,
rankings, profiles and controls. The new tracker checks audible progress,
preload/pause/buffer/mute exclusion, unplayed zeros, question redraw/restart,
Shelf player identity and seek-jump bounds. Health checks retain exact counts
while replacing headline percentage labels with categorical states.

## Live application checks

**571 checks pass** against Waitress/jsdom using an isolated copied V2 source
and a newly transferred V3 database. All 19 Dev sections and the public Home,
rankings/search, six stats dashboards, history, five game routes, Overall and
song/artist/album/tag profiles load actual local assets and endpoints without
script/request errors.

The run confirms all 507 songs/65 artists/151 albums/54 tags carry into a zero-
result competition, Guesser explains the initial equal-rating state, a real
browser-module vote saves four playback seconds across two measured tracks,
a selective first-round match contributes half preference influence, and the
Dev quality dialog saves a private note that stays out of public catalogue data.
It checks shared listening panels, categorical health, complete daily tables,
balanced profile mode cards and the shared baseline loading last. DOM controls
remain present under width settings 320, 360, 390, 430, 760 and 1280 px.

A separate full-app seed startup creates the same 507-song, 1200-Elo, zero-result
competition and serves the fresh Home/six stats pages. A full V3 JSON export and
rebuild reconcile every stored value, including nonzero listening samples,
private quality annotations and competition provenance.

## Selector simulations

Eight seeds × 3,000 preference draws × two policies = **48,000 draws**. Each
scenario starts with 80 equal-rated tracks, uses fixed noisy underlying
preferences and adds ten new tracks after round 1,500. Clock/seed inputs are
fixed. Compare the saved V4.1.6 policy with the final V5 policy:

| Checkpoint | V4 exposure CV | V5 exposure CV | New-track mean V4 / V5 |
| --- | --- | --- | --- |
| 100 rounds | 0.4416 | 0.4340 | — |
| 1,000 rounds | 0.0613 | 0.0545 | — |
| 1,700 rounds | 0.1290 | 0.1037 | 25.21 / 27.98 |
| 3,000 rounds | 0.0230 | 0.0209 | 66.67 / 66.94 |

CV is population exposure standard deviation / mean (lower is more even).
These are scenario results, not a promise of perfect uniformity or universal
improvement for every seed/library. The final policy preserves a randomness
floor and existing eligibility/recency constraints. Elo is never forced to the
health reference range. The tested capped-ratio alternative was rejected in
favour of the retained, slightly strengthened mean-deficit catch-up rule.

Full results: [SELECTION_VALIDATION.json](../../docs/SELECTION_VALIDATION.json). Reproduce
from the root with a saved V4.1.6 `selection.py`:

```sh
python tools/validate_v5_selection.py --reference PATH_TO_V4_SELECTION_PY --output selection_check.json
```

Without `--reference`, the tool runs V5 alone. It writes no database or ranking.

## Packaging and practical limits

- Python/JavaScript syntax, relative documentation links, source manifests,
  cumulative full/upgrade CRCs and original/prior-install overlay checks pass.
  The full ZIP's only database is a catalogue-only fallback seed. Neither ZIP
  contains an active V3 file, old results, session secret, SQL data dump, backup,
  QA dependency or temporary test repository.
- Extracted-ZIP startup checks pass for a fresh full installation, the upgrade
  merged over V4, and the full app merged over V4. All three retain 507 songs,
  start at 1200 with no old preference results, produce one complete backup,
  accept a new vote, and preserve it on the next process start. The upgrade
  paths also restart after the unchanged V2 source is moved into an archive.
- Old moved/superseded locations are listed explicitly in
  [TRIMMED_FILES.txt](../../docs/TRIMMED_FILES.txt). The list protects databases, backups,
  snapshots and the signing key. No automatic deletion is performed.
- DOM/computed-style checks do **not** render browser paint or calculate complete
  phone geometry. Physical-device appearance, real audio/autoplay/background
  behavior, CDN access and Windows hosting remain installation checks. No claim
  is made that those were tested on the user's phone.
- Live saves affect only the isolated QA copy. Preview-network calls are stubbed
  for live UI tests; no external Apple lookup or user Git remote is contacted.
  Listening values are browser observations and may be unavailable when the
  client cannot report them; grades and scores do not depend on those values.

Install normal requirements and run `python -m unittest discover -s tests`.
For JS tests, install jsdom as a test-only dependency and run each
`tests/test_*.js` with Node. Keep startup/live checks on a disposable database.
