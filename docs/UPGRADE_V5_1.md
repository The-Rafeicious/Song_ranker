# Subjective mode backends and safe testing

Current for V5.1.2. Shared Spotlight and Vibe Map are playable and have
[dedicated pages](UPGRADE_V5_1_1.md). For installation, retired files and the
schema-17 migration see [V5.1.1.2](UPGRADE_V5_1_1_2.md).

## Safe launch

Stop the app, then run `python safe_mode.py` or `python main.py --safe-mode`.
The first launch snapshots the main database through SQLite mode=ro, including
committed WAL data. Later launches reuse the same isolated database; browser
refresh resumes that copy too. All app writes, backups and settings stay beneath
its safe directory. Managed writes reject the main DB, aliases and destinations
outside that directory. App connections reject attached databases. Git is disabled.

To pick up new real songs, stop safe mode, add songs through a normal launch,
stop that app, then run `python safe_mode.py --refresh-safe-mode`. This clears
safe test results and replaces the same test database with the latest main
snapshot. A failed copy leaves the old safe database intact. The first updated
launch adopts the latest marked old test run and removes only other marked
runs for that same source. Unmarked folders and backups are preserved.

`SONG_RANKER_SAFE_MODE=1` enables safe mode. `SONG_RANKER_SAFE_DIR` chooses its
parent directory. The normal launcher coordinates live/safe launches with a
process lock for the same main path. Stop the app before switching. These guards
protect managed app writes; unrelated programs retain their own file access.
Use one WSGI worker. Flags do not switch databases during a running session.

`python tools/test_v51_backend.py` checks one synthetic decision per current
subjective mode in a disposable child copy. It leaves both the main database
and persistent safe progress unchanged. Stop the app before running this tool.

## Shared Spotlight

The [V5.1.2 placement line](UPGRADE_V5_1_2.md) calculates the existing
allocation payload from relative distances; no coordinates are stored.
Four distinct songs share **12 whole points**. Ties and zeroes are legitimate;
an unjudged skip is a separate result. The colour is **blue-violet `#7F91FF`**,
farther from Blind's mint `#55D6C2` than the original cyan proposal.

Statistics show points per completed offer, zero-share counts, collection
coverage, listening and history. Evidence strength changes with the current
population's exposure; it is not a fixed minimum-play gate.

For Overall, a song's support in one round is:

`3 * points / (12 + 2 * points)`

Equal three-point shares give 0.5, zero gives 0, and all twelve gives 1. Strong
allocations above six points remain distinct. A round contributes **one
observation per song**, not a collection of invented head-to-head votes.
Public Elo remains based on actual matches. The complete four-song offer is
retained, since allocations depend on which other songs appeared.

## Vibe Map: several tables, not one mood label

Vibe Map keeps the **vivid red `#FF3B3B`** colour. Its three independent 5-by-5 tables
draw on your existing tags and descriptions:

| Table | X axis, 0 to 4 | Y axis, 0 to 4 | Existing tag inspiration |
| --- | --- | --- | --- |
| Mood and energy | Heavy/dark to hopeful/bright | Calm/slow to driving/upbeat | sad, melancholic, hope, angry, slow, up-beat, dance, sad-pop |
| Sound and delivery | Acoustic/organic to electronic/produced | Restrained/soft to powerful/intense | acoustic, piano-ballad, electronic, dark-pop, low-pop, duet |
| Build and hook | Steady/immediate to big gradual build | Subtle/understated to instant earworm | build-up, catchy, chorus, bridge |

Place **one, two or three** tables for the heard preview. Omitted tables are
unknown; they are never recorded as zero or centre. The next offer suggests
the tables least reviewed for that song. Selection counts a one-table review
as one third of a complete three-table review, allowing depth to catch up.
A build or bridge that the preview does not contain can be left unanswered.

Optional annotations use up to **eight current catalogue tags**, including
relationship, breakup, nostalgia and other topics. Tag names and descriptions
come from the database on request, including tags you add later. The game
does not rename tags or change existing song-tag memberships. Omitted `themes`
means unasked; `themes: []` means reviewed with none selected.

Statistics provide a separate heatmap and per-song mean/spread/evidence for
each table, plus theme selection counts with reviewed-round denominators.
These are descriptions, not accuracy or quality grades.

## Adaptive weights and Overall

Both selectors reuse the existing mean-based exposure policy, uniform
exploration floor and fading new-song support. Their populations, means and
opportunities are read from the current database, so additions and new results
adjust the weights automatically. Recent repeats and Spotlight artist repeats
get soft penalties. Selection diagnostics expose **base probabilities**;
slate-specific diversity adjustments are applied later.

Overall remains **five game families**. Shared Spotlight belongs to the
preference/voting family, rather than getting a second correlated family.
The nominal policy below sums to 100; actual allocations adapt to participation
and depth and retain the family cap:

| Family / stream | Nominal share |
| --- | ---: |
| Preference: public Elo | 4 |
| Preference: non-blind voting | 3 |
| Preference: blind voting | 3 |
| Preference: Shared Spotlight | 10 |
| Recognisability | 20 |
| Tournament | 20 |
| Elo Guesser | 20 |
| Album Shelves | 20 |

The preference family's support follows its stronger supported view, without
double-counting correlated depth. Within the family, supported streams share
its allocation adaptively. When Spotlight is unplayed, its weight is zero and
the original voting proportions and scores are retained. Unplayed eligible
songs still have neutral priors; unplayable inputs are omitted.

Vibe Map is included in Overall's **descriptive coverage**
and adaptive support reporting, with zero composite-quality weight. A dark
song or an unusual song is not penalised, and no invented correctness score
is awarded. API clients receive these separately in `context_modes` and
`summary.descriptive_modes`. Their judgments do not alter a song's composite
until a meaningful quality/preference input is explicitly designed.

Calibration is version 7 and derives from each current snapshot. There is no
nightly recalculation, fixed played-song target or stored stale percentage.

## Backend API

The existing local-network and same-origin JSON protections apply. Offers and
receipts belong to the requesting browser session. Results are transactional
and idempotent: the same answer returns its receipt; a conflicting retry is 409.

| Operation | Endpoint |
| --- | --- |
| Mode definitions, colours, maps and current tags | `GET /api/mode-updates` |
| Launch identity | `GET /api/runtime-mode` |
| Request/resume offer, body `{}` | `POST /api/shared-spotlight/round` |
| Save Spotlight | `POST /api/shared-spotlight/answer` |
| Request/resume Vibe offer | `POST /api/vibe-map/round` |
| Save Vibe | `POST /api/vibe-map/answer` |
| Mode stats and paged history | `GET /api/<mode>/stats?page=1&page_size=20` |
| Authenticated selector diagnostics | `GET /api/dev/mode-updates/selection/<mode>` |

`<mode>` accepts the descriptive slug above or `spotlight` or `vibe`.
History page size is 1-50. Public history omits answer tokens and owner hashes.

Answer examples, with the server's real token substituted:

```json
{"token":"...","rules_version":1,"allocations":[5,4,2,1]}
```

```json
{"token":"...","rules_version":1,"maps":[{"map":"mood","x":1,"y":4},{"map":"craft","x":3,"y":2}],"themes":[3,7]}
```

```json
{"token":"...","rules_version":1,"choice":2}
```

Both modes accept
`{"token":"...","rules_version":1,"skip":true}`. A skip cannot also contain
an answer. Optional `listening` uses the existing version-1 measurement format;
partial, malformed or absent measurements remain unknown. Boolean/fractional
coordinates, duplicate tags/maps, wrong owners, unsupported versions and
out-of-offer choices are rejected without partial writes.

Authenticated resets accept `/api/dev/reset-history/spotlight`, `/vibe`,
with `confirmation` equal to `RESET SPOTLIGHT` or `RESET VIBE`. They clear that mode's facts/listening only. The existing full
competition reset includes both modes. Backup/export/recovery includes them too.

## Compact storage

Five tables hold reusable round receipts, offered song identities, point
allocations, chosen maps and selected themes. There
are no added counters on every song and no prefilled result rows. A short
identity fallback survives song removal; assets and source snapshots are not
duplicated. Omitted maps/themes consume no rows. Bounded pending/skipped records
expire after seven days; accepted judgments are retained.

Indexes cover song lookups, current offers, completed history and abandoned
offer cleanup. New listening samples reuse the existing table. Optional
VACUUM is deferred when it could renumber sparse implicit row IDs, preserving
extension data rather than trading correctness for a smaller file.

See [DATABASE.md](DATABASE.md), [VALIDATION.md](VALIDATION.md) and
[the release log](../update_logs/V5_1_UPDATE.md) for schema and verification details.
