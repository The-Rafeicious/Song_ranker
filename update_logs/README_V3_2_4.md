# Song Ranker V3.2.4

Run locally with `python -m pip install -r requirements.txt`, then `python main.py`.
Open http://127.0.0.1:5000. Your System Access PIN is unchanged.

## Installing this update

1. Stop Song Ranker.
2. Copy this ZIP's `Song_ranker` folder contents into your existing V3.2.3
   folder, replacing all matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder. No database
   is included in this patch.
4. Start `python main.py` and hard-refresh the browser to load the updated scripts.

The first start upgrades the database to schema 6. An automatic pre-upgrade
backup is saved before changes. This removes obsolete combined trivia totals
and the old scoring-scale high score. Current detailed trivia rounds, current
best score/streak, manual field corrections, match history, Elo, tournament
results and your song library are retained. The old `trivia_legacy` table is
replaced by a small `trivia_adjustments` table containing only manual deltas.
`trivia_stats` remains a view derived from completed rounds and those corrections.

Use Dev > Database to restore a backup. To roll back the update itself, restore
both the previous code and its pre-upgrade database together; starting this
version on an older backup runs the cleanup again.

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
