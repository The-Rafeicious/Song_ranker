# Song Ranker technical guide

**Application V5.5.10.2 · competition generation 3 · schema 22**

Current implementation reference. `APP_VERSION` is `5.5.10.2`; the internal mode
version remains `Vibe-Map-v1.1`.
Setup is in the [README](../README.md), migration/recovery in [UPGRADES.md](UPGRADES.md),
and historical changes in [release notes](../update_logs/README.md).

- [Feature and page lookup](#feature-and-page-lookup)
- [Architecture and ownership](#architecture-and-ownership)
- [Database lifecycle](#database-lifecycle)
- [Connections and transactions](#connections-and-transactions)
- [Preferences and Elo](#preferences-and-elo)
- [Game scoring](#game-scoring)
- [Vibe Map runtime and reporting](#vibe-map-runtime-and-reporting)
- [Stage-aware selection](#stage-aware-selection)
- [Impact and Overall](#impact-and-overall)
- [Reporting and presentation](#reporting-and-presentation)
- [Private preview analysis](#private-preview-analysis)
- [Health reporting](#health-reporting)
- [Catalogue editing and imports](#catalogue-editing-and-imports)
- [Reviewed source groups](#reviewed-source-groups)
- [Apple adding and request behaviour](#apple-adding-and-request-behaviour)
- [Developer maintenance](#developer-maintenance)
- [API map](#api-map)
- [Configuration](#configuration)
- [Hosting and recovery](#hosting-and-recovery)
- [Backups and controlled shutdown](#backups-and-controlled-shutdown)
- [Git database reconciliation](#git-database-reconciliation)
- [Validation and maintenance](#validation-and-maintenance)

## Feature and page lookup

| Concern | User surface | Implementation owner |
| --- | --- | --- |
| Voting and tournament Elo | Vote, bracket, histories, visibility comparisons | `modes/voting.py`, `modes/tournament.py`, `modes/preferences.py`, `catalog.py` |
| Trivia and Guesser challenges | Timed fields, streaks, frozen difficulty/answers | `modes/trivia.py`, `challenges.py`, `challenge_rules.py`, `guesser.py` |
| Album Shelves | Album assignment, track ordering, staged reveal | `modes/shelves.py`, shared game/round flow assets |
| Vibe Map | Continuous placement, averages, radar, similar tracks | `modes/vibe_map.py`, `vibe_similarity.py`, `vibe_maps.py`, `static/js/vibe_map.js` |
| Vibe reporting | Stats, profiles, Home/Global and collection rankings | `modes/vibe_map.py`, `vibe_charts.js`, `vibe_library.js` |
| Search and profiles | Tag counts, proper-album counts, achievements, Show more | `pages.py`, `catalog.py`, `site.js`, `search.js`, `profiles.js` |
| Ratings and health | Collection Impact, Overall, selection/data diagnostics | `impact.py`, `overall.py`, `reports/health.py` |
| Catalogue and Apple | Import, source-only repair, reviewed bulk edits and fill | `developer/dev_catalog.py`, `catalog_sources.py`, `metadata.py` |
| Tags and previews | Eight-tag capacity, Add/Replace/Remove, private quality flags | `storage/tag_limits.py`, `developer/dev_tags.py`, `apple_access.py` |
| Vibe maintenance | Average/count edit, map clear, song delete, mode reset | `developer/dev_vibe.py`, `storage/competition_reset.py`, `static/js/dev_vibe.js` |
| Recovery and Git | Backup, export/rebuild, restore, guarded upload/adoption, Stop app | `storage/database_io.py`, `git_database.py`, `developer/dev_system.py`, `git_sync.py`, `dev_shutdown.py`, `hosting.py` |

Public routes and detailed mode contracts are indexed below. The complete
operator tool list is in the [main README](../README.md#dev-tools).

## Dev workspace

`developer/navigation.json` is the single area/task registry. The authenticated
`/dev/<area>` and `/dev/<area>/<task>` routes validate against it and render
`templates/dev.html`. The original `/dev/dashboard?view=...` handler remains a
bookmark-compatible entry. API routes, review tokens, ownership and mutations are
unchanged. Section navigation uses canonical URLs and browser history; reloads
serve the same task. Unlisted area/task combinations return 404.

`dev_workspace.js` owns visible primary/section links, shared landing pages, the
inline editor/discard flow and guide rendering. Registry catalogue requirements
let Home, guides and independent system tools render without downloading the
whole catalogue. Entering a task that needs catalogue data loads it once with
retry and stale-response handling. `dev_workspace.css` owns their
geometry. Catalogue composition stays in `site.js`, Apple/source operations in
`dev_catalog.js`, tags in `dev_tags.js`, metadata in `dev_metadata.js`, record review
in `dev_records.js`, Vibe maintenance in `dev_vibe.js`, and system/database/selection
controllers in `dev_system.js`. `developer.css` retains common controls and tool
compositions; old Home/category-menu rules were removed.

Database inspection, backup recovery and reviewed resets no longer share one long
page. Backend review/apply contracts remain distinct. Navigation closes the inline
editor and invalidates stale work only after explicit draft discard; an active
restore blocks navigation. Plain-text guide URLs are retained. The authenticated
`/api/dev/help/<guide>?format=html` response supplies HTML and a table of contents,
rendered from the repository's Dev/technical Markdown via Python-Markdown. It does
not accept arbitrary filenames. Other repository documentation links resolve to
the corresponding GitHub reference.

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
| `songranker/apple_access.py`, `lan_security.py` | Bounded preview access/cache/diagnostics and the private-network/request/session gate. |
| `data/schema.sql` | Only canonical runtime DDL registry. Historical test fixtures are not alternate runtime schemas. |
| `templates/`, `static/` | Shared HTML/macros and feature-owned scripts/styles; details in [PAGE_STYLE.md](PAGE_STYLE.md). |

No old root Python-module wrappers are needed. Imports explicitly use the
`songranker` package, so a merged installation works before obsolete root files
are removed. [FILES.md](FILES.md) maps current locations; old package trimming lists are
[expired](RETIRED.md). Application notes live in `docs/`; release-family logs remain in
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

After this bootstrap, the normal launcher performs the separate V5.0.5 Git
database comparison described below, including for an existing V3 database.

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

Public Elo starts at 1200. Policy 2 retains the K32 budget with a tested-population
scale, evaluated immediately before each effective event:

```text
target      = clamp(8 * IQR(tested ratings), 200, 400)
mean        = completed appearances / tested songs
scale       = 400 + mean / (mean + 4) * (target - 400)
expected(A) = 1 / (1 + 10 ** ((rating(B) - rating(A)) / scale))
new(A)      = rating(A) + 32 * influence * (actual(A) - expected(A))
```

`influence` is 1 for ordinary votes and whole-library tournament first rounds;
it is 0.5 for tag first rounds. Artist and album brackets never create preference
events or contribute Elo confidence/exposure. Later rounds, bronze
playoffs and points-only brackets do not create preference events. There is no
high-K placement stage, forced rating range or health-based rating adjustment.

The IQR uses linearly interpolated quartiles, excluding zero-evidence songs.
Fewer than four tested songs use scale 400. Completed eligible first-round
tournament appearances count once for scale maturity, including scoped events;
their exchange budget remains halved. Public evidence is seeded ordinary matches
plus effective ordinary and tournament appearances. Each independent stream
uses only its own tested ratings and completed appearances. No catalogue-wide
mean or rank rescaling moves ratings without a saved result. The blend is bounded
200–400; broad mature distributions return to the classic scale of 400. Stable
logistic arithmetic handles very wide rating gaps without exponent overflow.

At startup, after Git database reconciliation and before serving, policy-1
databases receive a verified `database_backups/pre_adaptive_elo_*.db` archive.
The app replays effective events by ascending event ID, preserves ordered manual
overrides and legacy anchors, rebuilds public/independent projections, and updates
`preference_replay_state.rules_version` to 2 in the same write transaction.
Full-history peaks are rebuilt under policy 2; protected legacy-anchor peaks and
cutoffs remain. Backup/replay failure stops startup with ratings and marker
unchanged. Concurrent startups serialize; successful activation is never repeated.
Fresh databases start on policy 2. Lossless import/export/recovery does not itself
activate or modify an older policy; startup performs that explicit operation.
Original event receipts and frozen Guesser questions remain historical facts.

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
| Vibe Map | Four continuous descriptions saved as compact means/counts; radar, similarity and consistency are descriptive, without a performance score. |
| Album Shelves | Ten tracks across two or three proper albums. Correct album placement earns 0.5; correct relative-order comparisons earn up to 2.5 per track. Relative-order percentage is the primary accuracy; points retain their own saved denominator. |

Pending/prepared questions add no completed exposure, listening or result. A
prepared Trivia round starts neither the answer clock nor playback. Missing
identities remain explicit; reports do not invent answers or substitute current
ratings for absent saved snapshots.

## Vibe Map runtime and reporting

V5.1.0 integrates the mode; its internal release is Vibe-Map-v1.1, schema 19,
definition generation 2. The four maps are Pace & mood (Slow/Upbeat, Sad/Happy),
Sound & impact (Acoustic/Electronic, Soft/Powerful), Connection
(Fractured → Secure, Detached → Devoted), and Perspective
(Past/Future, Regretful/Hopeful; Present at X centre). Detached is a display-only
rename of canonical stored Casual. Every song has four linked slots.

Play coordinates are continuous −5…+5; storage/comparison readers use −1…+1.
The browser owns one current round. Draft/advance revision and request IDs reject
stale saves and replay accepted requests once. A five-second deadline restarts
on adjustment. Advancing accepts the latest draft, saves its averaged contribution
and moves to the next map. Reviewing a saved map replaces this pass's contribution.
A full pass increments progress once. One buffered round per browser and compact
per-map means/counts avoid an ever-growing placement-attempt table.

The page keeps one song/preview through maps and manual Finish. Completed results
show an ordered eight-axis radar and two related songs, then wait for Next song.
No map may be skipped by navigation. Missing points stay absent from comparisons.
Similarity is descriptive; coverage and Gaussian coordinate distance are distinct.

The coverage-first selector prioritises never-mapped songs. A bounded similarity
factor softly biases voting, tournament, Guesser and album-hotspot selection;
coverage adapts its strength, while positive random support prevents isolated
pockets. It does not rewrite Elo, quality scores or preferences.

Read-only/no-store reports share saved profiles and consistency helpers. The
main stats page supplies density maps, patterns, balances, pairs/contrasts and
five most/least consistent groups. Song profile cards need four placed maps;
collection cards and ranking eligibility need two fully mapped members and
proper albums. Home's final banner mixes up to twenty per entity category;
ranking boards expose albums/artists/tags with shared top/bottom-twenty limits.
Global activity uses each song's latest retained save, including partial maps,
not an exhaustive history of completed passes. Vibe writes no listening records
and contributes no Overall performance component.

Dev edits are atomic and fingerprint maps, progress and round drafts. Coordinates
are entered in −5…+5, with sample/pass constraints and preservation of unchanged
exact means. Edits/delete invalidate buffered rounds for that song. All-mode reset
shares `storage/competition_reset.py` and includes Vibe. The standalone merge
cleanup is explicit, preview-first and never an automatic migration.

See [complete API/statistics](VIBE_MAP.md) and [Dev/cleanup commands](VIBE_MAP_DEV.md).

## Stage-aware selection

All policy functions and canonical exposure/recency adapters live in
`modes/selection.py`. Pools are filtered for actual mode
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
eligible entry starts with a uniform exploration floor before voting recency and
per-track visibility adjustments; a preview-quality flag does
not alter eligibility or the calculation. Equal counts/ages remain uniform.

Standard/Blind draws read `max(8,ceil(4*sqrt(eligible pool size)))` answered pairs
across both visibilities from the owning browser, falling back to effective saved
results when none exist. This retains about eight recovery timescales and grows
with the collection (about 127 pairs for 1,000 eligible tracks).
The most recent pair is avoided when a complete alternative exists. Older tracks
receive a smooth factor `(1-exp(-(age+1)/recovery))^3`, where age is matches since
the latest appearance and `recovery=max(1,sqrt(eligible pool size)/2)`. Small pools
recover sooner; there is no fixed multi-match ban.

Each preview-ready track also compares its current-mode exposure to its own
other-mode exposure. With `gap=(current-other)/sqrt(1+min(current,other))`, multiply
by `2/(1+exp(gap))` (the exponent is bounded to ±50 for numerical stability).
An overplayed visibility is strongly discouraged even below the pool mean;
underplayed visibility gets up to twice the support, and balance pressure eases
as the track catches up. Missing previews exempt Non-blind tracks from this
comparison. These positive factors apply to both anchor and opponent after the
exposure floor; they are recomputed on every fresh offer. Counts retain the same
weighted tournament evidence and correction semantics as before. Existing open
offers remain frozen.

The opponent combines the same exposure support with Elo closeness:
`floor = 0.20 − 0.05*t`, closeness weight `1−floor`, and spread bandwidth
`1−0.15*t`. Closeness is `1/(1+(gap/scale)**2)`. Scale uses the current rating
IQR, then 10–90% span, then the median adjacent distinct-rating gap. This tightens
pairings modestly as evidence grows and remains relative to the live database.

Trivia excludes the previous track when alternatives exist. Guesser retains its
previous-pair multiplier 0.25 and the relative gap-target kernel (0.05 floor,
0.95 target weight, width 0.10). Tournament draws entries without replacement using the same soft recency and
own-track visibility adjustment as voting. Exposure is one entry per bracket,
split by Blind/Non-blind across scopes, including unfinished brackets. Advancement
and round counts do not inflate exposure. Recency groups contain eligible tracks
from recent brackets; group size advances the clock in pair-equivalent units,
and unrelated scoped brackets do not erase a collection's recent history. The
history horizon grows with the eligible pool. Non-preview tracks remain exempt
from visibility balancing. A full-pool bracket can still select every entry.
Diagnostics use these same initial entry weights. Tournament then uses the retained relative noisy seeding/champion spread. Shelves chooses
albums by exposure and recency with capacity lookahead, then distributes ten
tracks and draws within each album by exposure. All prepared questions remain
frozen even when the pool changes later.

## Impact and Overall

Collection Impact uses one finite current Elo per distinct linked song that has played at least one match. Unplayed songs do not dilute averages or supply evidence. The baseline is the tested-library mean; prior breadth is the square root of the median nonempty tested peer collection size in that entity class:

```text
prior_tracks = sqrt(median tested tracks per nonempty peer)
support = tested_tracks / (tested_tracks + prior_tracks)
impact = tested_library_mean + support * (tested_collection_mean - tested_library_mean)
```

The lighter prior avoids pulling typical collections halfway back to baseline, while still tempering tiny samples. Collections without tested songs have no Impact/rank; proper albums alone participate in album peer calibration. Values display to one decimal and sort at full precision. Catalogue song counts remain unchanged. This is a read-only calculation: song Elo, match history and Overall are unchanged.

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
macros for repeated records/metrics, `reports.css` for report geometry and
`site_baseline.css` for the accepted type/corner/spacing baseline. The baseline
loads last. Shared additions live in `components.css`; feature controllers retain
media/request/cancellation ownership. Styles preserve semantic mode colours and
entity-coloured names, green success and danger red failures. Phone breakpoints,
native disclosures, 44 px controls, complete accessible names and reduced-motion
behavior remain part of the baseline.

## Private preview analysis

Listening-time capture, payloads, storage and public summaries were retired in
v5.1.2. Preview audio and Trivia answer timing remain independent.

`song_details.preview_bad`, `preview_note` and `flagged_at` are private Dev data.
Only authenticated quality/analysis/full-export endpoints return the annotations;
normal collection/library/profile/game responses omit them. Flagging does not
rewrite audio, tags, album placement or evidence. Dev analysis exports source observations and flagged preview notes.

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
game facts, correction records, pending offers or backups.

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

## Reviewed source groups

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

## Apple adding and request behaviour

See [Apple Music](APPLE_MUSIC.md) for song/album links, the album checklist,
source review versus import, metadata/preview request limits and error handling.

## Developer maintenance

The [Dev tool index](../README.md#dev-tools) maps each area to its workflow; [Vibe maintenance](VIBE_MAP_DEV.md) adds map/count edits, clear/delete and reset.
Artist/album/tag mutations share catalogue validation and transaction cleanup.
The old overview response reuses current inventory and backup discovery, keeping
its response shape for clients. Bulk catalogue mutations accept up to 500
positive integer IDs. The interface uses reviewed restore and Git tools; older
backend aliases remain compatible. Developer-only assets load from one template
include; metadata polling and archive paging have separate script owners.

## Dev shell and shutdown

`templates/dev_nav.html` replaces the main navigation only on authenticated Dev
pages. `dev_shell.css` widens the working canvas and controls the responsive menu
and service grid, including a compact Tag Workshop card linked to the bench.
`dev_tags.css` shares the queue/editor geometry across single and bulk modes,
with bounded identity text and selected-card artwork.
`app_stop.js` owns the shared stop dialog; `dev_system.js` owns service/backup/Git
tasks. Stop endpoints accept a fresh PIN without a Dev session,
but retain localhost-only access, signed browser-owned target review, rate limits
and job ownership. Stop grants no Dev session. All other Dev endpoints keep their
admin requirements. See [Dev guide](DEV_GUIDE.md).

## API map

| Area | Endpoints |
| --- | --- |
| Library | `/api/collection`, `/api/library` and page/profile/ranking routes. Public collection contains active combined history. |
| Preferences | `/api/matchup`, `/api/vote`; offers are browser-owned and answers are validated/idempotent. |
| Trivia | `/api/trivia/round`, `/api/trivia/<token>/start`, `/pause`, `/field`, `/finish`. |
| Tournament | `/api/generate_bracket`, `/api/tournament_vote`, `/api/tournaments`, `/api/tournaments/<id>`, completion/stats routes. |
| Guesser/Shelves | `/api/elo-guesser/round`, `/answer`, `/api/album-shelves/round`, `/answer`; saved server questions own grading. |
| Vibe play | `/api/vibe-map/state`, `/round`, `/draft`, `/advance`, `/cancel`, `/profile/<song_id>`, `/similar/<song_id>`, `/heatmap`. Exact methods/bodies: [mode reference](VIBE_MAP.md#flow-and-endpoints). |
| Vibe reports | `/api/vibe-map/stats`, `/inspect/<song_id>`, `/entity`, `/library`, `/rankings`; page `/vibe_map_stats` and board `/mode_rankings/vibe`. |
| Vibe Dev | `/api/dev/vibe` search, `/api/dev/vibe/<song_id>` GET/POST/DELETE, `/api/dev/reset-history/vibe`; [maintenance contract](VIBE_MAP_DEV.md#api). |
| Preview | `/api/previews/<song_id>`, `/status`, `/api/previews/cache`; bounded in-memory audio cache/diagnostics, not a listening history. |
| Private analysis | `/api/dev/song-quality/<id>` GET/POST, `/api/dev/analysis`, `/api/dev/selection-health`. |
| Backups | `/api/dev/system`, `/api/dev/backups/review`, `/restore`, backup download, `/api/dev/database/export`, `/api/dev/database/guide`. |
| Git | `/api/dev/git/status`, `/check`, `/upload`, `/keep-local/review`, `/keep-local`, `/use-remote`, `/compact`; writes/checks are explicit tasks. |

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

General `db_tools` recovery/export commands write new files. The separately confirmed [test merge cleanup](VIBE_MAP_DEV.md#prepare-the-test-branch-for-merging) deliberately resets its explicit database and replaces an explicit SQL export. From the app root:

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

## Backups and controlled shutdown

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
reviewed target fingerprint and its history-preserving/database-only policy.
No background metadata scan writes data; applying a scan is a tracked request.

The browser displays backup/Git receipts before a four-second acknowledgement.
A job/owner-bound confirmation releases the normal Waitress launcher using its
own task dispatcher and socket map. The coordinator waits briefly for the HTTP
reply to leave before closing sockets. There is no process kill or WSGI-manager
shutdown. Failures, cancel and a 120-second acknowledgement timeout release the
gate and resume the app. The normal launcher registers its callback after server
creation; WSGI imports leave it unsupported. Stop does not close a browser-owned
tab. Three slots do not limit Git commit history or old/update recovery archives.

## Git database reconciliation

`developer/git_sync.py` owns transport/locking, safe code fast-forwards, SQL-only
commits, pending upload refs and local object compaction. `storage/git_database.py`
owns snapshot validation, the logical row model, SHA-256 baselines, numbered
installation identities and transactional adoption. No storage owner imports
Flask. App-managed source pulls compare databases before updating code, preserve
the live DB, then recheck after bootstrap/re-exec before serving. A future snapshot
can require newer code for validation; it never authorizes automatic data adoption.

Logical hashes include primary-keyed rows, sequence high-water marks and schema
objects, including extension data. Hidden rowids identify unkeyed extension rows;
junction rowids do not change relationship identity. Only competition install
start/provenance are device-local. The existing database validation/materialisation
rules still reject invalid, corrupt or future-schema SQL.

Version-2 private receipts bind the accepted remote model hash plus Git witnesses
to the repository, database path and destination; V1 receipts and confirmed history
remain readable. An unchanged remote hash authorizes local work regardless of Git
ancestry. Otherwise the latest snapshot's registered writer may authorize this
device's current local data; another/unidentified writer requires an explicit
whole-copy choice. Baseline and direct per-table deltas explain additions,
removals, edits, schema and sequence differences; row counts do not decide policy.

A random 128-bit installation key is private local state bound to the live DB path
and a private hashed host fingerprint. Copying Git metadata to another host does
not reuse that host's key; the fingerprint itself never leaves local state.
Each successful new-device upload carries the complete key→number registry in its
commit message (`Song-Ranker-Devices`), its writer number (`Song-Ranker-Device`)
and logical hash (`Song-Ranker-Hash`). Numbers allocate monotonically from 1 on the
latest remote registry. Manual SQL commits retain an unknown writer; prior registry
trailers preserve allocations. SQL itself adds only commit time and device number
as a comment header. No hostname/user identity is exported as device metadata.

Uploads use a disposable `GIT_INDEX_FILE`, read the latest remote tree, replace
only the SQL entry and create a single-parent commit. They preserve the real index,
local code commits and code checkout. Hooks/signing failures block publication;
hook-added paths or modified snapshot entries fail scope validation. A private
`refs/song-ranker/pending/<binding>` retains retryable commits, and successful
uploads retain `last-upload/<binding>`. A matching local code checkout advances
with a compare-and-swap; behind/diverged code stays unchanged for normal update.
Both DB and remote are rechecked before push. An explicit expected-remote-head
lease provides atomic race rejection; the verified sole parent is that exact head,
so this mechanism never rewrites remote history.

`keep-local/review` issues a browser-bound token for both choices. `KEEP LOCAL`
archives both copies and acknowledges the exact remote hash. `USE REMOTE` on
`/api/dev/git/use-remote` uses a `pre_git_database` safety backup, maintenance gate,
`BEGIN IMMEDIATE`, raw live-digest/remote rechecks and transactional rebuild/rollback.
Multi-worker WSGI replacement is refused. A completed mutation remains successful
if writing its receipt/status subsequently fails. UI replacement refreshes the
catalogue and clears stale tag/source drafts.

Git fetches only the configured branch without tags/submodules or automatic GC.
`/api/dev/git/compact` runs `repack -a -d --keep-unreachable` under the operation
lock: no reflog expiry, prune, history rewrite or worktree cleanup. Old plain SQL
safety copies migrate out of Git metadata only after a durable gzip write and exact
decompression verification; new compressed archives deduplicate by SHA-256 under
`database_backups/git_snapshots`. No database backup is rotated/deleted by this task.
Git object-byte counts are approximate loose+pack storage, not total directory size.

Fresh checks expose `status_source`, `checked_at`, `upload_ready` and independent
`database_sync` details. Cached status never proves current equality. WSGI imports
remain Git-free. [UPGRADES.md](UPGRADES.md) explains choices and first-upgrade limits.

## Validation and maintenance

Use [VALIDATION.md](VALIDATION.md) for reproducible Python, JavaScript,
served-Dev and Chromium checks. Frozen schema fixtures are present; earlier
missing-fixture/browser-unavailable statements are expired historical limits.
Automated checks use disposable databases. Current platform/audio behaviour
still needs the intended installation/device. New work follows
[AGENTS.md](../AGENTS.md) and [PAGE_STYLE.md](PAGE_STYLE.md), with one owner per
shared concern and updated current references.

## v5.2.1 maintenance inspection

The database-inspector companion in `developer/dev_system.py` owns authenticated GET `/api/dev/database/inspect`
(`name`, `offset`, `limit`) and `/api/dev/database/cell` (signed `review_token`,
`column`, `start`). Names must exist as tables/views in sqlite_master; identifiers
are quoted, values/limits bound, and user SQL is never accepted. Column metadata
uses table_xinfo; the inspector includes generated/hidden columns. Row previews
cap cell sizes and total cells per response. Long-value tokens bind the browser,
object, row offset and a type-sensitive row digest; changed rows return 409.
Read-only URI mode and query_only apply, with a three-second progress budget and
one-second busy timeout. BLOBs use base64 and integer values remain exact strings.
The `DevDatabase` companion in `static/js/dev_system.js` owns object/tab/page/value state and stale-response
protection; `dev_system.js` owns backups and Git status. GET `/api/dev/help/dev`
and `/api/dev/help/technical` serve the two allowlisted guides to authenticated Dev.

Git status reads are marked cached. Explicit checks return checked_at,
status_source=checked, upload_ready and an independent database_sync comparison,
including per-table local/remote deltas. Opening Git performs that check. Code
up_to_date alone cannot enable upload or represent database equality. The existing
hash/device policy and server-side upload/stop guards remain authoritative.

## v5.2.2.1 tag queue

`static/js/dev_tags.js` owns single/bulk mode, queue selection, filter/sort state,
drafts, signed review/apply requests and its preview timeline. Single mode sends
replace_tags for one song, checks the server Before IDs against the tags captured
when the draft opened, then applies that signed review. A changed baseline pauses
for reload; bulk continues to show explicit Before/After. Server stale checks
remain authoritative between review/apply. The next eligible ID is chosen from
the pre-save order after refresh, excluding already visited IDs and respecting
the current filter. Failures never claim an advance or a save that was not confirmed.

Preview audio uses the shared PreviewPlayback owner and its approved proxy/cache.
Native loop is set on each bound/replaced element; clips over 30 seconds rewind
on the timeline boundary. Seeking before metadata is loaded is deferred. Same-URL
recordings restart when the selected song changes; leaving/mode switching releases
the old element. Source details reuse DevCatalog's cached song-source summaries;
no per-row Apple requests or new telemetry are introduced. Existing tag APIs,
transactional new-name creation and the eight-tag cap remain unchanged.

### Dev catalogue table UI (V5.3.5)

The shared Songs/Artists/Albums/Tags table schema, filtering, sorting, column preferences, row rendering and edit dialog grouping live in `static/js/site.js`. `static/css/dev_catalog.css` owns the scoped compact table and dialog panels. Column preferences use the existing `tableColumns` localStorage key; per-type query, filters, page and sort use the existing session state. Editing still calls the existing `/api/dev/edit_*` endpoints and refreshes the collection. Field filters store `{op,value}` and migrate old string conditions. Suggestions
come from the loaded catalogue. Rows/page is per entity in session state; column
preferences remain local. One delegated control owner handles in-flow panels and
a single body-level popover with viewport clamping and keyboard/focus management.
Table and inspector height caps are removed: the page owns vertical scrolling.
No database migration is involved.

### Missing metadata (V5.3.5)

`developer/metadata.py` snapshots writable identity/target fields and artist links,
counts blanks, and recovers facts from unique saved Apple track identities before
network requests. Blank album/artist names require unanimous linked saved names
and IDs; artist names also require sole-artist relationships. Existing source facts
are enriched only where blank, without adding genre/tag observations. Saved
collection IDs permit verified lookups when local artwork was deliberately changed.
Unlinked releases retain exact title/artist/artwork verification. Album artwork
requires matching release identity; artist artwork requires an exact artist response
with genuine artwork, never an album-cover substitute. Media URLs require HTTPS.
Conflicting field evidence removes proposals. The public review exposes values,
fields and evidence; internal snapshots stay server-side. Apply rechecks the entire
snapshot under a write lock, validates occupied positions and source uniqueness,
and writes all proposed blanks in one transaction. Tags, results, relationships and
nonblank fields stay untouched; no routine backup or schema change is introduced.

## Album disc positions (V5.3.3 / schema 21)

`songs.disc_number` and `album_shelf_items.disc_number` are positive integer
fields defaulting to 1. The canonical position guard scopes occupied slots by
`(album_id, disc_number, track_number)`. Legacy conflicts remain visible; migration
never guesses replacement positions or rewrites album memberships from titles.

Shelves freezes disc/track facts on offering a round and uses lexicographic
`(disc_number, track_number)` order for the existing relative-pair grade. Defaulting
old saved items to disc 1 preserves the original rule-1 results and pending rounds.
No scoring constants or mode exposures change. Source-only refresh keeps local
disc placement; explicit source-album refresh uses the verified source position.

The lossless state transport defaults both columns when upgrading pre-21 data;
recognition also covers SQL dumps without a user-version pragma. Direct upgrades
make the existing pre-upgrade safety backup. Git baseline hashes are recomputed
from available baseline SQL under the current schema, so adding default disc
columns does not falsely look like another device changed the data.


## Album Shelves preview lifecycle (V5.3.7)

`special_modes.js` owns one ten-second sample player. Every selection cancels
pending/retired playback and installs a generation-bound state before starting
the selected clip. Timer, timeupdate, seeked and ended callbacks share a once-only
advance guard. Seeking and buffering cancel the deadline; remaining time is
measured from media position. Only a successful current play starts advancement.
The shared preview owner also silences native play promises that resolve after
cancellation, while preserving a newer request on the same element.

Shelves does not prime/preload future tracks, including answer-reveal clips.
The selected audio uses `preload=none` and loads only when played. Answer reveals
retain their brief, controlled transition when the revealed clip is ready.
The existing proxy has 18 new-clip reservations per rolling minute and 0.5-second
spacing; Apple lookups are separate at 12/minute and 5-second spacing. A normal
ten-second rotation needs about six new clips/minute and ten per 100-second pass.
Rapid manual skipping can still reach the shared gate and stops with its normal
status instead of bypassing or retrying it. Limits are unchanged.

Complete bounded downloads are cached in page-scoped RAM: ten previews, ten-minute
TTL, up to 4 MiB each. Cache hits (including byte ranges) bypass upstream admission.
Interrupted/partial streams are not falsely marked complete, so a cache miss may
need another network request. No disk cache or whole-round warm-up is added.


### Shelves reveal feedback (V5.3.7.1)

Revealed wrong cards receive `--shelf-error-depth` from the existing saved item
comparison counts: `1 - order_right / order_pairs`, bounded to 0–1. Wrong albums
use 1. Fully correct cards retain green; unrevealed cards expose no error depth.
The shared stylesheet mixes light and deep red surfaces while retaining readable
text, correction labels, counts and points. No grading or placement logic changes.
A completed reveal with positive available points and a points/available difference
under 1e-8 shows one Perfect shelves badge, matching the report's perfect tolerance.
It has one brief glow, respects reduced motion, and clears with the next round.


### Voting report cohort and presentation (V5.3.7.2)

`build_voting_stats` reconstructs tested current songs from valid, active saved
Non-blind/Blind matches, including eligible tournament first rounds. The Elo
distribution's median, extrema, standard deviation, mean, starting-rating balance
and every band use only tested songs with finite Elo. Starting/manual ratings and
stale `matches_played` counters alone never qualify a song. Excluded unplayed
tracks and tested tracks with unavailable ratings are separate counts; empty
cohorts show unavailable summaries and no invented percentages.

Coverage adds effective-appearance depth (<2, 2 to <5, 5+) and the tested-track
mean. These remain read-only projections in the existing snapshot. Activity keeps
one seven-day presentation in the shared fourteen-day pulse and a distinct
thirty-day summary. Tournament preview rows are removed in favour of the existing
filtered history, and the Daily figures disclosure remains as exact chart evidence.
The existing report owner supplies mode/entity colours without changing grading,
Elo calculation, source weights or public routes.


### Tournament scope policy and visual brackets (V5.5.0)

New artist/album tournaments use the existing points-only policy (`elo_policy_version=0`,
`elo_weight=0`). Whole-library first rounds retain full influence; tags retain half.
Only main first rounds qualify. Points, placements and tournament entry exposure
remain independent of Elo eligibility. Completed vote retries return the saved
result without awarding points or Elo twice, including points-only brackets.

After adaptive Elo activation, startup archives any remaining artist/album policy-1
brackets to `database_backups/pre_tournament_scope_*.db`, records void corrections
for their effective preference events, and rebuilds public/independent Elo and
confidence projections. Original matches, submitted receipts, points and placements
remain. Policy flags and corrections commit together; failure rolls back, and
subsequent starts find nothing to retire. The original archive remains available
for whole-database recovery with the earlier source.

`TournamentBracket` in `gameplay.js` renders the same connected tree for saved
stats brackets, live progress and the post-completion replay. The borderless workspace fills the page between banner and footer; drag/touch/keyboard navigation replaces stage selectors. Track selection highlights a route and opens saved match/win context directly below its match. A server-rendered match fallback remains available without
JavaScript. Unplayed Blind identities stay hidden in the interactive map.

Completion saves first, then reveals one side's advancing/eliminated tracks, the
other side, bronze and final, before the podium. Skip completes immediately;
reduced-motion mode omits staged motion and replay music. Opening a saved completed
bracket still offers the podium and an explicit replay action.

The soundtrack pool is the four semi-finalists, restricted to the currently filling side. The shared preview coordinator bounds playback to the incoming clip and one fading tail, looping six-second samples.
No batch preloading or next-track priming occurs. Existing browser/server preview
caches are reused when warm; missing clips load only on selection and existing
rate/cooldown limits remain authoritative. Failed clips are skipped and autoplay
or rate blocking turns sound off. Hide/leave, Skip, cancellation and podium handoff
retire the replay player; its Sound off choice carries into the podium.

Tournament Stats retains section order, uses semantic visibility/entity colours,
adds points-only first-round context and entry-depth metrics, and drops the duplicate
recent-Elo-history disclosure and repeated seven-day activity figures. Archive bracket disclosures link to the dedicated bracket workspace.


### Album Shelves exclusion (V5.5.5 / schema 22)

`albums.shelves_excluded` is a checked integer flag, default 0. Dev → Library →
Albums → Edit exposes **Exclude from Album Shelves**. The album table has an
Included/Excluded column with the normal filtering and sorting controls. The API
accepts only JSON booleans; omitting the field preserves its current value.

The flag excludes the album from new Shelves draws, current Shelves coverage and
Overall's Shelves eligibility. It does not turn it into a Single, change its songs,
artwork or album identity. New Trivia rounds also skip its album-name field. Frozen rounds remain answerable,
and completed rounds/results remain recorded. Unchecking restores normal eligibility
subject to the existing numbered-track and capacity requirements.

Startup uses the existing integrity-checked pre-upgrade backup and atomic migration.
Older schema-21 databases and unversioned SQL dumps default every album to included.
Exports, rebuilds, Git SQL snapshots and catalogue transfers preserve explicit flags.
Grouping tracks under an existing album can avoid extra placeholder album rows;
this flag itself does not merge or remove data or compress the database.

### Exclusion evidence and bracket workspace (V5.5.5)

Completed Shelves rounds containing any currently excluded saved album are hidden as whole exercises in all public summaries, trends, history, rankings and Overall evidence. Including that album again restores the unchanged saved facts. Keeping whole-round denominators avoids turning part of a saved round into a new perfect result. Dev inspection/export still retains every record. Profile Shelves panels require at least one current eligible track. Overall calibration topology includes the album flag. Read-only pre-22 archive grading assumes included albums.

`/tournament/<int:tournament_id>/bracket` is a shareable read-only workspace, linked from Tournament Stats. The shared map mirrors the two halves into a central final, with third place below. Drag, touch and keyboard navigation explore the full-width surface. Selecting a track opens an attached details panel with its route, opponents, results and points; Close or Escape dismisses it. Round shades brighten and gain glow towards the final. Replays hold each result for 3.5 seconds. Existing API endpoints and saved tournament rules are unchanged.

### Preview audio and tournament cues (V5.5.8)

The V5.5.5 loudness balancing has been removed. Previews retain their native recording level, site volume and shared crossfades; there is no Web Audio normalization, compression or calibration cache in the playback path.

Tournament replay walks each quarter's feeder matches in order before its semi-final, then the other half, third place and final. A quarter uses its qualifying semi-finalist's preview, continuously across results. Semi-finals, third place and final play their winner. Identical consecutive cues keep the same audio element and playback position. Whole previews loop natively rather than seeking every six seconds. The result hold begins after the cue is ready, so slow loading cannot race into the next song. A different cue retains one outgoing clip until the incoming clip is ready for the shared 1.5-second crossfade. Missing or failed previews leave that section silent rather than selecting an unrelated song. Mute/unmute uses the current match, and skip/cancellation still silence all clips.

### Full-page bracket replay (V5.5.6)

The shared map holds each result for 3.5 seconds and fills the available space between the banner and footer in both the saved workspace and pre-podium replay. The viewport has no inset border or rounded box. Resize observation gives the map almost a viewport of its own, with the header and footer outside that height; diagram overflow stays inside the drag surface. Stage selector controls are removed. Match details are attached to their selected node, support Close/Escape with focus restoration, and keep content scrollable on short screens. Round-local CSS variables produce darker outer rounds and brighter central rounds with increasing glow; winner/elimination markers and Blind privacy remain independent.

### Tournament competition and local reports (V5.5.10.2)

Library and tag tournament results have competition weight 1, and artist/album brackets zero. Tag first-round Elo remains half-weight. Local results cannot affect tournament competition achievements or Overall values, evidence, appearances or calibration. Overall calibration version 9 refreshes the changed policy. Saved points, matches, replay data and Elo are unchanged.

`/tournament_stats` contains only library/tag brackets, including its activity counts and archives. Old selected-local-bracket links redirect to `/tournament_local_stats`, filtered by saved scope. Direct bracket workspaces remain valid for every scope and link back to the appropriate report.

`/tournament_local_stats` accepts `scope=artist|album` and optional `scope_id`, or the form's `view=all|artist|album|artist:<id>|album:<id>`. All comparisons use completed local brackets only, before aggregation. Track favourites sort observed titles, win rate and match evidence, showing repeated entries, title rate, points and podiums. Artist/album comparisons pool those track facts; head-to-head scores count each valid pairing once. These are within-selection results, not cross-library strength estimates. Track, collection and pairing lists show up to 50, 25 and 20 rows; the full bracket archive pages by 20. Unfinished Blind participant identities never appear in comparisons. Compact artist/album profile panels link to their filtered report and latest replay.
