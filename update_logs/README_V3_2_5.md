# Song Ranker V3.2.5

This file groups the three-part release and its later hotfixes. The earlier
sections describe their historical release behavior; subsequent sections record
the changes applied by each patch.

Run locally with `python -m pip install -r requirements.txt`, then `python main.py`.
Open http://127.0.0.1:5000. Your System Access PIN is unchanged.

## Installing this update

1. Stop Song Ranker.
2. Copy this ZIP's `Song_ranker` folder contents into your existing V3.2.4
   folder, replacing all matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder. No database
   is included in this patch.
4. Start `python main.py` and hard-refresh the browser to load the updated scripts.

V3.2.5 uses schema 6, as V3.2.4 does. It adds no migration, stored counters,
or resets. Keep your database and backups. If you are upgrading from an older
version, install its intermediate updates first; V3.2.4 performs the backed-up
legacy trivia cleanup described below.

## V3.2.5 changes

- All twenty impact/Elo ranking rows now have a glow matching their entity:
  songs green, artists blue, albums purple and tags amber. First place glows
  brightest, then each rank fades. Bottom 20 starts very faint and brightens
  gently as the entries improve. Rankings retain their existing ordering.
- Each normal ranking entry shows its saved match count and overall win rate,
  plus non-blind and blind counts/rates. Group counts pool track appearances,
  so an internal match contributes both songs. Unplayed results show a dash.
- Performance ranking glows use gold for recognition and pink for tournament
  categories. Selection order is Recognisability, First place, Second place,
  Third place, Podiums, Match wins, Points.
- Global Stats panels have soft corner glows matching their stats. Mixed panels
  use the relevant colours at opposite corners. Song links are green; recent
  match losers are red. Elo distribution is retained.
- Global recognition adds separate song/artist/album accuracy, tested tracks,
  tracks above 90%, and current best score/streak. Tournament stats add match
  totals, awarded points, first/second/third totals, the latest podium and
  championship leaders. These are derived from existing records. Unfinished
  brackets do not count as completed podiums.
- Home recognition/champions panels, row accents and figures use gold/pink;
  song titles keep green and existing scrolling behaviour is retained.
- The full `static/js/trivia.js` is included to restore a missing local copy.
  Failed loading now gives a visible recovery message. Failed, timed-out or
  non-JSON trivia requests show a retry action instead of an endless loading
  screen. Healthy loading and the existing game behaviour are retained.

Trivia loaded successfully from the supplied files during verification, so the
original local failure was not reproduced. Install every file in this ZIP and
hard-refresh. If loading still fails, its error message and the app terminal
should identify the remaining issue.

## V3.2.4 database cleanup

V3.2.4 upgrades to schema 6 with an automatic pre-upgrade backup. It removes
obsolete combined trivia totals and the old scoring-scale high score, retaining
current detailed rounds, best score/streak, field corrections, match history,
Elo, tournaments and your library. The old `trivia_legacy` table is replaced by
sparse `trivia_adjustments`; `trivia_stats` remains a derived view.

## V3.2.4 changes

### Voting records

Song, album, artist and tag profiles now show overall, non-blind and blind win
rates, wins, losses and match counts above the recognisability and tournament
panels. These are queried from saved standard/blind match history; no additional
win counters or logs are stored.

Win rate is wins divided by wins plus losses. Unplayed tracks show a dash.
Album/artist/tag results pool their distinct linked songs' results rather than
averaging percentages. A match between two songs in the same group contributes
one win and one loss to that group: the displayed count measures track appearances.
Unclassified historical rows and tournament records are excluded from this
standard/blind breakdown because their voting mode is not known.

Global Stats shows total votes and the three highest track win rates for overall,
non-blind and blind voting, with win/loss counts. Its vote totals count each
saved match once. Elo distribution and the other global stats remain available.

### Tags and placements

- Tag impact rankings have Top 20 and Bottom 20 switches, like the other rankings.
- Tag profiles no longer show the wall of related tags. Their cover plays a
  looping queue of 10-second previews, ordered by descending Elo. Tracks without
  preview audio are skipped. Cover pause and previous/next controls remain.
- Mode rankings offer explicit First place, Second place and Third place
  categories. Top-four statistics are removed. Combined podiums, tournament wins,
  points and recognition rankings remain. Fourth-place results still exist in
  the tournament archive and Dev so bronze playoff results can be corrected.
- The home recognition and champion columns scroll automatically only when their
  content overflows. Hover, keyboard focus and touch pause scrolling; reduced
  motion disables it. Champions are limited to the latest 20 completed brackets.
  Recognition includes only songs with accuracy strictly above 90%.

### Trivia answers and maintenance

Bracketed additions in song and album names are optional when guessing: for
example, the main title is enough for `Song (feat. Guest)` or `Album (Deluxe)`.
Parentheses, square brackets and braces are supported. The main title still has
to match using the existing typo tolerance; sharing a feature credit alone does
not make a different title correct. The full saved name is used when the answer
flips into its canonical link. Artist matching is unchanged.

Dev trivia maintenance now shows only rounds, song correct, artist correct,
album attempts and album correct. Corrections remain sparse and preserve the
underlying saved rounds. Current best score and best streak remain editable.
Separate match, trivia and tournament resets still make backups and keep the
library, and bulk album/tag edits are retained.

## Existing behaviour retained

- Standard and blind voting retain the current scroll position while loading
  and revealing results. Elo stays hidden until voting; winner audio and score
  animation precede a silent next matchup.
- Standard matching softly favours less-played songs and balanced match counts,
  with a broad Elo-gap preference. Tournament selection and noisy Elo seeding
  retain randomness and spread selected previous champions across the draw.
- Tournaments support global/artist/album/tag scopes, searchable group choices,
  track-count eligibility, bronze playoffs before the final and looping podium
  snippets. Tournament results do not change normal Elo.
- Trivia remains Song → Artist → Album. Singles stay eligible with no album
  answer and SQL NULL album correctness. Applicable typed answers grade on blur,
  Enter or expiry; answer flips, pause/resume and current/best streaks remain.
  Its ending snippet waits for the timer or all applicable answers to finish.
- Player trivia points retain song 0.50, album 0.30 and artist 0.20 weights,
  with the existing speed factor and proportional scaling without an album.
  Recognition still counts one point per correct applicable field.
- Album previews loop in track order. Actual track numbers can have gaps;
  duplicate occupied album positions are rejected, including bulk moves.
- Shared colours, cover previews, home shelves, proper-album counts, search,
  championship badges and Dev column filters are retained. The unused visual
  tier-list page remains removed; global Elo distribution stays.

## V3.3 ideas

The separate `Song_Ranker_V3_2_3_Mode_Ideas.zip` is preserved for a later decision.
No proposed mode is installed by this update. See `V3_3_MODE_IDEAS.md` for the
shortlist and the saved preview filenames.

## Patch V3.2.5.1

### Song Ranker V3.2.5.1

Run locally with `python -m pip install -r requirements.txt`, then `python main.py`.
Open http://127.0.0.1:5000. Your System Access PIN is unchanged.

#### Installing this update

1. Stop Song Ranker.
2. Copy this ZIP's `Song_ranker` folder contents into your existing V3.2.5
   folder, replacing all matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder. No database
   is included in this patch.
4. Start `python main.py` and hard-refresh the browser to load the updated scripts.

V3.2.5 uses schema 6, as V3.2.4 does. It adds no migration, stored counters,
or resets. Keep your database and backups. If you are upgrading from an older
version, install its intermediate updates first; V3.2.4 performs the backed-up
legacy trivia cleanup described below.

#### V3.2.5.1 preview hotfix

- Shared Apple search/lookup handling allows at most 12 upstream calls per rolling
  minute, at least 5 seconds apart. Successful results are reused for 10 minutes
  in a bounded memory cache. Repeating Enter cannot send parallel Dev searches.
- HTTP errors and invalid lookup responses are shown in Dev, with retry waits.
  Cached suggestions remain available without another Apple request.
- Apple audio goes through a local streaming endpoint so its actual HTTP status
  can be checked. This stores no audio files, new database rows or request logs.
  Other custom preview hosts retain direct playback.
- Loading/buffering indicators become confirmed playing feedback when the media
  can play. Failures distinguish HTTP 429, refused access, missing URLs and
  connection/format failures. No developer account or API token is introduced.
- Preview safeguards allow at most 18 new clip reservations per rolling minute,
  with 0.5 seconds between different starts. The browser's byte-range requests
  for an active clip share its reservation for two minutes, preserving seeking
  and looping. This is a conservative local policy, not a published Apple CDN
  quota or a guarantee about the total number of range HTTP requests.
- HTTP 429 pauses new upstream requests for Apple's Retry-After duration (60
  seconds if absent). HTTP 401/403 pauses access too, without asserting that it
  was caused by rate limiting. Album/tag/podium queues pause on blocks rather
  than rapidly trying every track. Ordinary missing clips still skip with delay.
- Trivia no longer prefetches audio while idle; its timer starts after the audio
  is playable. Scores, voting, looping previews and the existing game rules stay.

Install **all files** together, including the new `apple_access.py` and
`static/js/preview.js`, plus the updated `main.py`. Restart and hard-refresh.
This hotfix adds no schema change or database reset. Safeguards/caches are scoped
to one running app process; use the normal local `python main.py` setup.

Apple's free iTunes Search API documents approximately 20 calls per minute,
subject to change, and recommends caching search/lookup requests. Preview URLs
point to separate media files; that documentation does not specify a preview-CDN
limit or a guaranteed 24-hour unblock time. The hotfix can report the response
it receives, but cannot remove a restriction already imposed by Apple.
Source: https://performance-partners.apple.com/search-api

If previews still fail, read the new status message. HTTP 429 includes the wait;
401/403 means refused access; 404/410 indicates a missing preview (refresh its URL
in Dev); a connection/format error needs a different diagnosis. Playback recovers
on a manual retry after the wait, rather than an automatic retry loop.

#### V3.2.5 changes

- All twenty impact/Elo ranking rows now have a glow matching their entity:
  songs green, artists blue, albums purple and tags amber. First place glows
  brightest, then each rank fades. Bottom 20 starts very faint and brightens
  gently as the entries improve. Rankings retain their existing ordering.
- Each normal ranking entry shows its saved match count and overall win rate,
  plus non-blind and blind counts/rates. Group counts pool track appearances,
  so an internal match contributes both songs. Unplayed results show a dash.
- Performance ranking glows use gold for recognition and pink for tournament
  categories. Selection order is Recognisability, First place, Second place,
  Third place, Podiums, Match wins, Points.
- Global Stats panels have soft corner glows matching their stats. Mixed panels
  use the relevant colours at opposite corners. Song links are green; recent
  match losers are red. Elo distribution is retained.
- Global recognition adds separate song/artist/album accuracy, tested tracks,
  tracks above 90%, and current best score/streak. Tournament stats add match
  totals, awarded points, first/second/third totals, the latest podium and
  championship leaders. These are derived from existing records. Unfinished
  brackets do not count as completed podiums.
- Home recognition/champions panels, row accents and figures use gold/pink;
  song titles keep green and existing scrolling behaviour is retained.
- The full `static/js/trivia.js` is included to restore a missing local copy.
  Failed loading now gives a visible recovery message. Failed, timed-out or
  non-JSON trivia requests show a retry action instead of an endless loading
  screen. Healthy loading and the existing game behaviour are retained.

Trivia loaded successfully from the supplied files during verification, so the
original local failure was not reproduced. Install every file in this ZIP and
hard-refresh. If loading still fails, its error message and the app terminal
should identify the remaining issue.

#### V3.2.4 database cleanup

V3.2.4 upgrades to schema 6 with an automatic pre-upgrade backup. It removes
obsolete combined trivia totals and the old scoring-scale high score, retaining
current detailed rounds, best score/streak, field corrections, match history,
Elo, tournaments and your library. The old `trivia_legacy` table is replaced by
sparse `trivia_adjustments`; `trivia_stats` remains a derived view.

#### V3.2.4 changes

##### Voting records

Song, album, artist and tag profiles now show overall, non-blind and blind win
rates, wins, losses and match counts above the recognisability and tournament
panels. These are queried from saved standard/blind match history; no additional
win counters or logs are stored.

Win rate is wins divided by wins plus losses. Unplayed tracks show a dash.
Album/artist/tag results pool their distinct linked songs' results rather than
averaging percentages. A match between two songs in the same group contributes
one win and one loss to that group: the displayed count measures track appearances.
Unclassified historical rows and tournament records are excluded from this
standard/blind breakdown because their voting mode is not known.

Global Stats shows total votes and the three highest track win rates for overall,
non-blind and blind voting, with win/loss counts. Its vote totals count each
saved match once. Elo distribution and the other global stats remain available.

##### Tags and placements

- Tag impact rankings have Top 20 and Bottom 20 switches, like the other rankings.
- Tag profiles no longer show the wall of related tags. Their cover plays a
  looping queue of 10-second previews, ordered by descending Elo. Tracks without
  preview audio are skipped. Cover pause and previous/next controls remain.
- Mode rankings offer explicit First place, Second place and Third place
  categories. Top-four statistics are removed. Combined podiums, tournament wins,
  points and recognition rankings remain. Fourth-place results still exist in
  the tournament archive and Dev so bronze playoff results can be corrected.
- The home recognition and champion columns scroll automatically only when their
  content overflows. Hover, keyboard focus and touch pause scrolling; reduced
  motion disables it. Champions are limited to the latest 20 completed brackets.
  Recognition includes only songs with accuracy strictly above 90%.

##### Trivia answers and maintenance

Bracketed additions in song and album names are optional when guessing: for
example, the main title is enough for `Song (feat. Guest)` or `Album (Deluxe)`.
Parentheses, square brackets and braces are supported. The main title still has
to match using the existing typo tolerance; sharing a feature credit alone does
not make a different title correct. The full saved name is used when the answer
flips into its canonical link. Artist matching is unchanged.

Dev trivia maintenance now shows only rounds, song correct, artist correct,
album attempts and album correct. Corrections remain sparse and preserve the
underlying saved rounds. Current best score and best streak remain editable.
Separate match, trivia and tournament resets still make backups and keep the
library, and bulk album/tag edits are retained.

#### Existing behaviour retained

- Standard and blind voting retain the current scroll position while loading
  and revealing results. Elo stays hidden until voting; winner audio and score
  animation precede a silent next matchup.
- Standard matching softly favours less-played songs and balanced match counts,
  with a broad Elo-gap preference. Tournament selection and noisy Elo seeding
  retain randomness and spread selected previous champions across the draw.
- Tournaments support global/artist/album/tag scopes, searchable group choices,
  track-count eligibility, bronze playoffs before the final and looping podium
  snippets. Tournament results do not change normal Elo.
- Trivia remains Song → Artist → Album. Singles stay eligible with no album
  answer and SQL NULL album correctness. Applicable typed answers grade on blur,
  Enter or expiry; answer flips, pause/resume and current/best streaks remain.
  Its ending snippet waits for the timer or all applicable answers to finish.
- Player trivia points retain song 0.50, album 0.30 and artist 0.20 weights,
  with the existing speed factor and proportional scaling without an album.
  Recognition still counts one point per correct applicable field.
- Album previews loop in track order. Actual track numbers can have gaps;
  duplicate occupied album positions are rejected, including bulk moves.
- Shared colours, cover previews, home shelves, proper-album counts, search,
  championship badges and Dev column filters are retained. The unused visual
  tier-list page remains removed; global Elo distribution stays.

#### V3.3 ideas

The separate `Song_Ranker_V3_2_3_Mode_Ideas.zip` is preserved for a later decision.
No proposed mode is installed by this update. See `V3_3_MODE_IDEAS.md` for the
shortlist and the saved preview filenames.

