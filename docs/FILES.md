# V5 file map

The root keeps the launcher, requirements, README and contributor rules. Runtime
Python code is grouped below; assets/templates retain their existing feature names.
Old root locations are listed in [TRIMMED_FILES.txt](TRIMMED_FILES.txt).

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
| `songranker/listening.py` | Optional bounded browser playback measurements, stored with accepted game facts. |
| `songranker/overall.py` | A personal composite score, derived on demand. No database writes or schema. |
| `songranker/pages.py` | Shared implementation helpers. |
| `songranker/paths.py` | Single project-root owner for data, templates, assets and documentation. |
| `songranker/services.py` | Flask, connections, hydration and shared service helpers. |
| `songranker/version.py` | Single version source for the footer and shared asset cache keys. |

## Storage

| File | Responsibility |
| --- | --- |
| `songranker/storage/catalog_source_state.py` | Lossless schema-13 upgrade: unknown legacy source identities/dates stay unknown. |
| `songranker/storage/challenge_state.py` | Pure schema-12 transport upgrade. Historical quiz rows remain classic facts. |
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
| `static/js/listening.js` | Shared playback measurement; other feature scripts retain their existing owners. |
| `static/css/v5.css` | Small shared V5 report/health additions; baseline loads last. |
| `docs/` | Current user/technical/upgrade/database/style/validation references. |
| `docs/archive/` | Historical validation and completed V4 roadmap; not current setup guidance. |
| `update_logs/` | Release-family history, retained. |
| `tests/` | Python/JavaScript regression tests and historical transport fixtures. |
| `tools/` | Optional offline audits/simulations; never started in the background by the app. |
| `instance/` | Locally generated/preserved signing secret; not bundled. |

Two tiny schema adapters were combined into `storage/schema_compat.py`; the old
standalone missing-metadata script was superseded by the reviewed Dev workflow. Old snapshot-based selector
experiments and V4 shadow comparisons were retired in favour of the current V5
benchmark and regression suite.
One browser tracker/server writer/report macro handles the new listening feature.
There are no compatibility copies of the moved root modules.

## V5.1 backend additions

- `safe_mode.py`: convenience safe launcher.
- `songranker/storage/safe_mode.py`: read-only source snapshots, persistent test identity, process lock and write/Git guards.
- `songranker/modes/shared_spotlight.py`, `vibe_map.py`: versioned mode rules and colours.
- `songranker/modes/judgements.py`, `judgement_selection.py`, `judgement_api.py`: transactional lifecycle, adaptive draws and backend contracts.
- `songranker/reports/judgement_stats_data.py`: read-only mode and Overall sources.
- `tools/test_v51_backend.py`: synthetic checks that always use a safe copy.
- `tests/test_mode_updates_v51.py`, `tests/test_safe_mode_v51.py`: new regressions; `tests/fixtures/` contains schema-only historical definitions.
- `docs/UPGRADE_V5_1.md`, `../update_logs/validation/V5_1_VALIDATION.json` and `update_logs/V5_1_UPDATE.md`: installation, measured validation and release notes.

## V5.1.1 game and stats pages

| File | Owner / purpose |
| --- | --- |
| `songranker/modes/judgement_pages.py` | Four public page routes, no-store responses and report pagination validation. |
| `songranker/reports/judgement_page_data.py` | Read-only identity hydration, renamed-tag links, histogram and paged Vibe track descriptions. |
| `templates/judgement_game.html` | Focused shared game shell and safely embedded mode configuration. |
| `templates/judgement_stats.html` | Mode-specific dashboards ordered from summary/findings to supporting details, history and notes. |
| `templates/judgement_components.html` | Shared identity, Spotlight record and accessible heatmap macros. |
| `static/js/judgement_game.js` | Offer/draft/edit/save/retry/result/next state, accessible grids, tags and preview/listening/pacing integration. |
| `static/css/judgement_modes.css` | Semantic accents, two game compositions, dashboard layouts and responsive controls. |
| `tests/test_mode_pages_v511.py` | Real templates, data projections, read-only guarantees, escaping, pagination, deleted/renamed identities and Global Stats integration. |
| `tests/test_judgement_game.js` | Actual scripts with controlled HTTP/media/pacing boundaries; budgets, optional maps/tags, retries, drafts, skip and reviewed-empty tags, playback ownership and stale responses. |
| `docs/UPGRADE_V5_1_1.md` | Installation, controls and report interpretation. |

Existing owners also updated: `main.py`, `version.py`, `judgement_api.py`,
`global_stats_data.py`, `base.html`, `stats_visuals.html`, `global_stats.html`,
`site.js`, `global_stats.js`, `style.css`, `home.css` and `global_stats.css`.
Startup-order test fakes register the new page module. The main README,
technical/database/style references, current validation and V5.1 release log
include this version. Schema 17 retires the removed mode; remaining selection and Overall formulas
retain their existing owners.

## V5.1.1.1 display hotfix

- `static/css/home.css`: sole seven-card Home composition owner.
- `static/css/special_modes.css`: obsolete Home spans/positions removed; mode-specific styles retained.
- `static/css/navigation.css`: shared navbar spectrum, relative type sizes and responsive rows.
- `templates/base.html`, `static/js/site.js`: consistent real mode emojis; shared navbar asset registration.
- `static/js/judgement_game.js`, `static/css/judgement_modes.css`: Standard-style full-cover overlays, playing state and proper album links.
- `songranker/version.py`: footer and cache version 5.1.2.1.
- `tests/test_judgement_game.js`: expanded metadata/overlay state coverage.
- `docs/UPGRADE_V5_1_1_1.md`: hotfix installation and scope.

Current README, technical/database/style guides, validation and V5.1 release
notes also include this patch. No storage, selector or Overall implementation changed.

## V5.1.1.2 retirement and safe reuse

- `songranker/storage/mode_retirement.py`: explicit retired-mode state transform.
- `tests/fixtures/schema_v16.sql`: historical DDL required for migration regressions.
- `tests/test_mode_retirement.py`: selective removal, backup, restore and route checks.
- `songranker/storage/safe_mode.py`, `safe_mode.py`: persistent copy, adoption and refresh.
- `tools/test_v51_backend.py`: disposable child smoke copy, preserving test progress.
- `docs/UPGRADE_V5_1_1_2.md`, `DELETE_FILES_V5_1_1_2.txt`: upgrade and obsolete files.
- `update_logs/validation/`: historical validation outside current guidance (relocated Markdown links adjusted).

## V5.1.2 relative Spotlight patch

- `static/js/spotlight.js`: relative integer allocation and cancellable four-player rotation.
- `static/js/judgement_game.js`: card selection, graph, draft/retry state and cover points.
- `static/js/round_flow.js`: shared Standard/Quick segment durations.
- `templates/judgement_game.html`: Spotlight asset loading and simplified heading.
- `static/css/judgement_modes.css`: selected cards, point bands, line and collision lanes.
- `tests/test_spotlight.js`: 625 allocation cases and deterministic rotation checks.
- `tests/test_judgement_game.js`, `tests/test_mode_pages_v511.py`: real DOM and template contracts.
- `docs/UPGRADE_V5_1_2.md`: patch-only installation, controls and allocation rules.

V5.1.2 ZIPs include only changed/added files and require V5.1.1.2 as their base.

## V5.1.2.1 refinements

- `judgement_game.js`: explicit selectors, cover markers, idle selection, hidden points and finite results.
- `spotlight.js`: score-order helpers and non-repeating preview completion.
- `round_flow.js`: short result/settle durations alongside placement-preview durations.
- `judgement_modes.css`: compact rail, hover/focus fan, integrated point bands and footer geometry.
- `docs/UPGRADE_V5_1_2.md`: preceding release relabelled to V5.1.2.
- `docs/UPGRADE_V5_1_2_1.md`: current patch instructions and controls.
- `docs/UPGRADE_V5_1_1_3.md`: compatibility pointer for old links.

Current ZIPs contain changed/added files only and apply directly over the previous
Spotlight download, whether its displayed version was V5.1.2 or V5.1.1.3.
