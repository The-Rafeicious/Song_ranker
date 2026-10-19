# V5.0.2 storage follow-up — V5.0.2.1

This cumulative V5 patch uses **schema 15** in the existing V3 competition file.
It keeps the V5.0.1 import and V5.0.2 source-read/status fixes.

## Install using your latest database

1. Stop every Song Ranker process.
2. Merge the package's `Song_ranker` contents into your existing V5 app folder.
3. Keep your current `data/song_ranker_v3.db` in place and restart the app.
4. First startup creates a complete `database_backups/pre_upgrade_…db` beside
   the active database, then verifies and performs the storage upgrade.
5. Hard-refresh the dashboard. The footer should show **V5.0.2.1** (or your later patch version).

Existing competition results are retained. This does not repeat the original
V5 fresh-start transfer. No additional package installation or file deletion is
required. Use the new code to read schema-15 databases; older app versions refuse
a newer schema. Preserve the pre-upgrade backup for older-code recovery.

## Optional copy in the original V5.0.2.1 storage package

The original V5.0.2.1 storage-review ZIP includes
`Optimized_database_copy/song_ranker_v3.db`, the verified optimized version of
the attachment supplied for that review. Later cumulative patches do not bundle
this optional database copy. It is outside the app overlay folder
so extracting the patch cannot replace your active database accidentally.

The normal installation above upgrades your latest file automatically. Only use
that optional copy in place of the live database if that attachment is still your
latest data. If you have played games or edited the catalogue since uploading,
keep the newer live database and let the patch upgrade it.

## Measured result on the attachment

| Item | Before | Optimized |
| --- | ---: | ---: |
| Active database bytes | 897,024 | 573,440 |
| Approximate decimal KB | 897 | 573 |
| SQLite page size | 4,096 | 2,048 |
| Source records | 241 | 232 |
| Songs / albums / artists / tags | 517 / 155 / 67 / 54 | Same |

**323,584 bytes saved, or 36.07%.** Only nine superseded source observations
were removed. Every field of the latest observation for each linked song and
every value in all other stored tables was verified against the original.
The original attachment is unchanged.

Most live preview URLs are unique (517 of 517); album artwork has 154 distinct
URLs across 155 albums. A shared full-URL lookup table would add joins/indexes
for little duplicate removal. Instead the source codec compresses repeated JSON
keys, names and URL prefixes losslessly, including the duplicate metadata held
inside a source observation. Main song/album/artist URLs stay unchanged and readable.

Vacuuming alone saved about 0.5%; keeping current sources alone saved about 1.8%.
Compression and page packing supply most of the reduction. A 1 KiB-page candidate
was slightly larger than the chosen 2 KiB candidate and performed worse in a
representative 10,000-vote storage scenario. Larger histories favour 4 KiB pages;
the app can increase the page size once used space reaches 4 MiB.

## What remains useful

The app keeps all catalogue links/dates/explicitness, source metadata, mode
results, correction inputs, listening measurements, pending questions and private
preview flags. It also keeps required empty tables/indexes for future gameplay.
Backups remain separate restore points and are not automatically deleted.

There is one current source per song. New source changes replace that row rather
than building a history. Previous observations remain available only in older
backups. Source review detects stale changes even though the row ID stays stable.

Dev → Selection health → Download analysis includes readable decoded current
sources. The full database JSON/SQL backup preserves the exact compressed storage
for restoration. No cover image or audio file is downloaded into the database.

## Verification

The package includes source codec/current-only migration tests and the existing
regression suite. Checks cover exact latest-source metadata/URLs, other table
values, backup recovery, stale reviews, schema constraints, export/rebuild,
growth to larger pages and corrupt/extension-reference failure protection. Live
checks use an isolated copy of the attachment; the original optional optimized copy has
none of those test matches or imports. See [VALIDATION.md](VALIDATION.md).
