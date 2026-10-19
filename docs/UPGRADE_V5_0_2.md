# V5.0.2 — source status and Edit summary

Cumulative code patch for V5.0.0 or V5.0.1. Existing V3 data and schema 14 remain
in use. Includes the V5.0.1 source persistence fix.

## Install

1. Stop the app.
2. Merge the patch's `Song_ranker` contents into your existing V5 folder,
   replacing the included files.
3. Restart `python main.py` and hard-refresh the dashboard. The footer should
   show **V5.0.2**.

Your saved sources are already there; reopen Actions → Source or Edit to see
their current details. No re-adding or relinking is needed for successful saves.
The patch contains no database, seed, SQL snapshot or signing key. It does not
reset results or modify existing source snapshots. No files need deleting.

## Fixed behavior

The fill-missing-information tool can save source snapshots without blank optional
fields. The dashboard's all-song source reader previously required those fields,
so a source could save successfully before the next read failed with HTTP 500.
The individual Source dialog could still show it correctly while Edit used an
unavailable/stale batch summary.

Source summaries and history now read those snapshots correctly. Confirmed saves
update the source cache immediately, and the Edit summary refreshes in place
without replacing unsaved fields. If a separate refresh fails after a confirmed
save, the dashboard reports that it was saved and asks for a reload. Rejected
saves still show their real error and leave the review open.

Artwork, preview links, album/artist/tag links and competition results are retained.
Validation and release notes are in [VALIDATION.md](VALIDATION.md) and
[V5_UPDATE.md](../update_logs/V5_UPDATE.md).
