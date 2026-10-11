# Song Ranker V3.2.7

Style and consistency patch for **V3.2.6**.

## Install

1. Stop Song Ranker.
2. Copy all files from this ZIP's `Song_ranker` folder over your existing
   V3.2.6 project, replacing matching files together.
3. Keep your own `song_ranker_v2.db` and `database_backups` folder.
4. Run `python main.py`, then hard-refresh the browser.

No database is included. Schema stays at **7**; this update introduces no
migration, reset, stored counters or changes to game scoring. V3.2.6's metadata
program, tag descriptions and Dev controls remain available. Install intermediate
updates first if starting from an older version.

## Changes

- Primary titles are centred across home, voting, trivia, rankings, search,
  stats, login, all entity profiles and all Dev sections. Profile titles now
  span the full top-box width; artwork and metadata remain below. Long profile
  titles retain ellipses and the full title on hover.
- Vote-button shadows and focus glows use the current voting mode: orange for
  non-blind, teal for blind. Tournament and trivia retain their own accents.
- Shared stat labels now match their values' colour roles. Page-heading shadows
  follow the heading colour. Dev entity headings, tournament links, song links
  in stats and card hover colours are consistent.
- Song-page cover previews loop while playing, with native looping and the
  same 30-second/end-event fallback as voting previews. Clicking the cover to
  pause still stops the loop. Existing preview-loading and rate-limit safeguards
  remain in use.
- Recent-match loser titles are red on song pages, match history and global
  stats; winner titles remain song green. History panels use the voting accent.
- Recognisability and champions on home are now horizontal artwork-card banners
  with the same automatic scrolling and arrows as Top Tracks/Artists/Albums.
  Recognition includes only songs strictly above 90%, up to 20; champions show
  the latest 20 completed brackets and keep both song and podium links.
- Trivia's best-score/streak/tested-track boxes move just above Top Tracks.
  A neighbouring tournament box shows completed brackets, distinct champions
  and podiums. The existing collection counts remain.
- Every banner pauses on hover or keyboard focus, avoids automatic scrolling
  when content fits, honours reduced motion and restores scrolling after back
  navigation. Arrow presses pause automatic scrolling for four seconds.
- Trivia stats group song, artist and album field accuracy into three cards,
  including correct/missed counts and progress bars. Best score, best streak,
  rounds and tested-track totals remain visible. Most/least recognised lists
  and the latest 100 rounds are retained.
- Recent trivia uses compact square artwork, individual artist/album links,
  clear field-result badges, round points, score, streak and local timestamps.
  Unavailable album guesses stay neutral and do not count as misses. Long
  histories scroll within their panel; mobile rows stack without losing data.
- Existing empty artist and album records now open the normal profile layout
  with an empty-track state, rather than a plain error. Missing records still
  return 404.

## Verification

73 backend tests and 440 interface assertions passed using copied/temporary
databases. Coverage includes all main page types and Dev sections, heading
alignment and colour roles, playback loops/pause, home banner motion/limits,
trivia field denominators, empty profiles, and existing game, ranking, metadata,
tag, preview-error and asset-loading flows. The supplied database is unchanged.

Interface tests use a DOM environment with simulated media. The local Chromium
process could not start, so rendered desktop/mobile screenshots and live Apple
playback were not verified in this environment.
