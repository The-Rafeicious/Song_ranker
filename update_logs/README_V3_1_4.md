# Song Ranker V3.1.4 patch

Apply over V3.1.3. The patch contains five application files, two updated/new test files and a small cleanup script.

## Install

1. Stop the server.
2. Merge this patch into your existing `Song_ranker` folder, replacing the included files and preserving the existing folders. Include `catalog.py` and `pages.py` as well as the `static` and `templates` files.
3. From your `Song_ranker` folder, run `python cleanup_v3_1_4.py`. This deletes only the obsolete `templates/tier_list.html`. Alternatively, delete that one file manually.
4. Restart and refresh the browser. Shared assets now use V3.1.4 cache versioning.

There is no database file, migration or new dependency. The cleanup script is safe to run again and does not read or modify the database.

## Changes

- The visual tier-list page, its route, inline styles, banner link and developer navigation mapping are removed. `/tiers` now returns 404.
- **Elo Distribution remains in Global Stats**, with the existing bands and counts.
- **Artist Performance** (`/artist_stats`) and **Album Performance** (`/album_stats`) are available in the Rankings menu. Each has recognisability, championships, top-four finishes, match wins and points categories, with Top twenty / Bottom twenty views.
- Existing artist/album impact rankings link to their performance pages. Artist and album profiles also link to the relevant recognisability and championship rankings while keeping the existing trivia and tournament archive links.
- Song search results show a gold championship badge with the title count, runner-up badges when applicable, and recognition percentages for tested songs. The existing Elo score remains visible.

## Calculations

All performance values are derived from existing songs, trivia attempts, tournament entries and saved results. No extra statistics are stored in SQLite.

| Category | Calculation |
|---|---|
| Recognisability | Total correct trivia points divided by twice the total attempts, as a percentage. Untested groups are omitted. |
| Championships | Titles won by linked songs in completed tournaments. |
| Top-four finishes | Distinct song/tournament finishes as champion, runner-up or semifinal loser, in completed tournaments. |
| Match wins | Completed matches won by linked songs, including saved matches in ongoing tournaments. |
| Points | Total points awarded to linked songs in completed matches. |

Each linked song contributes once within an artist or album. A collaboration contributes to each credited artist. Album leaderboards exclude single releases; artists still receive credit for their single tracks. Tournament leaderboards include groups whose songs have participated, including those with zero titles or wins.

Semifinal exits count as top-four finishes; the app does not invent third/fourth-place results. The performance row shows championships, runners-up, semifinal exits and wins/losses alongside the selected score. Higher attempt counts break recognisability ties; tournament ties use the other achievement totals, then the name.

## Validation

- 33 backend tests passed, including seven new performance tests for weighted recognition, completed placements, unfinished tournaments, duplicate entries and empty groups.
- 112 new interface assertions passed for both leaderboards, all categories, range switching, search achievements, navigation, retired tiers and preserved Elo distribution.
- 346 existing interface assertions passed for other pages, profiles, tag rankings, preview looping and automatic match progression.
- The cleanup script was tested for scoped deletion, safe repeat runs and preservation of the database and Global Stats template.
- JavaScript syntax, Python compilation and ZIP integrity checks passed. The original database checksum is unchanged; write tests used copies.

Interface tests used a DOM emulator and mocked audio. Live audio and graphical browser rendering were not verified here.
