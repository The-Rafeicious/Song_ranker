# V5.1.2.1 — Spotlight refinements

- Relabelled the preceding relative Spotlight release as V5.1.2.
- Moved Loop previews between the budget and renamed Next round action.
- Moved numbered selectors below metadata, with explicit selected feedback.
- Replaced the large marker panel with a compact cover rail and hover/focus fan.
- Added placement pulses and resettable 1.5-second automatic next selection.
- Hid points until confirmed results and joined point bands cleanly to cover edges.
- Rearranged bar covers into point order and added finite score-order result snippets.
- Retained existing receipts, schema, adaptive weights and safe-mode behavior.
- Changed/added-files patch applies over the previous Spotlight download.

[Installation](../docs/UPGRADE_V5_1_2_1.md) · [Validation](../docs/VALIDATION.md)

---

# V5.1.2 — Relative Spotlight and rotating previews

- Replaced manual point editing with card selection and a relative placement line.
- Automatic 12-point allocation retains equal ties, song order and distance strength.
- Moved live points onto cover bottoms and the budget into the former Skip position.
- Removed Spotlight’s heading Stats link, caption, steppers and Split equally.
- Added user-started four-song preview rotation: Quick 10 seconds, Standard 20.
- Manual cover jumps redirect rotation; buffering, pace changes and cancellation are handled.
- Preserved existing receipts, database schema, adaptive weighting and safe-mode behavior.
- Changed/added-files ZIP only, applied over V5.1.1.2.

[Installation](../docs/UPGRADE_V5_1_2.md) · [Validation](../docs/VALIDATION.md)

---

# V5.1.1.2 — Sound Twins retirement and persistent safe testing

- Retired Sound Twins gameplay, stats, API, resets, selection and Overall coverage.
- Schema 17 removes only retired facts/table/trigger after the usual verified backup.
- Safe launch reuses one database and adopts the latest marked old test run.
- Added explicit `--refresh-safe-mode` to reload the main snapshot at that same path.
- Gave Vibe Map vivid red and updated the navbar spectrum.
- Expanded Stats into one line per destination with no inner scrollbar.
- Updated current references; prior release entries below remain intact.

[Installation and deletion list](../docs/UPGRADE_V5_1_1_2.md) · [Validation](../docs/VALIDATION.md)

---

# V5.1.1.1 — Home and mode display fixes

- Removed obsolete five-card grid spans and fixed positions; Home now consistently aligns eight cards.
- Replaced the three new mode symbols with real emojis in Home and navigation.
- Matched Standard Vote's full-cover centred player and proper-album metadata links.
- Added the complete mode-colour spectrum to navbar headings, increased label/wordmark sizes and adjusted narrow layouts.
- Updated current documentation and asset/footer version. Schema, rules, weights and safe mode are unchanged.

[Installation](../docs/UPGRADE_V5_1_1_1.md) · [Validation](../docs/VALIDATION.md)

---

# V5.1.1 — Playable modes and dedicated statistics

- Added focused Shared Spotlight, three-table Vibe Map and Sound Twins game pages.
- Added dedicated dashboards: adjusted Spotlight support/point distribution,
  independent Vibe heatmaps/searchable track descriptions/reviewed tags, and
  directed Twins opportunities/adjusted links/reciprocal pairs.
- Added concise game-to-stats links, eight Home cards, menu destinations,
  Global Stats summaries and recent round results, including mode colour blends.
- Reused shared previews, volume, listening measurements and Standard/Quick pacing.
  Results preserve playing audio; preparation starts no audio or new decision.
- Added tab-local token-bound drafts, frozen same-answer retries, explicit
  skip/no-match/unknown-grid states, keyboard grid controls and tag review limits.
- Preserved schema 16, calibration 7, adaptive weights and safe-copy protection.
  No example decisions, database copy, new counters or result caches are packaged.
- Updated the main README, technical guide, database dictionary, file map,
  styling guide, upgrade guide and current validation. Preserved historical notes.
- Validation: 268 Python tests and 456 JavaScript assertions pass. See
  [current validation](../docs/VALIDATION.md) for scope and limitations.

Installation and controls: [UPGRADE_V5_1_1.md](../docs/UPGRADE_V5_1_1.md).

---

# V5.1 - Mode Updates

## V5.1.0 - Backend and safe launch

- Added Shared Spotlight, multi-table Vibe Map and Sound Twins Python backends,
  browser-owned resumable offers, validated transactional answers, idempotent
  receipts and explicit unjudged skips. New game screens are deferred.
- Added schema 16 through the existing verified backup/rebuild migration. Six
  compact fact tables, bounded pending/skipped storage and existing listening
  measurements support read-only reports without stored pair matrices or caches.
- Reused adaptive exposure/new-song selection. Vibe Map tracks partial table
  depth; Sound Twins balances anchor and pair opportunities. Selector diagnostics
  and the full analysis export include the new modes.
- Expanded Vibe Map into mood/energy, sound/delivery and build/hook tables,
  inspired by current tag descriptions. Optional theme judgments preserve
  catalogue memberships and support newly added tags automatically.
- Selected blue-violet `#7F91FF` for Shared Spotlight, lime `#C2DE74` for Vibe
  Map and vivid red `#FF3B3B` for Sound Twins. Existing entity colours remain.
- Integrated Spotlight into the capped preference family in Overall, with
  adaptive support and no synthetic public-Elo matches. Vibe/Twins contribute
  descriptive coverage/support, without treating mood or similarity as quality.
- Added safe launch via `python safe_mode.py`, `python main.py --safe-mode`
  or the environment setting. Read-only source snapshots, per-run destinations,
  three-run retention, write guards, a launcher lock, isolated sessions, visible
  identity and disabled Git keep synthetic decisions away from live results.
- Added `tools/test_v51_backend.py`, which always tests a fresh safe copy.
- Updated per-mode/full resets, inventory, listening, activity, exports,
  restoration and legacy SQL-dump layout recognition for the new facts.
- Fixed optional compaction so sparse implicit row IDs in extension tables are
  preserved; a new regression exposed that VACUUM could otherwise renumber them.
- Restored missing schema-only legacy test fixtures from the supplied history
  and updated startup/schema expectations. No user data is included in fixtures.

Installation and API contracts: [UPGRADE_V5_1.md](../docs/UPGRADE_V5_1.md).
Verification: [VALIDATION.md](../docs/VALIDATION.md).
