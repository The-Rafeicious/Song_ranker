# Song Ranker — V4 complete update log


## V4.0.0 — completed release and step 8

**All eight implementation steps are complete.** This final release brings
V3.4.13 directly to V4.0.0/schema 13. It includes all 7A/7B/7C work; no intermediate
startup is required. This section is current; the patch sections below retain
their historical decisions, validation counts and then-next steps.

### Complete V4 change map

| Area | Delivered behaviour |
| --- | --- |
| Data foundation | One canonical schema and field dictionary; complete typed export, canonical new-file rebuild, exact reconciliation, pre-upgrade backup and verified recovery. |
| Preference integrity | Persisted browser-owned offers, one accepted receipt, immutable events, recoverable void/replace/restore and ordered replay. |
| Independent ratings | Shared Public Elo plus independent Blind/Non-blind streams replayed from 1200 at K32, with honest evidence/cohort comparisons. |
| Tournaments | Frozen prospective first-round Elo policy: full influence globally, half for scoped brackets; later/bronze points-only and legacy brackets retained. |
| Overall | Direct existing composite percentage, separate competition rank and score/weight/points/evidence contributions including neutral collection share. |
| Selection | Mode-specific completed exposure, live relative rating gaps, soft recency and feasible ten-track Shelf draws. No high-K spread setup or special artist/album rounds. |
| Challenge runs | Server-saved Trivia requirements at 10/25, progressively closer Guesser comparisons, frozen rules/answers and preserved separate classic bests. |
| Catalogue tools | Apple source/content/date observations, hidden existing matches, safer Singles moves, quick album tracks, tag/preview workbench and reviewed batch edits. |
| Dashboard/recovery/Git | Task shortcuts, complete DB inventory, exact downloads, signed stale-aware restore, SQL-only upload, safe retry and startup-only guarded updates. |
| Final experience/docs | Optional Quick pacing, one prepared question, continuous result display, hidden-tab handling, fewer full-library requests and reorganized documentation. |

### Step 8 behaviour

- Shared **Round pacing** disclosure on Standard/Blind, Trivia, Tournament,
  Guesser and Shelves. Standard is the default; Quick is browser-local and
  optional. Pair result waits change 4.5→2.2s, Trivia 5.5→2.8s; Shelf close/hold
  becomes 0.16/1s with faster score/subtotal transfers. Every track and per-album
  transfer remains visible, and the final value equals the saved result.
  Trivia's full 30 seconds, all points/selection rules and reduced-motion
  behaviour remain intact.
- **Prepare next round** reserves at most one JSON question after a confirmed
  save, keyed by mode. It starts no future audio/Trivia clock, shares one promise
  with manual/automatic advance, expires after 60s and observes a 12s request
  deadline. Quiet failures fall back to an explicit load. Offline, hidden,
  Save Data/2G and the off switch suppress preparation. Tournament already holds
  its bracket; no ordinary offer is created for it.
- Shelf next uses `fresh:false`, consuming the already prepared server round
  instead of deleting/rerolling it. Pending questions never count as completed
  exposure; backend checks cover all four preparing families.
- Next loads keep the prior saved result visible, disable duplicate activation,
  preserve scroll/height and provide retry errors. Unrelated preview-cache
  release requests no longer block next-pair JSON loading. Game result payloads
  supply current figures instead of fetching the whole catalogue after every
  vote/Guesser/Shelf answer. Catalogue edits still refresh normally.
- Hidden tabs suspend result/reveal timers with their remaining duration and
  stop result audio. Active Trivia requests a server pause and offers Resume
  when confirmed; a failed network pause remains subject to server elapsed time.
  Navigation/return cancels obsolete requests/timers and guards late responses.
  Fresh pair games/Shelves stay silent; started Trivia runs retain their existing
  automatic continuation.
- The main README is reorganized around install/play/scoring/Dev/recovery tasks.
  A separate technical guide owns architecture, formulas, selection/contracts,
  pacing and QA. The database guide retains its complete field dictionary and
  exact recovery/Git cases. Prior validation is preserved in its own history,
  with a concise current report. This log/index and roadmap now show completion.

### Final packages and checks

**Completed App** contains the complete edited application, tests, all available
release-family notes and guides, plus the supplied original DB unchanged. Extract
it into a new folder. **Cumulative Upgrade** contains all edited/new V4 files and
excludes DB/data dumps, backups, keys, dependencies, caches and Git state. Use
that package to retain an existing installation's more recent activity. First
startup backs up/upgrades schema 8–12; schema 13 is unchanged by step 8.

**456 Python tests and 1,338 JavaScript assertions pass**, including the new
five release/preparation endpoint cases and 61 real-module pacing assertions.
The 507-song copied-data checks, exact SQL/JSON round trips, local Git cases,
cold full/upgrade distributions, fresh-process recovery and local HTTP server
restart are verified. Original data bytes/facts and classic records are retained.
No real user Git remote or live Apple request was used. Media/DOM checks do not
establish actual browser paint, phone audio/autoplay or Windows process locking;
those remain installation play-tests. Full evidence is in
[VALIDATION.md](../docs/VALIDATION.md).


## V4.0.0.7.3 — step 7C: dashboard, recovery and Git

**Cumulative patch: steps 1–7 over V3.4.13. Step 7 is complete.** Intermediate
startup is unnecessary. Keep the live database, backups and private instance key.
Schema remains **13**; there is no new dependency. New build: **4.0.0.7.3**.

### Developer workflow

- Default Tasks & health panel with shortcuts to Apple import, untagged songs,
  missing previews/source links, album inspection and bulk editing. Upload to
  Git, Create backup, full export and Lock stay in the top bar across panels.
- Database inventory reads all actual tables/views, including extensions, and
  labels stored facts, projections and derived views. Backups have search,
  purpose/date/size, exact binary download and reviewed restore. Full JSON
  export and technical-guide downloads are direct actions. Reset tools retain
  their typed confirmation and sit in a collapsed advanced group.
- Restore review validates/migrates a temporary candidate and compares counts.
  A browser-owned one-hour signed review binds the complete backup and live
  contents. Applying it rejects newer activity or a changed backup, takes a
  pre-restore snapshot and verifies/rolls back through the existing recovery
  path. Successful restore refreshes catalogue/source caches. Reload other game
  tabs. Multi-worker recovery remains offline; the prior authenticated restore
  endpoint stays compatible.

### Git behaviour

- Opening the panel reads local state. Check remote fetches references only.
  The destination/branch, cached incoming/local counts and ten recent app
  outcomes explain what happened. Credentials are excluded from status/errors.
- Upload snapshots the full SQLite database, commits **only**
  `database_backup.sql` and pushes the explicit configured branch. Unrelated
  staged/worktree edits are preserved. Unpublished code commits, incoming or
  diverged history, conflicts and changed target reviews block with guidance.
  Failed/lost push replies keep the local commit; retries reconcile with the
  remote and unchanged snapshots create no duplicate. No row merge, rebase or
  force-push is added. Unsupported Git setup is explicit.
- Full-data tests exposed the standard dump's hidden-row-ID loss. The new SQL
  transport retains those IDs, exact floats, NUL text/BLOBs, extension objects
  and deleted-ID sequences, then reconciles a real restoration before publishing.
- Startup updates run **before application imports**, make a database backup,
  allow only a guarded fast-forward and start a fresh Python process. Local
  edits/staged files, incoming database/private files or outside-folder changes
  block installation. Dirty generated SQL is archived before replacement and
  recovered if applying fails. An application failure/busy Git task stops boot;
  unavailable Git/remote otherwise keeps local startup available. Existing live
  data always wins over pulled SQL; a missing DB uses validated SQL bootstrap.
- Root ignore rules protect new data/private/generated files without removing
  already tracked files. App Git operations serialize through an OS lock; local
  Git metadata holds outcomes and at most ten updater SQL archives. User `.db`
  backups are retained. The [technical guide](../docs/DATABASE.md) covers cases.

### Validation and next step

**451 Python tests and 1,277 JavaScript assertions pass.** New coverage includes
29 actual temporary-local Git tests, 19 dashboard/recovery HTTP tests and 88
actual-module dashboard DOM assertions. Full 507-song copied-data recovery,
schema-8 review/restore, exact exports/rebuilds, pending-offer resumption and SQL
upload/restoration pass. All original facts and source database bytes are kept.
The cumulative ZIP is overlaid on the original V3.4.13 snapshot, upgraded cold
and checked across a fresh application process. No real user remote was touched.
Apple/audio/device/browser-paint and Windows-host testing remain release checks.

**Next: step 8**, mode pacing, bounded prefetch, final documentation consolidation
and combined release checks. No new decision is required to begin; retain the
accepted scoring, K32, optional faster pacing and no automatic fresh-round audio.


## V4.0.0.7.2 — step 7B: tag and preview workbench

**Cumulative patch: steps 1–6 plus 7A/7B over V3.4.13.** No intermediate startup
is required. Keep your database, backups and private instance key. Schema stays
13; no dependency or table was added. **7C dashboard/Git controls is next.**

### Find, listen and tag

Editing → Tags & previews adds library-wide song/untagged/preview-URL counts,
search, tag/preview status, artist/release and has/missing-specific-tag filters.
Sort by tag count, title, artist or album; browse twenty rows at a time. Select
a page or all matching songs, with an explicit count of hidden selections.
Selections survive filters and single-song editing. Songs and Tags management
provide direct workbench entry points.

Tag & listen opens the song's actual tag set, with a manual preview through the
shared player. Previous/next preview follows the current filter/sort across pages;
it never changes the edit target. Playback continues while choosing/reviewing/
saving tags. Missing audio is explicit and stops the preceding track. Failed or
browser-blocked playback allows retry. Entry does not autoplay; end does not
loop/advance. Leaving or hiding the workbench stops audio. Unsaved choices need
review/reset or explicit discard before switching song. Source review stays
available for checking a missing/bad preview.

### Reviewed bulk changes

Add keeps other tags; Remove changes only selected memberships; Replace uses
exactly the chosen set, including an explicitly empty set. Existing tags are
searchable by name/description. Comma-separated new names reuse normalized
existing names; new definitions are created only at save. Existing spelling/
descriptions remain intact. The Tags editor still handles those details.

Review shows every song's title/artist/release/ID and Before/After tags, total
changes and paged rows. The old bulk-tag controls use the same review. Saves bind
the reviewed targets, make a consistent backup and apply only membership deltas.
Song/tag edits invalidate stale reviews; ordinary voting does not. Reviews are
browser-owned and expire after 24 hours. Concurrent/repeated saves do not duplicate
tags/links. A retry reports Already matches when the result is already present,
without another backup. A failed screen refresh is distinguished from save failure.
New target IDs remain selected after a lost-response recovery.

Only tag definitions/memberships change. Song IDs, metadata, Elo, exposures,
saved answers and game records remain exact. Current tag-based reports follow
their new memberships. Restore backup now accepts the new tag backup prefix and
7A Singles/source-refresh backups. No review/audit table or grading change is added.

### Validation

**403 Python tests and 1,189 JavaScript assertions pass**, including 30 new backend
tag checks and 110 workbench assertions using the actual site/shared preview code.
A copied 507-song library passed 50-track additions, single-song replacement,
25-track removal, cross-browser stale-review refusal, backup creation, full
export/rebuild and pending-round recovery. All 427 original vote facts and classic
best 221 remain intact. See [validation](../docs/VALIDATION.md) for scope/limits.
Clean distribution overlay, direct upgrade and fresh-process recovery are checked.

Next: **7C dashboard polish, backup/Git task controls and clear sync outcomes**.
No new user decision is required. Step 8 retains pacing and final combined checks.

## V4.0.0.7.1 — step 7A: reviewed imports and easier Singles

**Cumulative patch: steps 1–6 plus 7A over V3.4.13.** Keep the app stopped until
the remaining upgrades are ready if preferred. This is the first of step 7's
three subpatches: 7B tags/previews and 7C dashboard/Git remain. Schema 13 upgrades
directly from 8–12 with a consistent backup and stored-fact reconciliation.
No runtime dependency was added. Keep your database, backups and private key.

### Import and version review

- Apple text searches request 100 tracks, album links up to 200. Duplicate Apple
  IDs are removed. Cards show twenty at a time, hiding library matches initially
  with counts and a Show library matches switch. Exact song links reveal their
  result. The store is explicit; a link uses its own store.
- Confirmed Apple ID matches and possible title/artist matches are labelled
  separately. Review a version before linking, or explicitly Add separately.
  An Add retry for a current saved Apple ID returns that existing song.
- Display available date, duration, original album, disc/track position and Apple
  links. Advisory flags remain Explicit / Cleaned / Not explicit / Unknown.
  Censored titles never imply cleaned audio; radio-edit text is only a title hint.
  Multi-disc numbering stays visible without inventing flattened positions.
- Query/results and selected tags can remain between additions. Add as hidden
  Single skips the later manual album move. Requests use the existing Apple
  adapter/throttling; missing data and network errors are not fabricated away.

### Sources, song dates and album work

Songs have a Source action and Needs Apple source link filter. Source review
shows local/current/candidate facts and saved observations. Saving a source
defaults to keeping local names, preview and album. Refresh local metadata and
Use Apple's album/position are two separate opt-ins. Refresh makes a backup,
keeps IDs/ratings/custom tags and does not rewrite saved answers. A catalogue
change during review requires reopening it; ordinary votes do not invalidate it.
Verified browser-owned lookup offers expire after 24 hours.

Schema 13 adds per-song release date/origin and append-only Apple observations.
Old songs initially have unknown song dates and unlinked source identities;
existing album dates are unchanged. Similar names never invent source identity.
The latest observation is current; relinking keeps earlier observations. Unchanged
current facts are not duplicated. Existing whole artist names, including commas,
are preserved; known collaborations split only when the composition is unique.

Make Single shows the destination and carried date before Back up & move.
Date priority is song, current Apple observation, previous album, then unknown.
The destination follows Song title - Single, with a distinct name on collisions.
The local track number clears; original source numbering remains. Optional empty
album cleanup protects saved Shelf links, other tracks and declared extension
references/custom album rules. Repeated moves are harmless. Albums' Tracks action
provides an ordered quick check with dates, source flags, manual previews and
Source/Make Single actions. The song editor has a separate release-date field.

### Validation and next work

373 Python tests and 1,079 JavaScript assertions pass. A supplied-data copy kept
all 427 vote facts, classic best 221 and every saved game fact through linking,
explicit refresh and two date-carrying Singles moves. Full export/rebuild resumed
the same pending ordinary and challenge offers. Clean cumulative overlay and a
fresh server restart are checked for distribution. See [validation](../docs/VALIDATION.md)
for scope and limitations. The shipped patch contains no database or data dump.

Next is **7B: preview/tag inspection and bulk changes**, then **7C: dashboard,
backup and Git controls**. No additional decision is needed before 7B. Step 8
retains pacing, final documentation consolidation and combined real-device checks.

## V4.0.0.6 — step 6: progressive Trivia and Elo Guesser runs

**Cumulative patch: steps 1–6 over V3.4.13.** The app can remain stopped until
the remaining upgrades are installed. Schema 12 upgrades directly from 8/9/10/11,
with a pre-upgrade backup and full stored-fact reconciliation. No runtime
dependency was added. Keep your database, backups and private instance key.

### New play

Trivia and Guesser now use database-owned runs per browser and mode. Current
score/streak no longer depends on cookie counters. Reload/restart resumes the
same pending question with the same browser session. Concurrent tabs share it;
an answer updates the result and run closure atomically. A miss closes the run,
and the next question starts at zero. Global bests remain shared.

| Starting Trivia streak | Required to extend the streak |
| --- | --- |
| 0–9 | Any correct available field. |
| 10–24 | Song or album. |
| 25+ | Song and album. |

Without a proper album, 10+ requires song alone. Artist answers still earn their
unchanged points. Title/album spelling tolerance, bracket handling, field timing,
weights and no-album normalization are retained. A partial answer can earn
points while ending the streak. Each modern offer freezes answers/artist
variants, album eligibility, starting streak and the named requirement.

Guesser uses target gap quantile **0.60 / (1 + streak / 10)**. Its existing
exposure/kernel/recency rules favour closer comparisons as the streak grows,
with randomness retained. Each offer freezes its target, rules, run and both
ratings; later Elo changes do not alter the answer. Correct/missed answers still
earn 1/0 points. Identical modern retries count once; opposite retries conflict.

### Records and developer controls

Existing results are explicitly classic, with no invented historical runs.
The saved classic records, including 221, remain separate and unchanged. An
unfinished classic question can finish with its original rule before starting
a new challenge. Game, Home, Global Stats and detailed stats show challenge bests
and a separate classic line; accuracy still pools completed answers from both.
History labels its rule set and uses its own saved streak. Manual record editing
is explicitly for classic bests.

Modern Trivia snapshots/results survive track removal; missing identities do
not create broken links. Individual progressive answer deletion is refused to
keep run chronology intact; field-total adjustments are still available.
Explicit per-mode/full resets remove the affected rounds and runs together.
Exports/rebuilds retain pending questions, ownership, targets, progress and bests.

### Verification

- **336 Python tests** and **958 JavaScript assertions** pass. Coverage includes
  10/25 boundaries, no-album fallback, partial points, frozen metadata/ratings,
  independent browsers/modes, simultaneous tabs/retries, resets, classic pending
  questions and current/schema-11 SQL-dump restore.
- **19,200 progressive Guesser draws** across eight seeds pass, plus 100 affine
  rating checks. On the supplied 507-song fixture, median gaps fell from 29.83
  Elo at a fresh streak to 3.81 at streak 50; no fixed Elo cutoff is used. The
  same 400-question batches each covered at least 419 distinct tracks.
- The 284 surviving detailed Trivia results backtest to a best of 220 with
  classic requirements and 46 with progressive requirements. This is an offline
  comparison, not a conversion of the separately saved 221 record.
- A copied-database HTTP play-through covered 60 ordinary votes, four tournament
  scopes, 30 Trivia rounds, 21 Guesser answers and ten Shelves rounds. All 427
  original vote facts and original completed game facts remained unchanged;
  exposure deltas and frozen answers reconciled. Pending challenges resumed
  after a full export/rebuild. Supplied and working-source DB bytes are unchanged.
- Browser DOM checks cover challenge/result controls at 320/360/390/430/568/768/
  1280 px configurations. These are not device paint or Safari/audio checks;
  combined real play remains the step-8 release gate.

The optional offline checks are in `tools/selection_lab/run_challenges.py`.
**Next: step 7**, developer workflow improvements in three subpatches. No new
decision is required before starting.

## V4.0.0.5 — step 5: adaptive selection across modes

**Cumulative patch: steps 1–5 over V3.4.13.** You can keep the app stopped until
the remaining steps are installed. Retain the database, backups and private key.
Schema remains 11; earlier-step migrations still handle 8/9/10 directly. There
is no new runtime dependency. The optional simulation kit uses its own NumPy QA
requirement and never opens the app database.

### Selection behaviour

All modes now use the accepted below-average exposure rule. Need is one plus
any shortfall below the eligible pool's mean count. Base probabilities mix 90%
normalised need with 10% uniform exploration. Zero-play entries participate in
the mean; no separate placement boost or count threshold is added. References
are calculated for the currently eligible mode/scope, rather than forcing the
user to play modes equally often.

- Ordinary voting reads that mode's effective ordinary appearances, rather than
  combined match counts. Public Elo remains the common gap reference. The gap
  scale uses IQR, then the wider 10–90% span, then distinct-rating gaps. A broad
  opponent component remains. Two fresh songs replace the last offered pair
  when feasible; small pools relax that restriction. Persisted pending offers
  and retry receipts retain their step-2 behaviour.
- Trivia draws from completed/adjusted exposure in the preview-only pool and
  avoids an immediate repeat when possible. Pending rounds resume and do not
  manufacture attempts. Grading, points and classic streak rules stay intact.
- Tournament fairness uses saved **entries**, including unfinished brackets,
  rather than matches survived. Draws are without replacement in the selected
  scope. Existing champion-first seed spread is retained; seed noise now scales
  with the live eligible Elo span. Entry count/read/draw persistence is one
  transaction, including concurrent creation. First-round Elo/points follow the
  already frozen full/half policy; no high K or special artist event is added.
- Guesser uses completed comparison counts, distinct public Elo and gap midranks.
  Classic live play uses the 60th gap-percentile target, a broad component and a
  soft quarter-weight last-pair cooldown. The old fixed 40–250 Elo band is removed.
  Offered ratings still decide the answer even if live ratings change later.
  Progressive difficulty is held for the versioned runs in step 6.
- Shelves balances albums first and tracks within each selected album. Recency
  follows eligible albums / albums drawn, replacing the fixed five-round window.
  Completed frozen membership defines album exposure. Feasible fresh albums
  avoid the last round; capacity lookahead always reserves room for ten unique
  tracks, with at least two per chosen album. Two/three-album automatic draws
  remain equally likely when both are feasible. Existing order/membership
  grading, track-number gaps and non-proper-album exclusions are preserved.

`selection.py` owns the pure policies and `selection_data.py` reads shared counts
and recency. No parallel selector counter is stored. Game transactions bind the
read snapshot to persisted questions/draws. Preference selection loads only IDs
and Elo for the pool, then hydrates the chosen pair. Shelf capacity lookahead
uses the largest remaining capacities without repeatedly sorting every remainder.

### Verification

**305 Python tests and 836 JavaScript assertions passed.** The 41 new pure and
endpoint regressions cover zero/large/imbalanced counts, exploration, scaling,
recency fallbacks, tied/invalid ratings, distinct Guesser answers, scope and
preview eligibility, entry counts, concurrent bracket creation, feasible Shelf
allocation, pending/retry behaviour, frozen answers and classic records.

The deployed helper run passed **1,205 simulation/invariant checks**, including
500 seeded production/prototype parity checks. It reproduced the original
eight-seed workloads (354,400 questions and 3,200 bracket draws) with no reported
statistical difference above 1e-10. Median exposure variation, lower being more
even, was:

| Mode / unit | Previous | Adaptive | Reduction |
| --- | ---: | ---: | ---: |
| Non-blind appearances | 0.3331 | 0.2076 | 38% |
| Blind appearances | 0.3427 | 0.2127 | 38% |
| Trivia attempts | 0.3245 | 0.2164 | 33% |
| Tournament entries | 0.2997 | 0.1884 | 37% |
| Shelves albums | 0.1353 | 0.0521 | 61% |
| Shelves within-album tracks | 0.1399 | 0.0980 | 30% |

Growth, heavy imbalance, live K32 updates, affine rating changes, tied/small
pools and infeasible layouts remained covered. This is the accepted overall
balance/variety policy, not a claim to win every extreme-imbalance metric.

On a copied supplied database, 30 votes per ordinary mode, four tournament
scopes, ten Guesser comparisons, ten Trivia rounds and ten Shelf rounds passed.
Exposure deltas were exact. Existing 427 vote facts and completed game facts
remained intact; current first-round influence, frozen answers, classic streaks
and grading stayed correct. Export/rebuild reconciled all state and reproduced
seeded draws. The original and working database files remain unchanged.

The optional [experiment kit](../tools/selection_lab/README.md) ships with its
anonymous feature snapshot and separate QA requirement. Classic-mode difficulty
is unchanged by the offline future-stage tests. UI/audio pacing still follows
step 8, and real desktop/phone/audio play remains a combined release gate.

**Next: step 6**, versioned Trivia/Guesser challenge runs with separate classic
records. The accepted 10/25 Trivia requirements and Guesser target curve already
settle the defaults; no new decision is needed to start.

## V4.0.0.4 — step 4: direct Overall scores and clearer mode contributions

**Cumulative patch: steps 1–4 over V3.4.13.** Keep the app stopped until all planned
steps are ready if preferred. Copy these files over the project, retaining the
database, backups and private key. Earlier-step migrations still upgrade schemas
8, 9 or 10 directly to 11; this step adds no schema change or dependency.

Overall now displays its **existing evidence-adjusted composite** directly.
The final rank-based 2–98% transformation is removed. Real gaps, exact ties,
true endpoints and unknown values stay consistent across Home, profiles, Global
Stats, Rankings and Dev. Scores display to two decimals; full precision determines
order. A lone measured composite keeps its value rather than becoming 50%.

Rank is a separate category standing: one plus the number of higher measured,
eligible composites. Exact ties share competition rank (1, 1, 3), including Bottom.
Existing evidence/name/ID tie-breaks retain deterministic ordering within a tie.
Very small differences may look tied after display rounding. The old
`rank_percentile` fields remain diagnostic API metadata, without a display role.

### Mode balance

The existing disclosure now separates **Adjusted score, Effective weight,
Contribution in Overall points, and Relative evidence**. Each mode's bar follows
its adjusted score and semantic colour. In collections, mode inputs use each
song's actual allocation and effective weights include collection confidence.
A visible neutral share accounts for the remainder, including unrepresented
untested tracks. All unrounded contributions add to the existing final composite.
Underlying mode/metric calculations, weights, priors, evidence and saved results
are unchanged; the new fields are response projections only.

Unknown Overall remains unavailable rather than receiving a fake neutral score,
and its main progress bar has no numeric state. Eligible unplayed mode inputs
are labelled neutral; entirely unavailable modes stay omitted. Relative evidence
is separate from performance. Native disclosure/keyboard behaviour remains, with
a 44 px target. Mode insets stack below 760 px and the main score spans the card
above its two context columns below 540 px. Dev explanation and lookup now show
the direct composite and collection arithmetic.

### Verification

**264 Python tests and 836 JavaScript assertions passed.** Fourteen additional
Python regressions cover gap preservation, separate tied ranks, full precision,
unknown/endpoint states, collection priors, mixed eligibility, reconciling
contributions and API/detail/refresh agreement. Ninety-six new Overall DOM
assertions cover all public mounts, Top/Bottom, Dev lookup, unknown vs zero,
neutral inputs, escaping, retry/disclosure behaviour and responsive rules.
Existing gameplay, preference review, profiles, search and ranking checks pass.

A copied supplied snapshot compared **777 entity records** against step 3.
Every composite, original input, allocation, evidence value, collection prior
and category ordering remained exact. All collection contribution displays
reconciled. The direct ranges on that snapshot are:

| Category | Tested, eligible | Direct score range |
| --- | ---: | ---: |
| Songs | 482 | 34.98–75.81% |
| Artists | 59 | 48.99–56.75% |
| Albums | 62 | 45.96–56.54% |
| Tags | 54 | 49.60–56.19% |

Each category previously displayed 2–98%. The new values preserve its existing
calculated distances. API/details/refresh and 11 relevant HTTP routes passed,
and Overall requests left the copied database unchanged. The original/working
databases remain unchanged. Final package checks cover clean cumulative startup,
file hashes, archive integrity and preservation of the supplied source files.
No real browser/phone paint or audio check is claimed; those remain part of the
combined release play-test.

**Next: step 5**, implementing the already tested adaptive match selectors.
No additional decision is needed before that step.

## V4.0.0.3 — step 3: independent Elo and prospective first rounds

**Cumulative patch: steps 1–3 over V3.4.13.** Copy these files over the project
when ready, retaining your database, backups and private key. You can keep the
app stopped until every upgrade step is installed. First launch backs up and
migrates schema **8, 9 or 10 → 11** directly; no intermediate launch is needed.

- Public Elo stays intact on upgrade. Independent Non-blind/Blind ratings each
  start at 1200 and replay effective saved votes in event order, at ordinary K32.
  Every new eligible vote updates public Elo and exactly one mode atomically.
  Public manual overrides/legacy anchors do not alter independent mode ratings.
- Song profiles show both ratings and counts. Artist/album/tag comparisons use
  the same distinct tracks rated in both modes, with equal track weights and
  visible cohort coverage. Existing public Impact/current Elo stays unchanged.
  Voting Stats adds signed Elo gaps with both sample sizes and first-round counts;
  the lists require three rated votes in each mode. Unplayed ratings are unavailable
  in the UI. These are observed differences, not proof of bias.
- New brackets freeze full first-round influence for whole-library scope and
  half for Artist/Album/Tag scope. Effective event K is 32 × influence; no high-K
  placement is used. Public plus the bracket's Blind/Non-blind stream update.
  Later rounds and bronze use tournament points only. All old brackets, including
  unfinished ones, retain points-only behaviour. Old tournament Elo is not added.
- First-round results have one immutable preference fact linked to historical
  bracket/match IDs. Match/points/event/ratings commit together. Same-result
  retries count once; opposite retries fail. Tournament events stay outside
  ordinary history, win rates, match counters and ordinary exposure totals.
- Deleting/resetting a bracket voids its Elo influence and replays ratings while
  retaining original preference facts. Dev review identifies tournament origin
  and explains its protected correction controls. Existing podium corrections
  affect later rounds and do not produce Elo. Vote corrections, catalogue deletion,
  manual public overrides and full export/rebuild remain compatible.

### Policy checks

The read-only shadow command `python tools/validate_v4_elo.py BACKUP.db` replayed
427 ordinary votes plus 72 historical first-round results, 36 restricted.
All-full influence moved a song by at most **42.0003** Elo relative to ordinary
votes alone; restricted-half reduced that to **31.3882**. Mean absolute movements
were **4.2426** and **3.2299**. A 100-repeat pair stress test gave spans of
**616.7772** at full influence and **490.1447** at half. All runs conserved rating
mass. Each entrant had at most one rated comparison per bracket. These checks
support the fixed full/half default without claiming to remove opponent bias.
No hypothetical historical tournament result is written to the upgraded database.

### Validation and next step

250 Python tests and 740 JavaScript assertions passed. Copied supplied data
passed direct 8/9/10-to-11 upgrades, exact preservation of existing public
projections and all 427 vote records, independent reference backfill (259
Non-blind / 168 Blind), retry/rollback/correction checks, 28 HTTP routes,
tournament-only deletion reversal and exact export/rebuild. The supplied
original and working database files were not modified. No new dependencies.
Browser/phone paint and real audio checks remain for the combined release;
DOM/media fixtures do not replace those checks.

**Step 4 is next:** display the existing Overall composite directly, preserving
raw score gaps and explaining mode contributions. No new decision is needed.
Selection, challenge difficulty and pacing still follow the later planned steps.

## V4.0.0.2 — step 2: reliable preferences and recoverable corrections

**Cumulative patch: steps 1 + 2 over V3.4.13.** The app may stay stopped until all
stages are complete. The latest download includes all earlier changes and
migrates schema **8 or 9 → 10** at first launch; no intermediate start is needed.

Previously, a timed-out vote could be sent again as a second independent result.
Now the server persists the offered pair/mode and accepts one outcome for that
round token. The same retry returns the saved original receipt. A competing
choice is rejected, and the game can reveal the already saved winner after a
lost response. Mode, origin and rules version come from the server's offer.
Offers are bound to the browser session, survive refresh/restart with that
session, and keep one pending ordinary round per browser/mode.

### Stored facts and shared projections

- Existing history IDs and all nine original vote fields move intact to
  `preference_events`. Original labels are retained with legacy provenance and
  rules version 0; missing historical offers/modes are never invented.
- `history` becomes a compatible nine-column view of active ordinary outcomes.
  Existing reports, profiles, rankings and Overall inputs read the same source.
- Preference saving, count/rating updates, offer closure and the receipt facts
  commit together. Concurrent duplicate/opposite submissions cannot save twice.
- `mode_exposures` and `shelf_album_exposures` define recorded appearances once.
  Pending quizzes are excluded; tournament exposure means entries, not match
  wins/rounds survived. Per-song exposure totals are available in collection JSON.
  Selector policies themselves remain for step 5.
- Dev Match History → Review saved votes offers a paged audit with original
  choice, active/voided state and correction notes. Void, restore and winner/mode
  replacement append recoverable corrections. Stale revisions/fingerprints and
  reused request keys cannot overwrite another change. Current Elo/counts and
  effective rating snapshots rebuild atomically; original snapshots stay intact.
- Match History labels affected rows Corrected/Recalculated. Manual Elo changes
  are also durable, retry-safe ordered overrides, so replay does not erase them.
- Song removal backs up the catalogue, voids vote influence, preserves original
  receipts/correction IDs and rebuilds surviving ratings. It no longer drops
  vote facts and spreads the removed rating arbitrarily. Historical offer/pair
  IDs remain stored even if their catalogue records are removed.

The supplied history replays exactly from 1200 at K32 and is fully correctable.
If another installation's older ratings/snapshots cannot be reconstructed, its
current values become an explicit legacy anchor instead of being reset or
silently guessed. Pre-anchor votes are protected from edits; new votes and
recorded rating overrides can still be replayed. Existing peak Elo/rank records
are retained as legacy floors; post-upgrade peak projections can be rebuilt.
Frozen Trivia/Guesser/Shelves answers and classic records are unchanged.

### Installation and checks

Keep the current database, backups and instance key. When ready, copy the newest
cumulative patch over the project and start it. Do not install the supplied test
database: no database/SQL data dump/private key is included. First start creates
`pre_upgrade_*.db`, validates a candidate and performs the transactional upgrade.
Current-schema export/rebuild/restore also retains offers, corrections, overrides
and retry receipts. See [database reference](../docs/DATABASE.md) and
[validation](../docs/VALIDATION.md).

Step 3 is next: independent blind/non-blind Elo beside public Elo, then validation
of new first-round tournament influence through the same event path. Ordinary
voting remains K32; no high-K placement or special artist-event rounds are added.

## V4.0.0.1 — step 1: database foundations

Development patch over **V3.4.13**, schema **8 → 9**. This is the first of the
eight agreed implementation steps, not the completed public V4 release.

- One current `schema.sql` replaces scattered current table/view/index/trigger
  definitions. Compatibility modules read the same registry.
- Startup preserves an existing database. With a missing database, SQL recovery
  happens before empty schema creation, including without Git/under WSGI. Bad
  restoration leaves no empty published database. Optional startup Git pull now
  runs from the project folder before bootstrap.
- The schema-9 upgrade takes a consistent pre-upgrade snapshot and rebuilds in
  one SQLite transaction. Every stored value, row ID, deleted-ID high-water mark
  and view result must reconcile before commit. New song/Guesser/Shelves IDs
  gain non-reuse behaviour. Unknown ordinary extension objects are preserved;
  incompatible known columns or unsupported virtual tables are refused.
- `db_tools.py` provides read-only audit, full checksummed JSON export, new-file
  rebuild, new-file recovery and comparison. Sources and existing outputs are
  never wiped. Rebuild compacts storage without guessing metadata.
- Dev restore installs the migrated candidate that passed checks, saves a
  `pre_restore` snapshot and rolls back if post-install verification fails.
  A local maintenance gate drains app connections while keeping normal database
  reads/writes concurrent. Multi-process WSGI restore is refused; use offline
  recovery after stopping workers.
- Dev Overview includes the full table/view inventory and schema version. New
  manual Git dumps retain schema/application versions. No remote Git action is
  performed by installing this patch.
- [docs/DATABASE.md](../docs/DATABASE.md) is the schema/data dictionary and
  recovery guide. README and the existing V4 roadmap link to current owners and
  implementation status.

Public Elo, saved preference snapshots, quiz grading facts/times, classic
records, pending rounds, tournament history and catalogue source fields remain
unchanged. New selectors, split Elo, tournament Elo, revised Overall display and
harder challenge rules belong to later steps. No special artist-event mode or
high-K placement is included.

### Installation

Stop the app, copy the patch's `Song_ranker` contents over the project and restart.
Keep your own `song_ranker_v2.db`, backups and instance key. The footer should read
`4.0.0.1`. The startup migration creates `database_backups/pre_upgrade_*.db` and
upgrades your current database rather than installing the supplied test snapshot.
Use `python db_tools.py audit` if you want the full integrity/count report.

For rollback, stop the app and retain the failed/current database and sidecars
together. Restore the matching pre-upgrade database with V3.4.13 code, or create
a verified recovery file using the procedure in the database guide. V3.4.13 code
does not understand this patch's newer schema marker, so roll back code and the
matching database together.

### Validation

See [VALIDATION.md](../docs/VALIDATION.md) for the exact checks, copied-database counts
and limits. The update package contains only changed/new source, documentation
and tests; it contains no live/test database, SQL data dump, backup or private key.

### Step 2 defaults

Implement persisted offered-round tokens, one saved preference per offer,
idempotent retries, explicit mode/origin/rules versions and shared exposure
projections. Keep old history IDs and labels. Old votes without an offer token
remain valid legacy events; do not guess missing offers or modes.

Recommended correction behaviour: keep the original event and a recoverable
correction/void record, excluding superseded outcomes from active statistics.
That is a change from permanent deletion, so keep the user-facing Dev action
clear. It supports the already agreed durable-corrections requirement. No Elo
policy or selector constants need another decision before step 2.
