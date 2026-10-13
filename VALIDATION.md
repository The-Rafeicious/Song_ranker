# V3.3.5.1 validation

- **40 new pair/cache/artist assertions passed**: silent two-cover preloading,
  queued download spacing, immediate cached playback, pair eviction, warmup
  cancellation, page cleanup, fresh cache scope on Back, native custom-host
  preloading, Standard/Elo Guesser pair cleanup, tournament round reuse, ranked
  artist queue order, cover controls and ten-second handoffs.
- **84 existing audio/controller assertions passed** for ready-only 1.5-second
  overlaps, buffering, volume mixing, cancellation, failed loads, loop rollover,
  six-second podium timing, Shelves reveals and Trivia transitions.
- **25 cache/backend tests passed**: the previous cache/stream/range cases plus
  page isolation, scoped pair eviction, late-download rejection, valid fresh
  reservations, closed-page protection and cache-control input validation.
- **46 calculator/lookup tests and 119 DOM/interface assertions passed.**
- JavaScript syntax and changed Python compilation passed; artist player CSS
  keeps circular artwork. The source database and Overall calculator are
  byte-for-byte unchanged. No schema or game-result logic changed.

The audio and CDN checks use controlled media events and mocked responses.
Actual Apple/device audio and first-click network latency were not tested here.
Preloading reduces waits once data arrives; it cannot guarantee instant playback
before loading completes or when the preview is unavailable.

The delivered patch contains only edited application files and release notes.
The dedicated scratch QA harnesses, database, backups, audio and compiled caches
are excluded. Apply over V3.3.5, restart and hard-refresh.
