# Vibe Map stats · v1.0.7

Open Stats → 📍 Vibe Map Stats, or the Stats link on the mode page.
The dedicated page is `/vibe_map_stats`; its read-only JSON projection is
`GET /api/vibe-map/stats`. Both read one SQLite transaction snapshot and return
`Cache-Control: no-store`. Opening stats creates no placements or play offers.
Schema remains 19. Existing generation-2 placements, averages, draw bias,
public song similarity and Overall are unchanged. No database reset is needed.

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

There are no invented activity timelines: the mode retains compact averages,
sample counts and completion counters, not an attempt-history table. Dedicated profile cards are available in v1.0.6; mode rankings remain future work.

## Compact song inspector · v1.0.5.1

Activating a heatmap dot keeps the stats page open and loads the Song vibe panel
just below the maps. Hover/arrow browsing alone never triggers a request.
The panel shows the song's saved average radar, explicit song/album/artist
links, mapped evidence and two closest comparable songs. Each match labels
shared maps; partial profiles retain radar gaps. Loading, retry and deleted-song
states are explicit. New selections cancel older requests, and late responses
cannot replace the current selection. Navigation cancels pending inspection.

`GET /api/vibe-map/inspect/<song_id>` returns song identity, saved `profile`,
`matches`, `total_comparable`, `map_count` and an autoescaped HTML fragment.
It uses the mode's existing fixed similarity and a single read transaction;
no play round, completion, listening observation or placement is created.

`templates/vibe_song_stats_panel.html` and `static/css/vibe_song_stats.css` own
the compact reusable layout shared with song profiles. Load shared
mode stats and Vibe chart assets too. `VibeCharts.radar(data, label, true)` uses
compact geometry; existing mode results keep their original default geometry.
Version 1.0.6 mounts the same component on dedicated song pages, immediately
above Overall.

Listening observations currently support Standard, Blind, Tournament, Trivia,
Guesser and Shelves only. The schema excludes Vibe Map and the mode sends no
listening payload. Consequently no Vibe listening mean/high/low container is
shown; unrelated playback data and unknown durations are not treated as zero.
Listening capture/schema changes are outside this conditional display patch.

## Dedicated profile cards · v1.0.6

Song, album, artist and tag pages mount Vibe Map directly above Overall. The
song card uses the saved-average radar and two comparable matches from the same
inspector endpoint. Its selected identity and metadata are centred at the top,
including when opened from the main stats heatmaps.

Collection cards show consistency, fully mapped / total songs and a partly
mapped count when nonzero. Their four small heatmaps stay in a 2×2 grid, capped
at 480 px across. A fixed 11 px dot represents one song on each placed map;
hover reveals its name. The continuous axes and density calculation are the
same as the main stats report, with one colour scale shared across the four
scoped maps. Coordinates are not rounded or snapped. No fake centre points are
created. These compact plots are summaries; the Stats link opens the larger
interactive dashboard.

Consistency uses only fully mapped member tracks and needs at least two. Empty
or single-track evidence gives an unavailable rate, not 0% or 100%. Partial
songs appear only on the maps they placed. Artist/tag membership uses EXISTS,
so collaborative or multiply tagged tracks never duplicate within a collection.
Single-release album pages can show their own descriptive card even though the
main dashboard's proper-album rankings exclude Singles.

`GET /api/vibe-map/entity/<kind>/<entity_id>` supports album, artist and tag.
It validates identity, bulk-loads only that collection's songs and returns
`kind`, `entity`, `summary`, `maps` and an autoescaped `html` fragment from one
read-only/no-store transaction. The profile loader owns local loading/retry and
cancellation, refreshes on browser history restoration, and does not block
Overall or replace the hero audio. Schema 19, saved maps and scoring stay unchanged.

## Compact profile follow-up · v1.0.6.1

Profile cards are hidden without reserving space until songs have all four maps
placed, or collections have at least two fully mapped tracks. Public responses
include `profile_ready`; missing data remains available to read-only consumers.
Loading placeholders stay hidden to avoid flashing empty panels. A request
failure remains a short retry state rather than pretending data is absent.

Song profiles request `/api/vibe-map/inspect/<id>?context=profile`, which omits
the repeated identity block. Default inspection on the main stats page retains
that block and continues to support partial radars. Collection cards now lay
out four small maps in one row above 760 px (maximum grid width 960 px); phones
retain two columns. All points and consistency calculations remain unchanged.

Connection displays Budding → Devoted for its Y axis: an early, unestablished
bond growing into devotion. This is a label-only presentation override across
maps, radar labels, common combinations and balances. The stored schema-19
Casual label is retained for snapshot validation/compatibility. No migration,
reset, coordinate reinterpretation or database write is required.

## Library surfaces and rankings · v1.0.7

Home places a compact all-song card directly after Overall Leaders, using all
saved per-map placements and the library's full-profile consistency. It follows
the existing two-fully-mapped-track visibility rule. The final Home banner has
Album/Artist/Tag tabs, each showing up to twenty most consistent groups. It uses
the shared scrolling owner, including pause on hover/focus, manual arrows,
hidden-tab pause and reduced-motion support. Empty categories have a short
empty state; the banner stays hidden when no category has ranked groups.

Global Stats places a Vibe Map summary directly after Overall: selected/full
tracks, saved map positions, completed passes, coverage and the best eligible
album/artist/tag, with mapped counts and ranked-group totals. Zero-data global
summaries remain visible as real counts. Stats and Rankings links are included.

`/mode_rankings/vibe` offers Albums, Artists and Tags only. Top twenty and Bottom
twenty use the existing shared mode controls, row geometry, artwork, semantic
entity colours and rank-dependent Vibe-red glows. Rows show consistency and
mapped/total tracks. Bottom rows retain their absolute full-population rank.
A song category query normalizes to Albums in the UI; the API rejects songs.

Only groups with two fully mapped members qualify; proper-album rules exclude
Singles/unknown albums. All saved averages count once per member, independent
of repeats. Consistency is the same all-four-map metric as the dashboard.
Unrounded values determine order, then mapped-track count, coverage and ID.
Bottom view reverses the full ordered list before taking twenty, matching other
mode boards. Banner order is the same as the corresponding top board. Display
percentages do not rescale as the library grows. This is descriptive cohesion,
not song quality, and adds no Overall component or draw change.

Library/ranking readers batch profiles and scan group members; they do not run
the main stats page's quadratic song-pair highlights or persist extra data.
Requests are read-only/no-store snapshots. Async selection/retry/navigation
handling ignores obsolete responses. Existing profile and stats links include
the new collection boards. Schema 19 and all saved data remain unchanged.
