# Song Ranker V5

**V5.0.5.1 · V3 competition database · schema 19 (test branch)**

`New-modes-test` adds **Vibe-Map-v1.0.6**: open **📍 Vibe Map** from Home or
Game Modes to place a song on four continuous red maps. Adjust a pin, let its
five-second timer save it, and use the arrows to revisit saved maps. Finish
opens a clean eight-axis radar and two similar songs with comparison percentages;
the same button then becomes Next song. Results wait for Finish.
Your preview stays with the song through every map and result screen.

The four maps are **Pace & mood**, **Sound & impact**, **Connection** and
**Perspective**, with one-word endpoints and Present at the time-axis centre.
The earlier v1.0.4.2 upgrade resets incompatible generation-1 test results once, after a
backup; catalogue and other game data stay intact. See the
[new axes and reset instructions](docs/VIBE_MAP_V1042.md).

Open **Stats → 📍 Vibe Map Stats**, or Stats from the mode, for coverage, four
all-track density maps, common combinations, axis balances, closest pairs and
biggest contrasts. Album, artist and tag lists show five most/least consistent
groups with mapped-track counts. This update keeps schema 19 and existing
placements. Click a heatmap point to inspect a compact song radar and its two
closest matches without leaving stats. Explicit song, album and artist links
remain in the panel, with the selected song centred at the top. Song pages now
show this radar card immediately above Overall; albums, artists and tags show
compact 2×2 heatmaps with consistency and mapped-track counts in the same spot.
Restart and refresh after updating. See the [stats definitions](docs/VIBE_MAP_STATS.md).

This is descriptive data, with no performance score or Overall contribution.
Repeated passes update compact averages; reviewing the current pass replaces
its contribution. See the [mode/API contract](docs/VIBE_MAP_API.md),
[implementation log](update_logs/VIBE_MAP.md) and
[code-only merge guide](docs/VIBE_MAP_MERGE.md). Alternative axes and four-map
sets are listed in [map options](docs/VIBE_MAP_OPTIONS.md). Keep a separate test database.

Vote between songs, identify previews, run tournaments, guess Elo and arrange
album shelves. V5 keeps your music catalogue and starts the competition again
at 1200 Elo, using the complete V4.1.6 feature set with cleaner reporting,
stage-aware selection and listening analysis.

Already on V5? Apply the [V5.0.2 storage follow-up](docs/UPGRADE_V5_STORAGE.md).
It backs up your current database, compresses source metadata losslessly and
keeps one current source per song. Competition results continue unchanged.
Apple ID and Apple link are available as optional columns in Dev → Songs.

## Start or upgrade

1. Stop the app. Merge the V5 `Song_ranker` folder into your existing app folder,
   or extract the full app into a new folder.
2. For your latest catalogue, keep your current `song_ranker_v2.db` beside
   `main.py` before the first launch. An existing V2 file takes priority over the
   catalogue supplied with the full download.
3. In that folder, run:

```sh
python -m pip install -r requirements.txt
python main.py
```

Use `python3` if that is your Python command. Python 3.10+ is required; validation
used 3.12. Open **http://127.0.0.1:5000**, then hard-refresh existing browser tabs.
The footer should show **V5.0.5.1**.

On first launch, V5 makes a complete SQLite backup of V2, verifies a catalogue-only
transfer and publishes **`data/song_ranker_v3.db`**. Song/artist/album/tag IDs,
relationships, artwork, previews, dates and current Apple source observations stay
intact. Votes, brackets, quiz results, streaks, records, ratings and listening
history start fresh. An existing V3 competition is reused on later launches.

The full download contains a fresh catalogue seed from the supplied app: **507
songs, 65 artists, 151 albums and 54 tags**, with no competition results. The
smaller upgrade contains code and notes only. Neither package overwrites an
active V3 database. To carry changes made since the supplied snapshot, use your
current V2 file when first launching either package.

Read the [V5 upgrade and patch guide](docs/UPGRADE_V5.md) for transfer details,
custom paths, recovery and the [obsolete-file list](docs/TRIMMED_FILES.txt).
Do not copy an old database over the active V3 file to undo an upgrade.

## What changed in V5

- A new competition database with a verified one-time catalogue transfer.
- Mean-based catch-up weights, a small fading bonus for recently added tracks
  and slightly tighter Elo pairing as a pool gains experience.
- Categorical data health, current exposure averages and stage-relative Elo
  spread references, alongside precise draw probabilities.
- Measured playback seconds before answers in all five game modes. Statistics
  show measured samples; missing measurements remain unknown.
- A private **Preview quality** annotation in Dev → Songs → Actions, included in
  analysis downloads without changing public pages or automatic selection.
- Consistent Voting Records, compact history and shared listening summaries.
  Old Classic-record captions no longer occupy current stats pages.
- A grouped backend, one canonical schema and one documentation folder. Release
  history stays in `update_logs/`.

## Play

| Mode | What you do | Recorded results |
| --- | --- | --- |
| Standard Vote | Pick between two tracks; Non-blind shows identities and Blind hides them until the result. | Public Elo, independent visibility-mode Elo and weighted preference outcomes. |
| Trivia | Identify song, artist and eligible album from a preview. | Available-field accuracy, time-sensitive points and progressive challenge records. |
| Tournament | Play an 8/16/32-track bracket across the library or an artist/album/tag. | Bracket points, placements and first-round Elo. |
| Elo Guesser | Pick the track with the higher frozen Elo. | Accuracy and a challenge streak whose pairs become harder. |
| Album Shelves | Place ten songs into two or three albums and arrange their relative track order. | Order accuracy, album placement and points. |

Every song starts at 1200. **Play Standard Vote or Tournament before Elo
Guesser** so there are different ratings to compare. Blind/Trivia need previews;
Shelves needs proper albums with unambiguous positive track numbers and enough
capacity for ten tracks. An unavailable mode explains what it needs.

The clock menu beside volume controls Standard/Quick result speed and preparing
next questions. Audio continues when changing browser tabs; explicit pause stays
in effect. Actual page navigation ends that page's players. Shelf points count
on each album cover before transferring once to the main score.

Whole-library first-round tournaments use full Elo influence; artist/album/tag
first rounds use half. Later/bronze matches award tournament points only. A
half-influence preference contributes 0.5 to win/loss evidence, selection exposure
and Overall support. Actual match counts remain whole events. Saved Elo deltas
already contain their influence and are not halved again.

## Explore results

Rankings and profiles cover Songs, Artists, Albums and Tags. Collection Impact
adapts to the current catalogue; Overall combines tested game families with
relative evidence. Nonempty collections also begin at 1200 Impact. Both scores are derived from
current data rather than imported old competition scores.

Global Stats and the detailed mode pages mix counts, rates, charts and history.
History includes ordinary votes and eligible tournament first rounds, with
mode/source filters, saved rating changes and bracket links. Profiles pool linked
tracks without counting the same song twice.

**Listening before decisions** reports browser-measured audible playback up to
submission. Pauses, buffering, preloading and muted playback are excluded. Zero
means a measured offered track was not listened to; an absent measurement is
unknown. These measurements are diagnostic and do not change scores or selection.

## Manage the catalogue

Open **System Access** in the footer and enter your Dev PIN (the retained default
is `9042`; set `SONG_RANKER_PIN` to change it). Dev groups catalogue search,
imports, tags, metadata, histories, records, selection health, backups and Git.
Table searches/conditions persist independently across categories.

- Apple source review and missing-information fill keep their scan/review/
  apply workflow. Fill-only retains art, previews, attached albums and tag links;
  exact song dates and other missing source fields can be filled when identified.
- Unmarked explicitness displays Not explicit; explicit/cleaned source statements
  remain authoritative. Attached tags are independent of Apple content labels.
- **Songs → Actions → Preview quality** stores a private bad-preview flag and note.
  Fix the preview URL through the usual edit/source tools when appropriate. The
  flag alone neither hides a track nor removes it from a game.
- **Selection health → Download analysis** exports listening observations,
  per-song summaries and preview flags. The public catalogue omits private notes.
- Corrections preserve submitted preference facts and rebuild effective Elo.
  Mode resets also clear that mode's listening measurements. Create a backup first if needed.

## Backups and recovery

Use Dev → **Create backup** or **Download full export**. Requested/shutdown backups
rotate through three verified slots; routine edits do not make backups. Backups sit in
`data/database_backups/` with the default active path; custom database locations
use a sibling `database_backups/` folder. Keep `instance/session_secret`, which
signs sessions and reviewed tasks. It is not a competition result.

The first-transfer `pre_v5_v2_…db` archive contains the complete old competition.
The original V2 file is also left untouched. Normal V5 restore accepts V3
competition backups; it refuses V2 archives so old results are not accidentally
reintroduced. See [recovery](docs/UPGRADE_V5.md#recovery) before changing files.

Git upload/check/restart controls remain explicit in Dev; launch-time code
updates happen before Flask imports. SQL snapshots from a V3 competition retain
its results when restored to a missing database. V5.0.5 also checks an existing
V3 database against the committed remote snapshot before the normal launcher
serves pages, including after a manual Git pull. Older V2 SQL snapshots carry
catalogue data into a fresh competition. A plain downloaded folder works without
Git. [Technical guide](docs/TECHNICAL_GUIDE.md#hosting-and-recovery) covers both.

## Use a phone

Connect the host and phone to the same private network. Set the phone's exact
current IP before launching, then browse to `http://HOST-IP:5000` on the phone.
The existing private-LAN gate is retained; this is not a public hosting setup.

PowerShell:

```powershell
$env:SONG_RANKER_ALLOWED_IPS = "192.168.1.42"
python main.py
```

macOS/Linux:

```sh
SONG_RANKER_ALLOWED_IPS="192.168.1.42" python3 main.py
```

Replace the example address with your phone's address. The computer's address is
the one used in the browser URL. Loopback access on the host remains allowed.
Keep the host awake and allow its Python server through the private-network
firewall. The full [configuration reference](docs/TECHNICAL_GUIDE.md#configuration)
includes custom ports, hostnames, secrets and database paths.

## Find files and technical details

| Location | Contents |
| --- | --- |
| `main.py` | The only root launcher / WSGI entry point. |
| `songranker/` | Shared application helpers and grouped `storage/`, `modes/`, `reports/`, `developer/` code. |
| `data/` | Canonical schema, optional catalogue seed and active V3 database after startup. |
| `templates/`, `static/` | Shared HTML, feature JavaScript and existing styled assets. |
| `docs/` | [Upgrade guide](docs/UPGRADE_V5.md), [technical guide](docs/TECHNICAL_GUIDE.md), [database dictionary](docs/DATABASE.md), [style rules](docs/PAGE_STYLE.md), [file map](docs/FILES.md) and [validation](docs/VALIDATION.md). |
| `update_logs/` | Current and historical release notes, starting with [V5](update_logs/V5_UPDATE.md). |
| `tests/`, `tools/` | Regression tests and offline maintenance/selection tools. |

If a page looks unchanged after copying files, stop/restart and hard-refresh. If
transfer fails, V5 leaves the source intact and does not publish a partial V3
file; read the terminal error and the [upgrade guide](docs/UPGRADE_V5.md). Fresh
zero rates should show `—`, not an invented percentage.

V5.0.4 validation passed **196 available Python tests**, **424 JavaScript
assertions** and **39 served-app DOM/HTTP cases**. Full discovery remains blocked
by missing upstream historical schema fixtures; browser painting and real-device
layout/audio were not validated here. Scope and commands are in
[VALIDATION.md](docs/VALIDATION.md).

V5.0.3 adds five-choice source selection and reviewed bulk source updates.
See [V5.0.3 installation and workflow](docs/UPGRADE_V5_0_3.md).


V5.0.3.1 adds a fresh-PIN **Stop app** button in the developer header: save a
rotating backup, optionally upload the database snapshot to Git, show the results,
then stop the normal launcher. See [installation and backup policy](docs/UPGRADE_V5_0_3_1.md).

V5.0.3.2 adds selection feedback, collapsed source alternatives and aligned bulk
controls. See [patch notes](docs/UPGRADE_V5_0_3_2.md).

## Apple Music imports — V5.0.3.3

Album links open a track checklist: untick unwanted songs, then add the selection.
Song links still select one recording. A trailing “ - EP” is removed from new
local album names. See [Apple adding and developer request behaviour](docs/APPLE_MUSIC.md)
for each dev-panel area, caching, throttling and partial-import recovery.

V5.0.3.3.1 fixes the album checklist Add button so checked songs are submitted,
the saved count is confirmed and the popup closes after success. Restart and
hard-refresh after updating to load the corrected JavaScript.


## V5.0.4 developer polish

Dev has searchable tool navigation, clearer shared controls, bounded bulk and
record lists, an improved album-import checklist and a separate metadata task
module with retry/polling ownership. Catalogue edits share validation and
transaction handling; current inventory/backup discovery has one owner.
Saved edits now report refresh failures separately, and old frontend restore/Git
paths and obsolete Classic Trivia record editing have been removed.

See the [V5.0.4 upgrade and developer audit](docs/UPGRADE_V5_0_4.md).
Restart and hard-refresh after updating, including all new scripts/templates.
Schema remains 15. Existing catalogue, competition and backup policy are kept.


## V5.0.4.1 profile pages

Song, artist, album and tag pages share compact mode records with inline
breakdowns. Overall keeps its Mode balance dropdown without explanatory copy.
Hero artwork and player overlays share rounded corners; artists remain circular.
Tags show six albums initially, and artist/album/tag pages show thirty songs,
with centred Show more buttons for additional items.

See the [profile patch guide](docs/UPGRADE_V5_0_4_1.md). Restart and hard-refresh.


## V5.0.4.2 song tag limit

Songs now have up to **eight tags**. The tag workbench and song details editor
show capacity and prevent adding a ninth tag. Bulk changes check each song’s
resulting set; checked tags can always be removed. Typed names are checked too.

The first launch upgrades to schema 16 with a pre-upgrade database backup. Songs
over eight retain their earliest eight saved tag links; later links are removed.
Tag definitions and competition records remain. Normal saves reject overflow
instead of silently dropping your choices. Apple-supplied genres count too.

See the [upgrade notes and suggested new tags](docs/UPGRADE_V5_0_4_2.md).
Restart and hard-refresh after applying the patch.


## V5.0.4.3 search result labels

Search cards use coloured titles without repeated Song/Album/Artist/Tag badges.
Song cards now show their attached tag count in tag gold, including **0 tags**
and **1 tag**. Copy has consistent spacing across all four result categories.
Restart and hard-refresh after updating. Schema remains 16.


## V5.0.4.3.1 search counts and achievements

Album and artist search cards show a separate green song-count line. Artists
with proper albums also show a purple album count; Singles are excluded.
Achievement badges stay in a bounded single row, with up to three whole badges
that fit the card width. Restart and hard-refresh after updating.

## V5.0.5 laptop / desktop database sync

Previously, Git could pull a newer SQL backup while the app kept using an older
live database. The normal `python main.py` launcher now checks database sync
after code update and schema bootstrap, even when Git was already pulled.

- A validated newer remote snapshot loads when it includes all local changes
  relative to the shared baseline. Updates and deleted rows are checked too.
- A complete `pre_git_database_…db` archive is made before replacement. The
  replacement is transactional and rechecks for intervening local writes.
- A split keeps the local database, saves an `incoming_git_…db` for review and
  blocks uploads that would overwrite remote changes. Dev shows database state
  separately from whether code commits are up to date.
- Shutdown uploads recheck the same baseline before committing the SQL file.
  Use **Stop app** with Git upload selected and wait for its success receipt.
  Closing a browser tab alone does not upload the database.

Apply the update on both computers. On the stale laptop, stop the app, pull the
update, then run `python main.py` and check the startup outcome / song total.
Do not delete the old database to force a reload. See the
[upgrade and split-recovery guide](docs/UPGRADE_V5_0_5.md). Schema remains 16.

V5.0.5.1 fixes the Windows Stop app socket race: after backup, optional Git upload
and confirmation, Waitress closes sockets on its event-loop thread. Database sync
and split-recovery rules are unchanged.
