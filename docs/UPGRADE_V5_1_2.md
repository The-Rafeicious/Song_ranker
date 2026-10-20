# V5.1.2 — Relative Spotlight placement

This preceding release is now numbered **V5.1.2**. For the current refinements,
use [V5.1.2.1](UPGRADE_V5_1_2_1.md).

## Install this patch

This ZIP contains **only changed and added files**, with paths preserved under
`Song_ranker/`. It requires an installed **V5.1.1.2**. Stop the app, merge that
folder into your installation, restart and hard-refresh. Check footer V5.1.2.
No files need deleting. The package contains no database or sample answers.
Schema stays at 17 and safe mode keeps its persistent copy and refresh command.

## Play Spotlight

1. Listen to the covers, or start **Loop previews**.
2. Select a song card or its numbered button, then place it on the **Worse → Better** line.
3. Place the remaining tracks; select any card/marker again to move it.
4. Review the live shares over the covers and **Save split**.

All four need a placement. Similar placements get similar shares; tied
placements get equal shares. The 12-point total is automatic. You can place
all four together for 3/3/3/3, or separate one far above the others for a strong
preference. Positioning the whole group elsewhere without changing its gaps
does not affect points. Only the four integer allocations are stored.

The budget sits in the old Skip position. The heading Stats link, caption,
manual point inputs, +/− and Split equally controls are removed. Dedicated
Spotlight stats remain in the navbar. Song, artist and album links are retained.
Vibe’s controls remain unchanged.

Arrow keys move the selected song by one; Shift+Arrow and Page Up/Down move ten.
Home/End reach the axis ends. Numbered markers stack only when they collide.
Unplaced tracks show an em dash; the first selected card is not a default rating.
Draft positions resume after refresh. Unconfirmed saves still retry their exact
original answer, including receipts started in the previous manual UI.

## Loop previews

Loop previews plays 20 seconds per track in **Standard** and 10 in **Quick**,
then advances and wraps after the fourth. Use the existing navbar speed control.
Clicking another cover continues from that song with a fresh segment. Clicking
the current playing cover or Stop previews pauses/stops rotation. Buffering
and paused time do not count. If playback is unavailable, it tries the next
track; four consecutive failures stop it. Playback permission blocks ask for Play.

Hiding/leaving stops the loop, and each new round starts silent. Saving stops
rotation while keeping the current preview element for the result. Preview
activity never auto-saves a judgement.

## Allocation and compatibility

Target shares are `3 + 12 * (position - mean_position) / 100`. The allocator
chooses the closest valid integer split totaling 12, preserving position order
and exact ties. Small differences may round to equal shares. There are no
new song-level weights or stored graph coordinates. Existing support, adaptive
selection, reliability and Overall calculations consume the same allocations.

See [controls](UPGRADE_V5_1_1.md), [technical reference](TECHNICAL_GUIDE.md),
[style rules](PAGE_STYLE.md) and [validation](VALIDATION.md).
