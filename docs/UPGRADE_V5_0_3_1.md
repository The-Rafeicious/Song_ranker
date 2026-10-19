# V5.0.3.1 — requested backups and Stop app

Stop the existing app, merge this package's `Song_ranker/` contents into your V5
folder, then launch with **`python main.py`**. Keep your current database, secret
and backups. No database replacement, competition reset or file deletion is
required. Schema remains 15; this cumulative patch also contains earlier V5 fixes.

## Backup policy

- Ordinary edits do not create backups: single/bulk source changes, source metadata
  refreshes, tag edits, Single moves, missing-information fills, deletes and resets.
  Their existing review, validation and transaction safeguards remain.
- **Create backup**, **Stop app**, and the explicitly labelled **Back up & restore**
  action share three slots: `rolling_1.db`, `rolling_2.db`, `rolling_3.db` in the
  active database's sibling `database_backups/` folder. Each new request replaces
  the oldest slot after a complete, verified SQLite snapshot is ready.
- Update/migration recovery archives remain separate. They protect the original
  data when startup upgrades its structure or storage. Ordinary restarts with no
  database change do not add such an archive.
- Existing backups are left untouched. This patch does not silently delete old
  files; the three-slot policy applies to the new rotating files. Full export
  downloads and Git commit history are independent of these three slots.

Use **Create backup** before edits if you want a restore point. SQLite snapshots
include committed WAL data. A failed snapshot/validation/replacement preserves
all previous rotating slots.

## Stop from the website

The **Stop app** button is in the developer dashboard's top action bar, accessible
from every developer view on the hosting computer. Enter the developer PIN again,
even if already signed in. The dialog shows the current Git branch and destination.
Git upload defaults on when configured; without Git, it clearly offers local-only
shutdown. No PIN is saved in the job or retained in the active form.

After **Back up & stop app**:

1. New app actions are paused and active requests/DB connections finish.
2. A rotating local backup is created and verified.
3. If selected, the app uploads `database_backup.sql` through the existing Git
   flow. This publishes only the database snapshot, not unrelated code edits.
4. Local-backup and Git outcomes appear together. After four visible seconds,
   the browser acknowledges them and the normal launcher shuts down.

**Cancel stop** or closing the dialog keeps the app running. If the local backup
or requested Git push fails, the app stays running and displays the error, keeping
any successful local backup. Missing browser acknowledgement times out after two
minutes and resumes the app. A Git snapshot already current on the remote is
reported as unchanged rather than claiming a new push.

The server stops; the browser retains the final receipt so you can close the tab.
Browsers generally do not allow a website to close a tab it did not open. Restart
with `python main.py` when needed. Closing the terminal is not the website's
backup-and-stop workflow.

Website shutdown is intentionally supported by the normal, single-process
Waitress launcher. An externally managed WSGI/Gunicorn host shows the feature as
unavailable; it must be stopped using its own process manager. Local-only System
Access restrictions and same-origin request protection continue to apply.

## Validation

550 Python tests, 2,090 JavaScript assertions and a real launcher/Git shutdown
exercise pass. Git testing uses a disposable local bare remote; no user remote or
live database is changed. Full details are in [VALIDATION.md](VALIDATION.md).
