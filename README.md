# Song Ranker

**Application V5.5.10.3 · competition generation 3 · SQLite schema 22**

Rank your music, recognise previews, play brackets and quizzes, arrange albums,
and describe songs on continuous Vibe Maps. Your songs, albums, artists and tags
share one catalogue; each mode keeps its own evidence and results.

[Start](#start) · [Modes](#modes) · [Results](#results-and-discovery) ·
[Dev tools](#dev-tools) · [Backups and sync](#backups-and-computer-switching) ·
[Phone access](#phone-access) · [Help](#troubleshooting) · [Documentation](docs/README.md) · [Development map](docs/FILES.md) · [Function index](docs/FUNCTIONS.md)

## Start

```console
python -m pip install -r requirements.txt
python main.py
```

Use Python 3.10+ (`python3` where appropriate), then open
<http://127.0.0.1:5000>. Stop the app before pulling updates; restart and
hard-refresh browser tabs afterwards. Keep the active database, backups,
`instance/` secret and Git metadata when updating code.

The normal database is **`data/song_ranker_v3.db`**. Existing V3 competitions
are reused and upgraded with backups. First creation can transfer a V2 catalogue,
restore a generation-3 SQL snapshot, use an optional catalogue seed, or start
empty. A **first V2-to-V3 transfer** resets results; a routine code update does
not repeat that reset. See [upgrades and recovery](docs/UPGRADES.md).

The app reports `5.5.10.3`; Vibe Map retains its internal mode version `1.1`.

## Modes

| Mode | Play | Results and requirements |
| --- | --- | --- |
| 🔥 Standard Vote | Choose between two tracks; Non-blind shows identities, Blind reveals them afterwards. | Public Elo, separate visibility Elo, wins/losses and comparisons. Blind needs previews. |
| 🧠 Trivia | Identify the song, artist and eligible album from a preview. | Field accuracy, timed points, challenge streaks and records. Needs preview audio. |
| 🏆 Tournament | Play 8/16/32-track brackets across the library or an artist, album or tag. | Points, placements and first-round Elo; later rounds and bronze award bracket points. |
| 🎯 Elo Guesser | Pick the track with the higher saved Elo. | Correct picks and progressively harder challenge streaks. Play voting/tournaments first to create different ratings. |
| 🗂️ Album Shelves | Place ten tracks into two or three albums and arrange their relative order. | Album placement, order accuracy and points. Needs proper albums, valid track positions and enough eligible tracks. |
| 📍 Vibe Map | Place each track on four continuous graphs. | Descriptive averages, radar, similarities, density maps and collection consistency. No performance score or Overall contribution. |

Elo begins at 1200. Global tournament first rounds carry full Elo influence;
tag first rounds carry half. Artist and album brackets award tournament points
without changing Elo. Ordinary votes carry full influence.
The clock menu controls Standard/Quick reveal speed and next-question preparation.
Playback, loop and preparation state are owned by the current mode; navigation
ends its players. Unavailable modes report the eligibility they need.

### Vibe Map

| Map | Horizontal | Vertical |
| --- | --- | --- |
| Pace & mood | Slow → Upbeat | Sad → Happy |
| Sound & impact | Acoustic → Electronic | Soft → Powerful |
| Connection | Fractured → Secure | Detached → Devoted |
| Perspective | Past → Future, with Present at the centre | Regretful → Hopeful |

Place the cover-art pin anywhere on the graph, using pointer or keyboard.
Five seconds after the last adjustment, the map saves and the next appears.
Revisit completed maps with the arrows; all four must be completed. **Finish**
opens the eight-spoke radar and two similar tracks, then becomes **Next song**.
The preview stays with the song throughout. Repeated passes update compact
averages rather than adding a permanent row for every attempt.

Mapped similarity gently influences voting, tournament, Guesser and Shelves
draws, adapting to available coverage while retaining randomness and every
eligible pairing. The Vibe selector strongly favours unmapped songs. Full
[mode, API and statistics reference](docs/VIBE_MAP.md).

## Results and discovery

| Page | What to find |
| --- | --- |
| Home | Six mode buttons, catalogue totals, Overall leaders, compact library Vibe maps, mode summaries and scrolling records. The final Vibe banner mixes top-twenty albums/artists/tags by consistency. |
| Search | Songs, albums, artists and tags with identity colours, song tag counts, collection song counts, proper-album counts and contained achievement badges. |
| Song profiles | Artwork/player, catalogue links, compact mode records, a Vibe radar above Overall once four maps are placed, and similar tracks. |
| Album/artist/tag profiles | Linked tracks/releases, pooled mode evidence and four compact Vibe heatmaps once two members are fully mapped. Tags initially show six albums; collection song lists show thirty, with Show more. |
| Rankings | Song and collection Elo/Impact, Overall, and detailed mode boards. Vibe boards have albums/artists/tags only, top/bottom twenty, with absolute ranks. |
| Global Stats | Catalogue/mode totals, recent activity, Overall, Vibe summary, detailed records and recent mode results. Vibe activity counts each song’s latest retained save. |
| Detailed mode stats | Coverage, distributions, trends, records and histories relevant to that mode. Vibe adds all-track heatmaps, patterns, pairs, contrasts and most/least consistent groups. |
| Match history | Ordinary votes and eligible tournament first rounds, visibility/source filters, saved Elo changes and bracket links. |

Collection **Impact** adapts to the current catalogue. **Overall** combines
eligible tested game families with relative evidence. Distinct linked songs are
pooled once; missing evidence is unavailable rather than a fabricated zero rate.
Vibe consistency requires at least two fully mapped songs; Singles/unknown
releases stay outside proper-album records.

Listening-time tracking and its stored observations were removed in v5.1.2.
Preview playback and Trivia’s answer timer remain available.

## Dev tools

Dev has visible Home, Library, Mode edits and Tools & systems links, plus Lock Dev,
Guides, Stop and library search. Home shows key status and direct links to every task.
Focused task URLs support bookmarks/reloads; routine editors sit beside the task
on wide screens and above it on phones, with explicit draft-discard protection.
Git shows separate freshly checked code/database states. Database inspection and backups/restore are separate pages; reviewed resets and
exports also have their own destinations.
Use the ⏻ button in either header for a single-PIN backup and stop.
The Tag workbench defaults to single-song tagging with looping/seeking previews,
tag-count filters and Save & next; reviewed bulk changes remain available.
See the [Dev guide](docs/DEV_GUIDE.md) for controls and page lookup.

Open **System Access** in the footer. Set `SONG_RANKER_PIN` to choose your PIN;
the retained default is `9042`. Searches, filters and optional columns support
catalogue maintenance without editing stored game facts unintentionally.

| Group | Tools |
| --- | --- |
| Library | Explorer plus Songs, Artists, Albums and Tags tables; edit/delete, track placement, source details, preview quality and Vibe shortcuts. |
| Editing | Apple song/album import, reviewed source changes, Singles moves, bulk album/source work, tag/preview workbench and missing-information scan → review → apply. |
| Records | Saved-vote review/correction and Elo overrides; Trivia totals; tournament view/delete/podium edits; Guesser/Shelves records; Vibe map/count edits, map clear, song delete and mode reset. |
| System | Tasks & health, Overall diagnostics, selection health and analysis downloads, inventory, backups, reviewed restore, lossless export/rebuild, Git check/upload, reviewed keep-local choice and controlled Stop app. |

Each song has at most **eight tags**, including imported genres. Add/Replace
checks the final membership of every selected song; Remove stays available.
The first schema-16 migration retained the earliest eight attachments on any
over-limit song. Suggested complementary tags are in [upgrades](docs/UPGRADES.md#tags-and-catalogue-policy).

Apple **song links** select one recording; **album links** open a track checklist.
Untick unwanted tracks before Add selected songs. Trailing “ - EP” is removed
from new local album names and the release uses normal album placement.
Source-only repair preserves local names, artwork, previews and relationships;
metadata replacement has separate options. See [Apple requests by Dev area](docs/APPLE_MUSIC.md).

Vibe maintenance edits the saved average and sample/pass counts, checks for newer
changes, and invalidates old round buffers. [Dev instructions](docs/VIBE_MAP_DEV.md)
cover reviewed maintenance controls. Retired one-time release-cleanup scripts are available only in Git history.

## Backups and computer switching

- Use **Create backup** or **Download full export**. Requested/shutdown backups
  rotate through three verified slots. Routine edits do not create backups;
  migration, sync and recovery archives are separate.
- Use **Stop app** with Git upload selected, enter the fresh PIN and wait for the
  local/Git success receipt before changing computers. Closing a tab does not
  upload or stop the server.
- Every app-managed source pull and database push compares the live and remote
  database hashes. An unchanged remote baseline permits local edits; a backup
  last uploaded by this registered device trusts the current local database.
- A changed backup from another/unidentified device requires **Compare databases…**
  in Dev → Tools & systems → Git sync. Review devices, timestamps, hashes and row
  differences, then type `KEEP LOCAL` or `USE REMOTE`. Replacements make a safety
  backup; changed reviews must be repeated. Whole databases are chosen, not merged.
- Database uploads extend the latest remote commit with only the SQL backup.
  Incoming code and unpublished local code no longer block a safe backup upload;
  local code commits and staging stay local. Code updates still use guarded
  startup fast-forwards.
- **Compact Git storage** repacks objects without expiring history/recovery
  objects. Old plain SQL safety files migrate from `.git` to verified compressed
  copies beside the database backups. No actual database/backup is removed.

Preserve `instance/session_secret`. Default backups are beside the live file in
`data/database_backups/`; custom database paths use a sibling folder. Keep test
and production databases separate when promoting code. [Recovery and sync](docs/UPGRADES.md#database-sync-and-split-recovery)
explains baseline limits and incoming-copy review.

## Phone access

Use the same private network, allow the phone’s exact IP, and browse to
`http://HOST-IP:5000`. Keep the host awake and allow Python through its private
network firewall. Loopback remains available on the host.

PowerShell:

```powershell
$env:SONG_RANKER_ALLOWED_IPS = "192.168.1.42"
python main.py
```

macOS/Linux:

```sh
SONG_RANKER_ALLOWED_IPS="192.168.1.42" python3 main.py
```

Replace the example with the phone’s IP. The full [configuration table](docs/TECHNICAL_GUIDE.md#configuration)
covers the host, port, allowed names, database, PIN and signing secret. This is a
local/private-LAN app.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Updated page still looks old | Stop/restart the app and hard-refresh; ensure templates and feature assets were updated together. |
| A mode has no eligible tracks | Preview availability, differing Elo, bracket size, or proper-album/track-number requirements. |
| Vibe card is hidden | Song needs all four maps; collection needs two fully mapped songs. Partial saves remain visible on dedicated stats. |
| Laptop catalogue is old | Use normal startup, read the database sync status and check the upstream branch; follow split recovery rather than deleting the live database. |
| Import partly succeeded | Read the saved count, fix the failed item and retry remaining checked tracks; saved tracks stay excluded. |
| Restore or migration fails | Keep the original and its backups; read the validation error before selecting a recovered copy. |

## Reference library

[Documentation index](docs/README.md) · [Technical guide](docs/TECHNICAL_GUIDE.md) ·
[Database dictionary](docs/DATABASE.md) · [File owners](docs/FILES.md) ·
[Styling guide](docs/PAGE_STYLE.md) · [Validation](docs/VALIDATION.md) ·
[Release notes](update_logs/README.md) · [Retired references](docs/RETIRED.md)

The release notes separate **v5.1.0 mode integration** from **v5.1.1 documentation
consolidation**. Earlier patch instructions are historical and marked accordingly;
current setup and operating rules live in the references above.

## V5.3 development

V5.3.1 introduced the focused Dev workspace; V5.3.2 replaces Git/database sync with hash and numbered-device checks. V5.3.3 adds multi-disc album support,
V5.3.4 repairs guide dependency recovery, and V5.3.5 expands metadata recovery
and simplifies Dev tables. The current
[Dev guide](docs/DEV_GUIDE.md) describes navigation, recovery and tools.

Related mode operations/statistics now share one owner. Catalogue queries, Dev
operations and common CSS/JavaScript have been consolidated; all assets load from
`templates/assets.html`. See the [consolidation report](docs/CONSOLIDATION.md).

```sh
npm ci
python tools/check.py all
python tools/check.py docs --write  # after adding/moving Python definitions
```
