# V5 competition transition and recovery

For the current backend update and safe launch, use [UPGRADE_V5_1.md](UPGRADE_V5_1.md).

## Existing V5 installations

Keep `data/song_ranker_v3.db` when merging code. V5.1 migrates its schema on a
normal launch, without resetting results. Safe mode migrates only its test copy.
Do not overwrite the active file with a catalogue seed, a V2 archive or another
installation's database. The code-only V5.1 download includes none of those files.

## Moving from V2 competition data

On first creation of a missing V3 destination, `storage/competition.py` reads the
existing `song_ranker_v2.db` or explicitly configured source. It saves a verified
complete source archive, then transfers catalogue facts only. Song, artist,
album and tag IDs, relationship rows, titles, artwork, previews, track numbers,
release dates and current source observations are preserved. Older competition
results are archived rather than imported; the new competition starts at 1200.
An existing valid V3 destination always wins on later launches.

`SONG_RANKER_DB` selects the active destination; `SONG_RANKER_LEGACY_DB` selects
an optional older source. The two paths must be distinct. A missing explicitly
configured legacy source is an error, not permission to publish an empty import.

## Recovery

Stop the app before offline recovery. Keep a separate copy of the original and
use the [database tools](DATABASE.md) to audit/export/rebuild into a **new** path.
Normal developer restore accepts V3 competition backups only, validates and
migrates a candidate, and retains a pre-restore safety backup. V2 archives remain
catalogue-transfer sources. Git SQL snapshots keep V3 results when restoring a
missing database; older V2 snapshots enter the catalogue-only transfer.

See [the technical guide](TECHNICAL_GUIDE.md) for paths and hosting, and
[the V5.1 guide](UPGRADE_V5_1.md) for testing without real result writes.
