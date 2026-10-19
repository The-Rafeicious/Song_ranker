# V5.0.1 — Apple source fix

This patch installs over **V5.0.0**. It fixes source details being dropped when
Apple fields arrive with plain song metadata, confirms saved sources in the Dev
client, and adds optional Apple ID/link columns. Database generation remains V3
and schema remains 14. Your current competition continues.

## Install

1. Stop Song Ranker.
2. Merge the patch's `Song_ranker` contents into the matching existing V5 folder,
   replacing the included code, documentation and test files.
3. Start `python main.py` again. Hard-refresh the Dev dashboard. The footer should
   show **V5.0.1**; its scripts use the new version in their asset URLs.

The patch contains no database, seed, SQL snapshot, backup, signing key or
automatic deletion. No reset or retransfer is needed. Keep your active
`data/song_ranker_v3.db` and existing backups. Requirements are unchanged.
For a pre-V5 app, complete the [initial V5 upgrade](UPGRADE_V5.md) first.

## Check an import

In Dev → Apple Music, search for a recording and add it. The song and verified
source are saved together. The source retains its Apple track ID, store, song/
album URLs, release details and advisory flag. Explicit/Cleaned is shown when
Apple states it; otherwise the existing Not explicit default applies. Advisory
labels do not create or replace your attached genre tags.

In Dev → Songs, enable **Apple ID** and **Apple link** under Displayed columns if
needed. These columns use the saved source and can be sorted/filtered. Apple
content remains available alongside the Linked/Needs link status. Open Actions →
Source to inspect the full saved observation after reloading the page.

Incomplete Apple offers now ask for a fresh search instead of quietly creating
a metadata-only song. Older payloads with a source ID or Apple song URL are
verified on the server. An unavailable/mismatched lookup creates no new song.
Normal signed-search imports do not need an additional Apple lookup to save.

## Songs already added without sources

1. Open Dev → Songs and select **Needs Apple source link**.
2. In the affected song's Actions, choose **Source**.
3. Find the exact Apple recording/version, choose it, and save.
4. Leave **Use Apple's names, preview and song release date** and **Also use
   Apple's album and track position** unchecked for a source-only repair.

This attaches the verified source to the existing song ID. Artwork, preview URL,
album placement, attached artists/tags, ratings and match history stay as they
are. Previously missing IDs cannot be reconstructed without choosing a recording;
the patch does not guess versions or add duplicate songs automatically.

## Included changes and validation

The patch updates the import/backend source handlers, Dev catalogue/table scripts,
version, guides, release notes and regression tests. No files need removing.
See [VALIDATION.md](VALIDATION.md) for the source-persistence, restart and existing
regression checks. Apple responses/media are mocked for automated tests; live
Apple availability remains dependent on the service and your network.
