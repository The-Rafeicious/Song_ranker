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
