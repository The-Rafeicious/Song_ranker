# V5.9 updates

## V5.9.4 — Retire Elo Guesser, rebalance Overall and polish Shelves

- Remove the unused game and its navigation, Home cards, Global/profile summaries,
  stats report, mode rankings, Query fields and dedicated developer controls.
- Rebalance Overall around four equally based families: Voting, Trivia, Tournament
  and Album Shelves. Voting retains one shared family across Elo/Non-blind/Blind.
- Keep adaptive participation/depth weights and configurable caps: the default
  full-pool family cap is now 35%, with eligible subsets scaling automatically.
- Preserve archived Guesser rounds and historical challenge rows in database
  exports, backups and the raw inspector. They contribute no active statistics.


- Make revealed Shelves album covers/titles clickable, enlarge result text and
  give perfect rounds a gold/mauve completion panel with a readable 100% value.
- Keep feasible two-/three-album formats equally likely. Balance album workload
  by size and track exposure, with stronger large-album support in two-album
  rounds, soft same-artist/recency preferences and a uniform random allowance.
- Pick albums before songs; favour under-tested songs while sampling without
  replacement and preserving ten tracks, capacity checks and frozen grading.

## V5.9.3 — Mixed-mode Global Stats theme and aligned summaries

- Blend the mode palette through Global Stats' heading, navigation label and
  background. Keep the specific mode/entity colours inside their summary panels.
- Align panel spacing, metric sizing and labels with the detailed stats pages.
  Add linked artist/album metadata to highlights and gold # identity to tag cards.
- Share Voting Stats' Elo distribution cohort and bands, excluding unplayed
  ratings even when stale counters claim appearances. Show rated/unplayed counts,
  the voted-track average and median, without changing any stored Elo.
- Open saved bracket workspaces from podium, champion and tournament activity
  links. Keep the page's compact summaries and one read-only database snapshot.

## V5.9.2 — Profile and statistics presentation cleanup

- Review song/artist/album/tag profiles, Global Stats and each mode report. Move
  calculation explanations into the technical guide and remove recalculation
  notices from public match/replay views without changing saved scoring or Elo.
- Promote useful evidence, mode ranks, saved rating changes, sample sizes and
  ungraded-result counts into labelled metrics and shared coloured fact panels.
  Give secondary metadata readable type instead of tiny footnotes.
- Fit exact counts to their real slot before abbreviating. Preserve score/rating
  precision and restore full counts when a wider layout has enough room.
- Put match mode, origin, date/time and gap into a full-width footer so the VS
  column cannot grow into a tall explanation stack. Retain linked identities,
  covers, outcomes, filters and page-bound histories.
- Collapse empty activity plots into a compact state while preserving counts and
  expandable daily figures.
- Align shared responsive spacing, numeric wrapping and metadata across reports
  while preserving each page's distinctive statistics and semantic colours.

## V5.9.1 — Retire the match network and streamline Git/backups

- Remove the whole match network workspace, song-page boxes, links, assets and
  graph API. Keep saved matches, normal histories, replays and tournament maps.
  Query retains its opponent evidence and first-round deduplication.
- Receive another device's newer backup without a typed choice when this device
  still exactly matches its accepted baseline. The normal launcher receives it
  before serving; Git sync offers a direct Receive backup action in the running
  single-worker app. Both paths validate again and make a safety backup first.
- Preserve explicit copy comparisons for divergent local/remote work, browser-bound
  receipts, stale checks, rollback, locks and multi-worker replacement restrictions.
- Show the next Git action clearly, collapse diagnostic details, and link Git and
  local backups directly. Add backup type and newest/oldest filters.
- Skip full database health/inventory scans when opening Git or backups; reuse a
  single live capture when hashing and avoid rebuilding an identical baseline.


## V5.9 — Bracket-depth points and fairer Overall tournament credit

- Round wins earn 1, 2, 3, 4 and 5 points as a bracket progresses. Champions of
  8/16/32-track brackets earn 6/10/15 points; bronze wins earn 1/1.5/2.
- Overall rewards knockout advancement instead of raw tournament win percentage,
  with size-weighted top-four achievement including fourth place. Losing a bronze
  playoff cannot undo the advancement or points already earned. In a 32-track
  bracket, fourth earns six points versus three for a quarter-final exit.
- Larger-bracket titles and podiums carry more Overall significance. Actual title,
  podium and win/loss counters remain accurate counts. Tournament's family and
  internal metric weights remain 20% and 30/45/25; calibration version 10 refreshes
  cached results under the new definitions.
- Apply one shared points policy to new games, old bracket views, rankings, Query,
  profiles, local reports, Global Stats and network match details. Historical raw
  point fields are preserved; viewing a report does not rewrite saved records.
- Preserve first-round preference Elo and the separation of local artist/album
  tournaments from library/tag competition and Overall.

## v5.9.5 — Cross-mode Match History

- Moved Match History above Voting Stats and applied the shared mode-spectrum palette.
- Added mode, song/album/artist/tag and inclusive UTC date filters, bounded Query lookup,
  filtered activity counts and twenty-result pagination with preserved filters.
- Reused Elo VS rows for ordinary and tournament first-round votes; added completed
  tournament podiums and bracket links, Trivia field results/timings, submitted
  Shelves with saved correction positions and shared grading, and retained Vibe maps.
- Kept missing evidence visible, excluded Shelves rounds consistent with reports,
  unfinished Blind identities private and Vibe's retained-state limitation explicit.


## v5.9.5.1 — History polish and tournament entry searches

- Coloured the history search controls and removed explanatory paragraphs.
- Unified voting and first-round Elo filters/totals, preserving per-match origin.
- Matched all result cards to the voting surfaces and corrected thumbnail constraints.
- Added per-song tournament finishes and points below podiums, including early exits.
  Collection filters show each matching entrant; tied exits retain place ranges,
  points use the existing scoring policy and missing results stay unavailable.


## v5.9.5.2 — Tournament draw clarification and fullscreen

- Added F to toggle native fullscreen across the app, with typing, selectors,
  dialogs, modifiers, repeats, composition and in-flight requests protected.
- Investigated artist clusters: selection is per-track weighted randomness with
  exposure/recency/visibility/freshness support and bounded first-track Vibe affinity.
  Artist names do not set quotas or force pairs. Selection rules and saved brackets
  remain unchanged; added artist-label invariance coverage and documentation.
