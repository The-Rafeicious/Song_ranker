# Song Ranker V3.2

Run locally with `python -m pip install -r requirements.txt`, then `python main.py`.
Open http://127.0.0.1:5000. Your existing System Access PIN is unchanged.

## Installing this update

1. Stop Song Ranker.
2. Copy the contents of this update's `Song_ranker` folder into your existing
   V3.1.4 `Song_ranker` folder, replacing the matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder. This update
   deliberately contains no database.
4. Start `python main.py`. The first start saves a `pre_upgrade_*.db` backup
   and upgrades the live database to schema 5. Refresh the browser afterward.

Use Dev > Database to restore a backup; restoring an earlier relational database
runs the appropriate migration again. Keep a copy of the old application if you
want to roll back both the code and its pre-upgrade database together.

## V3.2 changes

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

Nonempty answers are checked on blur or Enter, turn green/red, and flip quickly
to the canonical answer. The existing fuzzy typo matcher remains. A checked
field locks for that round. Filled but unchecked fields are graded when the
30-second timer expires or Reveal is pressed. Pause/Resume and Escape pause are
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
