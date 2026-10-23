# V5.3 consolidation review

V5.3 reorganises the application around current feature owners, removes retired
release tooling and makes the shared styling contract enforceable. Application
version is **5.3**; SQLite schema remains **20**. Current catalogue/results,
`database_backup.sql`, active databases, backups and the session secret are not
reset or replaced by this refactor.

## Scope and resulting ownership

| Area | Before | After | Result |
| --- | ---: | ---: | --- |
| Runtime Python files | 71 | 52 | Six mode owners contain operations plus detailed statistics; shared catalogue/history queries and Dev operations are grouped |
| Stylesheets | 33 | 15 | Core/components/baseline plus scoped feature groups; obsolete compatibility/version sheets removed |
| JavaScript files | 27 | 22 | Related lifecycle/record/system/Vibe renderers grouped; common helpers and volume have one owner |
| Templates | 26 | 22 | One asset registry and one named-collection profile shell; shared app shell reused for tags/tournament |
| Files under tools | 15 | 3 | One check CLI, one disposable browser fixture CLI and one production-selector benchmark |

The [ownership map](FILES.md) identifies every runtime owner. The generated
[Python function index](FUNCTIONS.md) includes functions, methods, nested helpers,
tools and tests with signatures, purposes and current source links. Regenerate it
with `python tools/check.py docs --write`; CI rejects a stale index.
Ambiguous runtime helpers now describe their contracts in source docstrings,
including ownership, stale-write checks, missing evidence and recovery behavior,
so the index explains their work rather than merely repeating their names.

| Feature | Current Python owner |
| --- | --- |
| Standard/blind voting and history | `modes/voting.py` |
| Tournament | `modes/tournament.py` |
| Trivia | `modes/trivia.py` |
| Elo Guesser | `modes/guesser.py` |
| Album Shelves | `modes/shelves.py` |
| Vibe rounds, detailed stats and profile/library reports | `modes/vibe_map.py` |
| Shared catalogue/cross-mode/history queries | `catalog.py` |
| Draw algorithms and exposure/recency reads | `modes/selection.py` |
| Preference writes/corrections and rating projections | `modes/preferences.py` |
| Source matching, placement and track constraints | `developer/catalog_sources.py` |
| Tag review and membership apply | `developer/dev_tags.py` |
| Metadata planning and scan lifecycle | `developer/metadata.py` |
| Dev system, recovery and raw inspection | `developer/dev_system.py` |
| Historical quiz/source/retirement adapters | `storage/schema_compat.py` |

Pure replay, transport, selector rules and fixed Vibe definitions remain separate
where offline migration/recovery needs them without Flask. Historical schema
fixtures are retained because they test supported restore inputs. Moved modules
have no compatibility copies to drift back into use.

## Frontend changes and issues found

- `templates/assets.html` is the only load list. UI dependencies load first;
  the shared baseline is the final stylesheet. Every asset uses APP_VERSION, so
  changed Vibe assets cannot retain an old independent mode cache key.
- The style guide now states the current contract once. Patch chronology and
  superseded instructions remain in release/Git history. CSS is readable, retired
  legacy/performance selectors are removed, and superseded same-selector
  declarations are pruned while retaining browser fallbacks.
- Artist/album/tag routes resolve identity once and use `profile.html`; old
  unused SQL aggregations and three duplicate profile shells are removed.
- Static reports and independently loaded modes initialise shared navigation
  without fetching/hydrating the entire catalogue. Feature requests remain owned
  by their controllers; optional modules do not execute on unrelated pages.
- Preview volume has one owner in `preview.js`, persists across pages and works
  in Dev even though its header has no volume slider. Common search and tag
  identity policies live in `ui.js`.
- Shared editor/Stop content lives in common components, so public Stop dialogs
  retain the same field and control layout as Dev. Feature-specific editor state,
  stale-result guards and reviewed mutations remain with their controllers.
- Unreachable former performance-ranking code, unused backend compatibility
  wrappers and old schema wrappers are removed. The maintained ranking routes
  continue to resolve to the current mode boards.

## Retired material

Removed the old V4 Elo/Impact comparison scripts (which still imported removed
root modules), frozen prototype selector lab, generation-1 Vibe reset helper and
one-time pre-merge competition cleanup tool. Tests dedicated solely to those
retired tools were removed; current migrations and reviewed result resets remain
covered. Other version-suffixed tests were renamed by behavior rather than lost.
The retained benchmark imports only the current production selector. Its report
records APP_VERSION and emits each checkpoint once, including a 1,700-round run.

Tracked Python bytecode, machine-specific IDE metadata and the generated ranking
text export were removed from source control. Existing ignore rules now also
exclude IDE state. The current SQL snapshot and all durable data are retained.

Node test dependencies are pinned in `package-lock.json`. Startup test stubs derive
the current route imports from the launcher rather than maintaining two stale
copies of a module map. Served Dev checks wait for the requested service content
and completed requests rather than assuming it is ready when a heading appears.

## Verification

- A fixture captured **134** pre-refactor URL/method/endpoint contracts. The new
  route registry matches it exactly.
- HTTP regression checks cover 25 public/game/report/profile/Dev pages, verifying
  existing assets, a single load per file, common cache versions and baseline-last
  ordering. Shared collection profiles remain read-only and preserve their JSON
  identity contract and missing-entity responses.
- Source checks validate all maintained Python imports/definitions, template
  references and asset ownership without importing the app or opening a database.
- `python tools/check.py all` is the common local/CI gate. Its groups and coverage
  are described in [Validation](VALIDATION.md). The PR records completed Python,
  JavaScript/served-page and Chromium results.

The local editing runtime cannot launch Chromium (the process exits before a
page opens), so painted desktop/phone verification is delegated to the PR's
Chromium CI job and screenshots. DOM/media mocks do not prove physical audio
output; live Apple transport and the user's LAN/device still need device checks.
