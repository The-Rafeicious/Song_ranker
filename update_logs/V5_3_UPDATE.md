# V5.3 — repository consolidation

V5.3 reduces duplicated ownership across Python, JavaScript, CSS and templates,
removes retired tooling and documents the current development contract.
SQLite schema remains 20; this update does not reset catalogue or game results.

- Runtime Python: 71 → 52 files. Each game owns its operations and detailed
  statistics; shared catalogue/history, selectors, Dev operations and historical
  adapters are grouped by purpose.
- CSS: 33 → 15 files. Current style rules have one guide and clear owners;
  compatibility/version patch sheets and retired selectors are removed.
- JavaScript: 27 → 22 files. Shared text policies and persisted preview volume
  have one owner; related lifecycle/system/record/Vibe rendering is consolidated.
- Templates: 26 → 22 files. One asset registry, one collection-profile shell and
  reused application shells replace duplicated declarations/pages.
- Tools: 15 → 3 files. `tools/check.py` runs the full PR gate and regenerates the
  complete source-linked Python function index; browser fixtures and current
  selector benchmarking have maintained entry points.
- Static reports avoid unnecessary catalogue hydration; Dev previews honour
  saved volume; profile routes omit unused queries; public and Dev dialogs share
  their core field/layout rules.
- Retired release cleanup/prototype tools, their obsolete tests, unused wrappers,
  tracked bytecode and IDE state are removed. Supported historical migration
  fixtures, current routes, active data and backups remain.

See [consolidation review](../docs/CONSOLIDATION.md),
[file ownership](../docs/FILES.md), [function index](../docs/FUNCTIONS.md),
[styling contract](../docs/PAGE_STYLE.md) and [validation](../docs/VALIDATION.md).

## V5.3.1 — focused Dev workspace

- Dev has Home, Library, Mode edits and Tools & systems with visible section links,
  direct task URLs and a single navigation registry. Old dashboard bookmarks remain
  supported. Home links to every task and shows essential local status/coverage.
- Routine editors sit beside the task on wide screens and above it on phones.
  Fields have bounded scrolling and persistent actions. Record, tag and Vibe drafts
  are protected when navigating; active saves/reviews and restores block navigation.
- Backups/restore, read-only database inspection, Git, reviewed resets, duplicate
  review and exports each have focused pages. Vibe uses a bounded song queue next
  to its editor. Small native selects remain native; field/column options expand
  within the page. Existing reviewed mutations and typed confirmations remain.
- Guides are readable inside Dev, with contents links, formatted tables/code and
  plain-text access. The Dev/style/technical/ownership guides reflect the new areas.
- Superseded Dev menu/Home rules were removed. Shared palette, typography, touch
  targets and the baseline remain the main site's styling contract.
- Application/asset version is 5.3.1. Schema 20, active data, backups, saved mode
  rules and API mutation contracts are retained. New focused routes are additive.
