# Vibe-Map-v1.0.4.1 mode and API contract

The test branch now serves `/vibe-map` with its template, CSS, JavaScript and
Home/Game Modes entries. Existing LAN/origin policy and shutdown guards apply.
Schema remains 18; no extra attempt/history tables are needed.

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
map definitions and their meanings are unchanged.

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
  "map_id": "mood_energy",
  "revision": 0,
  "request_id": "fresh-client-uuid-for-this-adjustment",
  "status": "placed",
  "x": -2.37,
  "y": 3.14
}
```

To mark a map not applicable, send `status: "not_applicable"` and omit X/Y (or
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

Schema **17 → 18** adds `sample_count` and `not_applicable_count` to each existing
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
pending drafts, deadlines and current receipts. Test this branch on a separate
database; schema-17 app code cannot open the upgraded schema-18 file.

## Review and results

The first-uncompleted index never moves backwards. Saved maps may be viewed
without writes; their submitted raw point, rather than the aggregate mean,
restores the pin. A new draft on a saved map returns `draft.map_id` and the same
five-second deadline. Advance removes that round's previous raw contribution
from the current sum/count and adds the replacement atomically. Placed ↔ N/A
changes update both counters correctly. Other browsers' or previous passes'
contributions remain intact. Editing never adds another completed pass.

The draft target occupies one reserved `_draft_map` key in the existing bounded
round JSON; map receipts remain limited to four. Legacy schema-18 drafts without
that key use the first-uncompleted index. No schema migration is required.
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
adjacent: Happy → Hopeful → Confident → Social → Close → New love → Dreamlike →
Intense. Missing spokes stay gaps. Results show the aggregate radar, without raw
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

The previous diagonal-normalised linear curve compressed typical comparisons
upwards. In the pushed backup reviewed for this patch (15 fully mapped songs,
60 points, 105 pairs), its median was 72.47%; the new curve gives 43.40%.
The pair range changes from 36.70–89.70% to 2.13–88.79%. This is a small early
sample, used to inspect scale behaviour rather than fit a moving percentile.
The width stays fixed: adding songs can change which neighbours appear, but
cannot change an existing pair's score. Tag membership and genre do not supply
hidden penalties or override user placements.

`vibe_map.similar_songs(conn, song_id, limit)` ranks unrounded percentages,
then shared-map evidence and song ID. HTTP results round to two decimals; the
mode displays one decimal plus n/4 shared maps. Limit remains 1..100 (default 2).
Partial evidence is labelled; fewer than two comparable songs gives fewer
matches. The gentle adaptive draw multiplier is unchanged: this sharper display
percentage does not increase clustering or restrict who can face whom.

See [map options](VIBE_MAP_OPTIONS.md) for alternative axes and four-map sets.
None are activated, and existing coordinates are not reinterpreted.

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

## Heatmap contract and future pages

Heatmap responses return one continuous aggregate point per placed song/map,
with -5..5 coordinates, song ID, sample_count and `weight: 1`, plus unmapped and
not-applicable song counts. Artist/tag membership does not multiply rows.
No heatmap grid is imposed or persisted; future pages can draw density fields
for library, artist, album or tag views. Each song contributes once per map.

This update builds the mode only. Future mode rankings put Vibe Map last;
individual stats pages place its descriptive container immediately below Overall.
Neither those pages nor a second new game mode are added here. See the
[code-only merge guide](VIBE_MAP_MERGE.md) before promoting test-branch code.
