# Vibe-Map-v1.0.4.2 — four simpler maps

The first two maps describe the sound and its emotional tone. The last two
cover connection and perspective. Each endpoint is one word; all eight axes
remain independent, continuous -5..5 placements.

| Map | X: left → right | Y: bottom → top | What to listen for |
| --- | --- | --- | --- |
| Pace & mood | Slow → Upbeat | Sad → Happy | Movement/pace separately from the emotional or lyrical tone. A sad song can be upbeat. |
| Sound & impact | Acoustic → Electronic | Soft → Powerful | Audible instrumental/electronic texture, separately from the impact of its delivery or main chorus. Slow songs can hit hard. |
| Connection | Fractured → Secure | Casual → Devoted | How the bond is doing, separately from depth/commitment. Deep love can coexist with conflict or separation. |
| Perspective | Past → Future | Regretful → Hopeful | The story's time focus, separately from its outlook. The centre of X is labelled **Present**. |

Stable map IDs are `pace_mood`, `sound_impact`, `connection`, `perspective`;
definition generation is 2. These replace the old definition generation, not
reinterpret its coordinates. Songs still get all four required linked slots.

## How to use the middle and mixed songs

Use the centre when an axis is balanced, mixed or not strongly expressed.
Perspective's time centre is the present, but a story mixing past/current events
can also sit near it. A song about self or life can stay near the middle of
Connection when a relationship theme is not central; do not force it into a
breakup or romance category. A fully absent theme and genuinely mixed feelings
are not distinguishable with these eight numbers. That is an accepted limit of
four simple maps, not a reason to invent confident extreme positions.

Casual captures lighter flirtation/attraction; Devoted captures sustained emotional
attachment. Sensuality can occur at either depth: a sexy love song need not be
Casual. Fractured/Secure describes the condition of the bond, not how much the
narrator wants it.

Judge Connection from the narrator's expressed position consistently. An ex
being hung up does not automatically mean the narrator is devoted. Use a broad
impression across the song: a strong chorus/bridge can raise impact even when
verses are soft, without requiring an extreme Powerful placement. Acoustic and
electronic elements can coexist; production quality is not the axis.

Agency, self-focus and narrative detail are intentionally not separate sliders.
Catchiness, favourite chorus/bridge, quality and song length are not measured.
Those either involve preference or would require more axes. The goal is a
repeatable overall impression, not a perfect lyrical analysis or genre classifier.

## Checking the design against your examples

These interpretations use your descriptions, not an independent lyric analysis,
and are guidance rather than automatic placements. No example coordinates are
written into your database.

| Song | Pace & mood | Sound & impact | Connection | Perspective |
| --- | --- | --- | --- | --- |
| Siren Sounds | Upbeat and sad at the same time. | Electronic, with a stronger chorus impact. | An unsettled bond can be Fractured while attachment remains Devoted. | Near Present for the described ongoing situation; judge outlook separately. |
| Go Away | Slower/relaxed and sad. | More Electronic but softer; a distinctive chorus need not mean a powerful hit. | Fractured and attached captures loving someone while resenting their behaviour. | Between Past and Present if both are part of the story. |
| Sleeping With the Lights On | Slow, with its mood placed independently. | More Acoustic in your description, but Powerful for the larger hit. | Fractured alongside Devoted fits growing apart while hung up. | Past/Present mixture does not force either extreme. |
| Blue | Place its pace separately from anger or sadness. | Instrumental texture can mix with production; the chorus/bridge raises impact. | Fractured fits conflict; commitment follows the narrator, not the ex's feelings. | Past-facing, with outlook judged from the expressed feeling. |
| Bubble Bath | Slow and sad. | Acoustic/soft with room for its build-up, rather than maximum impact just because the chorus is good. | Centre if the song's self/life questioning is not principally about a bond. | Place its actual time focus and outlook; self-questioning alone does not imply regret. |

## Radar and similarity

The eight-spoke order is Happy → Hopeful → Future → Secure → Devoted → Powerful
→ Electronic → Upbeat. This groups positive outlook, security/commitment and
sonic energy around the web, with links between those groups at the boundaries.
It is a visual arrangement, not a claim that adjacent feelings must correlate.
All eight dimensions remain present; low poles remain accessible in labels/titles.
There are no raw numeric legends on results. Radar values still use 0..1 radii
for each bipolar axis, with the neutral ring at 0.5.

Similarity continues to compare only shared placed maps using the fixed Gaussian
RMS curve. It starts without old evidence after the reset. The gentle draw bias
therefore starts neutral and adapts again as these new maps acquire placements.
Neither map definitions nor catalogue percentiles add a quality score to Overall.

## One-time test-data reset

Schema **18 → 19** replaces the four old map definitions/IDs and clears only:

- Old Vibe Map aggregate points, numeric/skip counts and timestamps.
- Old completed-pass counters.
- Old browser rounds, drafts, tokens and saved receipts.

Every song receives four new unmapped slots and a zero pass counter. Catalogue
rows, artists, albums, tags, links, Elo, matches and all other game facts are
preserved. No attempt history or retired-map table is added. A pre-upgrade SQLite
backup retains the original state for recovery; active tables have only new keys.
Schema 19 is the durable one-time marker. New results survive restarts, another
script run, canonical rebuilds, exports and SQL dumps without a version pragma.

Normal startup runs the backed-up migration automatically. To do it explicitly,
close the app and run from the test checkout, using its actual configured path:

```sh
python tools/reset_vibe_maps_v1042.py --database "path/to/your/test.db"
```

The script requires an existing explicit test database path. It accepts old Vibe
Map schemas 17/18, reports the backup, and does nothing to results already on 19.
It imports neither the launcher nor Git sync and does not rewrite/push the tracked
SQL snapshot. Closing the app later uses the normal backup upload process.
An old schema-18 backup restored with this code also upgrades/reset once; old
placements cannot silently return under new meanings. Older app code cannot
open the schema-19 database; use the pre-upgrade backup if reverting code.

Keep testing separate from main as described in [the code-only merge guide](VIBE_MAP_MERGE.md).
