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
