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
- Home, guides and independent system tools no longer wait for a catalogue/source
  download; catalogue-backed tasks load their data on demand with retry.
- Superseded Dev menu/Home rules were removed. Shared palette, typography, touch
  targets and the baseline remain the main site's styling contract.
- Application/asset version is 5.3.1. Schema 20, active data, backups, saved mode
  rules and API mutation contracts are retained. New focused routes are additive.

## V5.3.2 — hash and device based Git sync

- Database hashes are checked before app-managed pulls/pushes. Remote baseline
  equality permits local work; the same registered writer trusts the current local
  copy. Another/unidentified writer's changed database requires an explicit review.
- Backup commits allocate stable device numbers from 1; SQL headers show commit
  time and device number. The device registry travels in commit metadata.
- SQL-only uploads extend the latest remote commit using a temporary index;
  ahead/behind code, local commits and unrelated staging no longer block safe
  backups or leak into uploads. Expected-head leases reject races; pending refs
  retain/reuse failed uploads. Remote history is never rewritten.
- Comparison now shows device/time/commit, full local/remote/baseline hashes,
  catalogue/mode counts and per-table differences. Keep local and Use remote use
  typed, browser-bound, stale-checked reviews and safety archives.
- Compact Git storage repacks while retaining history/recovery objects; old plain
  SQL copies move out of .git into verified, deduplicated gzip backup archives.
  Matching hashes avoid timestamp-only commits. No existing database/SQL snapshot
  contents are part of this code update; schema remains 20.

## V5.3.3 — multi-disc albums and Album Shelves

- One album supports multiple discs with independent track numbers. Imports keep
  disc/track positions; duplicate checks scope positions to one disc.
- Shelves groups all discs on one album shelf and grades disc-first relative order.
  Saved disc positions keep results stable through later catalogue edits.
- Dev has disc fields, a compact Disc column, disc-aware album inspection and a
  direct Move / combine tracks workflow with an optional destination disc.
- Preferred artwork remains independent of source identity. Standard/deluxe
  records are not inferred or automatically combined. Existing IDs and user data
  remain intact; schema 21 defaults pre-existing positions to disc 1.

## V5.3.4 — Dev guide dependency recovery

- Missing/broken Markdown imports no longer crash the guide API. Both guide readers
  show escaped, wrapping text and the requirements installation command instead.
- The fallback uses the full reader width without an empty contents column; normal
  headings, tables and contents return when the dependency is available.
- Document that Git updates do not install Python dependencies. Add backend and
  workspace regressions for missing dependencies, safe text and recovery.
- Application/asset version is 5.3.4. Schema 21 and all existing user data remain.


## V5.3.5 — metadata recovery and Dev tables

- Missing metadata audits local blanks and recovers verified saved Apple facts before online requests. It covers release dates/origins, disc/track positions, preview URLs, missing titles/names, album artwork, genuine artist artwork and missing source details. Existing values, album placements and song tags are preserved. Review includes field values and evidence; ambiguous facts remain unresolved.
- The latest tracked backup has 228 missing song dates (227 available in saved sources), 12 missing album dates and one missing local Single position. It has no missing names, artwork or previews. Empty/ambiguous releases still require review. No live database or backup is changed by this release.
- Dev catalogue tables have stable Search/Filters/Columns controls, field/match/value entry with saved-value suggestions, removable filter chips, row-count choices and page jumps. The page owns vertical scrolling, including database inspection; wide tables retain horizontal scrolling. Actions stay reachable; More menus escape table clipping, fit the viewport and support keyboard navigation.
- Application version 5.3.5; schema remains 21. No migration or tag changes.


## V5.3.6 — Connection wording

- Connection's low attachment label is now Distant / hostile, opposite Devoted.
  Budding or young love belongs nearer Devoted at a lower intensity; breakup songs
  can express closeness, indifference or hatred independently of Fractured/Secure.
- Text only: saved coordinates, canonical definitions, averaging and comparisons
  stay unchanged. Application 5.3.6; schema 21 and Vibe definition version unchanged.


## V5.3.6.1 — Connection label and play-card tags

- Shorten the Connection endpoint to Detached, opposite Devoted, retaining saved
  coordinates and canonical definitions.
- Show assigned tag counts below the album on the Vibe Map song card, including
  zero and singular counts. Refresh from existing round replies without interrupting
  preview playback. Application 5.3.6.1; no schema or tag-data changes.


## V5.3.6.2 — Shared scrollbars

- Style viewport and inner scrollbars with dark tracks, rounded 12 px rails and
  the current page's semantic accent. Hover/drag states are clearer; horizontal
  record shelves retain their own entity/mode colour.
- Standard-colour fallback supports browsers without scrollbar pseudo-elements.
  Forced-colour mode keeps native controls; scrolling and OS overlay behaviour
  stay native. Consolidate older shelf-only scrollbar declarations.
- Application 5.3.6.2; no data, schema or gameplay changes.


## V5.3.6.3 — Quieter Album Shelves board

- Remove the redundant disc/track ordering instruction above the Album Shelves
  board. Gameplay and ordering rules remain unchanged. Application 5.3.6.3.
