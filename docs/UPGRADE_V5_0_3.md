# V5.0.3 — source selection and bulk review

Copy the contents of `Song_ranker/` over your existing V5 app, then restart it.
Keep your current `data/song_ranker_v3.db`, secret and backups in place. This
cumulative patch includes the V5.0.1, V5.0.2 and V5.0.2.1 fixes. No competition
reset, database replacement or file deletion is required. Schema remains 15.
If upgrading from schema 14, the earlier [storage upgrade](UPGRADE_V5_STORAGE.md)
backs up and optimizes the live database on first launch.

## Source choices

A song's Source dialog shows five results. Expand **Show 10 more versions**
for up to ten additional choices. If there are more than fifteen, refine your
search or paste an exact Apple song link. Titles, release names, dates, content
flags, Apple IDs and links remain available. Apple import browsing retains its
separate twenty-result paging.

## Bulk review

1. Open **Developer → Bulk edits**. Filter by artist, album and **Apple source**:
   all, needs link, or linked sources that need checking. Select the songs.
2. Choose **Review Apple sources**. Optionally paste an Apple album, EP or
   Single link to use that release across the group; otherwise each song is
   searched by title and artist.
3. Choose the recording and press **Keep choice & next**. Use Previous to
   revisit a song, or **Skip · leave unchanged** to omit it. Skipping a previously
   chosen song removes that choice from the pending changes.
4. **Review group** shows the chosen source releases and content flags.
   Review any item again, then **Back up & save sources** to apply the group.

Nothing is assigned just because a title or track position matches. A shared
release lookup is reused and exact title matches appear first; every assignment
still requires a choice. Up to 500 songs can be reviewed in one group. Closing
the dialog preserves the chosen draft for resuming in the same loaded page;
reloading, restoring a database or discarding the draft clears it. If a different
selection is made while a draft exists, the existing draft resumes first.

Saving updates only each song's current source, including its Apple content
flag. Names, covers, previews, dates, artists, tags, album placement, track
positions and game records stay unchanged. Use the individual source editor
for its separate metadata-refresh options.

The group saves in one transaction with a `pre_bulk_sources` backup. Expired
search offers, songs changed since review, duplicate choices and identities
owned by songs outside the group reject the whole save. Two misassigned sources
can be exchanged when both songs have reviewed replacements in the same group.
One current source per song and its existing source row ID are retained.

Bulk tag actions and the bulk tag filter were removed; use **Tag & preview
workbench** for tag editing. Album moves remain in Bulk edits.

## Validation

Release checks are recorded in [VALIDATION.md](VALIDATION.md). Tests use disposable
databases and mocked Apple responses; the supplied database is unchanged.


V5.0.3.1 supersedes this release's automatic per-edit backup policy and labels.
Bulk source save remains atomic but no longer backs up. See
[the requested-backup and shutdown policy](UPGRADE_V5_0_3_1.md).
