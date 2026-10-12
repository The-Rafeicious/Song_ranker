# V3.3.3 — Album Shelves ordering and review

## Install

Apply over **V3.3.2**. Stop the app, extract the patch and copy its `Song_ranker`
contents over your existing project, keeping the relative paths. Restart with
`python main.py` and hard-refresh the browser. The footer shows **3.3.3**.
Keep your existing database and backups. This patch contains neither.

## Shelves layout

- Song cards show titles without artist names. The Shelves round API omits artist
  clues too; other modes and catalogue pages retain their artist information.
- Larger square album artwork sits above each album title.
- Check shelves sits above a narrower preview player. There is no extra submit
  panel, sticky results banner, order instruction or point-rule explanation.
- Cards have numbered shelf positions, clearer title spacing and compact move/
  reorder controls. Dragging, keyboard ordering, album selectors and optional
  previews remain available.

## Reveal and review

- Songs flip sequentially and move into the correct album and track order inside
  the existing drop boxes. The duplicate correction lists beneath the boxes are
  removed. Original album track numbers remain visible, including gaps.
- Red/green feedback grades the **submitted answer**, even though the finished
  display shows the corrected arrangement. Wrong albums and any order error show
  red; a fully correct answer shows green. Partial credit is preserved.
- Each album cover counts its own earned points. The former Check shelves button
  counts the total. A short snippet plays for each reveal when available.
- Reveals make no scroll requests; the board disables browser scroll anchoring
  during rearrangement. Nothing overlays the album boxes.
- After the last flip, the result stays indefinitely. **Next round** appears beside
  the total above the preview player. Only pressing it starts another round,
  silently. Guesser's automatic progression is unchanged.
- Completed results keep optional track and cycling previews for review. Leaving
  the page cancels clips and reveal timers. Returning through browser Back can
  resume an interrupted reveal from the already-saved answer without resaving.

## Album and track selection

- Automatic selection now randomly chooses between two and three albums with
  equal probability **when both can supply a valid round**. If only one size is
  feasible, it uses that size instead of failing or creating an invalid round.
- Eligible albums need at least two distinct valid positive track positions.
  Singles and one-track albums are excluded from new rounds.
- Each offered album receives at least two songs. Allocation favours the smallest
  shelf with remaining capacity: normally 5/5 or 4/3/3. Uneven splits are allowed
  only where the available album sizes require them.
- If enough alternatives can supply the selected size, albums from the preceding
  round are excluded. Recent rounds and album exposure then reduce repeat chances.
  A small library can reuse albums when necessary to keep a valid round possible.
- Every album draw checks the remaining capacity, avoiding random selection
  failures in sparse libraries. Songs retain the existing lower-exposure bias.
- There are still exactly ten distinct tracks. No upstream Apple lookup is added.

## Ordering statistics

Track order leads Shelves rankings, Top Tracks/Tracks to Practise, played-album
percentages and the home Shelves banner. Profile summaries show ordering and
points. Album membership remains in a collapsed stats breakdown and its ranking
metric rather than repeated across primary cards. It still contributes its
original 1 point to scoring; relative order remains worth up to 2 points per track.

Played-album ordering is calculated from saved round facts, so later album moves
do not reassign historical participation. Existing singleton round grades are
preserved, although new rounds do not create singleton shelves.

## Database and other modes

No migration, table or stored attribute is added. Schema remains **8**. Scoring
and answer writes are unchanged, and reveals use one saved answer response.
Selection and read-only Shelves summaries are the backend changes. No Elo voting,
Guesser, trivia or tournament rules are changed. README and version notes are
updated; shared asset cache keys follow the version automatically.

## Verification

**93 backend tests** passed, including equal album-size selection, even allocation,
singleton exclusion, sparse-library fallback, non-repeating consecutive rounds,
saved album participation and existing score/reset/migration checks.

**192 interface assertions** passed using a copied database and controlled media
events/timers. Both two- and three-album boards were tested, including swapped
tracks, a submitted empty shelf, correct-order movement, cover/total counting,
original-answer colours, no reveal scroll requests, manual progression, silent
new rounds, review playback availability, ordering stats and an interrupted reveal.
JavaScript syntax and both shared stylesheets parsed successfully.

The original database was not edited. Actual Apple sound output and graphical
browser rendering were unavailable here; media tests verify event handling and
sequence logic, not pixel-level rendering or real playback.
