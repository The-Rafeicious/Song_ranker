# Vibe Map implementation log

## Vibe-Map-v1.0.7 — Home, Global Stats and collection consistency boards

Add compact all-song maps below Home's Overall Leaders and a final scrolling
consistency banner with Album/Artist/Tag tabs, twenty rows per category. Use the
existing scrolling owner and record-card layouts. Add a concise Global Stats
summary below Overall with coverage, passes and best eligible collection records.

Add Mode Rankings → Vibe Map with albums/artists/tags only, shared top/bottom
twenty controls, absolute ranks, red glows and semantic entity/track colours.
Use the existing four-map consistency, two-fully-mapped-member minimum and
proper-album exclusions. Sort raw scores before evidence/ID ties; bottom view
reverses the full list. Banner and top-board order match. Add context links.

New library/ranking endpoints read a consistent no-store snapshot, batch saved
profiles and scan member groups, avoiding quadratic song-pair highlights. Keep
missing evidence absent and repeats as one averaged point per song. Handle
retry, stale requests and history restoration without duplicate scrolling timers
or changing Overall scores. Schema 19 and all stored results/backups are intact.
Update README, API/stats docs and styling rules.


## Vibe-Map-v1.0.6.1 — compact conditional profile cards

Hide song cards until all four maps are placed; hide collection cards until two
tracks are fully mapped. Reserve no room for unknown/insufficient data. Omit the
selected identity only in dedicated song-page context; keep it on main stats
inspection. Put collection maps in one compact row on wider screens and retain
two columns on phones. Keep aligned captions and 11 px dots.

Rename Connection's low Y display label to Budding across maps, radar labels,
common patterns and balances. Retain the canonical stored Casual definition so
existing schema-19 databases, active rounds and SQL backups validate unchanged.
No migration, reset or scoring/coordinate change. Document visibility rules and
context flags; test both hidden and visible cards and read-only label behaviour.


## Vibe-Map-v1.0.6 — dedicated entity cards

Centre the selected song identity/metadata in the shared compact card. Mount
that saved-average radar and two nearest matches directly above Overall on song
profiles. Album, artist and tag profiles get red cards in the same position,
with consistency, fully mapped/total tracks, partial counts and four compact
heatmaps in a fixed 2×2 layout. Keep maps small and dots at 11 rendered pixels;
preserve exact positions, shared density colouring and hover names.

Reuse the dashboard's four-map consistency and missing-value rules. New scoped
read-only endpoint validates entities and bulk-loads only their songs, using
EXISTS membership for artist/tag deduplication. Local loading/retry is independent
of Overall and hero audio; cancel stale requests and refresh on history restore.
Version profile assets with the current mode release. Update README, API/stats
docs and style rules. Schema 19, placements, draw bias and Overall calculations
are unchanged; no database or backup snapshot is modified.


## Vibe-Map-v1.0.5.1 — compact heatmap song inspection

Heatmap point clicks and Enter/Space now inspect a song in place. Add a compact
saved-average radar, explicit song/album/artist links and two nearest comparable
songs with shared-map counts. Extract a reusable song-panel template/stylesheet
and optional compact chart geometry; leave the existing mode radar unchanged.
The read-only inspector endpoint uses one snapshot and existing similarity.
Keep loading/retry/deleted-song states, cancel obsolete requests and ignore late
responses. Preserve pointer/keyboard browsing, exact dots and explicit links.

Checked listening coverage: the table supports six older modes only; Vibe Map
has no listening submission and is excluded by the schema. Omit its listening
container under the requested condition. Do not invent durations or add capture
and schema changes in this display patch. Schema 19 and all results remain intact.


## Vibe-Map-v1.0.5 — dedicated descriptive stats

Add Stats → 📍 Vibe Map Stats and a mode-page Stats link. Start with distinct
selected/full/partial/unmapped songs, passes, samples and coverage. Draw all
placed songs on four continuous maps with a shared neighbour-density colour
scale and keyboard/hover song links. Show eight common two-axis combinations,
eight axis balances, two closest pairs and two biggest contrasts. Finish with
five most/least consistent albums, artists and tags, including mapped counts.

Use one read transaction and bulk catalogue/profile loading. Consistency uses
all four maps and an exact linear-time pair-distance mean per group. Pair
highlights stream candidates without storing a quadratic matrix. Missing/N/A
points remain missing; repeats affect saved averages, never dot multiplicity.
Keep shared stats styling and explicit empty states without disclosures.

Schema 19, generation-2 axes, stored results, draw weights, public similarity
and Overall remain unchanged. No live database or SQL backup is modified.
See docs/VIBE_MAP_STATS.md for metric definitions and limits.


## Vibe-Map-v1.0.4.2 — simpler generation-2 maps and one-time test reset

Select four maps with one-word endpoints: Pace & mood (Slow/Upbeat, Sad/Happy),
Sound & impact (Acoustic/Electronic, Soft/Powerful), Connection
(Fractured/Secure, Casual/Devoted), Perspective (Past/Future, Regretful/Hopeful).
Perspective labels its midpoint Present. Musical pace, mood and chorus impact
are independent; a troubled bond can still be deeply devoted. Self/life songs
can remain near Connection's centre when that theme is weak or mixed.

Use new stable keys and definition generation 2, never relabel old coordinates.
Schema 19 resets only the old Vibe Map definitions/points/counters/rounds, inside
normal backed-up transactional migration. Each song has four fresh empty slots.
The standalone reset script requires an explicit test DB and is a no-op on 19,
so new results survive reruns, restarts and plain SQL restore. No new history or
retired-map table is added. Legacy definition code exists only to validate and
migrate old backups safely. Other catalogue/game facts remain unchanged.

Reorder the radar to Happy, Hopeful, Future, Secure, Devoted, Powerful, Electronic,
Upbeat. Preserve the fixed similarity curve, adaptive gentle draw bias and manual
results flow. Document examples using the user's descriptions, the limits of
four maps, and the one-time script/startup/reset/rollback behaviour.

Validated a disposable copy of the pushed backup: all 1,003 songs retained,
60 old placed slots removed, 4,012 new unmapped slots; every other table's values
unchanged. Pre-upgrade backup kept and a second reset is a no-op. Regression and
browser verification are recorded in the PR checks.

## Vibe-Map-v1.0.4.1 — testing polish and clearer similarity

- Centre the desktop song card beside the map container and keep it visible with
  bounded sticky positioning. Adapt short screens; keep stacked layouts clear.
- Move save/countdown feedback below the song controls. Raise the map heading;
  remove its subtitle, X/Y sliders/readouts and N/A action. Keep keyboard placement.
- Replace contour circles with a soft central glow and solid axes. Pulse outward
  along the axes when a pin changes; honour reduced motion. Put X endpoint labels
  beside the axis inside the graph so scrolling is unnecessary to identify them.
- Keep automatic map saving, but wait for Finish after the fourth map. Results
  contain the radar and similarity matches without a raw coordinate legend or
  Readjust action. The existing Finish button becomes Next song.
- Replace the inflated linear similarity display with a fixed Gaussian of RMS
  shared-map distance. Keep missing evidence explicit and keep all existing
  opponent-selection biases unchanged. No score depends on catalogue percentiles.
- Inspect the pushed backup read-only: 15 fully mapped songs/105 pairs show the
  old median 72.47% versus 43.40% with the new curve. No placement is edited.
- Document 20 possible two-axis maps and six four-map sets based on current tag
  themes and sonic gaps. These are choices for later; the four live definitions,
  their meanings, schema 18 and stored coordinates remain unchanged.

Validation is recorded in the PR checks: Python regressions, serial/retry/media
UI tests and served-browser checks for manual Finish, Next song, centred/sticky
placement, clean results and 320–1365 px layouts. No database/backup snapshot is
part of this source patch. The existing code-only merge guide still applies.

## Vibe-Map-v1.0.4 — continuous play page, review and similarity results

Implemented on the test branch; app version remains V5.0.5.1 and schema stays 18.
No production/test database or tracked SQL backup is changed by this code update.

- Add 📍 Vibe Map last in Home/Game Modes, with six home cards in a desktop
  3 + 3 layout and equal responsive cards. Reset the old five-card stagger.
- Add the red `/vibe-map` page: stable song card/player on the left, one named
  continuous map on the right, artwork pin/glow, subtle contours and -5..5 axes.
  Pointer positions are unquantised; labels use two decimals. Keyboard arrows
  and labelled sliders provide accessible alternatives to dragging.
- Save after the server-enforced five-second readjustment period. Back/forward
  restores saved pins; unresolved writes and incomplete maps cannot be skipped.
  Offer a short visible-time final review window, Finish and result readjustment.
- Extend saved-map edits to replace just this round's contribution, including
  placed/N/A changes. Keep concurrent browser samples and completed-pass counts.
  Retain serial writes, exact retry IDs and browser-owned resumable state.
- Keep one preview through every map/result. Use shared automatic RAM warming;
  forget the old preview before loading the next song. Hidden tabs finish the
  current clip without restarting its loop, and pause automatic progression.
- Add reusable radar SVG/CSS with related poles adjacent and missing spokes as
  gaps. Results show the aggregate radar plus up to two comparable songs.
- Add reusable Python coordinate similarity and GET similarity rankings with
  percentages, shared-map counts and coverage. Missing/N/A evidence stays absent;
  percentages are descriptive and independent of the gentle draw preference.
- Document the API, shared styling and a future code-only promotion into main.
  Keep production catalogue/backup files, leave experimental data behind, and
  include schema SQL/migrations when promoting source. No branches are merged.

Validation: 319 Python tests and all JavaScript suites pass locally, including
27 new Vibe Map UI checks and 39 existing served developer-page checks. Six new
Python tests cover review averaging, shared browser data, placement/N/A switches,
ordered navigation, canonical recovery, read-only similarity and the play route.
The CI browser check exercises real served templates/assets/API saves, review,
results, next song, 3 + 3 Home and overflow at 320–1365 px, saving screenshots as
workflow artifacts. Local browser execution is unavailable in this environment;
CI's browser result is recorded in the PR checks.

## Vibe-Map-v1.0.3 — Python round flow and aggregate saves

Implemented the backend only on `New-modes-test`. `main.py` registers
`songranker/modes/vibe_map.py`; no template, page route, CSS, JavaScript or
navigation was added. The app version stays V5.0.5.1, while schema advances
17 → 18 for compact counters and resumable current-round state.

- Expose continuous -5..5 graph coordinates, with two-decimal display labels.
  Store unrounded -1..1 coordinates to preserve the existing similarity policy.
  No selectable grid or fixed placement step is introduced.
- Draw through the existing coverage-first picker, then visit all four maps in
  definition order. Draft edits restart a server-enforced five-second window.
  Advance accepts the latest draft and returns the next map in one transaction;
  only the fourth accepted map counts a completed pass.
- Resume the current browser's round/draft/deadline after refresh or restart.
  Enforce browser ownership and optimistic revisions. Retry-safe request IDs
  prevent duplicate samples, repeated pass counts and accidental timer resets.
- Maintain one aggregate row per song/map with true running means, numeric
  sample counts and separate not-applicable counts. Skips are not zero samples
  and do not erase a previously saved mean. Cancelling discards only the pending
  draft; accepted maps remain saved without counting an incomplete pass.
- Add one lifetime pass counter per song and one replaceable current round per
  browser, containing at most four map receipts. No attempt-history table.
  The mapper now reads real repeat-pass counts instead of a binary projection.
- Return both current-pass and aggregate eight-spoke radar data, preserving the
  X and Y dimensions of every map. Missing/not-applicable spokes remain gaps.
- Provide read-only, continuous aggregate point clouds for library, artists,
  albums and tags. Each song contributes once regardless of repeat count; the
  frontend can render heatmaps without persisted density tables.
- Migrate existing schema-17 points as one known historical sample/skip, with
  one completed pass only for fully resolved four-map sets. Preserve original
  coordinate precision and retain generic backup/rebuild/recovery support.

The complete endpoint, timing, retry, chart and next-frontend contract is in
[docs/VIBE_MAP_API.md](../docs/VIBE_MAP_API.md). The only remaining Python UI
wiring is the page route when its template is added; the described game state,
save flow, radar data and heatmap data are ready for the frontend.

Validation: all 313 Python tests passed with no exclusions, including 16 new
runtime tests for continuous values, five-second rearming, ordered maps,
idempotent retries, concurrent saves, true repeated averages, skips, cancellation,
rollback, browser/origin guards, legacy migration, radar/heatmap outputs and
pending-state/receipt rebuild plus SQL restore. Existing JavaScript suites also
passed, including 39 served-page checks. A disposable copy of the actual Git
backup migrated 1,003 songs into schema 18 with 4,012 map slots, 1,003 pass counters
and no rounds; all original table values stayed unchanged.

## Vibe-Map-v1.0.2 — gentle similarity across existing modes

Added shared similarity helpers in `songranker/modes/vibe_similarity.py` and
integrated them with Standard Vote, blind voting (the shared pair selector),
tournament entries, Elo Guesser and Album Shelves. The mapper's coverage-first
picker is unchanged. Schema remains 17; no database writes, stored clusters,
extra tables, scoring changes or UI changes are introduced.

### Adaptive strength and safeguards against isolated pockets

For each eligible draw pool, coverage is the number of valid placed map slots
divided by four times the number of distinct songs. Only finite coordinates
inside [-1,1] with status placed count. Unmapped and not-applicable maps are
unknown evidence, not fake neutral coordinates. The maximum adjustment is
`strength = 0.15 * coverage`, recomputed from current data whenever a draw runs.
There is no activation threshold or stale cached coverage. A catalogue with 10%
of its slots mapped has at most a ±1.5% weight adjustment; 100% coverage permits
at most ±15%. Partial shared map evidence reduces the adjustment further.

For a pair, compare the placed maps shared by both songs using a smooth
two-dimensional Gaussian distance kernel (coordinate bandwidth 0.65). Average
its signed closeness across the four possible maps, with unshared maps
contributing zero. Multiply the existing candidate weight by
`1 + strength * signed_closeness`. Nearby coordinates get a small boost;
widely different ones get a small reduction. This does not rank musical quality.

- Keep the first song or album's existing exposure-based draw unmodified.
- Bias only the second song, or subsequent tournament entries/albums relative
  to the first randomly drawn reference. Do not repeatedly multiply adjustments,
  compare against an ever-growing consensus, or walk from one neighbour to
  another. Tournament similarities to the reference are computed once per draw.
- Multipliers always stay within [0.85,1.15], usually much closer to 1 when
  mapping is sparse. Similarity can change a candidate's odds relative to
  another by at most 1.15/0.85, about 1.35 times.
- After normalisation, an otherwise eligible candidate retains at least
  0.85/1.15, about 74%, of its previous conditional probability. This bounds the
  effect even for opposite corners of every map. No vibe-based hard exclusion,
  bucket, cluster or similarity cutoff exists.
- No map evidence gives multiplier 1. Unmapped catalogues produce the same
  draws with the same random seeds. New unmapped tracks retain their original
  exposure and age support. An unknown anchor produces no similarity bias.

Existing mode constraints still apply: recent-pair cooling, distinct-rating
requirements for Elo Guesser, preview requirements for blind pools, tournament
scope/size, and shelf capacity/track eligibility. Vibe differences introduce no
new eligibility restriction. Existing exposure weights, Elo kernels, Guesser
target quantile, champion seeding, shelf recency and randomness remain in place.
Tournament entries receive the small membership preference; the established
seeding and bracket placement are not replaced by vibe clusters.

### Album hotspots and scopes

Build each eligible album's profile from **all** songs belonging to it, including
unnumbered songs that cannot be drawn as shelf questions. For each map, distribute
the placed coordinates over a 5×5 grid with bilinear interpolation, then smooth
the density using the same Gaussian bandwidth. Compare the normalised density
vectors by cosine overlap. This retains multiple hotspots and the album's spread:
an album split between sad/gentle and happy/intense does not collapse to the same
profile as one whose songs all occupy the centre.

Use the smaller mapped fraction of the two albums for each shared map as an
additional confidence factor. One mapped song in a mostly unmapped album cannot
pretend to represent its whole scope. Normalised densities compare proportions,
so a longer album does not receive extra strength just for having more songs.
Album-level strength uses placed-slot coverage across the eligible albums' songs.
The first album is selected through the existing policy; later albums get one
bounded comparison to it. Track allocation and the ten-track ordering question
remain unchanged. No density/profile tables are persisted.

### Validation

83 focused tests passed, including 12 new similarity/integration tests, existing
mapper selection/storage, preference, developer-polish and developer-system
checks. Tests cover full/sparse/no evidence, malformed or missing coordinates,
conditional probability bounds, unbiased first draws, tournament selection,
cross-vibe pairs, multimodal album profiles, unnumbered album tracks, shelf
capacity and read-only database behaviour. A fully mapped two-vibe simulation
still produces cross-vibe pairs frequently; the four-thousand-draw regression
requires a cross-vibe share between 45% and 55%, rather than isolated pockets.
One historical preference migration method remains unavailable because its
upstream schema_v9.sql fixture is missing. No gameplay results are fabricated.

## Vibe-Map-v1.0.1 — coverage-first song selection

Added the pure picker beside the other mode selectors in
`songranker/modes/selection.py`, with its read-only database adapter beside the
other pool readers in `songranker/modes/selection_data.py`. Schema stays 17,
map definition version stays 1, and the app version stays V5.0.5.1.

### Selection policy

`choose_vibe_song(songs, rng, counts=..., previous=...)` draws one distinct song.
It reuses the existing adaptive exposure probabilities: pool-relative shortfall
support, the uniform exploration floor and the bounded, decaying new-song boost.
Only completed **Vibe Map** counts matter; Elo, trivia attempts, tournament
appearances, ratings and missing previews do not influence eligibility or counts.

- While any song has zero completed passes, allocate 95% of probability to that
  least-completed group and 5% to the adaptive distribution over the whole pool.
  A single untouched song therefore retains at least 95% probability even among
  thousands of songs already mapped once or twice.
- After first coverage, allocate 75% to the least-completed group and 25% to the
  whole adaptive distribution. This helps later passes stay close together.
- Within each distribution, the previous song receives a 0.25 multiplier. This
  discourages repeats without excluding the only unfinished song or blocking
  one-song libraries. When all counts match, selection reduces to the existing
  adaptive distribution with that soft recency adjustment.
- Every eligible song retains a positive probability. This is a coverage bias,
  not a hard quota or a guarantee that no song can repeat before another is seen.
  Empty pools return None; duplicate IDs are counted once. Injecting a seeded
  random generator makes a draw reproducible for tests.

`vibe_song(conn, counts=..., previous=..., rng=...)` reads the library, attaches
the shared age/map metadata, draws, then hydrates the selected song using
`get_song_full()`. It returns all four independent map slots. The adapter does
not create an offer, reserve a song, record an exposure, or save any result.

Schema 17 currently stores placements, not a completed-round counter. For now,
the adapter projects an incomplete four-map pass as 0 and a fully resolved pass
as 1. A placed or explicitly not-applicable slot is resolved; an unmapped slot
is unfinished. A partly completed song remains in the first-pass group until
all four slots are resolved. A future round controller can pass actual saved
counts (0, 1, 2, ...) through the same interface; supplied entries override the
projection and omitted entries keep it. Timestamps are not used to invent repeat
counts. The adapter cannot distinguish one completed pass from two using only
the current schema; persistence belongs to the gameplay stage.

### Result storage rule for the later gameplay stage

Keep one existing `(song_id,map_id)` row for the aggregate placement. Do not add
an attempt table or append a new row for every play. The second placement updates
each coordinate to the mean of the first and second values. Later placements
must remain an equally weighted running mean, rather than repeatedly halving
the old mean and the newest value:

`new_mean = old_mean + (new_value - old_mean) / (sample_count + 1)`

The future writer must persist a small sample count on that same aggregate row
so it can compute the true mean and supply repeat counts to selection. Update
the mean and count atomically and make retries idempotent. Unmapped and
not-applicable decisions are not coordinate samples and must never be averaged
as zero. Completion of the four-map pass and coordinate sample counts are
different concepts, particularly when a map is not applicable; define their
compact counters in the gameplay update. This patch records that contract but
adds no saving script, schema migration, page, route or gameplay integration.

Existing tournament/Elo selection and Overall calculations are unchanged; this
new selection policy applies only when the future Vibe Map controller calls it.

Validation: 52 focused tests passed, including 12 new selection tests covering
coverage priority, adaptive age weights, recency, actual read-only draws and
future repeat-count overrides. One historical preference migration method was
excluded because its upstream schema_v9.sql fixture is absent. Across 100 seeded
simulations, all 100 songs received a first pick in 100–105 draws (mean 102.23),
incrementing counts after each simulated completion. This measures selection
coverage, not a guarantee for abandoned rounds or gameplay that is not yet built.

## Vibe-Map-v1.0.0 — database and query foundation

Implemented on `New-modes-test`, based on V5.0.5.1. The app version stays
V5.0.5.1; Vibe Map has its own version. SQLite schema advances from 16 to 17.
The reserved mode colour is red, `#d94b58`, stored with the definitions.

### Four maps

Each map has two independent coordinates, both from **-1 to +1**. The low
endpoint is -1, the high endpoint is +1. Zero means a deliberately chosen
middle position, not missing data. Coordinates describe the song's perceived
vibe or theme, not its quality, preference rating or chart position.

| Stable map key | X: -1 → +1 | Y: -1 → +1 | What it captures |
| --- | --- | --- | --- |
| `mood_energy` | Sad → Happy | Gentle → Intense | Emotional tone independently of musical intensity; a sad song can still be intense. |
| `relationships` | Breakup / separation → New / early love | Guarded / distant → Close / devoted | Relationship theme and emotional closeness; established love can sit between the X extremes. |
| `self_social` | Vulnerable / self-doubting → Confident / defiant | Introspective / private → Outward / social | Self-perception and whether the song turns inward or towards others. |
| `reflection_escape` | Looking back / nostalgic → Looking ahead / hopeful | Grounded / everyday → Dreamlike / escapist | Time perspective and how rooted in everyday life the song feels. |

These choices were informed by the existing tag catalogue: sad/melancholic,
slow/up-beat/build-up, brake-up/past-love/falling-in-love/current-love,
self-hate/self-destructive/strong/rebel, retrospective/nostalgia/hope, and
electronic/soundtrack. Tags are incomplete, so **no coordinates are inferred
from tags, artists, titles, audio sources or existing results**. The maps are
interpretive dimensions; they are not automatic genre classifiers.

### Stored data and lifecycle

- `vibe_maps` stores exactly four stable definitions: key, title, four axis
  endpoints, definition version (1), red colour and display order. Changing
  endpoint meanings later requires an explicit definition/data migration.
- `song_vibe_positions` links a song to a map with `(song_id,map_id)` as its
  composite primary key. It stores X, Y, status and the last placement time
  (`updated_at`, Unix seconds). There is one independent row per map per song:
  **every song has four rows**, rather than being assigned to just one map.
  A shared link table avoids repeating four identical table structures.
- `unmapped`: both coordinates and timestamp are NULL. Existing and newly added
  songs start here. This does not imply neutral, sad, low energy or low quality.
- `placed`: both coordinates are present and within [-1,1], and timestamp is
  present. No combined score, confidence, repeated-placement averaging or
  preference points are invented in this version.
- `not_applicable`: both coordinates are NULL, with a timestamp recording the
  explicit decision. For example, an instrumental or family-themed song need
  not be forced onto the relationship map. Its slot still exists.

Schema constraints reject partial/out-of-range/non-numeric coordinates,
invalid statuses, duplicates, unknown maps and orphan references. A song-insert
trigger creates all four slots for every existing import/add path. Slots cannot
be deleted or moved between songs/maps; reset an existing slot to unmapped.
Deleting the song cascades its placements through the existing foreign-key
enabled app connections. An index supports reads by map and placement status.

The existing backed-up transactional migration creates all four unmapped slots
for every existing song. It retains song IDs, tags, sources, ratings, results,
timestamps and other stored facts. Repeated startup does not reset placements.
Schema validation checks the definitions and four-slot coverage. Full export,
canonical rebuild, SQL snapshot and restore retain the new tables through the
existing generic transport; the state-upgrade adapter supplies explicit defaults
when importing older schemas, including SQL dumps without a version pragma.

### Query integration

There are several shared readers, rather than one query for the whole app:

| Reader | Added data |
| --- | --- |
| `services.fetch_songs()` / `get_song_full()` | Each song has `vibe_maps`, a dictionary keyed by all four map IDs. Song rows now return dictionaries; existing metadata keys and filters remain available. |
| `catalog.collection()` / `/api/collection` | Same per-song dictionary plus top-level `vibe_map_definitions`, ordered for a future map interface. Artist, album and tag collections retain the songs' individual placements rather than inventing aggregate map scores. |
| `selection_data.with_catalogue_age()` | Same dictionary beside existing ID, Elo and age fields. Existing preference, tournament, trivia and Elo Guesser pool readers use this shared annotation path. |
| `vibe_maps.song_profiles()` | Read-only batch reader for explicit song IDs, with batches of at most 500 IDs; no joins that multiply song rows and no per-song query loop. |

For example, a future manually placed song can expose:

```json
{
  "vibe_maps": {
    "mood_energy": {"x": -0.75, "y": 0.4, "status": "placed", "updated_at": 123},
    "relationships": {"x": null, "y": null, "status": "unmapped", "updated_at": null},
    "self_social": {"x": null, "y": null, "status": "unmapped", "updated_at": null},
    "reflection_escape": {"x": null, "y": null, "status": "unmapped", "updated_at": null}
  }
}
```

This is an illustrative payload, not an assignment made to a real track.
The raw `SONG_SELECT` SQL constant retains its existing contract; use the shared
hydration readers when Vibe Map metadata is needed. Read paths never write or
create placements. Historical offline selector fixtures without these tables
receive explicit unmapped profiles; live schema-17 databases require the tables.

### Scope and later work

This stage adds no page, navigation, gameplay, write endpoint or selection
weight. It changes no Elo calculation, tournament seeding, exposure policy,
randomness or Overall component. The existing match selectors ignore the new
metadata. The second new mode is not implemented here.

Later, similarity can compare only maps marked placed for both songs. Unmapped
and not-applicable values must not masquerade as (0,0). A future selection change
should apply a small, bounded preference for nearby songs while preserving a
non-zero chance for every otherwise eligible opponent. It must not turn vibe
coordinates into performance results or add them to Overall.

For testing, use a separate database via `SONG_RANKER_DB`; schema 17 belongs to
this test branch, and the schema-16 main app cannot open an upgraded database.
Existing pre-upgrade backups remain available. No active database or committed
database snapshot is changed by this source-only update.

### Validation

- 208 runnable regression tests passed, including 10 Vibe Map tests covering
  four-slot creation, validation, independent coordinates, nullable/unmapped
  semantics, batched reads, shared projections, rollback, restart, full export,
  rebuild and SQL restore (including dumps without the version pragma).
- Existing preference and Elo Guesser selectors returned the same opponents
  with identical random seeds before and after adding map metadata.
- Migrated a disposable copy of the actual Git SQL backup: 1,003 songs produced
  4,012 unmapped slots; every original table's stored values remained identical.
- Three historical test methods could not run because upstream fixture files
  `tests/fixtures/schema_v9.sql` and `schema_v12.sql` are absent. No result is
  claimed for those methods. The new schema-16 migration fixture is included.
