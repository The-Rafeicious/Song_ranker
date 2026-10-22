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
