# V5.0.4 — developer polish

Merge the V5.0.4 changes, stop/restart the app and hard-refresh your browser.
The footer must show **V5.0.4**. Include `dev_metadata.js`, `dev_records.js` and
`templates/dev_assets.html` when copying files manually. No schema migration,
competition reset or active database replacement is needed; schema remains 15.

## What changes in Dev

| Area | Result |
| --- | --- |
| Navigation | Find a tool searches the grouped sidebar. Clearing it restores the previous group expansion. Tasks & health and Git & exports have clearer labels. |
| Shared selectors | Label focus, keyboard choices, Escape, selected captions, form reset and disabled state use the shared picker. Native selects remain the state owner. |
| Explorer and catalogue tables | Shared control sizing and centred headings remain consistent. Empty artist averages stay unavailable. Edit, expandable actions, filters and optional Apple columns remain available. |
| Entity editing | Artist/album/tag edits use shared text/date validation, transactional writes and guaranteed connection cleanup. Missing records return 404; conflicting removals return 409. A successful save followed by a failed refresh is reported as saved. |
| Apple import | Album checklist has Select new songs, Clear selection and a selected count, with immediate saving progress. Saved tracks are excluded on partial retry. One error element belongs to each dialog. Song-link behaviour and EP normalisation are retained. |
| Bulk edits | Fifty rows initially, Show 50 more, selection counts outside the current filters, and a labelled selection cap of 500. Search/filter scope still covers the whole catalogue. Selected album choices show their pressed state; a truncated album list asks for a narrower search. |
| Tags & previews | Existing reviewed membership edits, tag creation, preview ownership and browser-bound stale-review checks are retained. Shared navigation, selector and dialog fixes apply here. |
| Missing metadata | Separate module owns polling, cancellation and late responses. Any two-letter store is accepted, with GB/US suggestions. Load errors have a refresh action. Apply success remains distinct from a later catalogue-refresh failure. |
| Match history | Search, visibility filter, match count and thirty-row paging. Saved-vote review/correction remains available. |
| Tournaments | Search, status filter, count and thirty-row paging; View, Edit podium and Delete remain with each record. Podium choices have associated labels. |
| Trivia / Elo | Maintains real Trivia totals and reviewed Elo corrections; saved-vote review replaces the obsolete Classic-record tile. Current challenge bests derive from completed runs. |
| Guesser / Shelves records | Existing latest-thirty histories retained. Removal wording now matches the requested-backup policy, rather than promising an automatic backup. |
| Overall calculator | Lookup also searches #ID and explains when only twelve results are shown. Calculations and weights are unchanged. |
| Selection health | Read-only current pool/weight diagnostics retained, including analysis download and private preview annotations. |
| Database & backups | Inventory and backup discovery are shared with the older overview endpoint, including safely quoted extension names. Download technical guide now returns the technical/Git guide its label promises. Reviewed restore, three-slot requested backups and schema archives remain. |
| Git / Stop app | Existing explicit tasks, target reviews, fresh PIN, backup receipts and acknowledged shutdown retained. The obsolete alternate frontend restore/upload flows are removed. |
| Templates | Dev-only asset declarations have one readable include. The common editor retains one error owner and bounded scrolling with visible footer actions. |

The previous authenticated backend aliases are retained for existing clients.
The current interface uses the reviewed workflows. Routine catalogue edits still
do not create backups; request one when you want a restore point.

## Backend audit

All fourteen modules under `songranker/developer/` were inspected (including the
package marker). Changes focus on `dev.py` catalogue/maintenance paths,
`dev_system.py` inventory/recovery outputs, metadata task validation/reporting,
and outdated imports/comments in supporting modules. Verified Apple offers,
source identity conflict checks, atomic bulk source saves, reviewed tag plans,
track-position checks, offline recovery tools, Git guards and shutdown leases
retain their existing owners. They were not replaced just to make files look new.

Metadata polling and record-list rendering now live in their own feature modules,
reducing the shared page script and removing duplicate system screens. Public
gameplay, selection/scoring, media behaviour and the database schema are outside
this update's changes.

## Validation and limits

See [validation](VALIDATION.md) for exact commands and evidence. Current tests
cover the reviewed/import/retry workflows and a disposable served app with all
nineteen Dev views. DOM checks do not prove physical layout, browser painting or
audio behaviour on a phone. Historical schema 9/12 fixtures are absent from the
upstream repository, blocking those older migration tests; they were not silently
removed or replaced with invented fixtures.
