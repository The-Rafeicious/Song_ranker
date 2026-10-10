# Validation

- 13 backend integration tests passed against temporary database copies.
- 76 DOM integration assertions passed using the running Flask HTTP server
  and jsdom. UI media playback was simulated to verify control states and volume.
- Regular/blind scoring, atomic match writes, mode preservation, proper-album
  exclusion, collaboration aggregation, metadata editing, track numbers,
  import duplicate detection, trivia totals, tournament progression/resume/
  completion and duplicate-vote protection were checked.
- Backup/restore/reset, unsupported backup rejection, active bracket deletion
  protection, foreign keys, exports and authenticated routes were checked.
- Migration preserved all domain records and aggregate trivia values. Running
  it again produced no database changes. Repeated song pairs kept their own
  modes and Elo changes. Fresh database creation and old relational backup
  upgrade passed.
- SQLite integrity check: `ok`; foreign-key violations: zero.
- All existing route paths remain available; `/api/collection` and
  `/api/matchup` were added for the shared UI.
- JavaScript syntax and Python compilation passed.

Limits: a graphical browser could not run in this environment, so pixel-level
rendering and responsive layout have not been verified. Live Apple Music search
and streamed preview audio were not exercised; their HTTP calls and playback
states were tested using simulated responses. Git pull/push were not invoked.

The delivery database contains no test votes or test imports.
