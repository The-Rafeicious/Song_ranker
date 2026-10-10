# Song Ranker V3.1.3 patch

Apply over V3.1.2. This patch contains three application files: `static/js/site.js`, `static/css/style.css` and `templates/base.html`.

## Install

1. Stop the local server.
2. Merge the included `static` and `templates` folders into your existing `Song_ranker` folder, replacing the included files.
3. Restart and refresh the browser. Shared assets now use V3.1.3 cache versioning.

No database, migration, backend change or additional dependency is included.

## Changes

- **Album previews:** the existing ten-second-per-track queue loops back to the first playable preview after the last one. Cover-edge previous/next controls wrap at both ends. Paused navigation stays paused, failed previews are skipped, and an album with no playable previews stops cleanly.
- **Standard and tournament previews:** playback loops from the start after thirty seconds, or the preview's natural end if it is shorter. Starting another preview still stops the current one.
- **After voting:** once the server saves the vote, the winning preview restarts and the result stays visible for 4.5 seconds. The next match then appears automatically with all audio stopped. The normal Next Match button is removed; load failures still offer a Retry button. Pausing the winner's audio does not cancel progression.
- **Standard scores:** Elo remains hidden before voting. Afterward, cover overlays show the previous rating, an animated new rating and its change. The winner rises in green and the loser falls in red. Blind mode reveals the song covers and metadata for the result, then hides the next pair again.
- **Tournament points:** the winning cover shows its awarded points counting upward in salmon pink. Tournament votes continue to leave regular Elo unchanged. The final result advances automatically to the champion page.
- **Standard heading:** the title is centred, with the Non-blind and Blind selectors below. Non-blind uses its orange colour and Blind uses teal. Score animations respect reduced-motion preferences.

## Validation

- 26 backend tests passed, including the existing database, import and track-position checks.
- 103 new interface assertions passed for preview looping, result timing, score animations, automatic tournament completion, silent next matches, failures, navigation cleanup and album controls.
- 293 existing interface assertions passed across the remaining pages and features, with expectations updated for automatic progression and album looping.
- A real JavaScript timer test confirmed the 4.5-second advance. Other timing checks used controlled timers.
- JavaScript syntax and ZIP integrity checks passed. The original database checksum is unchanged; write tests used copies.

Audio was mocked for testing. Live playback and graphical browser rendering were not verified here.
