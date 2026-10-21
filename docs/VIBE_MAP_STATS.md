# Vibe Map stats · v1.0.5

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
and Enter opens the track. Every song remains reachable even when dots overlap.

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
sample counts and completion counters, not an attempt-history table. Individual
song/album/artist/tag profile stats and mode rankings remain future work.
