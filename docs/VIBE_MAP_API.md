# Vibe-Map-v1.0.4 mode and API contract

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

The page sends serial drafts on pointer release or after a short keyboard/slider
idle, coalesces later adjustments, and uses server deadlines for acceptance.
Unsettled drafts, in-flight writes and failed saves block map navigation and
Finish. Exact retries keep request IDs. Reload round restores server state if
another tab has changed its token/revision. Every map requires a placement or
an explicit Not applicable decision; future uncompleted maps cannot be skipped.

After the fourth save, a five-second visible-time review window offers
Readjust or See results; Finish is also available below the song identity.
Readjust keeps the maps open until Finish. The results can reopen maps until
Next song. Hidden tabs pause progression and never initiate automatic saves or
results transitions. Already-sent writes may still finish normally.

The shared `VibeCharts.radar()` renderer and `vibe_charts.css` accept public radar
spokes for future profiles. Positive-pole order is Happy → Hopeful → Confident →
Social → Close → New love → Dreamlike → Intense. Low/high pole labels and the
neutral dashed ring retain the bipolar meanings. Missing spokes leave gaps.
The mode shows the aggregate radar so it agrees with similarity comparisons;
`selection_radar` remains available to consumers needing this pass alone.

## Similarity percentage

`vibe_similarity.compare_profiles(first, second)` takes normalised map profiles
and returns `similarity`, `shared_maps`, `map_ids` and `coverage`. For each shared
placed map, closeness is `1 - Euclidean_distance / (2 * sqrt(2))`. The percentage
is 100 times the equally weighted average closeness. The HTTP API rounds it to
two decimals after sorting.
Identical positions are 100%; opposite corners are 0%. No shared placed map
returns null and is excluded from ranking. Missing/N/A maps never become centres.

`vibe_map.similar_songs(conn, song_id, limit)` ranks aggregate means by unrounded
coordinate closeness, then shared-map count, then song ID. The public percentages
are rounded for display. Results expose comparison coverage; a 100% match on one
shared map is weaker evidence than on four. The mode displays `n/4 maps` with
each match. Fewer than two comparable songs produces only the available matches.
GET accepts limit 1..100 for future song-based similarity lists. This percentage
is independent of the small, coverage-scaled Gaussian draw bias and changes no
Elo, performance rankings or Overall score.

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
