# Song Ranker technical guide

**Application v5.2.2 · integrated modes v5.1.0 · competition generation 3 · schema 20**

Current implementation reference. `APP_VERSION` is `5.2.2`; the internal mode
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
| Voting and tournament Elo | Vote, bracket, histories, visibility comparisons | `modes/games.py`, `preferences.py`, `mode_ratings.py`, `elo_history.py` |
| Trivia and Guesser challenges | Timed fields, streaks, frozen difficulty/answers | `modes/trivia.py`, `challenges.py`, `challenge_rules.py`, `special_modes.py` |
| Album Shelves | Album assignment, track ordering, staged reveal | `modes/special_modes.py`, shared game/round flow assets |
| Vibe Map | Continuous placement, averages, radar, similar tracks | `modes/vibe_map.py`, `vibe_similarity.py`, `vibe_maps.py`, `static/js/vibe_map.js` |
| Vibe reporting | Stats, profiles, Home/Global and collection rankings | `reports/vibe_*_data.py`, `vibe_charts.js`, `vibe_profiles.js`, `vibe_library.js` |
| Search and profiles | Tag counts, proper-album counts, achievements, Show more | `pages.py`, `catalog.py`, `site.js`, `search.js`, `profiles.js` |
| Ratings and health | Collection Impact, Overall, selection/data diagnostics | `impact.py`, `overall.py`, `reports/selection_health.py`, `data_health.py` |
| Catalogue and Apple | Import, source-only repair, reviewed bulk edits and fill | `developer/dev_catalog.py`, `catalog_sources.py`, `metadata_tools.py`, `metadata_fill.py` |
| Tags and previews | Eight-tag capacity, Add/Replace/Remove, private quality flags | `storage/tag_limits.py`, `developer/dev_tags.py`, `tag_operations.py`, `apple_access.py` |
| Vibe maintenance | Average/count edit, map clear, song delete, mode reset | `developer/dev_vibe.py`, `storage/competition_reset.py`, `static/js/dev_vibe.js` |
| Recovery and Git | Backup, export/rebuild, restore, guarded upload/adoption, Stop app | `storage/database_io.py`, `git_database.py`, `developer/dev_system.py`, `git_sync.py`, `dev_shutdown.py`, `hosting.py` |

Public routes and detailed mode contracts are indexed below. The complete
operator tool list is in the [main README](../README.md#dev-tools).

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
(Fractured/Secure, Budding/Devoted), and Perspective
(Past/Future, Regretful/Hopeful; Present at X centre). Budding is a display-only
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
and service grid. `app_stop.js` owns the shared stop dialog; `dev_system.js` owns
service/backup/Git tasks. Stop endpoints accept a fresh PIN without a Dev session,
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
| Git | `/api/dev/git/status`, `/check`, `/upload`, `/keep-local/review`, `/keep-local`; writes/checks are explicit tasks. |

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

## Git database reconciliation

`developer/git_sync.py` still owns Git transport, locking, code fast-forward and
snapshot-only uploads. `storage/git_database.py` owns committed SQL validation,
logical row models, device baseline receipts, three-way change coverage and
transactional adoption. `main.py` calls reconciliation after schema bootstrap
and code re-exec but before the normal server starts, even after a manual pull.

A shared baseline tracks removals as well as additions/edits; sequence high-water
marks and extension objects participate. Device-local competition start/provenance
are omitted from logical equality. Confirmed-upload history or an exact older
Git snapshot can recover the initial baseline; absent/ambiguous history requires
review. No row count or modification-time heuristic decides which database wins.

Safe remote adoption uses an archival `pre_git_database` SQLite backup, a live
digest recheck inside `BEGIN IMMEDIATE`, and the existing verified transactional
rebuild. Conflicts retain local data and publish a validated `incoming_git` copy
for the existing reviewed-restore workflow. Upload preflight rejects stale or
split live databases even if source Git commits are already up to date.

Status is cached locally in Git’s private state folder and returned as
`git.database_sync`; Dev labels it separately from code status. Check remote
compares read-only. WSGI import bootstrap does not fetch or auto-adopt snapshots.
Details, first-upgrade limits and recovery are in
[UPGRADES.md](UPGRADES.md).

## Validation and maintenance

Use [VALIDATION.md](VALIDATION.md) for reproducible Python, JavaScript,
served-Dev and Chromium checks. Frozen schema fixtures are present; earlier
missing-fixture/browser-unavailable statements are expired historical limits.
Automated checks use disposable databases. Current platform/audio behaviour
still needs the intended installation/device. New work follows
[AGENTS.md](../AGENTS.md) and [PAGE_STYLE.md](PAGE_STYLE.md), with one owner per
shared concern and updated current references.

### Reviewed local database choice

Dev Git can compare live and committed upstream counts and issue a browser-bound
review token. Applying it requires `KEEP LOCAL`; changed data or Git targets
invalidate the review. Both copies are archived before acknowledging that exact
remote snapshot as the baseline. No live rows are changed. Normal upload then
publishes local data with the usual Git guards. Pending source updates require
a restart; the accepted choice survives that restart and prevents adopting the
rejected database. Later remote changes require another review.

## v5.2.1 maintenance inspection

`developer/database_inspector.py` owns authenticated GET `/api/dev/database/inspect`
(`name`, `offset`, `limit`) and `/api/dev/database/cell` (signed `review_token`,
`column`, `start`). Names must exist as tables/views in sqlite_master; identifiers
are quoted, values/limits bound, and user SQL is never accepted. Column metadata
uses table_xinfo; the inspector includes generated/hidden columns. Row previews
cap cell sizes and total cells per response. Long-value tokens bind the browser,
object, row offset and a type-sensitive row digest; changed rows return 409.
Read-only URI mode and query_only apply, with a three-second progress budget and
one-second busy timeout. BLOBs use base64 and integer values remain exact strings.
`static/js/dev_database.js` owns object/tab/page/value state and stale-response
protection; `dev_system.js` owns backups and Git status. GET `/api/dev/help/dev`
and `/api/dev/help/technical` serve the two allowlisted guides to authenticated Dev.

Git status reads are marked cached. Explicit checks return checked_at,
status_source=checked, upload_ready and an independent database_sync comparison,
including per-table local/remote deltas. Opening Git performs that check. Code
up_to_date alone cannot enable upload or represent database equality. The existing
shared-baseline algorithm and server-side upload/stop guards remain authoritative.

## v5.2.2 tag queue

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
