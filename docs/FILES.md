# File ownership map

V5.3 has one current owner per responsibility. Use the [function index](FUNCTIONS.md) for every definition, signature and source location.

## Python owners

| File | Responsibility |
| --- | --- |
| [main.py](../main.py) | Startup Git handoff, explicit route registration, database bootstrap and Waitress hosting. |
| [songranker/apple_access.py](../songranker/apple_access.py) | Apple request gates, bounded lookup/preview caches and streaming diagnostics. |
| [songranker/catalog.py](../songranker/catalog.py) | Shared catalogue projections, cross-mode results and Elo history queries. |
| [songranker/developer/catalog_sources.py](../songranker/developer/catalog_sources.py) | Source validation/tokens, placement plans and track-number constraints. |
| [songranker/developer/db_tools.py](../songranker/developer/db_tools.py) | Offline audit/export/rebuild/restore/compare CLI. |
| [songranker/developer/dev.py](../songranker/developer/dev.py) | Developer authentication, catalogue edits, records and controlled resets. |
| [songranker/developer/dev_catalog.py](../songranker/developer/dev_catalog.py) | Reviewed Apple source changes, release inspection and Singles moves. |
| [songranker/developer/dev_shutdown.py](../songranker/developer/dev_shutdown.py) | Fresh-PIN stop preparation/acknowledgement and in-flight request leases. |
| [songranker/developer/dev_system.py](../songranker/developer/dev_system.py) | Git/backups/recovery, inventory, database inspection and analysis routes. |
| [songranker/developer/dev_tags.py](../songranker/developer/dev_tags.py) | Canonical tag proposals, reviews and atomic membership apply routes. |
| [songranker/developer/dev_vibe.py](../songranker/developer/dev_vibe.py) | Authenticated stale-safe Vibe coordinate/count maintenance. |
| [songranker/developer/git_sync.py](../songranker/developer/git_sync.py) | Hash-reviewed SQL-only uploads, safe startup fast-forwards and Git storage compaction. |
| [songranker/developer/metadata.py](../songranker/developer/metadata.py) | Fill-only metadata planning/apply, scan lifecycle and HTTP reports. |
| [songranker/hosting.py](../songranker/hosting.py) | Drained single-process shutdown and the Waitress stop callback. |
| [songranker/impact.py](../songranker/impact.py) | Pure catalogue-relative Impact calculations; JavaScript parity lives in ui.js. |
| [songranker/lan_security.py](../songranker/lan_security.py) | Private-LAN addresses/hosts, session secret, origin and local-write policy. |
| [songranker/modes/challenge_rules.py](../songranker/modes/challenge_rules.py) | Pure streak/difficulty rules, reusable without Flask or a database. |
| [songranker/modes/challenges.py](../songranker/modes/challenges.py) | Browser-owned persisted challenge runs and public pure-rule exports. |
| [songranker/modes/guesser.py](../songranker/modes/guesser.py) | Elo Guesser rounds, frozen-answer results and detailed Guesser Stats. |
| [songranker/modes/preferences.py](../songranker/modes/preferences.py) | Preference offers, idempotent writes, corrections/replay and rating projections. |
| [songranker/modes/selection.py](../songranker/modes/selection.py) | Adaptive draw algorithms plus the shared SQL exposure/recency adapters. |
| [songranker/modes/shelves.py](../songranker/modes/shelves.py) | Album Shelves eligibility, ordering/grading and detailed Shelves Stats. |
| [songranker/modes/tournament.py](../songranker/modes/tournament.py) | Bracket generation, tournament voting/results and detailed Tournament Stats. |
| [songranker/modes/trivia.py](../songranker/modes/trivia.py) | Timed field recognition, answer grading/corrections and detailed Trivia Stats. |
| [songranker/modes/vibe_map.py](../songranker/modes/vibe_map.py) | Vibe round state, saving, similarity, stats, profile/library queries and APIs. |
| [songranker/modes/vibe_similarity.py](../songranker/modes/vibe_similarity.py) | Pure coordinate similarity and coverage-aware selector affinity. |
| [songranker/modes/voting.py](../songranker/modes/voting.py) | Standard/blind voting operations, history page and detailed Voting Stats. |
| [songranker/overall.py](../songranker/overall.py) | Derived, calibrated Overall scores and their rankings/details APIs. |
| [songranker/pages.py](../songranker/pages.py) | Home, catalogue/search/rankings, shared collection profiles and Global Stats routes. |
| [songranker/paths.py](../songranker/paths.py) | One resolved project root for data, templates, assets and documentation. |
| [songranker/reports/global_stats_data.py](../songranker/reports/global_stats_data.py) | Read-only cross-mode Global Stats from one SQLite snapshot. |
| [songranker/reports/health.py](../songranker/reports/health.py) | Shared exposure/coverage health and diagnostics using production selectors. |
| [songranker/reports/stats_activity.py](../songranker/reports/stats_activity.py) | Shared dated activity, comparison charts and report attachments. |
| [songranker/services.py](../songranker/services.py) | Flask configuration, managed connections, song hydration and catalogue writes. |
| [songranker/storage/competition.py](../songranker/storage/competition.py) | Configured database paths and one-time V2-to-V3 catalogue-only bootstrap. |
| [songranker/storage/competition_reset.py](../songranker/storage/competition_reset.py) | Transactional per-mode/all result resets; caller owns backup/commit. |
| [songranker/storage/database.py](../songranker/storage/database.py) | Backed-up transactional bootstrap and versioned migration. |
| [songranker/storage/database_access.py](../songranker/storage/database_access.py) | Connection gate and exclusive, drained maintenance context. |
| [songranker/storage/database_io.py](../songranker/storage/database_io.py) | Lossless capture/export/rebuild, validation, restore and backup rotation. |
| [songranker/storage/database_schema.py](../songranker/storage/database_schema.py) | Canonical schema.sql registry and transaction-safe DDL execution. |
| [songranker/storage/git_database.py](../songranker/storage/git_database.py) | Logical database hashes, numbered-device registry, baseline receipts and reviewed adoption. |
| [songranker/storage/preference_state.py](../songranker/storage/preference_state.py) | Pure preference replay and lossless historical state transport. |
| [songranker/storage/schema_compat.py](../songranker/storage/schema_compat.py) | Offline historical quiz/source/retirement adapters; no Flask imports. |
| [songranker/storage/source_storage.py](../songranker/storage/source_storage.py) | Lossless current-source codec, schema-15 adapter and SQLite page policy. |
| [songranker/storage/tag_limits.py](../songranker/storage/tag_limits.py) | Eight-tag policy and the historical schema-16 membership adapter. |
| [songranker/storage/vibe_state.py](../songranker/storage/vibe_state.py) | Fixed Vibe definitions, schema validation and schema-17/18/19 adapters. |
| [songranker/version.py](../songranker/version.py) | One application version for display and every asset cache key. |
| [songranker/vibe_maps.py](../songranker/vibe_maps.py) | Shared map display definitions, compact saved profiles and pass counts. |

## Frontend owners

| Location | Responsibility |
| --- | --- |
| `templates/base.html`, `assets.html` | Shared navigation/editor shell and the only asset registry |
| `templates/app_page.html`, `profile.html` | Dynamic application and shared named-collection shells |
| `templates/components.html`, `mode_stats_components.html`, `stats_visuals.html` | Shared artwork/record/report macros |
| `static/css/style.css`, `components.css`, `site_baseline.css` | Core tokens/layouts, common components and approved final baseline |
| `static/css/reports.css`, `vibe.css`, `profiles.css` | Report geometry and shared descriptive/profile presentation |
| `static/css/dev_workspace.css` | Dev navigation, Home/section/guide layouts and inline editor geometry |
| `static/css/developer.css`, `dev_catalog.css`, `dev_tags.css` | Shared Dev controls and system/record/Vibe, catalogue and tag compositions |
| Remaining feature CSS | Home, search, rankings, history, gameplay and Vibe play layouts |
| `static/js/ui.js` | Shared presentation and text policies |
| `static/js/elo_replay.js` | Lazy public Elo replay for Voting Stats and focused song journeys |
| `static/js/preview.js`, `gameplay.js` | Audio/volume and shared game geometry/round lifecycle |
| `songranker/developer/navigation.json`, `templates/dev.html`, `static/js/dev_workspace.js` | Single Dev destination registry, focused shell, navigation/discard lifecycle and guide reader |
| `static/js/site.js` | Catalogue page assembly and shared navigation/editor orchestration |
| `static/js/dev_catalog.js`, `dev_controls.js`, `dev_tags.js`, `dev_metadata.js` | Catalogue/source, searchable controls, tag editing and metadata task lifecycles |
| `static/js/dev_system.js`, `dev_records.js`, `dev_vibe.js` | System/database/selection, preference/record and Vibe maintenance controllers |
| `static/js/vibe_charts.js`, `vibe_map.js`, `vibe_stats.js`, `vibe_library.js` | Shared radar/profile, Vibe gameplay, statistics and library/ranking controllers |
| Remaining feature JS | Search, profile summaries, special modes/rankings, Overall, Global Stats and shared Stop |

## Maintenance

| Location | Responsibility |
| --- | --- |
| `tools/check.py` | Unified validation and deterministic function-index generation |
| `tools/browser_check.py`, `tests/browser_check.cjs` | Disposable HTTP/DOM and Chromium integration fixtures |
| `tools/benchmark_selection.py` | Current seeded production-selector benchmark |
| `tests/` | Behavior-owned regressions; shared fixtures in support.py and necessary historical schema inputs |
| `data/schema.sql` | Canonical DDL; V5.3.3 uses schema 21 |
| `docs/`, `update_logs/` | Current guides and historical release notes |
| `package.json`, `package-lock.json` | Pinned Node test dependencies and convenient check commands |

Do not create compatibility copies of moved modules. Historical migrations remain because old exports and databases must still restore. One-time release cleanup tools, prototype selectors, IDE metadata and tracked bytecode were removed; active data and backups are preserved.
