# File ownership map

The root keeps the launcher, requirements, README and contributor rules. Runtime
Python code is grouped below; assets/templates retain their existing feature names.
Old root/packaging inventories are [expired](RETIRED.md); current owners are listed here.

## Shared application

`songranker/storage/source_storage.py` owns the schema-15 current-source upgrade,
lossless snapshot codec and small/large SQLite page policy.

| File | Responsibility |
| --- | --- |
| `songranker/apple_access.py` | Bounded in-memory lookup/preview caching and streamed Apple diagnostics. |
| `songranker/catalog.py` | Shared library projections and aggregation. Each song contributes once. |
| `songranker/elo_history.py` | Read-only public Elo feed; ordinary vote/exposure views keep their meaning. |
| `songranker/impact.py` | Read-only catalogue-relative Impact, in the current public Elo scale. |
| `songranker/lan_security.py` | Direct private-LAN access policy. This app is not an internet-facing service. |
| `songranker/storage/retired_listening.py` | Schema-20 backed-up retirement of legacy playback observations. |
| `songranker/overall.py` | A personal composite score, derived on demand. No database writes or schema. |
| `songranker/pages.py` | Shared implementation helpers. |
| `songranker/vibe_maps.py` | Shared four-map definitions, display labels, profile reads and pass counts. |
| `songranker/paths.py` | Single project-root owner for data, templates, assets and documentation. |
| `songranker/services.py` | Flask, connections, hydration and shared service helpers. |
| `songranker/version.py` | Single version source for the footer and shared asset cache keys. |

## Storage

`songranker/storage/git_database.py` owns V5.0.5 whole-snapshot reconciliation:
committed SQL candidates, row/key comparisons, deletion-aware device baselines
and transactional adoption. `tests/test_git_database.py` uses two local
checkouts and a bare remote; [upgrade notes](UPGRADES.md) cover recovery.

`songranker/storage/tag_limits.py` owns the eight-tag policy, unique-name
counting and schema-16 membership cleanup. Database insert/update guards live in
`data/schema.sql`. [Tag-limit upgrade notes](UPGRADES.md) include suggested
new tag definitions; `tests/test_tag_limits.py` covers policy and migration.

| File | Responsibility |
| --- | --- |
| `songranker/storage/catalog_source_state.py` | Lossless schema-13 upgrade: unknown legacy source identities/dates stay unknown. |
| `songranker/storage/challenge_state.py` | Pure schema-12 transport upgrade. Historical quiz rows remain classic facts. |
| `songranker/storage/competition_reset.py` | Shared transactional mode/all result resets, including Vibe; caller owns backup/commit. |
| `songranker/storage/vibe_state.py` | Fixed map definitions, mode asset version and schema-17/18/19 transport/migrations. |
| `songranker/storage/competition.py` | One-time catalogue-only V2 -> V3 competition bootstrap. Never edits the source. |
| `songranker/storage/database.py` | Versioned database bootstrap and backed-up, transactional schema migration. |
| `songranker/storage/database_access.py` | Allow normal concurrent DB use; drain connections during local maintenance. |
| `songranker/storage/database_io.py` | Lossless SQLite transport, reconciliation and canonical rebuilding (stdlib only). |
| `songranker/storage/database_schema.py` | The schema.sql registry. Execute statements without executescript's implicit COMMIT. |
| `songranker/storage/preference_state.py` | Pure preference replay and schema-8/9 transport upgrade; no Flask imports. |
| `songranker/storage/schema_compat.py` | Offline schema adapters for recovery and historical fixtures; current DDL has one owner. |

## Modes

| File | Responsibility |
| --- | --- |
| `songranker/modes/challenge_rules.py` | Pure versioned streak rules shared by the server and offline checks. |
| `songranker/modes/challenges.py` | Server-owned quiz runs. Frozen round rules govern progress, never cookie counters. |
| `songranker/modes/games.py` | Shared implementation helpers. |
| `songranker/modes/mode_ratings.py` | Read-only independent Elo projections and evidence for public comparisons. |
| `songranker/modes/preferences.py` | The ordinary preference write path: offers, receipts, corrections and replay. |
| `songranker/modes/selection.py` | Adaptive draws from eligible pools; standard library only, no stored counters. |
| `songranker/modes/selection_data.py` | Read the shared exposure projections and saved recency for game selectors. |
| `songranker/modes/special_modes.py` | Elo predictions and album-order quizzes. Neither writes voting/trivia records. |
| `songranker/modes/vibe_map.py` | Continuous mode state/draft/advance flow, compact averages, profiles and heatmap/similarity APIs. |
| `songranker/modes/vibe_similarity.py` | Coordinate-distance comparisons and coverage-aware gentle draw affinity, including album profiles. |
| `songranker/modes/trivia.py` | Field-by-field trivia: one persisted round, with summaries derived by a view. |

## Reports

| File | Responsibility |
| --- | --- |
| `songranker/reports/data_health.py` | Stage-relative diagnostics, not a target that rewrites or normalises Elo. |
| `songranker/reports/global_stats_data.py` | Read-only Global Stats projections from one SQLite snapshot. |
| `songranker/reports/guesser_stats_data.py` | Read-only Elo Guesser dashboard, using saved comparisons rather than today's Elo. |
| `songranker/reports/recognition_stats_data.py` | Read-only Trivia dashboard. Field totals and saved-round records stay distinct. |
| `songranker/reports/selection_health.py` | Read-only selector diagnostics using the production pools, counts and kernels. |
| `songranker/reports/shelves_stats_data.py` | Read-only Shelves reporting. Saved shelf slots/numbers remain scoring facts. |
| `songranker/reports/stats_activity.py` | Dated, completed result trends. Counts and pooled rates share one read snapshot. |
| `songranker/reports/tournament_stats_data.py` | Read-only tournament dashboard, derived from saved brackets, entries and matches. |
| `songranker/reports/vibe_stats_data.py` | Dedicated density/pattern/pair/consistency statistics. |
| `songranker/reports/vibe_song_data.py` | Compact song radar, metadata and nearest matches. |
| `songranker/reports/vibe_entity_data.py` | Collection profile readiness, maps and consistency. |
| `songranker/reports/vibe_library_data.py` | Home/Global Vibe projections and fixed-limit collection rankings. |
| `songranker/reports/voting_stats_data.py` | Read-only standard/blind voting report. No migrations or counter writes. |

## Developer

| File | Responsibility |
| --- | --- |
| `songranker/developer/catalog_operations.py` | Reviewable Singles moves. Catalogue placement never rewrites game facts. |
| `songranker/developer/catalog_sources.py` | Verified Apple observations and conservative catalogue matching; no lookup side effects. |
| `songranker/developer/db_tools.py` | Offline maintenance: audit, lossless export, rebuild, restore and compare. |
| `songranker/developer/dev.py` | Authenticated catalogue maintenance, records, resets and reviews. |
| `songranker/developer/dev_catalog.py` | Authenticated source review and atomic bulk source saves, album inspection and Singles moves. |
| `songranker/hosting.py` | Drained, acknowledged single-process shutdown and Waitress callback. |
| `songranker/developer/dev_shutdown.py` | Fresh-PIN stop routes, reviewed Git target and request leases. |
| `songranker/developer/dev_system.py` | Local-admin dashboard inventory, explicit Git tasks and reviewed recovery. |
| `songranker/developer/dev_vibe.py` | Authenticated Vibe search, stale-safe average/count edits and song deletion. |
| `songranker/developer/dev_tags.py` | Authenticated, browser-bound review/apply endpoints for tag-only catalogue work. |
| `songranker/developer/git_sync.py` | Database-only Git uploads and guarded, startup-only fast-forward updates. |
| `songranker/developer/metadata_fill.py` | Conservative, fill-only Apple metadata planning. No library import helpers. |
| `songranker/developer/metadata_tools.py` | Authenticated, single-job developer metadata scan and report endpoints. |
| `songranker/developer/tag_operations.py` | Reviewed tag membership changes. No ratings, identities or game facts are edited. |
| `songranker/developer/track_numbers.py` | Album track positions: gaps and blanks are valid; occupied slots are not. |

## Other directories

| Location | Responsibility |
| --- | --- |
| `data/schema.sql` | Canonical SQLite DDL. |
| `data/catalogue_seed.db` | Full-package fallback catalogue; no old results. Not in the upgrade ZIP. |
| `data/song_ranker_v3.db` | Created on first start; active competition, never shipped in a package. |
| `templates/` | Shared base, macros, game/profile/report pages. |
| `static/css/v5.css` | Small shared V5 report/health additions; baseline loads last. |
| `docs/` | Current user/technical/upgrade/database/style/validation references. |
| `docs/RETIRED.md` | Expired references and their current replacements; original texts remain in Git history. |
| `update_logs/` | Release-family history, retained. |
| `tests/` | Python/JavaScript regression tests and historical transport fixtures. |
| `tools/` | Optional offline audits/simulations; never started in the background by the app. |
| `instance/` | Locally generated/preserved signing secret; not bundled. |

Two tiny schema adapters were combined into `storage/schema_compat.py`; the old
standalone missing-metadata script was superseded by the reviewed Dev workflow. Old snapshot-based selector
experiments and V4 shadow comparisons were retired in favour of the current V5
benchmark and regression suite.
Listening tracker/writer/report components were removed in v5.1.2.
There are no compatibility copies of the moved root modules.


V5.0.4 adds `static/js/dev_metadata.js` for metadata task state/polling and
`static/js/dev_records.js` for searchable developer history/archive lists.
`templates/dev_assets.html` owns Dev stylesheet/script declarations.
`tools/validate_dev_pages.py` runs the disposable served-page DOM/HTTP checks;
its companion is `tests/test_dev_pages.js` (requires Node and jsdom).


## Frontend and maintenance lookup

| Owner | Function |
| --- | --- |
| `templates/base.html`, `dev_assets.html` | Navigation/shared asset order; Dev-only feature declarations. |
| `static/js/ui.js` | Shared escaping, entity semantics, ranking rows/controls and banner headers. |
| `static/js/site.js` | Page assembly, shared catalogue/editor wiring and shared scroll ownership. |
| `static/js/dev_vibe.js`, `static/css/dev_vibe.css` | Vibe Records search/edit/reset interface and responsive composition. |
| `static/js/vibe_map.js`, `static/css/vibe_map.css`, `templates/vibe_map.html` | Play state, pin movement/timing, audio handoff, review and manual results. |
| `static/js/vibe_charts.js`, `static/css/vibe_charts.css` | Shared radar/compact heatmap rendering. |
| `static/js/vibe_stats.js`, `static/css/vibe_stats.css`, `templates/vibe_stats.html` | Dedicated stats charts and point inspection. |
| `static/js/vibe_profiles.js`, `static/css/vibe_profiles.css` | Conditional profile cards above Overall. |
| `static/js/vibe_library.js`, `static/css/vibe_library.css` | Home/Global Vibe mounts, combined banner and collection-only rankings. |
| `templates/vibe_song_stats_panel.html`, `vibe_entity_stats_panel.html`, `vibe_global_stats_panel.html` | Shared compact server-rendered fragments. |
| `tools/prepare_vibe_merge.py` | Explicit one-time test cleanup/backup/verified SQL export; preview by default. |
| `tools/validate_vibe_page.py`, `tools/vibe_browser_check.cjs` | Disposable server plus Chromium play/stats/Dev integration and screenshots. |

Optional benchmark/legacy tools remain tools, not current setup instructions.
The [documentation index](README.md) maps current guides; release details live
only in [release-family logs](../update_logs/README.md).
