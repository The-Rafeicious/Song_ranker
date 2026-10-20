# V5.1.2.1 — Spotlight bar and results refinement

## Install

The preceding relative Spotlight release is now **V5.1.2**, replacing its former
V5.1.1.3 label. This patch applies directly over that download; you do not need
a separate reinstall. The ZIP contains **changed and added files only** under
`Song_ranker/`. Stop the app, merge that folder, restart and hard-refresh. Check
footer **V5.1.2.1**. No files need deleting; the old guide is a compatibility link.

Schema 17, existing results, adaptive selection/Overall weights and persistent
safe mode remain unchanged. No database or synthetic results are included.

## Placement

Choose the numbered button below a song’s artist/album metadata. Selected ✓ and
a glow confirm the selection. Cover clicks control audio; metadata links remain
normal links. Position the selected song on the compact Worse → Better rail.
Its miniature cover appears above the line. Nearby/overlapping covers fan apart
on hover or keyboard focus, leaving the rail itself available for tie placements.

The rail pulses on a change. After **1.5 seconds** without another adjustment,
the next unplaced song is selected; once all are placed, it moves to the next
card. Dragging waits until release. Editing restarts the delay, selecting a song
manually cancels it, and returning to change an earlier song enables it again.
You can always reselect and adjust. All four still require an explicit placement.
Keyboard arrows, Shift+Arrow/Page Up/Down and Home/End remain supported.

## Footer and results

The footer is **available points · Loop previews · Next round**. Placement loop
previews retain Standard 20 seconds / Quick 10 seconds per song, redirecting from
clicked covers. Points remain hidden while placing and during an uncertain save.

**Next round** saves the existing automatic 12-point split, then shows results:
clean point bands over the covers, rearranged bar covers by point order and a
brief preview of each song from highest points down. Snippets last two seconds
in Standard or one second in Quick. Exact ties stay grouped and play in original
card order. The new offer starts after this finite pass; the results Next round
button skips the rest immediately. Loop previews can stop/replay the result pass.

Buffering does not consume snippet time. Missing previews are skipped and
permission blocks retain results for manual cover Play/Next. Hiding/leaving stops audio.
Result previews never add another judgement or listening sample. Fresh offers
begin silent. Failed/uncertain saves do not reveal points or start result audio.

See [page controls](UPGRADE_V5_1_1.md), [technical guide](TECHNICAL_GUIDE.md),
[style guide](PAGE_STYLE.md), [database reference](DATABASE.md) and
[validation](VALIDATION.md).
