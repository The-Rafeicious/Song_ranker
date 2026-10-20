# Song Ranker V5.1.2.1

**V5.1.2.1 · Spotlight placement and results refinements · V3 competition · schema 17**

Vote between songs, identify previews, run tournaments, guess Elo, arrange album
shelves, share a spotlight or describe a vibe. Home has seven games in a
responsive four/two/one-column grid, with real emojis and full-cover preview
players. Proper album links follow Standard Vote’s metadata pattern.

## V5.1.2.1 Spotlight refinements

Use the numbered selector **below each song’s artist/album details**, then click
its position on the compact Worse → Better bar. Selection has a clear highlight;
metadata links and preview covers have their own actions. Small cover thumbnails
replace the bar’s numbers, with overlapping covers fanning apart on hover/focus.
The bar pulses on placement. After 1.5 seconds without adjustment, selection moves
to the next unplaced song (or the next song if all are placed). Dragging, further
adjustment and manual selection reset/cancel the wait; revisiting remains possible.

The footer now reads **available points · Loop previews · Next round**.
Points remain hidden while placing. Next round saves the same automatic 12-point
split, reveals clean point bands over the covers and rearranges bar thumbnails
by point order. Brief result previews play highest points first, once through,
then a new round opens. The results Next round button can advance immediately.

This download contains **changed and added files only**, to merge over your last
Spotlight release, now named **V5.1.2** (previously labelled V5.1.1.3). No separate
reinstall is needed. Stop the app, merge `Song_ranker`, restart and hard-refresh.
Schema 17, saved results, adaptive weighting and safe mode are unchanged.
[Installation and controls](docs/UPGRADE_V5_1_2_1.md).

## V5.1.1.2 changes

Vibe Map now uses vivid red `#FF3B3B`. The navbar spectrum includes every current
mode, and the Stats dropdown gives each destination its own line without an
internal scrollbar. Shared Spotlight keeps blue-violet `#7F91FF`.

The retired mode is removed from current play, reports, Overall coverage,
resets and storage. Schema 17 selectively removes its results after a verified
pre-upgrade backup. Your catalogue and the remaining modes’ results are kept.
Historical release notes are unchanged; see the
[upgrade and deletion list](docs/UPGRADE_V5_1_1_2.md).

## Shared Spotlight and Vibe Map

- **Shared Spotlight 🔦:** place four tracks on a relative line. Distances
  divide 12 points automatically; ties and zeroes remain valid.
- **Vibe Map 🗺️:** place one, two or all three independent tables. Optional
  tags use the catalogue’s existing selections and descriptions. Unplaced
  tables and unreviewed tags stay unknown.

Both have focused game pages and dedicated stats: summaries and main findings
first, then detailed tables, listening and history. They use shared preview,
volume and Standard/Quick pacing. Drafts and open rounds resume on refresh;
**Retry same save** retains the original answer and listening sample. Selectors
and evidence weights remain self-adjusting. Spotlight contributes adaptively to
Overall’s preference family; Vibe provides descriptive coverage with no quality
weight. Overall remains calibration 7.

## Test safely

Merge the code into your existing folder while keeping the database and backups.
Stop the app, then launch:

```sh
python safe_mode.py
```

First use creates an isolated copy. Later launches reopen the same safe database,
and browser refresh retains its test data. The banner identifies safe mode;
results, edits and backups stay there. Git is disabled and test changes never
merge into the main database. To copy your latest real songs into that same
location, stop the app and explicitly refresh:

```sh
python safe_mode.py --refresh-safe-mode
```

Refresh clears test results in the safe database; it leaves the main database
unchanged. The first updated launch adopts the latest marked old test run and
removes other marked runs for that same source. Unmarked folders and backups
are kept. Stop the test app and run `python main.py` for real play.

See [page controls](docs/UPGRADE_V5_1_1.md),
[backend contracts](docs/UPGRADE_V5_1.md) and [release history](update_logs/V5_1_UPDATE.md).

## Start or upgrade

1. Stop the app. Merge this download's `Song_ranker` folder into your existing app folder.
2. Retain your current `data/song_ranker_v3.db`, backups and local settings.
   For an older V2 installation, follow [the transition guide](docs/UPGRADE_V5.md).
3. In that folder, run:

```sh
python -m pip install -r requirements.txt
python safe_mode.py
```

Use `python3` if that is your Python command. Python 3.10+ is required; validation
used 3.12. Open **http://127.0.0.1:5000**, then hard-refresh existing browser tabs.
The footer should show **V5.1.1.1**.

When moving from V2 into a missing V3 destination, V5 makes a complete SQLite
backup of V2, verifies a catalogue-only
transfer and publishes **`data/song_ranker_v3.db`**. Song/artist/album/tag IDs,
relationships, artwork, previews, dates and current Apple source observations stay
intact. Votes, brackets, quiz results, streaks, records, ratings and listening
history start fresh. An existing V3 competition is reused on later launches.

This V5.1.1 download is a code-only upgrade. It includes no active SQLite database,
SQL backup snapshot or fabricated results. Your existing V3 database takes
priority; it is preserved and migrated on a normal launch. The code-only package
also supports an empty installation, but does not supply its music catalogue.

Read the [V5 upgrade and patch guide](docs/UPGRADE_V5.md) for transfer details,
custom paths, recovery and the [obsolete-file list](docs/TRIMMED_FILES.txt).
Do not copy an old database over the active V3 file to undo an upgrade.

## What changed in V5

- A new competition database with a verified one-time catalogue transfer.
- Mean-based catch-up weights, a small fading bonus for recently added tracks
  and slightly tighter Elo pairing as a pool gains experience.
- Categorical data health, current exposure averages and stage-relative Elo
  spread references, alongside precise draw probabilities.
- Measured playback seconds before answers in all eight game modes. Statistics
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
| Shared Spotlight | Place four previews on a relative line; distance divides 12 points automatically. | Allocations, adjusted preference support and adaptive Overall evidence. |
| Vibe Map | Place a preview on independent mood/energy, sound/delivery and build/hook grids; optionally choose tags. | Descriptive coordinates, heatmaps, spread and reviewed-tag counts. |

Every song starts at 1200. **Play Standard Vote or Tournament before Elo
Guesser** so there are different ratings to compare. Blind/Trivia need previews;
Shelves needs proper albums with unambiguous positive track numbers and enough
capacity for ten tracks. Spotlight needs four distinct previewable songs; Vibe needs one. An unavailable mode explains what it needs.

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
its results when restored to a missing database. Older V2 SQL snapshots carry
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

Earlier V5 validation included **511 Python tests**, **2,037 JavaScript assertions**,
**571 live app checks** and **48,000 simulated preference draws**. Browser QA used
DOM/computed-style checks; physical-device layout, audio and Windows hosting
remain installation checks. Scope and reproducible commands are in
[VALIDATION.md](docs/VALIDATION.md).

V5.0.3 adds five-choice source selection and reviewed bulk source updates.
See [V5.0.3 installation and workflow](docs/UPGRADE_V5_0_3.md).


V5.0.3.1 adds a fresh-PIN **Stop app** button in the developer header: save a
rotating backup, optionally upload the database snapshot to Git, show the results,
then stop the normal launcher. See [installation and backup policy](docs/UPGRADE_V5_0_3_1.md).

V5.0.3.2 adds selection feedback, collapsed source alternatives and aligned bulk
controls. See [patch notes](docs/UPGRADE_V5_0_3_2.md).

V5.1.1.1 verification: **268 Python tests** and **466 JavaScript assertions**,
including 14 page/report cases and 88 gameplay assertions. The unchanged
V5.1 selectors previously passed 600 simulated rounds. See
[the current validation report](docs/VALIDATION.md) for scope and limits.


### V5.1.2.2 — connecting bar

Shared Spotlight now measures Not connecting → Some connection → Really
connecting. For positions x in [0,1], points are rounded half-up from
max(0, min(12, 6*x + 8*(x - group_mean))). Each round awards 0–24 points;
the maximum is a ceiling, not a target. Equal positions score equally:
0/20/50/80/100% give 0/1/3/5/6 points each. A lone 100% standout receives 12.

The server calculates scores from the four saved integer percentage positions.
Schema 18 retains positions alongside rules-versioned receipts. Upgrade uses
the existing verified pre-upgrade backup and transactional rebuild. Answered
legacy rounds and pending legacy receipts retain their 12-point rules; new
offers use rules version 2. Statistics sum actual awarded points; Overall
continues the monotone support mapping with three points at 50% and one
observation per song. Public Elo remains based on preference matches.

Starting a preview enables Loop previews. Selection follows each preview;
selecting another song while looping switches playback to that song. Selecting
while stopped stays silent. Stop previews stops the loop. Results retain their
finite playback pass, and new connecting receipts retain actual bar locations.


### V5.1.2.3 — longer reveals and Spotlight Stats

Spotlight's result pass now takes 15.2 seconds in Standard or 7.9 seconds in
Quick, including a final pause; Next round skips it at any time. Preview-loop
listening intervals are unchanged.

The Spotlight dashboard follows Standard Vote's established stats layout.
It shows actual points awarded, averages per round and track, round ranges,
zero/full-point outcomes, connection averages and endpoint counts, activity,
coverage, a point histogram, artist/album/tag records, and paged history.
Each record list stops at five; there is no hidden full leaderboard. Mean-point
and connection leaders need at least three observations, and category support
needs five track appearances. Track support adjusts for evidence; category
support pools actual track observations. Connection percentages describe bar
placement, not correctness or the fraction of the 24-point ceiling spent.
Legacy rounds retain their saved scores and have no invented connection values.
No schema or scoring changes are introduced by this patch.
