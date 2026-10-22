# V5.2 release notes

## V5.2.0 — Dev revamp, step one

Replace the main app navigation inside Dev with a dedicated task menu, central
Lock Dev, library search and persistent Git/local backup shortcuts. Give Dev tools
a wider canvas and rebuild Home into compact service containers: library counts,
database health, catalogue coverage, stored rounds/votes, Git state and backups.

- Preserve all twenty existing tool destinations. Search carries its query into
  the existing Library Explorer; its larger redesign belongs to a later step.
- Git backup & push checks the current remote and uses the normal snapshot-only
  upload. Blocked operations stay in Git for review; local backup stays separate.
- Add ⏻ to the app and Dev headers. Share the existing acknowledged stop flow
  across pages, requiring one fresh PIN without first unlocking Dev. Preserve
  localhost restriction, rate limits, browser ownership, backup/Git failure handling
  and the externally managed server safeguard.
- Start the [Dev guide](../docs/DEV_GUIDE.md); retain existing editing/record tools
  for future revamp steps. No schema or stored-result changes.

## V5.2.0.1 — compact Dev navigation and Home

- Split navigation into Library, Editing, Records and System dropdowns. Remove
  header backup buttons; place Stop directly before the rightmost search.
- Remove Home action rows. Make entity metrics open their tables and service
  titles open integrity details, Git controls and Database & backups.
- Align health, slim branch/commit/status Git and backups in one equal-sized row.
  Keep coverage and stored activity below, without repeating service data.
- Present integrity totals as compact metrics with bounded issue details.

## V5.2.0.2 — direct Dev Home

Move Home outside the System dropdown into its own navigation link.

## V5.2.1 — Git and database page rebuild

- Rebuild Git around freshly checked, separate code and live-database states,
  check time, per-table deltas, guarded upload/local choice and bounded outcomes.
  Fix the misleading code-only Up to date presentation; keep overwrite safeguards.
- Rebuild backups with compact health, a bounded list and adjacent restore review.
  Move longer explanations into linked Dev/technical guides.
- Add authenticated read-only raw inspection for tables/views (including SQLite
  sequence metadata), column attributes, definitions/indexes/FKs and paged rows.
  Support exact integers, NULL, escaped text and base64 BLOB chunks. Protect signed
  value review against changed rows or another browser; accept no executable SQL.
- Test real Git code-current/data-behind and stale-SQL/local-addition cases, raw
  types, keyless/generated tables, injection, paging and stale UI responses.
- No schema or user-data changes.

## V5.2.2 — single-song tag bench

- Default to a focused song editor beside a searchable queue. Add strict less/more/
  exact tag-count filters and retain artist/album filters and fewest-tags sorting.
- Start checkboxes with current tags; support new tag names and the eight-tag cap.
  Save one song and advance in the pre-save queue order; Skip makes no changes.
- Add native looping and a seekable 30-second preview line. Keep identity, album,
  local track and saved-source facts visible, including missing-preview states.
- Retain reviewed bulk Add/Remove/Replace editing. Protect dirty drafts, stale
  server membership, failed saves/refreshes and lost-response retries.
- Update the Dev/technical/style guides; no schema or game-score changes.

## V5.2.2.1 — tag bench layout polish

- Rebalance the single-song bench so the tag editor has more room than the song
  queue, and keep long song titles and album names inside their queue cards.
- Add a full-width Tag Workshop row below the main Dev health services with a
  direct link plus tagged, untagged and available-tag totals.
- Keep the established Dev panels, semantic colours and responsive stacking.
  No schema, membership or game-score changes.
