# V4.1 release notes

## V4.1.0 — overall release summary

Developer dashboard, game refinements, health/listening reports, metadata fill, adaptive collection Impact and combined first-round Elo evidence.

**Historical reference.** Installation commands, schemas, validation totals and
then-planned features below describe their original release. Expired setup
instructions are no longer necessary for current installs; use the
[current upgrade guide](../docs/UPGRADES.md). Exact repeated prose is recorded once.

## Detailed updates

### V4.1 update log

#### V4.1.6 — Voting Record balance and half-match evidence

18 October 2026 · cumulative over completed V4.0 and every prior V4.1 patch.

- Simplified the shared song/album/tag/artist Voting Record into outcome totals
  and two balanced mode cards. Wins use green, losses red, Non-blind orange,
  Blind mint and tournament history pink. Keep rates, independent Elo and actual
  match counts visible; longer comparisons and history use native disclosures.
- Tournament Stats' recent first-round Elo history now uses compact paired rows
  with bounded artwork, consistent spacing and phone stacking. Retains both
  participants, saved changes, mode, bracket and half/full influence.
- Selective first-round results contribute 0.5 to preference wins/losses,
  effective appearances, pooled win/upset rates, selection exposure and Overall
  preference evidence. Full results contribute 1. Sample thresholds use effective
  evidence. This supersedes V4.1.5's one-full-outcome rule for half results.
- Actual match/history/source totals, activity bars and consecutive win runs
  retain event counts. Saved Elo deltas already have half influence: no second
  halving, replay, migration or reset. Bracket points/results keep their rules.
- The collection API retains raw match counts alongside weighted results;
  Selection health identifies round-one effective weight. Overall model version
  is 6 to distinguish the changed preference evidence.

Validation: **497 Python tests**, **2,022 JavaScript assertions** in 17 suites,
and **1,227 live app checks** pass on isolated data. Tests cover full/half pooling,
mode/origin distinctions, raw counts, unchanged Elo snapshots, correction/void/
retry behavior and profile layouts. DOM/computed-style QA does not render paint;
see [validation](../docs/VALIDATION.md) for limits.

##### Install V4.1.6

Stop the app, merge this patch's `Song_ranker` contents into your completed
V4.0/V4.1 folder, restart and hard-refresh. Earlier V4.1 changes are included.
Keep the existing database in place. Preference rates, draw weights and Overall
may update immediately from existing saved influence; stored Elo is unchanged.


#### V4.1.5 — Dev controls, Shelf counters and combined preference evidence

18 October 2026 · cumulative over completed V4.0 and every prior V4.1 patch.

- Fixed library/table and Apple Music search layout: bounded fields, normal text
  buttons, store-label clearance and matching source-search dialog treatment.
- Each Dev category retains its query, column filters, sort/direction and page
  on section changes/reload. Added active-filter count and Clear filters; clamp
  pages after edits. Preserve column selection, actions and source shortcuts.
- Shelf cover counters now stay above positioned artwork. Each track reveals
  a saved-point increment and animates the album subtotal; the completed album
  transfers once to the main counter. Standard/Quick and reduced motion retain
  the authoritative saved result. No point/grade changes.
- Combined first-round tournament Elo with ordinary preference outcomes in
  Standard/Blind selection counts, win rates, Elo movement, activity/coverage,
  records, matchups, collection profiles and Overall evidence. Maintain exact
  modes and source breakdowns. A half-influence event is still one outcome.
- Added bounded round-one histories and mode counts to relevant profiles and
  Voting/Tournament Stats. Global source counts and Selection health expose the
  round-one contribution. Full history/source filters remain available.
- Retained schema-13 ordinary storage/views for compatibility; added derived
  Elo-match counts and combined API projections. No migration, rating replay,
  K-factor or selection-kernel change. Overall model version is 5 because its
  preference evidence now includes these previously omitted results.

Validation: **491 Python tests**, **1,733 JavaScript assertions** and **165 live
app integration checks** pass on disposable/copied data. Six new Python cases
cover mode/origin totals, selection/Overall evidence, source histories, retries,
corrections/voids and exclusion of later/legacy points-only matches. New UI tests
cover per-category state/reload, actual count-up timing at both speeds, overlay
stacking and scoped origin histories. See [validation](../docs/VALIDATION.md).

##### Install V4.1.5

Stop the completed V4.0/V4.1 app. Merge the patch's `Song_ranker` contents into
your existing matching folder, restart and hard-refresh. Earlier V4.1 patches
are included. Existing data remains in place; no reset or rescore is needed.
Preference statistics/Overall may change as existing round-one evidence is now
included; stored Elo and Impact calculations are unchanged.


#### V4.1.4 — proportional catalogue Impact

18 October 2026 · cumulative over the completed V4.0/V4.1 app.

- Replaced summed Elo gains with a library-relative average and adaptive breadth
  support: `mu + n/(n+m) * (linked_mean-mu)`. The baseline is current mean Elo;
  `m` is the median positive peer track count for that artist/album/tag board.
- Count each distinct song once. Proper-album calibration excludes Singles and
  Unknown Album. The score remains within the current library Elo range and
  adjusts with collection growth and rating development. Broad tags cannot
  multiply small average gains into oversized scores.
- Shared Python/browser policy across library API, main boards, home shelves,
  search, profiles and Dev. Removed unused legacy profile sum calculations.
  Impact shows one decimal; full precision determines order. Empty collections
  remain accessible/editable with unavailable Impact/rank and do not fill boards.
- No stored ratings, event/scoring formula, selection policy, Overall calculation,
  metadata, database schema or runtime dependency change.

Supplied-data tag examples (read-only):

| Tag | Previous Impact | New Impact |
| --- | ---: | ---: |
| pop | 1731.00 | 1203.17 |
| catchy | 2011.70 | 1210.90 |
| chorus | 1904.91 | 1214.53 |

Tag range is now approximately 1187.76–1214.53 versus 434.97–2011.70. These are
values from the supplied snapshot; a live database recalibrates its own values.

Validation: **485 Python tests**, **1,587 JavaScript assertions**, policy parity,
new/flat/mature/growing collection cases, and **148 live server/browser
projection checks** pass. See [current validation](../docs/VALIDATION.md) for scope.

##### Install V4.1.4

Stop the completed V4.0/V4.1 app, merge this patch's `Song_ranker` files into the
matching folder, restart and hard-refresh. All earlier V4.1 updates are included.
Existing data stays in place; rankings recalculate without a migration or reset.


#### V4.1.3 — expanded fill-only metadata

18 October 2026 · cumulative over completed V4.0 and all prior V4.1 patches.

- Kept Scan → review → Back up & fill matched blanks, cancellation and the
  downloadable report. Extended the same planner/API/standalone helper.
- Added exact song release dates with Apple origin and missing schema-13 source
  facts: Apple identities/links, duration, explicitness and disc/source positions.
  Song dates use the track date; album dates use the collection date.
- Existing source identities, known facts, local dates/positions and historical
  observations are preserved. Enrichment appends observations; conflicts remain
  unresolved. Multi-disc source data does not invent local track positions.
- Album matching/search handles removed trailing `- Single` / `- EP`, retaining
  unique artist/exact-art verification and other edition names.
- Unmarked content displays Not explicit, with source badges distinguishing an
  assumed default. Explicit/Cleaned values stay distinct; raw unknown flags are
  retained. No attached genre tags are added/changed.
- Local artwork, album/artist links, tags, previews, names, ratings and game facts
  stay unchanged. Expanded targets/source facts participate in stale-plan checks.
  Backup captures the full locked pre-write database; all fill writes are atomic.
- Review counts/details include song dates and source updates, and new-field-only
  plans enable Apply. Source summaries refresh after saving. Version remains on
  schema 13 with no new runtime dependency.

Validation: **477 Python tests** and **1,565 JavaScript assertions** pass. Twelve
new Python cases cover preservation, backup equality, rollback, repeat/no-op,
stale plans, matching/ambiguity, content flags, disc metadata and authenticated
review/apply/report. Seventeen new DOM assertions cover new-field-only plans,
escaped review values, save/error/no-op state and source refresh. Apple responses
are mocked; no live metadata fill was run on the supplied database.

##### Install V4.1.3

Stop the completed V4.0/V4.1 app. Merge this patch's `Song_ranker` contents over
the matching existing folder, restart and hard-refresh. Keep existing data.
All prior V4.1 changes are included. See `INSTALL_V4_1_3.md` in the patch.


#### V4.1.2 — stats, tournament Elo history and selection health

18 October 2026 · cumulative over the completed V4.0.0 app, including V4.1.0/.1.

- Match History, Voting Stats, song history embeds, Dev history and Global Stats'
  recent activity now include active first-round Tournament Elo. Rows identify
  the bracket, mode, half/full influence and saved public Elo changes. Corrected
  events use replayed ratings; voided events stay out of the active feed.
- Added source filters and full-history pagination without changing ordinary
  win-rate, lifetime vote or selection exposure denominators. Embedded song
  filtering happens before its ten-row display limit.
- All six stats dashboards share a 14-day UTC chart, current/previous week
  numbers and exact daily data. Voting, Trivia, Guesser and Shelves add pooled
  rate trends. Missing evidence remains unknown; zero dates remain visible.
- Added public Elo source mix and tournament full/half influence figures.
  Shortened captions and folded supporting calculation notes into disclosures;
  retained existing records, rankings, grades, colours and dark-panel styling.
- Added Dev → System → Selection health: data coverage percentages, live eligible
  and tested pools, production ratios, current Guesser targets, Shelves formats
  and a searchable/paged per-record weight inspector. Snapshot refresh is
  read-only and late requests cannot replace another view.
- No schema or scoring change. Named production weight constants retain the
  same values/math. The existing database and frozen questions are preserved.

Validation: **465 Python tests**, **1,548 JavaScript assertions** and **149 live
app integration checks** pass using disposable/copied data. All 19 Dev sections,
six stats pages, full history and song history load with actual modules/assets.
See [current validation](../docs/VALIDATION.md) for coverage and environment limits.

##### Install V4.1.2

Stop the completed V4.0/V4.1.0/V4.1.1 app. Copy this patch's `Song_ranker`
contents over the matching existing folder, merge/replace files, restart and
hard-refresh. Keep existing data. This changed/new-file patch includes the prior
V4.1 updates; it is not a standalone app. See `INSTALL_V4_1_2.md` in the patch.


#### V4.1.1 — concise game screens, background previews and tournament Elo reveal

18 October 2026 · cumulative over V4.0.0, including the V4.1.0 Dev refinement.

- Removed general rule/policy paragraphs, scope-menu descriptions, repeated Elo
  influence captions, historical-record explanations and keyboard hints from
  play screens. Trivia keeps a short frozen streak target, field percentages,
  scores and result feedback. Useful readiness, progress and errors remain.
- Moved Result speed and Prepare next round into a small clock menu beside
  volume. It stays outside the play area, fits the viewport, closes on outside
  click/Escape and retains browser settings. Closing it does not pause Trivia.
- Switching browser tabs no longer pauses voting, tournament, podium, Trivia or
  workbench previews. Explicit pauses remain paused on return. A fade already
  underway waits while hidden; normal page navigation still releases audio.
- Active Trivia keeps the 30-second clock running with its background audio.
  Pause/Escape still pauses both. Hidden expiry saves once and leaves the result
  ready for return without silently starting another question.
- Eligible tournament first rounds reveal Tournament points, then both songs'
  saved public Elo before/after and signed changes. Total reveal is 7.5s Standard
  or 4.4s Quick (points stage 2.8s / 1.6s). Later/bronze/legacy points-only rounds
  keep 4.5s / 2.2s. Stage changes preserve audio; Next cancels both stages.
- Tournament saves/retries now expose their existing immutable public Elo
  receipt. Values are the saved result, rather than recomputed from today's
  ratings. No schema, scoring, K-factor or selection change.
- Updated version/cache keys, game style decisions, README, technical guide,
  regression coverage and installation notes.

Validation: 99 targeted Python tests and 628 JavaScript assertions pass. All
five game entry points/settings/assets load on copied data. Source DB unchanged.
See [VALIDATION.md](../docs/VALIDATION.md) for scope and browser/device limits.

##### Install V4.1.1

Stop the completed V4.0.0 or V4.1.0 app. Merge the contents of the ZIP's
`Song_ranker` folder into the matching existing folder, replacing the supplied
files, then restart and hard-refresh. The cumulative patch includes V4.1.0 Dev
files and contains no database, SQL dump, signing key or backups.

#### V4.1.0 — developer dashboard usability

18 October 2026 · first V4.1 patch · based on the completed V4.0.0 app.

- Standardised developer buttons and dialog actions: consistent readable text,
  44 px minimum targets, balanced padding, wrapping labels and keyboard focus.
  Search fields, selects and form fields now share a dark, readable treatment.
- Record tables keep Edit visible and put other tools in an expandable Actions
  group. Songs retain Stats, Tags & preview, Source, Make Single and Delete;
  albums retain Tracks and Delete. Other entity deletes remain available.
  Only one group opens at once; Escape or clicking outside closes it.
- Kept every table column/filter and the existing column chooser. Long values
  retain their full text and hover title. Grouping tools reduces action-column
  width without removing information.
- Added searchable artist/release/tag filters to Tags & previews and Bulk edits,
  plus searchable treatment for long select lists in Dev dialogs. Options retain
  counts and complete labels; type to filter, use arrows/Enter or a pointer, and
  Escape to dismiss. Native select values and form submissions remain intact.
- Simplified the tag workbench's initial filter area. Frequent filters stay
  visible; Artist, release & tag filters has its own expandable group and active
  count. Clear filters resets both the native value and picker caption.
- Moved the keyboard-focusable, bounded song list before the preview player and
  tag editor. Page selection, hidden selections, tag descriptions, Add/Remove/
  Replace, Before/After reviews, preview controls and backups are retained.
- Reviewed all 18 developer sections and applied shared layouts to heading
  actions, selection toolbars, explorer rows, record controls and dialogs.
  Fields collapse on narrow screens; wide data remains scrollable in its table.
- Bumped the app/footer/cache version to 4.1.0 and refreshed installation,
  dashboard, style and validation notes. No schema or gameplay changes.

Validation: 91 targeted Python tests, 378 JavaScript assertions and 81 live
integration checks pass. All 18 Dev sections load from a copied database.
The supplied DB hash is unchanged. Rendered browser/device QA remains a manual
installation check; details are in [VALIDATION.md](../docs/VALIDATION.md).

##### Install this patch

Stop V4.0.0. Copy the contents of the ZIP's `Song_ranker` folder over the
matching folder in your existing app, merging folders and replacing the files
provided. Restart and hard-refresh the browser. This is a source-only update:
it contains no database, SQL dump, key or backup. Keep your own data in place.
