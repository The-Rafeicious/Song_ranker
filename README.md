# Song Ranker

A local, single-user music library with voting, trivia, tournaments and knowledge games. Current release: **V3.3.5.1**, database schema **8**. Release-specific changes live in [update_logs](update_logs/README.md).

## Run locally

From the project folder:

```sh
python -m pip install -r requirements.txt
python main.py
```

Open **http://127.0.0.1:5000**. Keep the app bound to localhost. Your existing System Access PIN is unchanged. Python 3.10 or newer is recommended.

When installing an update, stop the app, copy the supplied `Song_ranker` files over your existing project, restart, and hard-refresh the browser. Keep your own `song_ranker_v2.db` and `database_backups` folder. Updates do not include a replacement music database. V3.3 upgrades existing databases to schema 8 automatically, with a consistent pre-upgrade backup. V3.3.5.1 adds no migration. This update supplies edited files only. Detailed instructions: [V3.3.5 update](update_logs/V3_3_5_UPDATE.md).

## Modes

| Mode | What you do | Scores and records | Colour |
| --- | --- | --- | --- |
| Standard Vote | Pick your preferred song from two visible tracks. | Changes Elo; saves one match with before/after ratings. | Warm orange |
| Blind Audition | Vote from anonymous previews; identities appear after voting. | Same Elo system, separately labelled blind match history. | Mint |
| Elo Guesser | Pick the song with the higher Elo. It has its own page. | 1 point per correct answer; independent accuracy and perfect streaks. Never changes Elo or votes. | Red-orange |
| Trivia | Guess song, artist and, when applicable, album from a preview. | Weighted user points, streaks and field-level recognisability. | Gold |
| Tournament | Run a bracket from the whole library or an artist, album or tag. | Independent match points, championships and first/second/third placements. | Pink |
| Album Shelves | Assign ten tracks to two or three albums and order each shelf. | 0.5 album points plus up to 2.5 order points per track. Separate history and rankings. | Deep aubergine |

### Voting and Elo

Standard and blind voting use gently weighted randomness: less-played tracks receive more opportunities and rating gaps influence pairing without making selection rigid. Albums in the visible metadata are proper albums; ` - Single` releases do not appear as album links. Elo is shown only after voting. The chosen track plays briefly while the score changes are shown, then the next pair loads without automatically starting audio. Both Standard/Blind covers preload quietly when their pair appears. The pair cache is released after its result sample, before the next pair loads. Previews loop when started. Your selected tab is remembered; scroll position is preserved between rounds.

### Elo Guesser

Open **Elo Guesser** at `/elo_guesser`, or use its home/nav link. Covers, song names and artists are visible, but Elo is hidden until you answer. The answer uses a frozen pair of ratings taken at question creation. Ties are excluded; a soft bias favours useful rating gaps and less-tested tracks.

Both cover previews preload quietly before selection. Their cache is released when advancing to the next pair, after the answer sample. A correct answer earns 1 point and adds to the current streak. A wrong answer earns 0 and resets the current streak. Best streak is derived from saved answers and appears in global stats. Ratings appear at the bottom of each cover after answering, with a clear red loss message for a wrong pick. The higher-rated song plays a short answer snippet in either case. After about 4.5 seconds the next pair loads automatically and starts silently. Reopening the mode resumes an unanswered question. Both songs in a pair receive one tested appearance with that comparison’s correctness, allowing song, album and artist accuracy summaries. An artist/album’s counts are pooled song appearances, not extra user points.

### Trivia

Song, artist and album inputs mark on blur or Enter, correct minor spelling mistakes, and flip to linked canonical answers. Song is worth more than album, and album more than artist. Single releases have no album guess and save that field as null. Bracketed extras such as featured artists or deluxe labels are not required to identify the main title.

The ending sample waits until the main preview ends or all available fields are marked. Highest score and best streak are recorded. Recognisability divides correct fields by fields actually available; unavailable albums are not misses. Recognised badges and the home recognition banner require more than 90%.

### Tournaments

Choose 8, 16 or 32 tracks, optionally scoped to an artist, album or tag. Scope search shows track counts and disables insufficient choices. Brackets balance Elo, previous exposure and champions while retaining randomness. A third-place playoff runs before the final.

Both current match previews preload quietly; the tournament keeps up to ten recent previews between rounds so returning tracks can reuse them. Tournament points are independent of Elo. Voting shows the winner’s point gain, plays its sample briefly, then advances. The final podium shows first place larger, second on the left and third on the right, with optional cycling previews. Podium snippets last six seconds, with a 1.5-second overlap once the next preview is ready. Tournament rankings offer first, second, third, podiums, match wins and points. Unfinished brackets do not award final placements.

### Album Shelves

Open `/album_shelves`. Rounds offer two or three albums with a 50/50 choice when both sizes are feasible. Albums need at least two valid numbered tracks. The picker avoids albums from the preceding round whenever enough alternatives can supply the chosen round size, favours less-used/recently unused albums, and distributes tracks as evenly as the chosen albums allow (normally 5/5 or 4/3/3). Every round has exactly ten distinct tracks from proper albums with known, unique positive track numbers. The distribution can be uneven. Albums may share an artist or come from different artists. If the library cannot supply a valid round, the mode explains what metadata is missing instead of inventing positions or reducing the number of tracks.

Drag tracks to an album, choose an album from the row menu, and reorder with drag, up/down buttons or arrow keys when a row has focus. Unsorted tracks show song titles without artist clues, album covers or track numbers. Album artwork is larger with its title underneath. **Play previews** cycles available samples for ten seconds each, highlights the current row and loops back to the first sample. Row play controls start from that track. Playback is optional; missing previews do not prevent a title-based round.

Checking requires all ten tracks to be placed once. Correct album membership earns **0.5 points per track**. Track order earns **up to 2.5 more points**, using the fraction of correctly ordered comparisons with the other offered tracks from the same album. Both tracks must be on the correct shelf for a comparison to count. This gives partial credit without letting one misplaced item spoil every later position.

Real track numbers are preserved: 1, 4 and 8 is a valid sequence. The game checks the relative order of the selected tracks, not whether your collected album is complete. Older saved rounds may have singleton shelves: those tracks have a 0.5-point membership denominator without free order points. New rounds always have at least two tracks per album. A round is usually out of 30; its actual denominator is shown. Percentages use earned points divided by available points.

The Shelves play page has a wider desktop layout. Submit above the compact preview player. Each song flips in turn and moves into its actual album and original track order, playing a short snippet when available. Wrong cards also show the submitted shelf position in small red text beside the actual album track number. Green means the submitted answer was fully correct; wrong album or any ordering error stays red even after the card moves to the correct position. Partial-credit points still count. Each album cover counts its own points while the submit button counts the total. Reveals do not scroll your screen or display a sticky banner. Once all ten tracks are revealed, the result remains until you press **Next round**, between the total score and the track-order percentage box above the preview player. All three boxes share the same border, background and height. The new round starts silently. Unanswered rounds resume when reopened. Each reveal holds for a second longer than V3.3.3. One preview is buffered ahead. The outgoing snippet continues while the incoming one buffers, then the shared player overlaps them for 1.5 seconds; missing or stalled audio does not stop the flips. The album menus show artwork and full titles, mark the current selection, and support arrow keys, Home/End and Escape. No Apple metadata lookup is performed while generating either new mode.

## Pages and navigation

| Page | Contents |
| --- | --- |
| Home | Five mode cards in a staggered three-plus-two layout, library counts, mode records, and seven scrolling banners: songs, artists, albums, recognition, champions, Elo guesses and album track ordering. |
| Overall Rankings | Composite percentages for songs, artists, albums and tags; top/bottom twenty, evidence and two-decimal display. |
| Normal Rankings | Separate song, artist, album and tag pages with top/bottom twenty, impact/Elo and voting figures. Singles are excluded from album rankings/counts. |
| Mode Rankings dropdown | Separate Recognisability, Tournament, Elo Guesser and Album Shelves pages. Each switches between songs, artists and albums and shows top/bottom twenty. |
| Search | Songs, artists, albums and tags; related metadata matches, impact/Elo and existing achievement badges. |
| Song | Cover playback, Elo, votes/win rates, new knowledge records, trivia, tournaments and recent matches. |
| Artist / Album | Shared profile layout, pooled track records, highlights, linked tracks and new mode summaries. Artist artwork stays circular. Artist and tag covers cycle ranked tracks for ten seconds each; album covers cycle in track-number order. |
| Tag | Description, linked tracks and an Elo-ordered looping preview queue. |
| Global Stats | Library, Overall summary/leaders, Elo distribution, voting, recognisability, podiums, knowledge modes and recent activity. |
| Match History | Standard/blind voting records and filters; loser names are red. |
| Mode Stats | Detailed trivia, tournament, Elo Guesser and Album Shelves records. New modes include percentage bars, top/practice lists and recent rounds. Shelves emphasises track ordering and lists albums actually played; album placement is available as an optional breakdown. |
| Dev Dashboard | Catalogue search/editing, imports, bulk changes, metadata maintenance, records, backups and separate mode resets. |

Songs use green links, artists blue and albums bright purple. Each game and its stats use their own mode accent. Song/artist/album names sit beside artwork; page headings stay centred. Profile mode panels follow recognition, tournament, Elo Guesser, then Album Shelves, with a full-width row per mode. Long titles retain ellipses with full names on hover. The footer shows the running version below System Access.

## Overall Stats

**Overall** combines personal preference and performance across the saved modes.
It appears on song, artist, album and tag profiles, in Global Stats, in the home
leaders panel and at **`/overall_rankings`** (Mode Rankings → Overall). Rankings
switch between the four entity types and top/bottom twenty. Percentages display
with two decimal places; sorting uses the full calculated value.

The displayed Overall percentage is an **adjusted percentile**. First, each tested song
gets an evidence-adjusted composite from its eligible modes; then that composite
is compared with other tested songs. A 90% song sits near the top tenth and a 10%
song near the bottom tenth. Ordinary standings map onto **2–98%**, keeping the
wide spread and a 50% centre. First/last place alone cannot produce 100%/0%; those
values require the evidence-adjusted composite itself to be exactly 100/0. Ties
share a midpoint and a lone ordinary tested song gets 50%. Genuine absolute
endpoint exceptions can shift the cohort mean slightly. Untested songs stay
unknown and out of rankings.

Five game families start with equal **20% bases**: voting, recognisability,
tournament, Elo Guesser and Album Shelves. Voting's Elo, non-blind and blind
components share that one base at **8%, 6% and 6%**. Actual weights adapt to the
fraction of eligible songs played and each game's average appearances relative
to typical use across active families. With all five active, one family cannot
exceed **30%**. When a song cannot enter a family, the remaining shares are
rescaled and capped again for its playable families.

Evidence is relative to each metric's current exposure distribution: zero plays
means 0%, average tested-song exposure means 50%, and the high reference means
100%. The high reference uses the 90th percentile of appearances, or twice the
average when that percentile is not above it. The same relative exposure works
whether typical counts are 1–2 or 10–20. Lightly tested results shrink towards a
neutral input of 50; a song left behind loses relative evidence as others get
more plays. Rate performance still blends 60% actual success with 40% performance
against its population average; Elo uses its tested-song distribution. There is
no additional coverage multiplier suppressing the whole composite.

Songs without a proper album omit album recognition and Shelves, rather than
receiving a missing score. Shelves requires a positive, unique track position
in a proper album with at least two eligible tracks. Blind voting and trivia
require an audio preview. Eligible but unplayed modes remain neutral; modes
without results anywhere have no influence.

Artists, albums and tags average distinct linked songs' **composites**, including
50 for untested songs. A two-effective-song confidence prior shrinks that mean
before it is percentile-ranked against other tested entities of the same type.
Singles and unknown albums stay outside the album rankings and percentile pool.
These percentages describe relative standing, rather than literal success rates.

Every Overall view uses a fresh, consistent read-only snapshot. Participation,
exposure references, weights and percentiles adjust immediately, without the old
30-minute/25-appearance calibration threshold. An unchanged model is reused in
memory, and the session only stores a compact calibration version marker.

Dev → System → **Overall calculator** explains the family weights, participation,
play averages, evidence references, composite and percentile stages. Song,
artist, album and tag lookups show actual allocations and collection confidence,
with a linked-song drill-down. No score tables, columns or migrations are added.
The complete calculation is documented in
[V3.3.4 notes](update_logs/V3_3_4_UPDATE.md), including its calculation and endpoint hotfix sections.

## Developer tools

Open **System Access** in the footer and unlock the dashboard. The music library explorer searches songs, artists, albums and tags together. Entity tables have field filters, sort controls and a column picker. Bulk edits support moving songs into albums and adding/removing tags. Existing tag suggestions and descriptions reduce spelling mistakes and tab switching.

Apple search supports Enter, keeps suggestions after adding when selected, and uses shared request throttling. Importing music does not manufacture missing facts. The optional metadata program fills only blank **track numbers** and **album release dates** after conservative identity checks; it never renames songs/albums or changes artwork/preview URLs. It uses a review/backup step and produces a text report. Instructions remain in [V3.2.6 notes](update_logs/README_V3_2_6.md).

**Elo Guesser** and **Album Shelves** have separate pages under Dev Records. Each shows the latest thirty results in a dedicated table, with full-width search, readable wrapped track names and individual round deletion. Deleting a round creates a backup. Database tools separately reset matches/Elo, trivia, tournaments, Elo Guesser or Album Shelves while retaining the catalogue and other modes. Resetting all competition data clears all five competition histories. Resets require the scope-specific confirmation shown in the dialog and create a backup.

## Data, backups and previews

- `song_ranker_v2.db` is the live SQLite database. `database_backups` stores consistent snapshots made before migrations and destructive Dev operations.
- Song-to-artist and song-to-tag relationships are shared junction tables. Album track positions are checked for uniqueness; skipped positions are valid.
- Voting saves one match row. Trivia stores field-level results. Tournaments have their own brackets/matches. Elo Guesser and Album Shelves use three new lean tables, with scores/stats derived from their saved answers rather than duplicate audit logs or cached totals.
- New-mode answer facts are frozen at question creation, so later Elo/album/track edits do not change a completed answer’s score. Deleted catalogue records keep historical results but lose their links; summaries for living entities use their current linked songs.
- Shelves points are derived from saved answer facts. V3.3.3.1 applies the 0.5/2.5 split to existing as well as new rounds, updating points, accuracy, records and rankings together without rewriting the answer history.
- The Shelves **Albums Played** section uses saved round membership, so moving a track later does not move its historical album participation. Missing or blocked answer audio does not interrupt reveals; navigating away cancels reveal timers and playback.
- Apple free lookup/search calls are limited to 12 upstream calls per rolling minute, at least five seconds apart, with short-lived successful lookup caching and 429 backoff. Audio has loading/error checks and streamed status diagnostics. Rate limits do not trigger automatic retry storms.
- The local app keeps up to ten complete Apple previews in RAM for ten minutes, up to 4 MiB each; it writes no audio files. Cache entries belong to the page that loaded them. Standard/Blind Vote and Elo Guesser release each completed pair after its result sample, while tournaments retain recent previews across rounds. Leaving a page clears its cache and native buffers; another open tab is unaffected. Back navigation uses a fresh cache scope. Edited preview URLs bypass old entries. Replays and byte ranges use cached audio when available; custom hosts retain native buffering.
- Voting pairs warm both previews without autoplay and without retaining a second JavaScript copy. Downloads are spaced to respect the existing local preview request gate. An immediate click or a failed preload can still show the buffering notice.
- A shared player keeps the outgoing preview audible until the next preview starts and can play its buffer, then overlaps them for 1.5 seconds. Album/tag queues, Shelves, podiums, cover switching, trivia handoffs and full-preview loops use this behavior. Loading/buffering notices remain visible. Volume changes preserve the fade mix; pause, navigation and cancelled requests stop pending/retired audio. Fresh Standard/Tournament/Guesser rounds still begin silently.
- `SONG_RANKER_DB`, `SONG_RANKER_PIN` and `SONG_RANKER_SECRET` can override the database path, Dev PIN and session secret. Keeping a stable secret preserves existing sessions.
- If the project has Git configured, its existing startup pull/manual database sync remains available. The live database is kept on a pull; a remote SQL dump does not overwrite it.

## Project structure and future updates

`main.py` starts the app and registers modules. `services.py` handles common app/database helpers, `catalog.py` shared catalogue projections, `pages.py` page routes, `games.py` voting/tournaments, `trivia.py` trivia and `special_modes.py` both knowledge games and `overall.py` the read-only composite calculator. `database.py`, `mode_schema.py` and `special_schema.py` own versioned schema setup. Templates and shared scripts/styles live under `templates` and `static`.

The current version is defined once in **`version.py`**. The footer and shared CSS/JS cache keys read it. For every update, change that constant. Keep one Markdown changelog per **three-part release** in **`update_logs/`** and append fourth/fifth-part hotfixes inside that release file; update the index rather than creating standalone hotfix documents. Keep this README as the current project guide rather than a growing stack of patch notes. Older ideas remain in `V3_3_MODE_IDEAS.md`; they are not enabled simply because their concepts are documented.

Run backend checks with `python -m unittest discover -s tests -v`. Tests use copied/temporary databases, not the live one. See [VALIDATION.md](VALIDATION.md) for the current release’s checks and verification limits.
