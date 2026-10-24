# Vibe Map reference

**Integrated in app v5.1.0 · internal mode v1.1 · schema 20 · definition generation 2**

The current six-mode application serves `/vibe-map`, `/vibe_map_stats` and
`/mode_rankings/vibe`. This reference owns map meanings, play/storage/API rules,
similarity and statistics. [Dev editing and optional cleanup](VIBE_MAP_DEV.md)
has a separate operator reference. [Historical milestones](../update_logs/V5_1_UPDATE.md)
record earlier test-only versions; do not use their old setup instructions.

- [Map meanings](#map-meanings)
- [How to use the middle and mixed songs](#how-to-use-the-middle-and-mixed-songs)
- [Checking the design against your examples](#checking-the-design-against-your-examples)
- [Coordinates and charts](#coordinates-and-charts)
- [Flow and endpoints](#flow-and-endpoints)
- [Five-second readjustment and request ordering](#five-second-readjustment-and-request-ordering)
- [Averages, counts and storage](#averages-counts-and-storage)
- [Review and results](#review-and-results)
- [Similarity percentage](#similarity-percentage)
- [Preview ownership and cache](#preview-ownership-and-cache)
- [Heatmap contract](#heatmap-contract)
- [Reporting endpoints](#reporting-endpoints)
- [Coverage and evidence](#coverage-and-evidence)
- [All-track maps and patterns](#all-track-maps-and-patterns)
- [Pairs and consistency](#pairs-and-consistency)
- [Song inspection and profile cards](#song-inspection-and-profile-cards)
- [Home, Global Stats and rankings](#home-global-stats-and-rankings)
- [Activity and listening boundaries](#activity-and-listening-boundaries)

## Map meanings

| Map | X: left → right | Y: bottom → top | What to listen for |
| --- | --- | --- | --- |
| Pace & mood | Slow → Upbeat | Sad → Happy | Movement/pace separately from the emotional or lyrical tone. A sad song can be upbeat. |
| Sound & impact | Acoustic → Electronic | Soft → Powerful | Audible instrumental/electronic texture, separately from the impact of its delivery or main chorus. Slow songs can hit hard. |
| Connection | Fractured → Secure | Detached → Devoted | How the bond is doing, separately from affection or distance. Deep love can coexist with conflict or separation. |
| Perspective | Past → Future | Regretful → Hopeful | The story's time focus, separately from its outlook. The centre of X is labelled **Present**. |

Stable map IDs are `pace_mood`, `sound_impact`, `connection`, `perspective`;
definition generation is 2. These replace the old definition generation, not
reinterpret its coordinates. Songs still get all four required linked slots.

## How to use the middle and mixed songs

Use the centre when an axis is balanced, mixed or not strongly expressed.
Perspective's time centre is the present, but a story mixing past/current events
can also sit near it. A song about self or life can stay near the middle of
Connection when a relationship theme is not central; do not force it into a
breakup or romance category. A fully absent theme and genuinely mixed feelings
are not distinguishable with these eight numbers. That is an accepted limit of
four simple maps, not a reason to invent confident extreme positions.

Detached captures emotional distance, indifference or active resentment;
Devoted captures close, sustained emotional attachment. Budding attraction or young
love sits toward Devoted, at a lower intensity than deep commitment. A breakup can
express devotion, detachment or hatred: judge the narrator's feelings rather than
treating every breakup alike. Fractured/Secure describes the condition of the bond,
separately from those feelings. Sensuality alone does not imply devotion.

Judge Connection from the narrator's expressed position consistently. An ex
being hung up does not automatically mean the narrator is devoted. Use a broad
impression across the song: a strong chorus/bridge can raise impact even when
verses are soft, without requiring an extreme Powerful placement. Acoustic and
electronic elements can coexist; production quality is not the axis.

Agency, self-focus and narrative detail are intentionally not separate sliders.
Catchiness, favourite chorus/bridge, quality and song length are not measured.
Those either involve preference or would require more axes. The goal is a
repeatable overall impression, not a perfect lyrical analysis or genre classifier.

## Checking the design against your examples

These interpretations use your descriptions, not an independent lyric analysis,
and are guidance rather than automatic placements. No example coordinates are
written into your database.

| Song | Pace & mood | Sound & impact | Connection | Perspective |
| --- | --- | --- | --- | --- |
| Siren Sounds | Upbeat and sad at the same time. | Electronic, with a stronger chorus impact. | An unsettled bond can be Fractured while attachment remains Devoted. | Near Present for the described ongoing situation; judge outlook separately. |
| Go Away | Slower/relaxed and sad. | More Electronic but softer; a distinctive chorus need not mean a powerful hit. | Fractured and attached captures loving someone while resenting their behaviour. | Between Past and Present if both are part of the story. |
| Sleeping With the Lights On | Slow, with its mood placed independently. | More Acoustic in your description, but Powerful for the larger hit. | Fractured alongside Devoted fits growing apart while hung up. | Past/Present mixture does not force either extreme. |
| Blue | Place its pace separately from anger or sadness. | Instrumental texture can mix with production; the chorus/bridge raises impact. | Fractured fits conflict; commitment follows the narrator, not the ex's feelings. | Past-facing, with outlook judged from the expressed feeling. |
| Bubble Bath | Slow and sad. | Acoustic/soft with room for its build-up, rather than maximum impact just because the chorus is good. | Centre if the song's self/life questioning is not principally about a bond. | Place its actual time focus and outlook; self-questioning alone does not imply regret. |



## Coordinates and charts

Use a **continuous Cartesian graph**, not a collection of selectable grid boxes.
The page-facing X and Y ranges are **-5 to +5**; +Y should be upward. Stored and
shared similarity-reader coordinates remain -1 to +1. Conversion is `stored =
page / 5`. Both coordinates are required, finite JSON numbers; booleans, strings,
missing coordinates, NaN, infinity and out-of-range values are rejected.

No position is quantised to a grid. Drafts and averages keep full floating-point
precision. `display_x`/`display_y` and radar `value` are rounded to two decimal
places for labels; a frontend can format them with exactly two digits. Use raw
X/Y for graph placement. Each map definition provides endpoints, `min=-5`,
`max=5`, `step=null`, `display_decimals=2` and the reserved red colour. The four
map definitions are generation 2. Perspective also returns `x_center: "Present"`.
Stable keys are pace_mood, sound_impact, connection and perspective.

Completed-round summaries contain two representations:

- `summary.selection_radar`: the current pass's four submitted placements as
  eight spokes, X and Y for each map, in the semantic order below. Each spoke has its
  map ID/title, axis, low/high labels, displayed -5..5 `value` and full-precision
  `radius` in 0..1. Radius is `(normalised_coordinate + 1) / 2`. Neutral is 0.5.
- `summary.aggregate`: the song's running averages and sample counts, plus an
  identically shaped aggregate radar. This can differ from the current pass.

This eight-spoke graph preserves the eight independent dimensions; no quality
score is created by merging X and Y. Negative values are not invalid radial
distances: the radius conversion represents the low-to-high axis. Missing or
not-applicable spokes have null values/radii and should remain gaps, never fake
zero samples. Label the poles so a small radius is not mistaken for a poor song.

## Flow and endpoints

All writes use same-origin JSON POSTs. Normal successful responses contain
`version` and `round`; a missing current round is `round: null`. Round fields
include its server-issued `token`, song metadata/preview, `status`, `revision`,
`map_index` (0..4), ordered `maps`, `current_map`, `draft`, saved maps, the timing
fields below and a `summary` only when complete. Only one current round is kept
per browser session. No developer PIN is needed for this game mode.

| Method and endpoint | Purpose / body |
| --- | --- |
| GET `/api/vibe-map/state` | Read/resume this browser's current round. Does not create a session owner or draw a song. |
| POST `/api/vibe-map/round` | `{}` creates the first round or resumes an active/completed one. After viewing a completed/cancelled round, send `{"previous_token":"that-round-token"}` to draw the next song. Repeated starts cannot replace an active round. |
| POST `/api/vibe-map/draft` | Save/re-adjust the first uncompleted map or an already saved map from this round: token, map_id, revision, request_id, status, and X/Y. It changes no aggregate or completed-pass counter. |
| POST `/api/vibe-map/advance` | After the readjustment deadline, atomically accept the saved draft and return the next map, or the completed summary: token, map_id, revision, request_id. Do not send coordinates here; the server uses its latest acknowledged draft. |
| POST `/api/vibe-map/cancel` | token and revision. Discard the pending draft and end the round. Already accepted maps remain saved; an incomplete pass is not counted as complete. |
| GET `/api/vibe-map/similar/<song_id>?limit=2` | Rank comparable songs by coordinate closeness. Limit 1..100, default 2; exclude the source and songs with no shared placed maps. |
| GET `/api/vibe-map/profile/<song_id>` | Read the song's aggregate maps, sample/skip counts, updated times, completed passes and eight-spoke radar. |
| GET `/api/vibe-map/heatmap?kind=all` | Read the full-library aggregate point clouds. |
| GET `/api/vibe-map/heatmap?kind=artist&id=1` | Same for an artist. Also supports `kind=album` and `kind=tag`, using numeric IDs. |

An example first draft (coordinates are illustrative, not assigned to a real song):

```json
{
  "token": "server-issued-round-token",
  "map_id": "pace_mood",
  "revision": 0,
  "request_id": "fresh-client-uuid-for-this-adjustment",
  "status": "placed",
  "x": -2.37,
  "y": 3.14
}
```

**Legacy/API compatibility only:** the current player has no N/A button. To mark
a map not applicable through a compatible consumer, send `status: "not_applicable"` and omit X/Y (or
set both null). This decision gets the same readjustment window and can be
changed before advancing. Do not send zero coordinates as a substitute.

## Five-second readjustment and request ordering

The draft response returns the new revision, `server_time`, `advance_at`,
`remaining_ms`, and `readjust_seconds: 5`. The server, not the client, establishes
the deadline. Each acknowledged new adjustment restarts that five-second window.
The frontend should reset its visible timer on a user adjustment, send that draft,
wait for the response and schedule advance from the returned remaining time.
Keep at most one draft write in flight, coalescing pointer moves, so older
responses cannot overwrite a newer choice. Do not use display rounding to change
the submitted point. The graph stays editable during the window.

When the timer expires, POST advance with the **latest draft revision** and a new
request ID. One transaction updates the running average, records a compact
receipt, advances the map and, on the fourth map, increments completed passes.
Replace the graph with the returned next map only after a successful response.
The next map starts blank with no running timer until placed. An expired timer
does not save in the background while the page is closed; on resume the UI can
advance the acknowledged draft immediately if its deadline has passed.

Tokens, revisions and request IDs have different jobs:

- A token identifies the current browser-owned round. Sending another browser's
  token, or an old token after starting a new round, returns 409.
- Revisions enforce draft/save ordering and prevent stale tabs from saving over
  a more recent adjustment. They increase on each accepted adjustment/transition.
- Each adjustment and advance gets a nonempty request ID up to 96 characters.
  Retry an uncertain request with the same body and ID. Identical draft retries
  do not reset the timer; identical advances do not add another sample or pass.
  Advance retries return `replayed: true` and `accepted_map`. Reusing an ID with
  conflicting data or for another saved map is rejected.

A too-early advance returns HTTP 409 with `code: "readjusting"` and remaining_ms.
Other 409 codes include stale_round, stale_revision, wrong_map, ended and
changed_sample. Refetch state when a revision/token conflict occurs. Invalid
coordinates or malformed JSON return 400; missing songs return 404. All requests
use the existing same-origin/LAN policy; cross-origin attempts are rejected.
Readers send no-store headers and read one database snapshot.

## Averages, counts and storage

The historical schema **17 → 18** added `sample_count` and `not_applicable_count` to each existing
song/map row, one `song_vibe_progress` counter row per song, and `vibe_rounds`
containing one replaceable round per browser. There is no per-play history table.
The round stores its current draft and at most four accepted-map receipts. Starting
the next round replaces that browser's prior row. This bounds receipts by browser
count rather than number of plays. Deleting a song cascades its mode data.

For a placed point, update each stored coordinate atomically using
`mean += (new_coordinate - mean) / (sample_count + 1)`, then increment the count.
No intermediate rounding occurs. The second point therefore averages equally
with the first; later points remain equally weighted, rather than repeatedly
halving the old mean. Simultaneous saves are serialised and retries are idempotent.

Not-applicable decisions increment their separate counter and are not coordinate
samples. They leave an existing numeric mean intact. If no numeric sample exists,
the aggregate status becomes not_applicable. A current pass can therefore show a
gap on its selection radar while the song's aggregate radar still has a historical
mean on that axis. Resetting/erasing historical averages is not part of gameplay.

Only a complete four-map pass increments completed_passes. Partial/cancelled
passes keep their accepted map samples but do not invent completed attempts.
The V1.0.1 picker now reads actual saved pass counts, retaining its strong
coverage bias. Similarity readers continue to consume the normalised means;
sample count is not allowed to make a track dominate a pool. No Elo, tournament,
Trivia, Overall, challenge or listening result is created by this descriptive mode.

Migration uses the existing backed-up transactional process. A schema-17 placed
point becomes one historical sample, not an invented history; a not-applicable
slot becomes one historical skip. A fully resolved old four-map set establishes
one prior completed pass, otherwise zero. Existing coordinates retain their exact
stored values. Exports, SQL backups and canonical rebuilds preserve counters,
pending drafts, deadlines and current receipts. These are historical schema-18
transport rules; the subsequent schema-19 generation change cleared incompatible
old Vibe data once. Normal current-schema startup retains current placements.
See [upgrade handling](UPGRADES.md#schema-and-storage-changes).

## Review and results

The first-uncompleted index never moves backwards. Saved maps may be viewed
without writes; their submitted raw point, rather than the aggregate mean,
restores the pin. A new draft on a saved map returns `draft.map_id` and the same
five-second deadline. Advance removes that round's previous raw contribution
from the current sum/count and adds the replacement atomically. Placed ↔ N/A
changes update both counters correctly. Other browsers' or previous passes'
contributions remain intact. Editing never adds another completed pass.

The draft target occupies one reserved `_draft_map` key in the existing bounded
round JSON; map receipts remain limited to four. Schema 19 drops incompatible old
rounds/receipts and starts these new definitions unmapped. No old point is relabelled.
A completed round with a pending review draft cannot be replaced by Next song.
Once Next song replaces the row, its previous pass is no longer editable.

The page sends serial drafts on pointer release or after a short keyboard idle,
coalesces later adjustments, and uses server deadlines for acceptance. Unsettled
writes and failed saves block navigation and Finish. Exact retries keep request
IDs. Reload restores server state after another tab changes token/revision.
The UI offers placement only; historical N/A points and the API's N/A support
remain intact for compatibility. Keyboard arrows remain available without sliders.

Automatic next-map saving remains. After all four maps save, the last map stays
open for adjustments until the user presses Finish. Results do not open on a
timer, and have no Readjust action. Finish becomes Next song in the stable song
card. A tab-local sessionStorage token remembers an explicitly opened result on
reload; a completed round that was not finished stays on its map. Hidden tabs
pause automatic progression. Already-sent writes may finish normally.

The shared `VibeCharts.radar()` renderer and `vibe_charts.css` keep related poles
adjacent: Happy → Hopeful → Future → Secure → Devoted → Powerful → Electronic →
Upbeat. Missing spokes stay gaps. Results show the aggregate radar, without raw
coordinate figures or a detailed legend. Pole meanings remain available through
SVG labels/titles. The public API retains coordinates and selection_radar for
future consumers; removing displayed figures does not discard stored precision.

## Similarity percentage

`vibe_similarity.compare_profiles(first, second)` returns similarity,
shared_maps, map_ids and coverage. Only shared placed maps count. Compute mean
squared Euclidean distance `D2` on normalised -1..1 points, then
`similarity = 100 * exp(-D2 / (2 * 0.65**2))`. This is a fixed Gaussian curve of
RMS map distance, not a probability or musical-quality score. Identical points
are 100%; opposite corners approach zero. No shared maps returns null and is
excluded. Missing/N/A points never become fake centres. One strongly different
map contributes its squared distance, rather than being diluted by a mean of
individually high map percentages. Swapping the two songs gives the same result.

The earlier linear curve was replaced during development; its sample-specific
comparison is [historical](../update_logs/V5_1_UPDATE.md). Width remains fixed:
adding songs changes neighbours, not an existing pair’s score. Tags/genre add
no hidden similarity penalties.

`vibe_map.similar_songs(conn, song_id, limit)` ranks unrounded percentages,
then shared-map evidence and song ID. HTTP results round to two decimals; the
mode displays one decimal plus n/4 shared maps. Limit remains 1..100 (default 2).
Partial evidence is labelled; fewer than two comparable songs gives fewer
matches. The gentle adaptive draw multiplier is unchanged: this sharper display
percentage does not increase clustering or restrict who can face whom.

Alternative-axis proposals are **expired / no longer necessary**; [retired-reference index](RETIRED.md). Changing definitions requires a versioned migration, not relabelling saved coordinates.
The selected generation-2 meanings are listed above. Old coordinates are never
reinterpreted by changing their labels.

## Preview ownership and cache

The song card keeps one audio element across map, review and result renders.
Its artwork play control uses the shared PreviewPlayback owner, source routing,
volume and bounded server RAM cache. Preload the current preview automatically;
Next song awaits `forgetPair` for the old track before warming the new one.
No persistent browser cache or second JavaScript audio copy is introduced.
Fresh entry is silent. A requested preview loops while visible. Switching tabs
leaves its current clip playing, but never starts another loop while hidden.
Returning resumes a requested ended loop; a deliberate pause remains paused.
Actual navigation cleans up through the shared page lifecycle.

## Heatmap contract

Heatmap responses return one continuous aggregate point per placed song/map,
with −5…+5 coordinates, song ID, sample count and weight 1, plus missing/skipped
counts. Artist/tag membership never multiplies rows. No grid is imposed or
persisted; library/artist/album/tag views retain exact coordinates and overlaps.
Profiles, rankings and library summaries are implemented as described below.

## Reporting endpoints

| Read endpoint | Result |
| --- | --- |
| `/api/vibe-map/stats` | Dedicated dashboard counts, map points/density, patterns, balances, pairs, contrasts and group records. |
| `/api/vibe-map/inspect/<song_id>?context=profile` | Compact song radar/metadata/two matches; profile context omits the duplicate song identity. Default stats context retains it. |
| `/api/vibe-map/entity/album/1` | Collection summary and compact maps; artist/tag use the same path contract. |
| `/api/vibe-map/library` | `profile_ready`, summary, four maps, compact Home/global HTML, per-category counts and top-twenty banner arrays. |
| `/api/vibe-map/rankings?entity=albums&view=top` | Albums/artists/tags only, top/bottom, fixed limit 20, absolute rank, mapped counts and displayed consistency. Invalid entity/range returns 400. |

Readers return one consistent, read-only/no-store snapshot. Ordering uses raw
consistency before evidence/coverage/ID ties. Album rows retain title and name.
Inspection/entity cards expose `profile_ready`: all four song maps or at least
two fully mapped collection members. Missing points stay absent. Connection's
Detached label is presentation only; canonical stored Casual is unchanged.

## Coverage and evidence

- Tracks with selections: distinct songs with any saved placed/N/A status.
- Fully mapped: songs with valid numeric placements on all four current maps.
- Partly mapped: selected songs that are not fully mapped. Still to map: songs
  with no saved selection. Legacy N/A statuses never create artificial points.
- Completed passes: saved per-song completion counters. Repeat-mapped tracks:
  more than one completed pass or more than one saved sample on any map.
- Saved placements: accumulated numeric samples across all four maps, not rows
  of history. Reviewing a current pass replaces its sample rather than adding
  another. Library tracks and saved map positions provide the denominators.

## All-track maps and patterns

Each map draws exactly one continuous dot for each song with a placement on
that map, using its saved average. Repeats never duplicate or weight that dot.
Unmapped/N/A positions are omitted, counted as without a point, and never drawn
at the centre. Points retain their coordinates, including exact overlaps.

Colour uses the number of songs within a radius of one displayed axis unit
(0.2 in normalized storage), including the song itself. A spatial grid finds
neighbours without rounding song positions. All four charts share one colour
scale; denser neighbourhoods are brighter and overlapping dots accumulate.
The largest neighbourhood count is shown on each chart. Hover or focus a dot
to identify its song; arrow keys browse all points, Home/End select endpoints,
and Enter or Space opens the in-page song inspector. Every song remains reachable even when dots overlap.

Common combinations count distinct songs beyond one displayed unit from the
centre on two different axes. Both requested map placements must exist; the
shown denominator is the number with that evidence, not the whole library.
Eight combinations are ordered by count, then share, then label. Axis balance
shows both poles and an inclusive -1..1 centre band. Perspective calls its
centre Present. Partial songs contribute only to axes they actually placed.

## Pairs and consistency

Closest matches and biggest contrasts each show two distinct unordered pairs
from fully mapped songs. All four maps have equal weight. They use the same
fixed Gaussian similarity as the mode's results, with normalized width 0.65;
adding songs cannot rescale an existing pair. Unrounded values decide order;
percentages display one decimal. Pairs may share a song, never repeat its inverse
or compare a song with itself. The search streams pairs, retaining four results
rather than an NxN table. It is quadratic time in fully mapped tracks.

Album, artist and tag consistency uses fully mapped member songs only, with at
least two required. Singles and unknown albums follow the catalogue's normal
proper-album exclusion. Collaboration/tag membership includes a song once per
group. Each row shows mapped / total tracks, so sample size stays visible.

Let D be the mean squared distance over all distinct song pairs and all four
maps. Consistency is `100 * exp(-D / (2 * 0.65²))`. All eight coordinates count;
a tight cluster approaches 100%, a broad spread scores lower. It is descriptive
cohesion, not quality. With two songs it equals their public similarity. Centred
sums compute the exact pair-distance mean in linear time per group. Repeated
attempts and larger group size do not multiply a song's contribution. Five most
and five least consistent groups are shown; ties prefer more mapped tracks,
then coverage and ID. Small libraries can show a group in both lists.

## Song inspection and profile cards

On the main stats page, activating a heatmap dot opens a compact song inspector
below the maps. Hover/arrow browsing alone sends no request. The selected song
is centred above its saved-average radar, explicit song/album/artist links and
two closest matches. Partial evidence retains gaps and labels shared maps.
Enter/Space activates; arrow/Home/End browsing can reach overlapping points.
Loading/retry/deleted-song states are explicit; changing selection/navigation
cancels obsolete work so late responses cannot replace the current selection.

`GET /api/vibe-map/inspect/<song_id>` returns identity, saved profile, matches,
`total_comparable`, `map_count` and autoescaped HTML, using one read-only/no-store
transaction. It creates no play round, placement, pass or listening observation.
`templates/vibe_song_stats_panel.html` and `vibe_song_stats.css` own the reusable
compact card; `VibeCharts.radar(data, label, true)` selects its compact geometry.

On dedicated song profiles the same card sits directly above Overall and omits
the duplicate identity via `?context=profile`. It is hidden, including its loading
space, until all four maps are placed. The main stats inspector keeps identity
and supports partial profiles. A request failure offers Retry instead of implying
that no data exists.

Album/artist/tag cards sit above Overall once two members are fully mapped.
Their summary gives consistency, fully mapped/total tracks and a partial count
when nonzero. Four compact heatmaps share one wide row above 760px, capped at
960px; phones use two columns. Fixed 11px dots are larger than the main stats
dots, retain exact positions and reveal song names on hover. All four scoped
maps share a density colour scale. Single-release album pages may show their
own card, although proper-album rankings exclude Singles.

`GET /api/vibe-map/entity/<kind>/<entity_id>` supports album/artist/tag and
returns kind, entity, summary, maps, readiness and an autoescaped HTML fragment.
The loader owns local retry/cancellation/history restoration and never replaces
the hero audio or blocks Overall. Detached is a display-only Connection label;
canonical Casual, saved coordinates and schema-19 validation remain unchanged.

## Home, Global Stats and rankings

Home's compact all-song card follows Overall Leaders and requires two fully
mapped songs. All saved per-map placements contribute once, including partial
songs on their existing maps. The final scrolling banner mixes up to twenty
albums, artists and tags per category into one strip, ordered by displayed
consistency and category rank; there are no category buttons. Shared scrolling
handles arrows, focus/hover pause, hidden tabs and reduced motion. No eligible
groups hides the banner. Mode figures are red; song/album/artist/tag identities
retain green/purple/blue/gold and their existing art shapes.

Global Stats places a Vibe summary below Overall: selected/full tracks, map
positions, completed passes, coverage and best eligible album/artist/tag with
mapped counts and group totals. Real zero-data summaries remain visible.

`/mode_rankings/vibe` has Albums, Artists and Tags only. The API accepts top or
bottom, fixes the limit at twenty, and returns absolute ranks from the full
eligible population. Invalid categories/ranges return 400; a song category URL
normalizes to Albums in the UI. Proper-album rules exclude Singles/unknown
albums. Each eligible group needs two fully mapped tracks. Raw consistency
orders within each category, then mapped count, coverage and ID; bottom view
reverses the full list before taking twenty. Repeated attempts do not multiply
a song’s contribution. Display percentages are not rescaled with library size.

Library/ranking readers batch saved profiles and scan member groups rather than
running the dedicated page's quadratic pair highlights. They add no persisted
scores. These read-only/no-store surfaces share ranking controls, row geometry,
semantic colours, fixed limits and rank-dependent red glows with other modes.

## Activity and listening boundaries

Global's fourteen-day chart and recent-results feed include one latest retained
Vibe update per song on its saved UTC date. Partial saves count; unseen slots
do not. Repeats replace the retained song timestamp rather than adding a complete
pass history. This activity contributes no accuracy denominator, Elo result or
Overall score.

Listening-time capture and storage were retired across the app in v5.1.2.
Preview playback remains available; no listening-duration cards are shown.

The play card shows the number of assigned tags directly below the album. Counts
refresh with round responses, so tagging alongside Vibe Map becomes visible on
the next save or map advance; playback stays mounted.
