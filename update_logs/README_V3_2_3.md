# Song Ranker V3.2.3

Run locally with `python -m pip install -r requirements.txt`, then `python main.py`.
Open http://127.0.0.1:5000. Your existing System Access PIN is unchanged.

## Installing this update

1. Stop Song Ranker.
2. Copy the contents of this update's `Song_ranker` folder into your existing
   V3.2.2 `Song_ranker` folder, replacing the matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder. This update
   deliberately contains no database.
4. Start `python main.py` and refresh the browser. V3.2.3 keeps schema 5;
   no additional migration is required on a V3.2 database.

Use Dev > Database to restore a backup; restoring an earlier relational database
runs the appropriate migration again. Keep a copy of the old application if you
want to roll back both the code and its pre-upgrade database together.

## V3.2.3 changes

Standard Vote preserves the current page height while requesting the next match,
then retains your current scroll position when the cards change. This also applies
to blind voting, vote-result reveals, retries and switching voting modes. You can
still scroll during loading. When the new page is shorter than the old page, the
browser naturally clamps the position to its new bottom.

This patch is installed over V3.2.2. It changes no database schema or records.
The separate Mode Ideas ZIP contains standalone interactive HTML concepts and
implementation notes; none of those proposed modes is installed by this patch.

## V3.2.2 changes

- Trivia plays its ending snippet only after the 30-second round expires or
  all applicable fields have been checked. Checking a field never pauses or
  restarts the preview. Short media cannot finish a round early. Answer flips,
  fuzzy matching, pause/resume and typed-answer credit remain.
- Dropdowns sit together in the banner. Game Modes blends standard/trivia/
  tournament colours, Rankings blends song/artist/album colours, and Stats
  and Mode Rankings blend trivia/tournament colours.
- The podium plays four seconds of first, second and third place in a loop,
  with a stronger glow on the playing card. Silver is slightly larger than
  bronze. Click a cover or Pause previews to pause; click a different cover to
  start from that place. Missing clips are skipped. If browser autoplay is
  blocked, click Play previews. Leaving the page stops playback; hiding the
  tab pauses it.
- Tournament artist/album/tag choices are sorted by usable track count.
  Groups too small for the selected bracket are dimmed and disabled; blind
  mode counts only tracks with previews. Changing requirements clears an
  invalid selection, and Enter selects the first eligible search result.
- Entity profiles have a little more space and a glow matching the entity.
  Low-Elo rediscovery cards use coral rather than album purple.
- Home keeps its three horizontal shelves and adds recognition leaders,
  player records and a vertically scrollable column of the latest 20 completed
  champions, with song and podium links.
- Song data stays green, artists blue and albums purple. Standard voting and
  Elo are orange; blind voting is teal, trivia/recognition gold, tournaments
  pink and tags amber. Page edges softly glow in the relevant colour. Search
  categories and performance-ranking metrics update their colour as selected.

No data is cleared or migrated by this patch. Install all included files together
on V3.2.1; the database schema remains 5.

## V3.2.1 changes

- Trivia uses Song → Artist → Album, with the current score/streak left of the
  artwork and best score/streak right. Both streaks have the fire emoji. The title
  is centred and round points sit directly below the artwork.
- Nonempty answers grade on blur/Enter, flip visibly for about 1.55 seconds, then
  become song/artist/album links inside the same coloured answer boxes. Exact
  correct answers flip too. Reduced-motion settings show links immediately.
  Marking an individual answer leaves the main preview uninterrupted.
- The Reveal answers button and repeated answer block are removed. A round finishes
  when all applicable fields are checked or time runs out; typed unchecked answers
  still count. Singles remain eligible, have a blank disabled album row, and save
  `album_correct` and `album_seconds` as SQL NULL.
- Tournament results use one podium, with larger gold in the centre, silver left
  and bronze right. All three retain previews, links and point totals. On small
  screens gold sits above the two side places.
- Voting titles are larger and green; artist and album names are larger but remain
  secondary. Names elsewhere are slightly larger too. Long names truncate with
  ellipses; hover titles and entity pages retain their full text.
- The banner has direct Rankings and Mode Rankings links. Extra links between
  the impact and performance ranking pages are removed; category links remain.
- Search recognition badges appear only above 90% accuracy, including 100%.
- Dev has separate **Reset match history**, **Reset trivia history**, and
  **Reset tournament history** controls, plus the existing full reset. Each saves
  a backup and requires its own confirmation phrase before clearing records.

### Separate resets

| Dev reset | Data cleared/reset | Data retained |
| --- | --- | --- |
| Match history | Standard/blind match history, legacy Elo changes, Elo to 1200, match counts and peak records | Trivia, tournaments, library |
| Trivia history | Trivia rounds, legacy recognition totals, manual trivia adjustments, current run and best score/streak records | Elo, matches, tournaments, library |
| Tournament history | Brackets, entries, tournament matches, placements and championships | Elo, matches, trivia, library |

The library includes songs, albums, artists, tags, their links, track positions,
artwork and preview URLs. Resetting a mode refreshes the stats and rankings derived
from it. These resets are only performed when requested from Dev; installing this
patch clears nothing.

## V3.2 mode behaviour

### Dev

Bulk edits let you select songs by title, artist, album, tag or `#ID`, select all
matching songs, move them to an existing album, and add or remove existing tags.
Selections persist while filtering. Album moves are atomic: duplicate track
positions cancel the whole move. You can explicitly clear selected track numbers
instead. Actual album track numbers and gaps remain valid; nothing renumbers them.

Trivia maintenance has separate song/artist/album counts, album attempts and legacy
totals. Sparse manual corrections preserve saved rounds. Best player score and
best streak are editable. Completed brackets can have their final and bronze
winners corrected; the saved deciding matches, placements and derived rankings
are updated together. Unfinished bracket qualifiers cannot be rewritten this way.

### Standard voting

Random selection softly favours songs with fewer votes and similar match counts.
A broad preference around a 110-Elo difference reduces repetitive near-identical
matches and huge mismatches. Every eligible song still has a chance; no hard Elo
band excludes tracks. Blind mode still requires previews. Elo remains hidden
until voting; winner playback, score animation and silent automatic next matches
remain unchanged.

### Tournaments

Weighted sampling gives less-played tournament songs a little more opportunity.
The draw uses noisy Elo seeding, with selected previous champions spread across
opposite halves and quarter-brackets. Champions are not guaranteed a place in
every draw. Global, artist, album and tag-group scopes are supported; scoped
selection has a searchable picker and track counts.

New tournaments have a bronze playoff between the semifinal losers, before the
final. First, second, third and fourth are retained. Champion points still total
7 for any supported size; bronze earns half the semifinal's points. Tournament
results never change standard Elo. Old or already-running brackets finish using
their original structure; no third place is invented for them.

### Trivia

The player earns up to **1 point per round**: song 0.50, album 0.30, artist 0.20,
with a modest speed factor from 75% to 100%. Without a proper album, the two
remaining weights scale proportionally to a maximum of 1. Singles and unknown
albums do not get an album field. This makes artist-only answers worth less than
song-only answers and keeps scores compact.

Nonempty answers are checked on blur or Enter, turn green/red, and flip visibly
to linked canonical answers. The existing fuzzy typo matcher remains. A checked
field locks for that round. Filled but unchecked fields are graded when the
30-second timer expires. Pause/Resume and Escape pause are
retained. A partially correct round keeps the streak; an entirely wrong round
ends it. Successful rounds continue automatically after the reveal. Failed
rounds have a Restart button.

Recognition is separate from the player's weighted score: **each correct field
is one recognition point**, against the fields available in that round. Saved
rounds retain the three correctness flags, field timings, score and streak.
`trivia_stats` is now a derived view, avoiding a second running totals table.
Older combined trivia results are kept as legacy totals because their original
field breakdown was never recorded. The old high score stays visible as a
legacy record; the new scoring scale starts its own high-score record. Highest
streak starts accumulating in V3.2 because it was not previously stored.

### Stats and the existing design

Recognisability shows field accuracy, best score, best streak and recent rounds.
Song/group profiles, global stats, search badges, tournament stats and artist/album
performance rankings use the new denominators and actual podiums. Podium and
third-place categories are added to the existing rankings. The approved colours,
shared banner, home shelves, cover-art previews, separate Top/Bottom rankings,
proper-album counts, tag pages and Dev table column controls are retained.

The unused tournament flag has been removed from standard match history. Any
old flagged history rows retain their meaning as `legacy_tournament` instead of
being discarded. Standard votes, tournaments and trivia remain separate records.
The visual tier-list page stays removed; global Elo distribution stays available.
