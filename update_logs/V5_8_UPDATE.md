# V5.8 updates

## V5.8.0 — Interactive song match network

- Add a large Match network workspace linked from Voting Stats, plus a lazy focused panel on song pages. Explore opponents by dragging, pinch/zoom, keyboard pan, Fit map, fullscreen, song/artist search and a keyboard-friendly visible-song list.
- Connect songs through ordinary voting, first-round tournament Elo and later tournament rounds. Deduplicate first-round records; combine repeated meetings into one connection with win/loss counts and visibility/source colours. Local artist/album tournaments are optional and separate. Only completed brackets appear.
- Song views default to four layers and four new branches per expanded song, adjustable from one to five layers and three to five branches. Recenter on any song to follow the web. Preserve cross-links without duplicating nodes or looping through cycles.
- Select a song or connection for current Elo/rank, artwork, artist/album links, wins/losses, date, mode, round/bracket link and real saved Elo before/after values. Points-only or unavailable snapshots stay explicit. Pair history pages retain every matching result.
- A match-history slider filters the web through a chosen point. It does not pretend to reconstruct historical ranks; nodes retain clearly labelled current Elo. Focusing another song keeps that selected history point.
- Keep drawing bounded (180 focused nodes; 1,400 full-view nodes and 6,000 edges), announce limits, and keep all catalogue songs searchable beyond them. Reuse images, cull offscreen drawing and preserve hero/replay audio. Loading, retry, timeout, stale-response guards and exit cleanup are included.
- No migration, rating/formula changes or saved-result writes.

Validation: all 491 Python regressions, JavaScript/DOM suites, 58 served developer-page checks, structure and generated documentation pass. Focused coverage verifies corrections, first-round deduplication, pending/local privacy, timeline prefixes, breadth/depth/cycles, dense/large caps, uncapped search/pair paging, camera gestures, filters, retry/stale cancellation and hero ownership. A saved 1,128-song backup produced a 693-node/594-connection full graph and 44/59-node focused views; graph reads took about 12–27 ms. Full repository checks were invoked; browser layout, gestures and screenshots run in CI because local Chromium is unavailable.

## V5.8.0.1 — Directed match connections and clearer spacing

- Add arrows from loser to winner. A pair with wins on both sides shows arrowheads at both ends, preserving the existing exact W/L history and visibility/tournament colours. Heads stay outside song covers.
- Spread out the whole-network layout and reserve separate cover/title/Elo space after placement, including between components. Bound drawn title width so long names cannot collide.
- Open large whole maps at a readable zoom around a connected hub; Fit map gives the full overview. Keep focused song rings, filters and history behaviour.
- No match, rating, result or database changes.

Validation: all 491 Python tests, JavaScript suites, 58 served developer-page checks, structure and generated documentation pass. Network regressions cover both arrow directions, split/empty results, rendered arrowheads, non-overlapping label slots in 1,200-song and dense layouts, readable initial zoom and Fit overview. Full checks reached Chromium integration; responsive whole-map screenshots run in CI because local Chromium is unavailable.

## V5.8.1 — Cross-mode query workspace

- Add Query under Mode Rankings for songs, artists, albums and tags. Combine up
  to eight numeric, missing-evidence, membership or won-against/lost-to filters.
  Inclusive Elo ranges, recognition rounds/field accuracy, voting visibility,
  tournament/local results, Guesser, Shelves, descriptive Vibe and Overall evidence
  can be compared in one result list.
- Choose primary, secondary and third sort keys with independent directions;
  duplicate keys are removed from choices and unavailable values always sort last.
  Relationship filters expose only relevant source/visibility controls.
- Common presets include most played, highest recognised, recognition by rounds,
  Blind versus Non-blind, tournament leaders, unplayed recognition and Vibe coverage.
- Choose up to six visible metrics. Expand artwork-backed records for compact mode
  figures and linked tracks/artists/albums/tags; titles open the full profile.
  Results use twenty rows per page, direct page input and first/previous/next/last.
  Queries can be shared through the URL and restored through browser history.
- Pool collection rates from their underlying counts and use rated-track mean Elo.
  Keep completed local brackets separate, deduplicate first-round opponent evidence,
  and distinguish unavailable evidence from zero. No rating or saved-result changes.

Validation: focused query engine/API and DOM regressions cover pooling, nulls,
relationships, sorting, paging, input validation, linked identities, escaping,
retry and reset. Responsive browser coverage is included in CI.


## V5.8.1.0.1 — Query heading and category layout

- Give Query a larger green/blue/purple title using the banner wordmark palette,
  with matching multicolour background glows instead of the default green wash.
- Move Songs, Artists, Albums and Tags into a centred category row directly below
  the title, above the query builder, matching the rankings navigation pattern.
- Remove the introductory and evidence-explanation paragraphs around the builder.
- Preserve filters, sorting, expandable records, shared query URLs and pagination.


## V5.8.1.0.2 — Query button styling

- Replace native grey action boxes with rounded, padded controls: a multicolour
  Apply query action, green Add filter, purple Reset, blue navigation and quiet
  red Remove controls. Add restrained hover glows and visible keyboard focus.
- Give category selections tinted pill states and dropdowns a subtle blue/purple
  surface. Keep disabled paging visibly inactive and artwork results rounded.
- Preserve query behaviour, reduced-motion support and high-contrast controls.
