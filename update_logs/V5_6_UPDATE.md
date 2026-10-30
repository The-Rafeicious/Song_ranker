# V5.6 updates

This family continues the existing application; the entries below document these updates.

## V5.6.2 — Statistics that grow with the collection

- Summary counts abbreviate from 1,000 (for example 1.3k) and retain exact title and accessible values. Ratings, scores, percentages and raw tables preserve their precision.
- Metric typography responds to available space; ranking columns expand for exact four-digit positions.
- Voting, Trivia, Tournament, Elo Guesser and Album Shelves participation bars show the first unfinished appearance milestone in the current eligible collection. Completing one advances to two, then three and beyond. New eligible records can lower the target automatically.
- Voting participation counts encounters separately from weighted Elo evidence. Shelves albums count once per gradeable round. Vibe retains its saved map coverage semantics.
- Read-only presentation and report changes; no database migration, saved result changes or backup changes.

Validation: structure and function documentation checks, focused Python regressions, standalone JavaScript suites and 58 served developer-page checks pass. Local Chromium layout validation was unavailable because its browser download failed.

## V5.6.3 — Adaptive voting recency and visibility balance

- Blind and Non-blind selection reads a pool-sized history across both modes (about 127 answered pairs for 1,000 eligible tracks), using the browser history or effective saved results as a fallback. The history horizon grows with the collection.
- A smooth recency penalty discourages tracks seen several matches ago, with a recovery timescale relative to eligible pool size. The existing immediate-pair avoidance remains when alternatives exist; small collections recover faster.
- Preview-ready songs compare their Blind and Non-blind exposures against their own history. The overplayed mode is strongly discouraged, even when it is below the collection average; underplayed visibility gains support until the gap narrows. There is no fixed play quota or multi-match lockout.
- Non-blind songs without previews are exempt from visibility balancing. Saved weighted evidence, correction handling, Elo closeness, opponent diversity, Vibe preferences and frozen open offers are preserved.
- Selection diagnostics use the same recency and per-song balance weights as live voting.
- No database migration or changes to saved results.

Validation: 69 focused selection, preference, adaptive-Elo and Vibe/Shelves regression tests pass, including seeded repeated-play comparisons, balance recovery, tiny pools, owner history, preview eligibility and read-only checks. Structure and generated function documentation checks pass.

## V5.6.3.1 — Adaptive tournament selection

- Tournament entries use the same soft recency and per-song Blind/Non-blind balance as Standard Vote. Selection suppresses the overplayed visibility relative to the song's own tournament entries, even below the pool average.
- Count one appearance per saved bracket entry, including unfinished brackets; advancement and match counts do not inflate exposure. Counts span tournament scopes.
- Recent bracket groups use a pool-sized memory and pair-equivalent elapsed appearances. Unrelated tracks do not age a scoped pool's history. Small and full-pool brackets remain playable without fixed quotas or lockouts.
- Preserve preview eligibility, Vibe affinity, unique entries, Elo/local-evidence seeding and existing brackets. Non-preview tracks are exempt from Non-blind visibility balance. Selection diagnostics share the production weights.
- No schema migration or saved-result rewrite.

Validation: 51 focused selection, bracket-route, tournament policy/credit, Vibe and Shelves tests pass, including entry-count semantics, both visibilities, recent scoped history, unique/full-pool draws and diagnostic parity. Full regression checks were also invoked.

## V5.6.4 — Top-five and song Elo replays

- Voting Stats gains an on-demand top-five replay from saved starting ratings to the current leaderboard, with a UTC vote clock, animated rank lanes, Elo changes and brief opponent cues.
- Play/Pause, Restart, timeline seeking and Relaxed/Normal/Quick pace keep the replay readable. Normal uses two seconds per visible change; quiet votes are skipped.
- Song pages use the same player with a persistent track rank/Elo card and its match journey, including movement outside the top five.
- Read stored effective public projections, seeds, cutoffs and rating overrides; include first-round tournament Elo without recalculating historical votes. Current catalogue scope, unavailable snapshots and legacy anchors are explicit. Manual adjustments are not attributed to opponents.
- Preserve semantic artwork/artist/album links, keyboard controls, reduced motion and cancellation when hidden or leaving the page. Loading and retry states remain in the player.
- No database migration or changes to saved ratings/results.

Validation: all 468 Python regressions pass, along with replay interaction/cancellation tests, existing profile and independent-shell tests, 58 served developer-page checks, structure and generated documentation checks. A saved 1,128-track/506-vote backup produced 48 visible frames with no unavailable projections and an exact current top-five endpoint. Chromium replay/screenshot coverage is included in the disposable CI fixture; a local browser was unavailable. Full repository checks were invoked.
