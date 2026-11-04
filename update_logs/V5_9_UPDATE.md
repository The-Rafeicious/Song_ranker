# V5.9 updates


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
