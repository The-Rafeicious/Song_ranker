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
