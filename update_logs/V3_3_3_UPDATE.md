# V3.3.3 — Album Shelves ordering and review

This file groups the three-part release and its later hotfixes. The earlier
sections describe their historical release behavior; subsequent sections record
the changes applied by each patch.

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

## Patch V3.3.3.1

### V3.3.3.1 — Shelves scoring and reveal polish

#### Install

Apply over **V3.3.3**. Stop the app, extract the patch and copy its `Song_ranker`
contents over your existing project, preserving the relative paths. Restart with
`python main.py` and hard-refresh the browser. The footer shows **3.3.3.1**.
Keep your database and backups; neither is included in this patch.

#### Points

The selected split is **0.5 points for the correct album and up to 2.5 points for
relative track order**. A perfectly answered current ten-track round is still out
of **30**. Correct albums with completely reversed track order earn 5 rather than
10. Order comparisons, partial credit, gap handling and wrong-album rules otherwise
stay the same. Historical singleton shelves have a 0.5-point denominator and no
free ordering points; new rounds still exclude singleton shelves.

Scores are derived from saved answers, so this split applies to **existing and new
rounds**. Points, accuracy, best results, rankings, global/profile summaries and
Dev records update consistently. Stored answer facts are not rewritten. No new
table, stored field or migration is needed; schema remains **8**.

#### Reveal audio and timing

- Each answer holds for **2.6 seconds**, one second longer than before, following
  the existing 0.42-second closing flip. The hold starts after playback begins or
  after a bounded load/error fallback, giving buffered audio a longer window.
- Only the next answer preview is buffered. It stays silent until its card flips.
  The same audio element is reused for playback rather than creating another
  player for the already-buffered song.
- The outgoing song keeps playing during the next flip/loading window. When the
  incoming song starts, a short **180 ms fade** hands the audio over. After the last
  reveal, its audio fades out.
- Buffering is delayed by at least 650 ms after current playback starts, respecting
  the existing preview gate's minimum spacing. Request limits and metadata lookup
  limits are unchanged. There are no automatic retry loops or saved audio files.
- Missing/failed/cooldown-blocked previews do not stop the reveal. A playback start
  that stalls beyond three seconds is cancelled and the visual sequence continues.
  Leaving the page or starting another round disposes active, outgoing and buffered
  media and cancels scheduled buffers/reveals. Volume changes are respected.

Buffering depends on Apple and the connection; this reduces gaps but cannot promise
gap-free real playback.

#### Cards, menus and results

- Wrong cards retain their red feedback and show the **submitted shelf position
  crossed out beside the actual album track number**. Hover/accessibility labels
  distinguish the two, including original track-number gaps and wrong-album cases.
  Correct cards keep their single number. Submitted positions come from the saved
  answer response, not from the reordered display.
- The bottom Round complete/Perfect shelves text is removed. The centred controls
  now show total score, **Next round**, then a **Track order** percentage box on its
  right. On narrow screens the total sits above the Next/order pair. Results still
  wait for manual progression, and reveals make no scroll requests.
- Album selectors now have themed artwork options, readable full titles and a
  selected checkmark. Mouse, Tab/Enter, arrow keys, Home/End and Escape are supported;
  clicking outside or moving focus away closes a menu. Drag/drop, row keyboard
  reordering and preview controls remain available.

The balanced two/three-album selection and anti-repeat behaviour are unchanged.
Voting, Guesser, trivia and tournament rules are unchanged.

#### Verification

**94 backend tests** passed. The scoring regression checks reversed 5/5 shelves
earning 5/30, exact partial credit, authoritative submitted positions and consistent
derived summaries. Existing mode, selection, migration and reset checks remain.

**351 interface assertions** passed with a copied database and controlled media
events/timers, covering both board sizes, scores/corrections, centred controls,
menu navigation, buffered-element reuse, silent prefetch, outgoing-audio handoff,
volume changes, failures, cooldown, bounded load timeout and cancellation. JavaScript
syntax and shared stylesheet parsing passed.

The original supplied database is untouched. Real Apple playback and graphical
rendering were unavailable here; these tests verify events, timing and DOM structure
rather than actual sound continuity or pixel-level layout.


## Patch V3.3.3.2

### V3.3.3.2 — Shelves spacing and result styling

Apply over **V3.3.3.1**. Stop the app, copy the patch's `Song_ranker` contents over
your project, restart and hard-refresh the browser. The footer shows **3.3.3.2**.

- The Album Shelves play page has a **1480 px desktop maximum**, increased from
  1280 px. Existing padding, mobile stacking and compact preview controls remain.
- Submitted positions stay small and red beside the correct number, with the
  strike-through removed for readability. Saved-position labels remain available.
- Points, Next round and Track order use matching backgrounds, borders, corners,
  height and glow. Points and Track order use matching label/value typography.
  The centred layout and narrow-screen arrangement are retained.

This is a CSS patch plus version/documentation updates. JavaScript, scoring,
selection, audio, data and schema are unchanged. No migration is required, and
no database or backups are included.

Verification: shared CSS parsing and the existing **351 interface assertions**
passed using a copied database with controlled media/timers. Computed-style
inspection confirms the width, matching box frames and readable submitted numbers.
The original database hash is unchanged. Graphical rendering was unavailable;
pixel-level appearance has not been verified here.

