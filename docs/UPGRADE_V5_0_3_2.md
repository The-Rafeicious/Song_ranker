# V5.0.3.2 — quicker source confirmation

Stop the app, merge the package's `Song_ranker/` contents into your V5 app folder,
then restart and refresh the browser. Keep your database, secret and backups.
This cumulative patch includes the previous V5 fixes. Schema remains 15.

Selecting a recording now:

- Shows a green **✓ Selected recording** confirmation and marks its choice button.
- Collapses the other versions into **Change selected recording**.
- Scrolls to confirmation and focuses **Keep choice & next** (or the individual
  source-save button). Reduced-motion preferences are respected.

Reopen the choices to change your mind. Confirmation remains required; selecting
an option does not save or advance the queue by itself. Search, version details,
five-plus-ten choices, skips and group review remain available.

Bulk filters now share aligned labels and 44 px controls, including the Apple
source dropdown and enhanced artist/album pickers. The action selector and
optional Apple release-link field use consistent label spacing.

No database operations, backup policy or shutdown behavior changed. No files
need deleting. See [the previous backup/shutdown guide](UPGRADE_V5_0_3_1.md) for
that workflow and [validation](VALIDATION.md) for the checks.
