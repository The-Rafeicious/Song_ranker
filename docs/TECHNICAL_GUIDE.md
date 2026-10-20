# Song Ranker V5 technical guide

**Application 5.1.2.1 · competition database generation 3 · SQLite schema 17**

This is the current implementation reference. Installation is in the
[main README](../README.md); the one-time reset is described in
[UPGRADE_V5.md](UPGRADE_V5.md). Historical changes belong in
[update_logs/](../update_logs/README.md), not in the running app's help copy.

## V5.1.2 / V5.1.2.1 Spotlight

The preceding relative-placement update is V5.1.2. V5.1.2.1 refines its controls
and results without changing storage. `static/js/spotlight.js` owns allocation,
result order/positions and preview rotation. Target points remain
`3 + 12 * (position - mean_position) / 100`. The closest of 455 nonnegative integer
splits totaling 12 is chosen, respecting position order and exact ties. The
allocator is card-order/translation invariant. Small gaps may round to equal shares.

Browser drafts retain positions and selection; accepted receipts still contain
only four integer allocations. Next round first saves through the existing
idempotent endpoint. No points are shown before confirmation, including uncertain
retries. Old unconfirmed manual receipts keep their exact original payload.
Schema 17, rules version 1, support, adaptive selection and Overall calibration
7 are unchanged. Result playback never sends another judgement/listening sample.

Selection is explicit via metadata-bottom buttons or cover markers. Card and
preview clicks do not change it. A cancelable 1,500 ms idle timer follows each
changed placement, advancing to an unplaced song or the next card. Pointer drag
defers scheduling until release; edits restart it, selection cancels it, and
revisited songs can schedule again. Token/selection serials reject stale callbacks.
Saving, hiding, new offers and page exit cancel the wait.

The native rail remains under the cover markers, with a 760 px maximum width.
Collision groups use 14 px resting offsets; hover/focus spreads covers to 52 px
separation within the rail bounds. Distinct score groups occupy ascending rank
positions during results, with exact ties sharing a position. Pulse animation
alternates names to restart without forced layout and respects reduced motion.

Placement preview rotation retains 20/10-second Standard/Quick segments.
After confirmation, `resultOrder` sorts descending points with stable tied card
order. `createRotation` runs that player order with `repeat:false`, 2/1-second
snippets and a completion callback, followed by a 700/350 ms settle. Raw audio
nodes stay in offer-slot order, preserving receipt mapping; bar positions alone
move to result order. Waiting/seeking/paused time does not consume segments.
Manual Next cancels remaining playback and consumes the prepared offer.
A manual result loop stop completes the visual result; replay cancels pending
advancement and starts one fresh finite pass. Permission blocks leave results available for manual Play/Next; other failures
complete safely. Hidden pages stop playback and defer advancing via RoundFlow.

## V5.1.1.2 retirement and safe reuse

Schema 17 retires Sound Twins through `storage/mode_retirement.py`. Canonical
migration, JSON rebuilds and versionless SQL restores remove only retired
rounds/items, choices, listening and obsolete table/trigger definitions.
All other values, row IDs, extension objects and sequence high-water marks are
reconciled. The retired exposure view entries intentionally disappear. Normal
startup creates a verified pre-upgrade backup; safe startup upgrades only its copy.
Historical release logs retain the retired mode.

Safe identity uses `run_<24-character SHA-256 source-path digest>` beneath
`SONG_RANKER_SAFE_DIR` (default `data/safe_mode`). It adopts the latest valid
legacy marked run, then prunes only other marked runs for that same source.
Later launches validate/reuse the same database. Unmarked folders are preserved.
`--refresh-safe-mode` implies safe mode and rebuilds that same database from the
latest main snapshot, clearing test results. A temporary SQLite candidate is
checked before replacement; copy failure preserves the existing test database.
Backups/settings remain in the safe folder. Launcher locks, mode=ro source,
write/attach guards and disabled Git remain enforced. `/api/runtime-mode`
reports persistence/reuse. The backend smoke tool uses a disposable child copy
so synthetic decisions do not pollute persistent test progress.

## V5.1 launch and mode backend

`storage/safe_mode.py` configures launch identity before Git, Flask or schema
work. Safe mode reads the main database through SQLite mode=ro and routes writes
to one persistent test database per resolved source path. The normal launcher uses a process lock; WSGI requires one
worker. [UPGRADE_V5_1.md](UPGRADE_V5_1.md) documents the scope and test commands.

`modes/judgements.py` owns shared round transactions and idempotency; the two
mode files own answer rules. `judgement_selection.py` derives adaptive weights;
`reports/judgement_stats_data.py` derives reports without stored counters.
`judgement_api.py` registers the HTTP contract. Overall calibration
7 shares the preference family with Spotlight and reports descriptive Vibe
coverage separately from quality weights.

## V5.1.1 page and presentation contracts

`modes/judgement_pages.py` registers `/shared_spotlight`, `/vibe_map` and each corresponding `_stats` URL. Games use
`templates/judgement_game.html`; reports use `judgement_stats.html` and
`judgement_components.html`, alongside the established stats macros and styles.
`GET /api/mode-updates` now reports `backend_only: false` and each mode's play
and stats URLs. Existing POST and stats API contracts remain compatible.

`static/js/judgement_game.js` owns the two mode UI state machines: loading, editing,
saving, uncertain/retry, saved and unavailable. It requests/resumes a real offer
before rendering choices. Validation prevents incomplete point budgets, empty Vibe placements. A cell is never preselected as a
result. Grid coordinates increase right/up; radio cells and table tabs support
keyboard navigation. Tag reviews distinguish omitted themes from a reviewed
empty list. HTML text/attributes are escaped through `SongRankerUI.esc`;
server configuration uses Jinja's `tojson`.

A single session-storage draft per mode is keyed to the offered token. It stores
only this tab's choices and, when needed, the frozen pending save. An uncertain
save keeps inputs locked and retries exactly the same answer/listening payload,
including after refresh. Definite validation failures can return to editing.
Acknowledged saves remove drafts. Generation checks reject stale responses;
page exit aborts in-flight requests and cancels advancement. Browser back/forward
cache restoration requests the current offer again. Server receipts remain the
only result authority; browser drafts are never used by statistics.

The UI uses `PreviewPlayback` for user-started playback/ready handoffs,
`Listening.start/sample` once per offered/saved decision, and `RoundFlow` for
preparation, Standard/Quick result waits and visible-tab timers. It replaces
controls/status after saving while retaining existing audio elements. Next
consumes the prepared offer; no preparation starts audio or submits an answer.
All new play routes load the same navbar clock, preview and listening assets.

`reports/judgement_page_data.py` adapts `build_judgement_stats` in its caller's
read transaction. It hydrates current song/artist/album identities, preserves historical tag
labels with current tag URLs, builds the Spotlight allocation histogram and
pages/searches Vibe track descriptions. HTML history is ten rounds per page;
Vibe tracks are twenty per page. API history retains its own 1–50 size contract.
Reports show the first five Spotlight leaders, with up to 50 disclosed.

Global Stats renders mode summaries and includes one saved subjective round as
one recent item. The live mode blend and listening labels include both subjective modes.
Home shows seven mode cards and the Stats menu links to all dedicated reports.
The `spotlight-mode` text class avoids the older `.spotlight` record-card class.

Current schema is 17; calibration 7 and remaining selection rules are retained. See [UPGRADE_V5_1_1.md](UPGRADE_V5_1_1.md) for controls and
[PAGE_STYLE.md](PAGE_STYLE.md) for page composition and responsive rules.

## V5.1.1.1 display ownership

`home.css` owns the seven-card grid and automatic child placement. Obsolete
five-card spans, nth-child positions and sizing rules were removed from
`special_modes.css`; they no longer interfere with Home's four/two/one columns.
`navigation.css`, loaded before the final shared baseline, owns navbar spectrum,
17/16 px labels, the relative 28/25 px wordmark and responsive header rows.
Its single mode spectrum includes all eight accents, including Blind and the
two subjective modes. Both Home and menu entries use the same real emoji per mode.

The subjective-mode controller renders the shared `cover-button` / `play-overlay`
structure but retains its own `data-judgement-play` owner, so the site's
`data-audio` delegation cannot toggle the player twice. Audio events update both
ARIA and `data-playing` state. Shared preview readiness/loading styles remain
in use. Proper album names are escaped and URL-encoded, with Singles and Unknown
Album omitted exactly as on Standard Vote. Existing audio nodes and listening
samples survive result rendering. This patch changes no backend rules or schema.

## Architecture and ownership

`main.py` is both the direct launcher and the WSGI export (`main:app`). When run
directly, it finishes any configured Git source update before importing Flask
routes; an updated process re-executes before loading the new application. A
WSGI import bootstraps the database without running a source update or server.
Waitress is the normal local/private-LAN host.

| Package / directory | Responsibility |
| --- | --- |
| `songranker/services.py`, `paths.py`, `pages.py` | Flask app, single root-path owner, connections, shared hydration and page/library routes. |
| `songranker/catalog.py`, `impact.py`, `overall.py` | Distinct-song aggregation, adaptive collection Impact and the derived Overall composite. |
| `songranker/storage/` | Canonical schema, transactional migration, first-competition transfer, lossless transport, replay state and maintenance gate. |
| `songranker/modes/` | Offered questions, accepted answers, progressive challenge rules, Elo streams and pure selectors. |
| `songranker/reports/` | Read-only dashboard builders, activity series, selector diagnostics and stage-relative health labels. |
| `songranker/developer/` | Authenticated catalogue/source/tag tasks, metadata fill, corrections, exports, backups, recovery and Git. |
| `songranker/listening.py`, `static/js/listening.js` | One server measurement owner and one shared browser playback tracker. |
| `songranker/apple_access.py`, `lan_security.py` | Bounded preview access/cache/diagnostics and the private-network/request/session gate. |
| `data/schema.sql` | Only canonical runtime DDL registry. Historical test fixtures are not alternate runtime schemas. |
| `templates/`, `static/` | Shared HTML/macros and feature-owned scripts/styles; details in [PAGE_STYLE.md](PAGE_STYLE.md). |

No old root Python-module wrappers are needed. Imports explicitly use the
`songranker` package, so a merged installation works before obsolete root files
are removed. [FILES.md](FILES.md) and [TRIMMED_FILES.txt](TRIMMED_FILES.txt) map the
old locations. Application notes live in `docs/`; release-family logs remain in
`update_logs/`.

## Database lifecycle

The default live file is `data/song_ranker_v3.db`. `competition_state.generation`
must be 3; `PRAGMA user_version` must match the canonical schema. A database with
an unsupported/newer schema or an older competition at the V3 destination is
refused rather than silently overwritten.

First creation follows this order:

1. Reuse a verified existing V3 database.
2. If the configured/default V2 source exists, transfer its catalogue only.
3. Otherwise inspect a local Git `database_backup.sql`: generation-3 SQL restores
   its complete competition; older SQL contributes only catalogue data.
4. Otherwise use the full package's catalogue-only seed if present.
5. Otherwise create an empty catalogue and fresh competition.

An explicitly configured missing V2 source stops initial creation. It does not
block restarts once a valid V3 exists. The retained `SONG_RANKER_DB` filename
`song_ranker_v2.db` maps to a separate sibling V3 destination; other custom source
names use the separate `SONG_RANKER_LEGACY_DB` setting.

The catalogue transfer opens the source read-only, takes a consistent SQLite
snapshot, builds a private canonical destination and copies this whitelist:
`albums`, `artists`, `genres`, `songs` metadata, `song_artists`, `song_genres`,
`song_sources`. Exact carried values and ID high-water marks are verified. No
rating, result, manual score adjustment, pending offer, challenge, bracket or
analysis row is copied. New song ratings/peaks are 1200, match/win counters are
zero and highest-rank records use their unplayed default.

A no-overwrite publish makes the completed destination visible. Another startup
can win publication; the loser verifies and reuses that V3 file. Failure leaves
the source and completed archive available. Existing V3 launches never run the
catalogue reset. The source is not deleted. Full provenance/counts are saved in
`competition_state.migration_report`; public collection data exposes only the
competition generation and start time.

Runtime V3 rebuild/export/recovery remains lossless: all stored values,
relationships, implicit row IDs, application ID, sequence high-water marks,
views and supported extension objects are reconciled. Older-schema compatibility
lives in storage adapters for offline recovery; it does not import old results
into a new V5 competition. Normal Dev full restore requires a V3 competition
marker. See [DATABASE.md](DATABASE.md) for every table and field.

## Connections and transactions

App connections enable foreign keys and use a 30-second SQLite busy timeout.
The shared maintenance gate allows concurrent ordinary connections and reserves
exclusive maintenance for replacement/recovery. In-progress route work is not
replaced by a background database swap. Multiprocess live restore is refused;
stop workers for offline recovery instead.

Question creation and accepted answers use write transactions. Read dashboards
use one SELECT snapshot; their builders do not update counters or repair data.
Backups use SQLite's backup API so committed WAL transactions are included.
Scores are stored in their existing result facts/projections, not recomputed
from browser text. New analyses do not change saved outcomes.

## Preferences and Elo

Public Elo starts at 1200 and uses the retained logistic K32 policy:

```text
expected(A) = 1 / (1 + 10 ** ((rating(B) - rating(A)) / 400))
new(A)      = rating(A) + 32 * influence * (actual(A) - expected(A))
```

`influence` is 1 for ordinary votes and whole-library tournament first rounds;
it is 0.5 for selective artist/album/tag first rounds. Later rounds, bronze
playoffs and points-only brackets do not create preference events. There is no
high-K placement stage, forced rating range or health-based rating adjustment.

An ordinary offer freezes pair/order, owner, visibility mode, rules and identity
facts. The server validates the accepted choice against that offer. Its immutable
`preference_events` row is the submitted fact; projection rows are rebuildable
caches, not additional votes. Retries return the saved receipt once. Corrections
retain source facts and replay active effective outcomes and ordered manual
rating overrides. Histories label corrected/recalculated snapshots accordingly.

Independent Non-blind/Blind streams each begin at 1200 and receive the same
accepted event only in its saved visibility mode. Public Elo combines both.
Collection profile comparisons use the same distinct cohort rated in both
streams, with equal track means; they do not establish causal visibility bias.

`elo_history.source_sql` supplies active corrected ordinary and first-round
preference events. `catalog.voting_records` pools weighted wins/losses and
Standard/Blind evidence, with `ordinary`, `tournament` and `raw` breakdowns.
A full win plus a half-weight loss gives 1 / 1.5 = 66.7%. Raw match counts remain
two. Stored ordinary `matches_played` and compatibility views retain their
meaning; `elo_matches_played` is the combined raw count.

Selectors, Overall preference confidence, minimum rate samples and mode
comparisons use effective evidence. Actual history/source totals, daily activity
bars, repeated-pair occurrence and consecutive win runs count events. Elo
movement uses the already influenced saved deltas without halving them again.
Daily outcome percentage lines weight both numerator and denominator. Later
bracket points are not reduced by this preference-evidence policy.

## Game scoring

| Mode | Current rule |
| --- | --- |
| Trivia | A 30-second answer clock, paused explicitly. Song/artist/eligible-album field weights are 0.5/0.2/0.3, renormalised by 0.7 without an album. A correct field earns its weight × `(0.75 + 0.25 × (1 − seconds/30))`; points round to four decimals. Field accuracy pools correct available fields, independently of timing. |
| Trivia challenge | Below 10 streak: any correct available field; 10–24: song or album when eligible; 25+: song and album. Without an eligible album, song is required from streak 10 onward. The offered rule is frozen with the round. |
| Tournament | An 8/16/32-track champion's bracket path totals seven points before display rounding. Round points are `7 × 2**(round−1)/(size−1)`. Bronze awards half the semifinal value. Placement requires the completed bracket. |
| Elo Guesser | Choose the higher frozen offered rating. One correct point and a progressive streak. Target relative gap rank is `0.60/(1 + streak/10)`; frozen ratings are never replaced by current Elo when grading. |
| Album Shelves | Ten tracks across two or three proper albums. Correct album placement earns 0.5; correct relative-order comparisons earn up to 2.5 per track. Relative-order percentage is the primary accuracy; points retain their own saved denominator. |

Pending/prepared questions add no completed exposure, listening or result. A
prepared Trivia round starts neither the answer clock nor playback. Missing
identities remain explicit; reports do not invent answers or substitute current
ratings for absent saved snapshots.

## Stage-aware selection

All policy functions live in `modes/selection.py`; `selection_data.py` supplies
canonical exposure and recency projections. Pools are filtered for actual mode
eligibility before computing their mean. Ordinary exposures combine with
first-round preference weight only in the appropriate visibility mode.

For eligible exposure counts `c`, mean `m` and maturity `t = m/(m+4)`:

```text
strength       = 1 + 0.12*t
catch_up(c)    = (1 + max(0, m-c)) ** strength
recent_bonus   = 0.20 * exp(-age_seconds/(7*86400)) / (1 + c/(1+m))
weight(c)      = catch_up(c) * (1 + recent_bonus)
probability(c) = 0.08/N + 0.92 * weight(c) / sum(weights)
```

Imported tracks have `added_at=0`, so none gets a recent-addition advantage at
competition start. Future catalogue inserts are timestamped by the schema
trigger. “New” refers to catalogue addition, not a newer release date. Every
eligible entry retains a uniform exploration floor; a preview-quality flag does
not alter eligibility or the calculation. Equal counts/ages remain uniform.

Standard/Blind anchor draws avoid the previous pair when a complete alternative
exists. The opponent combines the same exposure support with Elo closeness:
`floor = 0.20 − 0.05*t`, closeness weight `1−floor`, and spread bandwidth
`1−0.15*t`. Closeness is `1/(1+(gap/scale)**2)`. Scale uses the current rating
IQR, then 10–90% span, then the median adjacent distinct-rating gap. This tightens
pairings modestly as evidence grows and remains relative to the live database.

Trivia excludes the previous track when alternatives exist. Guesser retains its
previous-pair multiplier 0.25 and the relative gap-target kernel (0.05 floor,
0.95 target weight, width 0.10). Tournament draws entries without replacement,
then uses the retained relative noisy seeding/champion spread. Shelves chooses
albums by exposure and recency with capacity lookahead, then distributes ten
tracks and draws within each album by exposure. All prepared questions remain
frozen even when the pool changes later.

## Health reporting

Selection health uses the same production eligibility, exposure and probability
functions. The table shows actual per-pool probabilities, recency exclusions,
mean, support strength and the current voting floor/bandwidth. Its starting
kernel card is explicitly a baseline, not a claim that all pools use that floor.

Balance dispersion is `population_stddev(exposure)/(1+mean)`. Empty pools are
Unavailable, no exposure is New competition and mean below one is Building
evidence. Above that, dispersion over 1 is Poor balance, over 0.6 Uneven, over
0.35 Fair, over 0.15 Good and otherwise Excellent. Coverage categories use the
actual eligible numerator/denominator; exact counts remain visible.

The Elo reference IQR is approximately `1.349 × 16 × sqrt(mean)` for an equal-rating
K32 random-result process. The displayed reference band is half to twice that
value. Mean exposure below two remains Still settling. Other labels are Compact,
Within reference and Wide preference spread. This is a stage-relative diagnostic,
not an “ideal” rating target: consistent preferences may legitimately make a
wider range. Health never changes Elo, grades or K.

The release simulations cover eight seeds, 3,000 draws each, V4/V5 comparison,
80 initial tracks and ten additions after round 1,500. The final policy improves
mature exposure balance and newcomer catch-up in that scenario; results and
limits are recorded in [VALIDATION.md](VALIDATION.md).

## Listening and private preview analysis

`static/js/listening.js` is loaded once on the eight game pages. A question begins
one measurement session keyed by mode and offered token/match. The tracker uses
media identity plus actual playback progress, capped by elapsed wall time.
Playing/time-update/pause/waiting/end/seek events distinguish audible progress
from preloads, pauses, buffering, muted audio and jumps through a clip. Shelf's
reused player updates its song identity. Reveals are not part of the submitted
sample. An abandoned round has no accepted measurement.

The accepted answer carries optional `{version, decision_ms, songs}` data. Server
callers supply the authoritative mode, reference and offered IDs; clients cannot
attach measurements to arbitrary tracks. Only a complete, finite, bounded sample
is inserted. Invalid telemetry is ignored without losing the valid game answer.
`UNIQUE(mode,reference,song_key)` makes samples idempotent. An unplayed track can
be a measured zero; a request without telemetry remains unmeasured. Measurements
are self-reported browser observations, not proof that the user heard the clip.

References identify `preference_events.id` for Standard/Blind,
`tournament_matches.id`, `trivia_rounds.id`, `elo_guess_rounds.id` or
`album_shelf_rounds.id` for other modes. `selected` records the original chosen
track for pair decisions, and is null for Trivia/Shelves. Corrections do not
rewrite observed listening or the original measured choice. Mode/full resets and
explicit round removals clear the corresponding measurements. Removed songs
leave their original `song_key` while their live foreign key becomes null.

Shared dashboards show measured decisions, track samples, total seconds and
sample-weighted mean seconds, with mode details in a disclosure. Profiles pool
linked songs once. New measurements have no influence on game grades, ranking
formulas or selectors.

`song_details.preview_bad`, `preview_note` and `flagged_at` are private Dev data.
Only authenticated quality/analysis/full-export endpoints return the annotations;
normal collection/library/profile/game responses omit them. Flagging does not
rewrite audio, tags, album placement or evidence. Dev analysis exports raw
observations and per-song summaries alongside flagged preview notes.

## Impact and Overall

Collection Impact uses one finite current Elo per distinct linked song. The
baseline is the current-library mean, and prior breadth is the median nonempty
peer collection size in that entity class:

```text
support = tracks / (tracks + prior_tracks)
impact  = library_mean + support * (collection_mean - library_mean)
```

Empty collections have no Impact/rank; proper albums alone participate in album
peer calibration. Values display to one decimal and sort at full precision.
All new songs start at 1200, so nonempty collections initially share 1200 Impact.

Overall retains five equally based game families: voting, Trivia, Tournament,
Guesser and Shelves. Voting's correlated Elo/Non-blind/Blind views split its 20
base points as 8/6/6. Only applicable tested evidence contributes. Current/peak
Elo split 85/15 within Elo; mode win rates, Trivia fields/perfect rounds, bracket
wins/podium/points and quiz/order accuracies provide the other metrics.

Relative evidence is 50% at the current mean sample count and 100% at its robust
high reference (90th percentile, with a fallback when flat). Rate calibration
mixes 60% actual rate and 40% population-relative position. Untested modes do not
become zeros or count as tested evidence. Collection aggregation includes its
confidence prior, keeps distinct songs and displays the composite percentage
directly. Rankings use competition rank for exact ties. Inspect each profile's
Mode balance or Dev Overall for the live unrounded weights/contributions. V5 does
not replace these formulas; it restarts their evidence.

## Reporting and presentation

Dashboard builders read one snapshot and preserve exact counts alongside rates,
source/mode splits, 14 UTC days, accessible daily tables and bounded recent
history. Unknown rates are `—`; undated/unavailable facts are explicit. Event
history filters are applied before limits/pagination. Category rates pool
numerators/denominators, not means of percentages.

Shared owners are `ui.js` for formatting/escaping/entity links, shared template
macros for repeated records/metrics, `mode_stats.css` for report geometry and
`site_baseline.css` for the accepted type/corner/spacing baseline. The baseline
loads last. V5's small additions live in `v5.css`; feature controllers retain
media/request/cancellation ownership. Styles preserve semantic mode colours and
entity-coloured names, green success and danger red failures. Phone breakpoints,
native disclosures, 44 px controls, complete accessible names and reduced-motion
behavior remain part of the baseline.

## Catalogue editing and imports

Schema 15 retains one source row per song. The backed-up upgrade selects the
highest previous source ID, preserves all of that observation's fields and
compresses its JSON with the versioned source codec. New relinks update that
row in place. Source/Single review fingerprints include the stored source revision,
so an in-place change still invalidates stale reviews. Identical retries are no-ops.

`storage/source_storage.py` owns plain-JSON compatibility, bounded decoding and
`srz1:` encoding (zlib/DEFLATE with a permanent public-prefix/schema dictionary,
then base64 text). Tiny objects stay plain if compression would enlarge them.
Do not change the format-1 dictionary; a future dictionary needs a new prefix.
Already encoded bytes are retained across zlib versions. Corrupt/oversized
snapshots stop migration before the active file is changed. JSON/SQL backups
retain the lossless stored representation; Dev analysis exports decoded current
observations with all source URLs and metadata for ordinary analysis.

Fresh/small rebuilt databases use 2,048-byte SQLite pages. After schema migration,
VACUUM reclaims freed pages. On later starts, a database with at least 4 MiB of
used pages can move once to 4,096-byte pages with a pre-compaction backup. This
avoids repeatedly compacting every launch and reduces larger-history overhead.
Compaction handles WAL mode and is optional: a busy disk/database defers it with
a log notice while preserving the successfully upgraded data. It never deletes
game facts, listening samples, correction records, pending offers or backups.

Unknown extension tables/values retain the existing rebuild verification. An
extension referencing an obsolete source row blocks removal rather than leaving
broken foreign keys. The complete pre-upgrade backup retains old source history.

Catalogue edits use current relationships, never comma-splitting artist names.
Reviewed Apple identities/observations are separate from local art, preview,
release placement and attached tags. Unmarked explicitness displays Not explicit;
Explicit/Cleaned observations remain explicit labels. Missing-information fill
keeps its scan/review/apply workflow and fills only proposed missing fields.
Album lookup tolerates removed “- Single”/“- EP” suffixes without changing local
placement or artwork. Ambiguous sources remain unresolved instead of guessed.

V5.0.1 keeps a song write and its verified source observation in one transaction.
Apple adds are explicitly marked and require a signed offer. Empty offers cannot
fall through to a manual add. Older flat payloads with `source.track_id`,
`apple_track_id`, `apple_id`, `trackId`, or an Apple song URL are resolved through
a server-side lookup; client advisory flags are not trusted. Missing, conflicting
or unmatched identities fail before creating a song. Successful add/link replies
include the saved `source_id` and public source projection; the Dev client confirms
the recording ID before showing success. Repeated imports return the existing
song/source receipt. Manual metadata-only adds remain supported.

Dev Songs reads its optional Apple ID/link columns from saved source summaries,
including their sort/filter values. A song edit reloads these summaries. Existing
unlinked songs can be repaired using Source with both metadata/album options off;
this changes only `song_sources`, leaving catalogue placement and game data intact.

V5.0.2 accepts omitted optional fields in fill-only source snapshots when projecting
source summaries/history. Preview comparison requires an observed preview URL.
The saved observation itself stays unchanged. Confirmed source receipts update
the Dev cache immediately; batch refreshes update open Edit summaries without
replacing form inputs. A failed follow-up refresh is reported separately from a
confirmed save; an actual failed POST remains an error.

Tag workbench plans Add/Remove/Replace changes against actual memberships, reviews
Before/After, retains preview/selection state and prevents stale saves. Single
moves/source changes use a signed review without an automatic backup. Dev table conditions remain
independent across categories, including reloads in the same tab. Other row
actions stay inside the bounded Actions expansion.

## API map

| Area | Endpoints |
| --- | --- |
| Library | `/api/collection`, `/api/library` and page/profile/ranking routes. Public collection contains active combined history and nonprivate listening summaries. |
| Preferences | `/api/matchup`, `/api/vote`; offers are browser-owned and answers are validated/idempotent. |
| Trivia | `/api/trivia/round`, `/api/trivia/<token>/start`, `/pause`, `/field`, `/finish`. |
| Tournament | `/api/generate_bracket`, `/api/tournament_vote`, `/api/tournaments`, `/api/tournaments/<id>`, completion/stats routes. |
| Guesser/Shelves | `/api/elo-guesser/round`, `/answer`, `/api/album-shelves/round`, `/answer`; saved server questions own grading. |
| Preview | `/api/previews/<song_id>`, `/status`, `/api/previews/cache`; bounded in-memory audio cache/diagnostics, not a listening history. |
| Private analysis | `/api/dev/song-quality/<id>` GET/POST, `/api/dev/analysis`, `/api/dev/selection-health`. |
| Backups | `/api/dev/system`, `/api/dev/backups/review`, `/restore`, backup download, `/api/dev/database/export`, `/api/dev/database/guide`. |
| Git | `/api/dev/git/status`, `/check`, `/upload`; writes/checks are explicit tasks. |

Existing authenticated catalogue, metadata, tag, correction/reset and source
routes remain available in their developer modules. New telemetry rides the
accepted-answer routes; there is no unauthenticated generic write-measurement
endpoint. Security middleware still enforces local/private allowed clients,
host/origin checks, write formats, size bounds and Dev authentication.

## Configuration

Set environment variables in the launch shell; the app does not auto-load an
`.env` file. Session/secret configuration is owned by `lan_security.py`.

| Variable | Use |
| --- | --- |
| `SONG_RANKER_DB` | Active V3 destination; default `data/song_ranker_v3.db`. Exact old V2 filename gets the compatibility path mapping described above. |
| `SONG_RANKER_LEGACY_DB` | Optional existing V2 source for first transfer. |
| `SONG_RANKER_HOST` | Waitress bind address; default `0.0.0.0`, still subject to the private-LAN gate. |
| `SONG_RANKER_PORT` | Integer 1–65535; default 5000. |
| `SONG_RANKER_ALLOWED_IPS` | Exact comma-separated client device IPs; loopback is always allowed. The supplied launcher's existing private-phone allowance is retained unless overridden. |
| `SONG_RANKER_HOSTNAMES` | Optional exact permitted hostnames, without scheme, port or wildcards. |
| `SONG_RANKER_PIN` | Dev PIN; retained default 9042. |
| `SONG_RANKER_SECRET` | Optional strong signing secret of at least 32 characters; otherwise a random key is persisted in `instance/session_secret`. Keep it stable. |

Do not expose this local app as a public internet service or assume reverse-proxy
headers grant trusted access. Preserve `instance/session_secret` across upgrades
so signed sessions/reviews remain valid. Preview loading needs the existing Apple
network access; proxy/cache failures do not turn into bad-preview flags by guess.

## Hosting and recovery

Use `python main.py` for the normal Waitress launcher. For WSGI, `main:app` exports
the application; deployment/process management remains yours. Use one worker
when performing live database restoration, or stop workers and recover offline.
The secret, active database and backups are local files, not bundled defaults.

Dev restore validates a reviewed V3 snapshot, binds the live and backup digests,
creates a safety backup and uses exclusive maintenance before replacement.
Restore invalidates old game tabs; reload before continuing. Old V2 archives are
read-only transfer/recovery sources, not normal full-restoration candidates.

Offline tools always write a new file. From the app root:

```sh
python -m songranker.developer.db_tools audit --db data/song_ranker_v3.db
python -m songranker.developer.db_tools export --db data/song_ranker_v3.db --output competition.json
python -m songranker.developer.db_tools restore --backup data/database_backups/YOUR_V3_BACKUP.db --output recovered_v3.db
```

Stop the app and inspect a recovered database before selecting it as the active
path. `rebuild` and `compare` retain lossless reconciliation; `--help` lists the
full offline options. SQL uploads use complete verified snapshots; Git protects
live databases, private keys, backups and generated files from source updates.
An unchanged SQL snapshot does not make another upload commit. No remote is
contacted by opening the Dev status panel.

## Validation and maintenance

Run `python -m unittest discover -s tests` from the root with normal requirements
installed. JavaScript suites use Node and jsdom as test-only dependencies and
run with `node tests/test_NAME.js`. Historical schema fixtures stay in `tests/`
to test transport/recovery, not to make parallel runtime schemas.

The release's migration, listening, selection, UI, live-route, seed, CRC/overlay
and original-DB preservation checks are in [VALIDATION.md](VALIDATION.md). The
DOM/computed-style harness does not render browser paint or physical audio;
those remain device installation checks. New app work should follow [AGENTS.md](../AGENTS.md)
and [PAGE_STYLE.md](PAGE_STYLE.md), keep one shared owner per concern and update
the current documentation rather than adding another root note file.


## V5.0.3 reviewed source groups

`POST /api/dev/song-sources/bulk` accepts `changes` (1–500 objects with
`song_id`, `source_token`, `fingerprint`). Administrator authentication, signed
session-owned Apple offers and per-song review fingerprints are required.
Validation, source replacement and commit run under one `BEGIN IMMEDIATE`.
Duplicate song/track IDs are rejected. `save_source(..., replacing=ids)` permits
exchanging assignments only among songs that all have reviewed replacements;
external conflicts still roll back every source write. From V5.0.3.1, source
changes commit without making an automatic backup.
No catalogue or game metadata is written. Source row IDs remain stable.

`dev_catalog.js` owns the in-memory review queue, stage/skip/revisit controls,
shared release search cache and final batch request. A closed modal retains its
queue until save, discard, restore or page reload. Individual source choices
show five plus ten collapsed results; import browsing keeps its own paging.


## V5.0.3.1 backup policy and controlled shutdown

`storage/database_io.create_rolling_backup` serializes requested snapshots into
three atomic slots, validating SQLite integrity and foreign keys before replace.
Manual/shutdown/explicit restore safety backups share these slots. Old archives
are not pruned. `create_backup` remains the separate update/migration archive
function. Catalogue edits, deletes, resets and metadata fills no longer invoke it.

`hosting.StopCoordinator` owns the shutdown job. `developer/dev_shutdown.py`
provides administrator-only `/api/dev/stop`, `/prepare`, `/confirm`, `/cancel`
routes. Prepare requires a fresh PIN, a browser-owned signed target review and an
explicit boolean Git choice. Five incorrect PIN attempts per browser are throttled
for one minute. The job exposes no PIN, Git credentials or executable callback.

A before-request lease covers complete write requests, including direct-SQL
metadata fills and Git requests. Once a stop starts, new APIs are refused with
503. Existing requests finish; the maintenance gate then drains DB connections
and remains held through backup, Git upload and UI acknowledgement. Git uses the
reviewed target fingerprint and its existing no-force-push/database-only policy.
No background metadata scan writes data; applying a scan is a tracked request.

The browser displays backup/Git receipts before a four-second acknowledgement.
A job/owner-bound confirmation releases the normal Waitress launcher using its
own task dispatcher and socket map. The coordinator waits briefly for the HTTP
reply to leave before closing sockets. There is no process kill or WSGI-manager
shutdown. Failures, cancel and a 120-second acknowledgement timeout release the
gate and resume the app. The normal launcher registers its callback after server
creation; WSGI imports leave it unsupported. Stop does not close a browser-owned
tab. Three slots do not limit Git commit history or old/update recovery archives.
