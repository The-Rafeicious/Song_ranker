# Vibe Map implementation log

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
