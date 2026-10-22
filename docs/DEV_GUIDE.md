# Developer guide

**v5.2.0.1 · step one of the Dev revamp**

Open **System Access** on the hosting computer and enter the Dev PIN. Dev replaces
the app header and gives the active tool the full content width. Existing editing
and record tools remain available while their later revamp steps are pending.

## Header

| Control | Action |
| --- | --- |
| Category menus | Four dropdowns: Library, Editing, Records and System. All twenty existing destinations remain available. |
| Lock Dev, centre | Ends the Dev session and returns to the app home page. |
| Search library | Opens Library Explorer with your query. The current explorer is retained for the next revamp steps. |
| ⏻ Stop app | Opens the same backup-and-stop dialog from either app header. Enter the PIN once; a separate Dev login is unnecessary. |

The page menu supports keyboard navigation, Escape and clicking outside to close.
Backup and upload controls live on their dedicated pages. A restore in progress must finish before changing tools.

## Developer home

| Container | Shows |
| --- | --- |
| Library | Clickable songs, artists, releases (including Singles) and tags open the corresponding tables. |
| Database health | Application/schema version, SQLite integrity and foreign-key errors. Click the title for the compact integrity report. |
| Catalogue coverage | Untagged songs, missing preview URLs and missing Apple source links. These are stored-data checks, not network playback tests. |
| Stored rounds & votes | Stored vote/round/bracket counts, including prepared rounds where those modes store them, plus songs with all four Vibe positions placed. |
| Git sync | Branch, short commit and cached remote status. Click the title for Git controls; opening Home does not fetch a remote. |
| Local backups | Backup count, newest timestamp and live database file size. Click the title for Database & backups. File size excludes transient SQLite sidecar files. |

Database health, Git sync and Local backups share one aligned row on desktop.
Coverage and stored activity remain below; Home has no separate action rows.

## Page lookup

| Group | Pages / purpose |
| --- | --- |
| Library | Library Explorer searches all entity types. Songs, artists, albums and tags provide existing record tables and editing actions. |
| Editing | Apple Music adds/reviews source versions; Tags & previews handles the eight-tag song limit and preview workbench; Bulk edits reviews sources/album placement; Fill missing metadata runs bounded reviewed requests. |
| Records | Match history and corrections; Trivia / Elo maintenance; tournament brackets/podiums; Elo Guesser, Album Shelves and Vibe Map maintenance. |
| System | Developer home; Overall calculator; Selection health; Database backups/inventory/restore and typed resets; Git & exports. |

Detailed source-request rules: [Apple Music](APPLE_MUSIC.md). Vibe edit/delete/reset:
[Vibe Dev maintenance](VIBE_MAP_DEV.md). Storage and recovery:
[Upgrades](UPGRADES.md). API and configuration: [Technical guide](TECHNICAL_GUIDE.md).

## Stop and recovery

Stop remains available only from localhost on the hosting computer, with the normal
`python main.py` launcher. The PIN is checked freshly and rate-limited; using Stop
does not unlock other Dev tools. A successful preparation drains requests, creates
a rotating local backup and, when selected, uploads the Git snapshot. The visible
receipt waits four seconds before acknowledging shutdown. Cancel keeps the app running.

Backup or Git errors keep the server running. Use **Review in Dev** to inspect them.
For a deliberately restored/wiped local save, use **Git & exports → Keep local
database…**, compare both copies and type `KEEP LOCAL`, then upload normally.
See [split recovery](UPGRADES.md#database-sync-and-split-recovery) before replacing data.
