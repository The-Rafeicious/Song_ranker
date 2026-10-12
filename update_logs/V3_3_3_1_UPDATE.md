# V3.3.3.1 — Shelves scoring and reveal polish

## Install

Apply over **V3.3.3**. Stop the app, extract the patch and copy its `Song_ranker`
contents over your existing project, preserving the relative paths. Restart with
`python main.py` and hard-refresh the browser. The footer shows **3.3.3.1**.
Keep your database and backups; neither is included in this patch.

## Points

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

## Reveal audio and timing

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

## Cards, menus and results

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

## Verification

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
