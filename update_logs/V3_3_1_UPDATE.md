# Song Ranker V3.3.1

Layout patch for **V3.3**. Database schema remains **8**.

## Install

1. Stop Song Ranker.
2. Copy this ZIP’s `Song_ranker` contents over your existing V3.3 project,
   replacing matching files. Keep your database and backups.
3. Restart `python main.py` and hard-refresh the browser.

Only changed files are included. No new migration, reset, scoring change,
selection change or playback-rule change is introduced.

## Changes

- Album Shelves now has a visibly darker aubergine surface, borders and glows,
  with readable muted-mauve text. Album entity links retain their bright violet.
- Elo Guesser moves to its own `/elo_guesser` play page. Standard voting has
  only non-blind/blind tabs again. Old `/game?mode=guesser` links redirect to the
  dedicated page; an old remembered Guesser tab falls back to standard voting.
- New modes receive emoji icons in Game Modes and Stats. Mode Rankings is moved
  before normal Rankings so the three dropdowns sit together.
- In-page stats/ranking/bracket shortcuts are removed from Guesser, Shelves and
  tournament play screens, including the podium. Shared navigation, song links,
  playback controls, next-round actions and statistics pages are retained.
- Shelves’ preview bar is narrower and shorter. Its play control is centred,
  between the sample duration and available-preview/current-track information.
- Global stats puts Guesser and Shelves immediately below recognition and
  tournaments. Song, artist, album and tag profiles use the same mode order;
  each new mode panel has a separate full-width row.
- Dev Records has separate Elo Guesser and Album Shelves pages, retaining
  history search, individual deletion and the mode’s own reset control. An old
  `view=knowledge` link opens Guesser records for compatibility.
- Home’s existing summary figures are retained. New horizontal banners show
  songs by Elo-guess correctness percentage and albums by correct shelf-placement
  count, each limited to twenty. Ties use exposure/accuracy and then title.
  Untested entries are omitted; empty banners show a neutral empty state.
- All seven home banners use their own coloured tile borders and soft glows.
  New banners reuse the existing scroll arrows, automatic movement, focus/hover
  pause, reduced-motion support and no-overflow guard.
- Home summary values now use their mode’s colour instead of inheriting the
  tournament pink.
- Ways to Play shows the first three modes across the top, with the new two
  centred beneath the gaps. Cards are larger; narrow screens wrap appropriately.
- Footer and shared asset keys advance to **V3.3.1**. The main README and this
  update-log index are updated.

## Verification

Backend regression checks use copied databases. Interface checks cover dedicated
mode navigation, preserved play/save flows, preview-bar structure, new banners,
section ordering, full-width profile panels and separate Dev pages. Core API
grading/save functions and schema files are unchanged from V3.3. The original
supplied database is unchanged.

JavaScript syntax and shared CSS parsing are checked. Graphical browser rendering
and real Apple audio are not verified here; DOM checks use mocked media events.
