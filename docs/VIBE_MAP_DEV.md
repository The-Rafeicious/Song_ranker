# Vibe Map maintenance · v1.1

Open **Dev → Records → 📍 Vibe Map**, or use **Vibe Map** in a song’s Actions menu. The existing Dev PIN protects every
maintenance endpoint. Find a song by title, artist, album or ID; the list shows
30 tracks per page with mapped counts and completed passes.

**Edit** opens all four maps. Coordinates use −5 to +5 with two decimal places.
They edit the saved average, not a hidden history of placements. Placed and
skipped sample counts determine the weight of the next normal placement;
completed passes control the selection/exposure count. A placed map needs at
least one placed sample. Completed passes cannot exceed any map's total samples.
Unchanged displayed coordinates retain their exact existing averages.

**Clear map** marks that map unplaced and sets completed passes to zero; press
**Save Vibe data** to apply it. **Delete this song’s Vibe data** clears all four
maps and passes after `DELETE VIBE`. **Clear all Vibe data** requires `RESET VIBE`.
Required map slots and definitions remain; catalogue links and other modes stay
intact. The existing **Reset competition** now clears Vibe data as well.

Saving or deleting a song's Vibe data invalidates its pending/completed round
buffers, preventing a stale player tab from reapplying an old contribution.
An edit fingerprint also checks map values, counts and round drafts: if anything
changed since loading, reload with **Edit** rather than overwriting it. Group
heatmaps, similarities, consistency and draw bias read the corrected data on their
next request. Album/artist/tag Vibe summaries are derived, not separately editable.
Use the existing Database backup action if you want a restore point for manual edits.

## Prepare the test branch for merging

`tools/prepare_vibe_merge.py` is a separate, one-time cleanup tool. It is never
called at startup, from a migration, or by the Dev panel. **It has not been run
on the project database as part of this update.** Test the Dev controls first.

Close the app. Run commands from the repository root, using the actual **test**
database path if you set `SONG_RANKER_DB`. The normal path is shown below.

Preview only (no database, SQL or backup writes):

```console
python tools/prepare_vibe_merge.py --database data/song_ranker_v3.db
```

After checking the counts, apply and export the Git snapshot:

```console
python tools/prepare_vibe_merge.py --database data/song_ranker_v3.db --export database_backup.sql --apply --confirmation "RESET TEST COMPETITION"
```

The script:

- Validates schema 19 and references, refuses unknown extension tables, and
  detects changes between preview/backup and the write transaction.
- Writes a verified `database_backups/pre_merge_vibe_v11_*.db` restore point.
- Clears all votes, corrections, offers, tournament entries/results, trivia,
  challenges, guesses, shelves, listening observations and Vibe selections/rounds.
  Ratings and records return to neutral defaults; no test-mode samples survive.
- Preserves exact song/album/artist/tag IDs, metadata, relationships, every Apple
  source observation, preview notes, catalogue sequences and fixed map definitions.
- Verifies the catalogue values, marks the cleanup complete, and publishes a
  verified SQL round trip to the explicit `--export` path.

A rerun does not reset again or create another backup. It can retry the export
if the first export failed. If any new results exist after cleanup it refuses
to erase them. Keep the app closed until the clean snapshot is reviewed and
pushed, so startup sync or new test play cannot replace it.

Review `git diff -- database_backup.sql`, then commit/push that snapshot on the
test branch using your normal Git workflow. The script runs no Git commands
and never merges branches. Keep backup `.db` files local.

For the eventual code merge, keep your desktop/main live database separate.
If main's existing results should survive, keep main's `database_backup.sql`
when resolving that file; the cleaned test snapshot is a catalogue-only seed,
not a replacement or merge of your production results. No database file is
included in the v1.1 implementation PR.

## API

- `GET /api/dev/vibe?q=...&offset=0`: bounded 30-song search with counts.
- `GET /api/dev/vibe/<song_id>`: four maps, averaged normalized coordinates,
  counts, completed passes, active-round count and edit fingerprint.
- `POST /api/dev/vibe/<song_id>`: fingerprint, all four map records with −5…+5
  input coordinates, status/counts and completed passes. Atomic validation;
  `409` on stale edits and `400` on invalid coordinates/counts.
- `DELETE /api/dev/vibe/<song_id>`: fingerprint and `DELETE VIBE` confirmation.
- `POST /api/dev/reset-history/vibe`: `RESET VIBE` confirmation.

These use existing Dev authentication/request protections. Fixed map definitions
and catalogue membership are not writable through the Vibe endpoints.
