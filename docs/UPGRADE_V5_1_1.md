# V5.1.1 — Mode game pages and dedicated statistics

Current controls for V5.1.2.1; see [patch installation](UPGRADE_V5_1_2_1.md).

V5.1.1 makes Shared Spotlight and Vibe Map playable. Each has its
own statistics page, linked from the game, the Stats menu and Global Stats.
All seven Home modes are available from Home and Game Modes. The new pages use the
existing dark panels, entity colours, mode accents and responsive controls.

## Install and test safely

1. Stop your current app. Merge this download's `Song_ranker` folder into it.
2. Keep your current database, backups, `instance` settings and Git folder.
   V5.1.2.1 is a changed/added-files patch over the preceding Spotlight release; no live database or sample results are included.
3. Run `python safe_mode.py`, open the app and hard-refresh. Check the footer
   says **V5.1.2.1** and the **SAFE MODE** banner identifies persistent safe testing.
4. Try both subjective games and their statistics. Safe mode writes only to its
   separate test copy. Stop it and run `python main.py` when ready for real play.

Schema 17 selectively retires the removed mode after a verified backup.
Remaining results are kept; Overall remains calibration 7. Safe launches reuse
one database, with explicit `--refresh-safe-mode` to replace only test data.

## Play

| Mode | Game | Dedicated stats |
| --- | --- | --- |
| Shared Spotlight | `/shared_spotlight` | `/shared_spotlight_stats` |
| Vibe Map | `/vibe_map` | `/vibe_map_stats` |

### Shared Spotlight

Use the numbered **Place on bar** button below the metadata; Selected ✓ and
the card glow identify the active song. Place it on the Worse → Better line.
The bar uses small covers. Overlapping covers fan apart on hover or keyboard
focus, and the line remains clickable below them. Every song needs a placement.
Arrow keys adjust by one; Shift+Arrow/Page Up/Down adjust by ten; Home/End reach
the ends. No placement is a default rating.

The bar pulses on a changed placement. After 1.5 idle seconds, the next unplaced
song is selected; once all are placed, it moves to the next song in card order.
Dragging defers this wait until release. Repeated changes restart it, and manual
selection cancels it. Revisiting a song and changing it starts a fresh wait.

Points are hidden during placement. The footer contains the budget, **Loop
previews**, then **Next round**. Next round submits the existing automatic
12-point split. Confirmed results reveal the cover points and rearrange the bar
by point order. Previews play highest score first, once per song: two seconds
in Standard or one in Quick. Equal scores share a bar position and retain card
order for playback. The next offer starts after the short result pass; the
results Next round button skips the rest immediately.

Loop previews during placement retains 20-second Standard / 10-second Quick
segments. Cover clicks can redirect it. Stop previews pauses it. During results,
the same button stops/replays the finite score-order pass. Hiding/leaving stops
playback, and new rounds begin silent. Buffering is excluded from segment time.
Unavailable previews are skipped; browser permission blocks leave manual Play
available. Stats remain in navigation. Metadata links remain separate from selection.

### Vibe Map

Play the track, choose **Mood & energy**, **Sound & delivery** or **Build & hook**,
and select a cell. You can save one, two or all three tables. None starts with a
default placement. Clearing one table leaves the others intact. The first tab
suggested for a round is the song's least-reviewed table.

X increases left to right; Y increases bottom to top. Arrow keys change the
focused grid placement. Home/End move to the row's first/last X value. Left/Right
and Home/End also work on the table tabs. Every cell has a complete coordinate
label and a visible keyboard focus state.

**Tags** is optional and initially collapsed. Search includes descriptions.
Choose up to eight current catalogue tags, use **None fit** for a reviewed empty
set, or **Clear review** to leave tags unanswered. Selecting a tag and then
unchecking the last one remains an explicit empty review. These choices never
change the catalogue's existing tag memberships.

## Shared round behaviour

- Previews start only after Play. They use the shared volume, readiness and
  audio handoff owner. The existing listening tracker measures playback before
  the submitted decision, with one frozen sample for retries.
- Draft choices live in this browser tab's session storage against the offered
  token. Refresh resumes an open offer and its draft; drafts are not database results.
- Save locks the choice while the server acknowledges it. If the connection
  fails, **Retry same save** sends the identical payload. An unconfirmed save
  stays locked across refresh. Explicit validation errors allow a correction.
- A confirmed result stays visible, then advances using the navbar's
  Standard/Quick speed. **Next round** advances immediately. Preparation fetches
  only the next offer, without starting audio or saving a decision.
- Hidden tabs pause result advancement; page exit cancels requests, timers and
  players. Vibe’s Skip loads the next offer without adding judgement evidence.

## Statistics, from summary to detail

Both reports begin with saved rounds, meaningful mode totals and current
preview-pool coverage. Main mode findings come next. Further down are collection
coverage, 14-day activity, listening measurements, saved round history and
calculation notes. History uses ten rounds per page.

- **Spotlight:** the most supported tracks, adjusted for evidence, with mean
  points and offer counts beside each; up to 50 leaders are available through a
  disclosure. The lower point-distribution chart includes zeroes and ties.
- **Vibe:** three independent heatmaps, followed by a searchable track table
  with table selection, mean coordinates, placements and spread. Track rows
  use 20-item pages. Tags show selected/reviewed counts and percentages.
  Unknown maps/tags remain unknown; descriptions are not accuracy scores.
Reports preserve short archived identities for removed songs, without broken
song links. Saved tag labels link to the current tag name after a rename.
Global Stats includes the two subjective-mode summaries and their recent results;
activity colours blend the visible modes.

All statistics remain derived reads. This patch adds no result cache, nightly
task, saved heatmap or pair matrix. Spotlight retains its adaptive Overall
preference contribution; Vibe retains descriptive coverage with zero
quality weight. [The backend guide](UPGRADE_V5_1.md) has the complete formulas.

## Ownership and validation

`modes/judgement_pages.py` owns page routes; `reports/judgement_page_data.py`
adapts existing facts for HTML. `judgement_game.js` owns round/draft/request
state; `judgement_modes.css` owns their layouts. Existing preview, listening,
pacing, shared stats macros and baseline styles retain their responsibilities.

See [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md), [DATABASE.md](DATABASE.md),
[PAGE_STYLE.md](PAGE_STYLE.md), [FILES.md](FILES.md) and
[VALIDATION.md](VALIDATION.md) for the updated references and test limits.
