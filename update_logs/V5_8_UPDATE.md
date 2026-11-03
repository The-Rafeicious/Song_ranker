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


## V5.8.1.0.3 — Query search and statistics chooser

- Restore underlined Songs / Artists / Albums / Tags navigation without pill fills.
- Give search fields inset surfaces, clear actions and visible focus. Library name
  search updates after a short typing pause; Enter still applies immediately.
  Match all accent-insensitive search words across names and linked metadata.
- Rank record suggestions by exact name, prefix and then metadata matches; show
  artwork and linked names, loading/no-results/retry states, and support arrows,
  Enter and Escape. Clear stale requests when a search changes or closes.
- Group Statistics to show by mode with a local search, mode filter, selected chips,
  readable checkbox rows and a live six-field count. Keep sorting fields visibly
  selected and required; disable additional choices at the limit.
- Preserve the current query, paging, URL sharing and underlying statistics.


## V5.8.1.0.4 — Query labels, numeric fields and filter discovery

- Style selector captions with compact accent rules, stronger weight and consistent
  spacing. Replace plain grey number boxes with inset, rounded fields, tabular
  values and clear focus states, including paging inputs.
- Add a searchable filter picker grouped by category, with common shortcuts for
  Elo, matches, win rate, recognition and opponent relationships. Show the eight-
  filter limit, focus newly added controls and support Enter to choose a result.
- Shorten displayed metric and comparison names. Show mode/scope details quietly
  below the main name, retaining full wording for search and accessible context.
- Keep query calculations, evidence definitions, sorting and saved data unchanged.


## V5.8.1.0.4.1 — Roomier Query panel and compact categories

- Give the builder more padding, control spacing and separation between sections,
  with a quiet blue/purple/green surface, coloured border and soft glow.
- Strengthen section titles and picker headings with clearer weight and accents.
- Order filter and statistics categories by option count, largest first, with
  alphabetical ties. Pack whole categories into responsive columns to remove
  large gaps left by unequal grid-row heights.
- Preserve filtering, selection, keyboard navigation and all query calculations.


## V5.8.1.1 — Query identity cards and proper albums

- Keep won-against/lost-to suggestions to cover, song title, artists and the album
  only when it is a proper album; omit tags and Single/unknown release labels.
- Exclude singles and unknown placeholders from album results and album lookups
  using the same proper-album rule as rankings. Retain their songs and cover art.
- Colour result cards by entity and show useful linked metadata beneath the title:
  artists/albums for songs, artists for albums, and catalogue counts for collections.
- Use the shared gold # tile for tags, including related records and search results,
  instead of borrowing a song cover. Keep complete accessible labels and links.
- Remove the green rectangular input outline; show one rounded blue focus ring
  around the whole search field. Preserve forced-colour keyboard focus.


### V5.8.1.1 — Result statistics presentation refinement

- Give the statistics beside result identities clearer label/value hierarchy,
  aligned responsive columns, more spacing and quieter mode captions.
- Colour values and slim dividers by their evidence mode: voting green, Non-blind
  orange, Blind teal, tournament pink, recognition yellow, Guesser coral, Shelves
  purple, Vibe red and Overall cream. Keep unavailable values muted.
- Apply matching value colours inside expanded statistics. Preserve entity card
  colours, exact-value accessibility and all query calculations.


## V5.8.1.2 — Expanded Query mode panels and tag badges

- Give expanded result mode boxes matching coloured borders, subtle surfaces and
  clear headings; avoid repeating the mode name below every figure.
- Replace repeated artist/album/track links with profile-style gold tag badges
  below the statistics. Collection tag counts use the whole current cohort, not
  just the limited related-song preview; tag results show co-occurring tags.
- Keep the result title as the profile link and remove the extra link underneath.
- Give Query's navigation label the page's green/blue/purple gradient everywhere.
- Preserve the compact result metadata, calculations, filters and saved data.


## V5.8.2 — Consistent ranking headers and navigation

- Share the heading, category tabs and top/bottom controls across catalogue,
  mode, Overall and Vibe rankings, with Query using the same heading/tab geometry.
  Preserve entity/mode colours and Query's multicolour title.
- Standardise type, spacing, touch targets and responsive sizes. Give title text
  enough line height and padding for descenders, including Query's final y.
- Remove the explanatory text directly below Overall Rankings.
- Consolidate header/navigation rendering in ui.js and its styles in
  standard_rankings.css; remove superseded Query and core ranking overrides.
- Make navbar link/summary hover decoration consistent, retaining visible keyboard
  focus and existing semantic colours. No ranking or query calculation changes.


## V5.8.3 — Recover transient cover loading failures

- Fix the permanent first-error artwork state: share bounded image recovery in
  ui.js across Query, rankings, profiles, report rows, menus, reveals and replays.
- Retry an actually failed cover twice with backoff, preserving the exact URL and
  browser caching. Share retry timers for duplicate covers; skip detached nodes
  or changed sources and wait while offline or the page is hidden.
- Clear failed styling after a successful load, including already-completed images
  that failed before deferred scripts attached. Keep permanent/missing fallbacks,
  image dimensions, lazy initial loading and game-owned reveal visibility intact.
- Remove conflicting one-shot inline/error handlers. No database/URL rewrites,
  replacement art, audio changes or full-library preloading.
