# V5 database dictionary

**V3 competition database · schema 17 · application V5.1.2.1**

The active default is `data/song_ranker_v3.db`. The schema registry is
[data/schema.sql](../data/schema.sql); this dictionary is derived from it.
There are 33 stored tables, five views, 27 explicit indexes and eight triggers.
IDs/relationships and exact catalogue values survive first transfer; old results
do not. See [UPGRADE_V5.md](UPGRADE_V5.md) for the catalogue whitelist and backup.

## V5.1.2 and V5.1.2.1: same stored Spotlight receipt

The placement line calculates the existing four integer shares totaling 12.
Coordinates are browser-tab drafts and are not stored or sent as additional
result rows. Completed rounds still use `spotlight_allocations` and rules
version 1. Live graphs, rotation timers and point overlays add no tables,
columns, caches or migrations. Stats and Overall read the same saved shares;
selection and reliability weights remain adaptive. Schema stays at 17. Points
reveal only after confirmation; result-order covers/audio and delayed selection
are transient presentation state and create no extra result rows.

## V5.1 subjective mode facts

The five compact mode tables are `judgement_rounds`, `judgement_items`,
`spotlight_allocations`, `vibe_placements` and `vibe_themes`. No seeded results,
duplicated audio/artwork, pair matrix or cached totals are stored. See
[the backend guide](UPGRADE_V5_1.md) for contracts and derived statistics.

Schema 17 removes retired Sound Twins choices, rounds/items, listening samples
and its obsolete table/trigger. All catalogue values and remaining results,
row IDs and sequence high-water marks are preserved. A verified pre-upgrade
backup keeps the original data. JSON/SQL restores use the same migration.
Normal launch migrates the main database; safe launch migrates only its copy.

Safe mode reuses one database per source path. Explicit
`python safe_mode.py --refresh-safe-mode` replaces test data at that same path
from the latest main snapshot. Other marked legacy runs for that source are
pruned after successful adoption; unmarked folders and backups are retained.

All successful decisions are transactionally closed receipts. A browser owner
and answer hash make retries idempotent. Missing song/tag links become NULL;
original keys and short identities preserve the history. Skips do not enter
`mode_exposures` or Overall. New mode listening uses the existing table.

## V5.1.1 pages: unchanged schema and compact writes

The two subjective game pages write through the existing round/answer transactions.
No tables, columns, seed results or cached percentages are added by V5.1.1.
Schema-16 databases receive the selective schema-17 migration. Session-storage
choices are browser-tab drafts, not database evidence; an unconfirmed save
retains the same token, canonical answer and frozen listening sample on retry.

`reports/judgement_page_data.py` uses the read-only stats projections for HTML.
Spotlight's point histogram groups saved allocation rows. Vibe's three heatmaps
count actual placements; track means/spread are filtered and paged without
writing derived values. Reviewed theme denominators include explicit empty
reviews. Removed-song identities and renamed-tag labels remain
historical facts. Reports expose no browser owner hashes or receipt tokens.

The new pages use the existing listening table and `mode_exposures` view.
Global Stats includes these saved rounds in its recent feed; unjudged skips and
unsubmitted drafts are excluded. No activity cache, map table or pair matrix is
stored. See [UPGRADE_V5_1_1.md](UPGRADE_V5_1_1.md) for routes and page behaviour.

## V5.1.1.1 display-only patch

Current schema is 17; calibration 7 is retained. Album links read the current offer's
existing album title/ID; they introduce no duplicated metadata or stored values.
Home/nav/cover-player styling changes add no database writes or migrations.

## Fact ownership

| Area | Authoritative stored facts | Read projections / use |
| --- | --- | --- |
| Catalogue | `songs`, `albums`, `artists`, `genres`, relationship tables, `song_sources`, `song_details` | Public metadata and distinct-song grouping. Preview flags/notes are private Dev fields. |
| Competition | `competition_state` | Generation 3, current start and private migration provenance. Not an old-results import. |
| Preference | Offers, immutable events, corrections, rating seeds/overrides/replay state | Effective history and rebuildable public/mode Elo projections. |
| Trivia / Guesser | Saved questions, choices, grades, field time and challenge runs | Completed accuracy, streaks and reports; pending rows add no result. |
| Tournament | Bracket, entries, match facts and placements | Bracket points and eligible weighted first-round preference events. |
| Shelves | Offered album/track facts and submitted positions | Regraded relative order/placement totals from frozen facts. |
| V5.1 judgements | Five mode tables above | Completed allocations, independent maps, selected themes. |
| Listening | `listening_observations` | Accepted-decision samples with mode/reference, original song key and chosen state. |

## Units and privacy

- `songs.elo_score` and independent ratings start at 1200. Preference influence
  is 1 or 0.5; it is already applied to saved rating changes.
- `song_details.added_at`, competition/listening/source epoch times are seconds
  since Unix epoch. Imported catalogue age is zero; future inserts are timestamped.
- Listening `seconds` is actual measured playback up to answer submission;
  `decision_ms` is elapsed browser question time in milliseconds. Missing rows
  are unknown, not zero. `selected` is nullable for non-pair games.
- The listening reference is the server result ID in that mode. `song_key`
  preserves the original ID after removal; nullable `song_id` links a live song.
- Preview `preview_bad`, `preview_note` and `flagged_at` never appear in public
  catalogue/game/profile payloads. They do appear in authenticated analysis
  downloads and full database exports/backups.
- Ordinary stored match counters and raw event totals remain distinct from
  weighted effective appearances. Do not multiply saved Elo deltas by influence again.
- `competition_state.migration_report` is JSON with source schema/name, archive
  name/hash, transferred counts and reset scope. It contains no old match results.

## Stored tables

The following are exact column names/types/defaults. Constraints and foreign-key
actions are authoritative in the schema. Empty default means no SQL default.

### albums

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `title` | TEXT | Not null |  |
| `cover_url` | TEXT | Nullable |  |
| `release_date` | TEXT | Nullable |  |

### artists

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `name` | TEXT | Not null |  |
| `cover_url` | TEXT | Nullable |  |

### genres

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `name` | TEXT | Not null |  |
| `description` | TEXT | Not null | '' |

### songs

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `title` | TEXT | Not null |  |
| `album_id` | INTEGER | Nullable |  |
| `audio_url` | TEXT | Nullable |  |
| `elo_score` | REAL | Nullable | 1200 |
| `matches_played` | INTEGER | Nullable | 0 |
| `highest_elo` | REAL | Nullable | 1200 |
| `highest_rank` | INTEGER | Nullable | 9999 |
| `track_number` | INTEGER | Nullable |  |
| `tournament_wins` | INTEGER | Nullable | 0 |
| `release_date` | TEXT | Nullable |  |
| `release_date_origin` | TEXT | Nullable |  |

Foreign keys: `album_id` → `albums.id` (delete NO ACTION).

### song_sources

One current source per song, enforced by the unique `song_sources_song` index.
Relinking updates the existing row; older observations are not retained here.
`snapshot` is either compact JSON or lossless `srz1:` compressed text. Use
`source_storage.unpack_source` or the decoded Dev analysis export to inspect it.
Every field of the current observation, including complete URLs, is retained.

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `song_id` | INTEGER | Not null |  |
| `provider` | TEXT | Not null | 'apple' |
| `external_id` | TEXT | Not null |  |
| `storefront` | TEXT | Not null |  |
| `collection_id` | TEXT | Nullable |  |
| `snapshot` | TEXT | Not null |  |
| `observed_at` | REAL | Not null |  |

Foreign keys: `song_id` → `songs.id` (delete CASCADE).

### song_artists

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `artist_id` | INTEGER | Primary key 2 |  |

Foreign keys: `artist_id` → `artists.id` (delete NO ACTION); `song_id` → `songs.id` (delete NO ACTION).

### song_genres

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `genre_id` | INTEGER | Primary key 2 |  |

Foreign keys: `genre_id` → `genres.id` (delete NO ACTION); `song_id` → `songs.id` (delete NO ACTION).

### preference_events

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `winner_id` | INTEGER | Nullable |  |
| `loser_id` | INTEGER | Nullable |  |
| `mode` | TEXT | Not null | 'standard' |
| `created_at` | DATETIME | Nullable |  |
| `winner_before` | REAL | Nullable |  |
| `winner_after` | REAL | Nullable |  |
| `loser_before` | REAL | Nullable |  |
| `loser_after` | REAL | Nullable |  |
| `offer_token` | TEXT | Nullable |  |
| `origin` | TEXT | Not null | 'legacy' |
| `rules_version` | INTEGER | Not null | 0 |
| `winner_snapshot` | TEXT | Not null | '{}' |
| `loser_snapshot` | TEXT | Not null | '{}' |
| `rating_weight` | REAL | Not null | 1 |
| `tournament_id` | INTEGER | Nullable |  |
| `tournament_match_id` | INTEGER | Nullable |  |

Foreign keys: `offer_token` → `preference_offers.token` (delete SET NULL); `loser_id` → `songs.id` (delete SET NULL); `winner_id` → `songs.id` (delete SET NULL).

### tournaments

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `size` | INTEGER | Not null |  |
| `scope_type` | TEXT | Not null |  |
| `scope_id` | INTEGER | Nullable |  |
| `champion_id` | INTEGER | Nullable |  |
| `timestamp` | DATETIME | Nullable | CURRENT_TIMESTAMP |
| `status` | TEXT | Not null | 'completed' |
| `created_at` | DATETIME | Nullable |  |
| `updated_at` | DATETIME | Nullable |  |
| `completed_at` | DATETIME | Nullable |  |
| `current_round` | INTEGER | Not null | 1 |
| `points_version` | INTEGER | Not null | 1 |
| `is_blind` | BOOLEAN | Not null | 0 |
| `playoff_enabled` | INTEGER | Not null | 0 |
| `runner_up_id` | INTEGER | Nullable |  |
| `third_place_id` | INTEGER | Nullable |  |
| `fourth_place_id` | INTEGER | Nullable |  |
| `elo_policy_version` | INTEGER | Not null | 0 |
| `elo_weight` | REAL | Not null | 0 |

Foreign keys: `champion_id` → `songs.id` (delete NO ACTION); `fourth_place_id` → `songs.id` (delete NO ACTION); `third_place_id` → `songs.id` (delete NO ACTION); `runner_up_id` → `songs.id` (delete NO ACTION).

### global_stats

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `key` | TEXT | Primary key 1 |  |
| `value` | INTEGER | Nullable |  |

### tournament_entries

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `tournament_id` | INTEGER | Primary key 1 |  |
| `song_id` | INTEGER | Primary key 2 |  |
| `seed` | INTEGER | Not null |  |

Foreign keys: `song_id` → `songs.id` (delete NO ACTION); `tournament_id` → `tournaments.id` (delete CASCADE).

### tournament_matches

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `tournament_id` | INTEGER | Not null |  |
| `round_number` | INTEGER | Not null |  |
| `match_number` | INTEGER | Not null |  |
| `song1_id` | INTEGER | Nullable |  |
| `song2_id` | INTEGER | Nullable |  |
| `winner_id` | INTEGER | Nullable |  |
| `loser_id` | INTEGER | Nullable |  |
| `status` | TEXT | Not null | 'pending' |
| `points_awarded` | REAL | Not null | 0 |
| `played_at` | DATETIME | Nullable |  |
| `match_type` | TEXT | Not null | 'bracket' |

Foreign keys: `loser_id` → `songs.id` (delete NO ACTION); `winner_id` → `songs.id` (delete NO ACTION); `song2_id` → `songs.id` (delete NO ACTION); `song1_id` → `songs.id` (delete NO ACTION); `tournament_id` → `tournaments.id` (delete CASCADE).

### trivia_adjustments

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `new_attempts_delta` | INTEGER | Not null | 0 |
| `title_correct_delta` | INTEGER | Not null | 0 |
| `artist_correct_delta` | INTEGER | Not null | 0 |
| `album_attempts_delta` | INTEGER | Not null | 0 |
| `album_correct_delta` | INTEGER | Not null | 0 |

Foreign keys: `song_id` → `songs.id` (delete CASCADE).

### challenge_runs

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `owner` | TEXT | Not null |  |
| `mode` | TEXT | Not null |  |
| `rules_version` | INTEGER | Not null |  |
| `created_at` | REAL | Not null |  |
| `ended_at` | REAL | Nullable |  |

### trivia_rounds

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `token` | TEXT | Not null |  |
| `song_id` | INTEGER | Nullable |  |
| `album_available` | INTEGER | Not null |  |
| `started_at` | REAL | Nullable |  |
| `paused_at` | REAL | Nullable |  |
| `paused_seconds` | REAL | Not null | 0 |
| `completed_at` | REAL | Nullable |  |
| `title_correct` | INTEGER | Nullable |  |
| `artist_correct` | INTEGER | Nullable |  |
| `album_correct` | INTEGER | Nullable |  |
| `title_seconds` | REAL | Nullable |  |
| `artist_seconds` | REAL | Nullable |  |
| `album_seconds` | REAL | Nullable |  |
| `user_score_after` | REAL | Nullable |  |
| `streak_after` | INTEGER | Nullable |  |
| `run_id` | INTEGER | Nullable |  |
| `rules_version` | INTEGER | Not null | 1 |
| `streak_before` | INTEGER | Nullable |  |
| `streak_rule` | TEXT | Nullable |  |
| `streak_passed` | INTEGER | Nullable |  |
| `answer_snapshot` | TEXT | Nullable |  |

Foreign keys: `run_id` → `challenge_runs.id` (delete NO ACTION); `song_id` → `songs.id` (delete SET NULL).

### elo_guess_rounds

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `token` | TEXT | Not null |  |
| `song1_id` | INTEGER | Nullable |  |
| `song2_id` | INTEGER | Nullable |  |
| `elo1` | REAL | Not null |  |
| `elo2` | REAL | Not null |  |
| `started_at` | REAL | Not null |  |
| `completed_at` | REAL | Nullable |  |
| `chosen_slot` | INTEGER | Nullable |  |
| `run_id` | INTEGER | Nullable |  |
| `rules_version` | INTEGER | Not null | 1 |
| `streak_before` | INTEGER | Nullable |  |
| `target_quantile` | REAL | Nullable |  |
| `streak_after` | INTEGER | Nullable |  |
| `user_score_after` | REAL | Nullable |  |

Foreign keys: `run_id` → `challenge_runs.id` (delete NO ACTION); `song2_id` → `songs.id` (delete SET NULL); `song1_id` → `songs.id` (delete SET NULL).

### album_shelf_rounds

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `token` | TEXT | Not null |  |
| `started_at` | REAL | Not null |  |
| `completed_at` | REAL | Nullable |  |
| `rules_version` | INTEGER | Not null | 1 |

### album_shelf_items

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `round_id` | INTEGER | Primary key 1 |  |
| `item_slot` | INTEGER | Primary key 2 |  |
| `song_id` | INTEGER | Nullable |  |
| `album_id` | INTEGER | Nullable |  |
| `album_slot` | INTEGER | Not null |  |
| `track_number` | INTEGER | Not null |  |
| `answer_slot` | INTEGER | Nullable |  |
| `answer_position` | INTEGER | Nullable |  |

Foreign keys: `album_id` → `albums.id` (delete SET NULL); `song_id` → `songs.id` (delete SET NULL); `round_id` → `album_shelf_rounds.id` (delete CASCADE).

### preference_offers

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `token` | TEXT | Primary key 1 |  |
| `owner_hash` | TEXT | Not null |  |
| `song1_id` | INTEGER | Not null |  |
| `song2_id` | INTEGER | Not null |  |
| `mode` | TEXT | Not null |  |
| `origin` | TEXT | Not null | 'ordinary' |
| `rules_version` | INTEGER | Not null |  |
| `status` | TEXT | Not null | 'open' |
| `created_at` | DATETIME | Not null | CURRENT_TIMESTAMP |
| `closed_at` | DATETIME | Nullable |  |
| `song1_snapshot` | TEXT | Nullable |  |
| `song2_snapshot` | TEXT | Nullable |  |

### preference_corrections

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `event_id` | INTEGER | Not null |  |
| `request_token` | TEXT | Not null |  |
| `action` | TEXT | Not null |  |
| `winner_id` | INTEGER | Not null |  |
| `loser_id` | INTEGER | Not null |  |
| `mode` | TEXT | Not null |  |
| `active` | INTEGER | Not null |  |
| `reason` | TEXT | Not null | '' |
| `created_at` | DATETIME | Not null | CURRENT_TIMESTAMP |

Foreign keys: `event_id` → `preference_events.id` (delete CASCADE).

### preference_rating_projection

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `event_id` | INTEGER | Primary key 1 |  |
| `winner_before` | REAL | Nullable |  |
| `winner_after` | REAL | Nullable |  |
| `loser_before` | REAL | Nullable |  |
| `loser_after` | REAL | Nullable |  |

Foreign keys: `event_id` → `preference_events.id` (delete CASCADE).

### preference_rating_seeds

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `elo` | REAL | Not null |  |
| `matches` | INTEGER | Not null |  |
| `highest_elo` | REAL | Not null |  |
| `highest_rank` | INTEGER | Not null |  |

Foreign keys: `song_id` → `songs.id` (delete CASCADE).

### preference_replay_state

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `cutoff_event_id` | INTEGER | Not null |  |
| `legacy_boundary` | INTEGER | Not null |  |
| `baseline_kind` | TEXT | Not null |  |
| `rules_version` | INTEGER | Not null | 1 |

### preference_rating_overrides

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `request_token` | TEXT | Not null |  |
| `song_id` | INTEGER | Nullable |  |
| `song_snapshot` | TEXT | Not null |  |
| `after_event_id` | INTEGER | Not null |  |
| `previous_elo` | REAL | Not null |  |
| `new_elo` | REAL | Not null |  |
| `reason` | TEXT | Not null | '' |
| `created_at` | DATETIME | Not null | CURRENT_TIMESTAMP |

Foreign keys: `song_id` → `songs.id` (delete SET NULL).

### preference_mode_ratings

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `mode` | TEXT | Primary key 2 |  |
| `elo` | REAL | Not null | 1200 |
| `matches` | INTEGER | Not null | 0 |
| `tournament_matches` | INTEGER | Not null | 0 |

Foreign keys: `song_id` → `songs.id` (delete CASCADE).

### song_details

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `song_id` | INTEGER | Primary key 1 |  |
| `added_at` | REAL | Not null | unixepoch() |
| `preview_bad` | INTEGER | Not null | 0 |
| `preview_note` | TEXT | Not null | '' |
| `flagged_at` | REAL | Nullable |  |

Foreign keys: `song_id` → `songs.id` (delete CASCADE).

### competition_state

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `generation` | INTEGER | Not null |  |
| `started_at` | REAL | Not null |  |
| `migration_report` | TEXT | Not null | '{}' |

### listening_observations

| Column | SQLite type | Required / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `mode` | TEXT | Not null |  |
| `reference` | TEXT | Not null |  |
| `song_key` | INTEGER | Not null |  |
| `song_id` | INTEGER | Nullable |  |
| `seconds` | REAL | Not null |  |
| `decision_ms` | REAL | Not null |  |
| `selected` | INTEGER | Nullable |  |
| `recorded_at` | REAL | Not null |  |

Foreign keys: `song_id` → `songs.id` (delete SET NULL).

## Derived views

| View | Purpose |
| --- | --- | --- |
| `trivia_stats` | Completed available-field totals plus explicit sparse adjustments. |
| `preference_effective` | Effective active/voided/corrected preference state, source, visibility and influence. |
| `history` | Active corrected ordinary preference history with projected snapshots. |
| `mode_exposures` | Canonical completed per-mode exposures; preference first-round weights are combined by read adapters. |
| `shelf_album_exposures` | Album appearances in completed Shelves rounds. |

## Maintenance

Use the authenticated full export or the offline tools described in
[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md#hosting-and-recovery). A full V3 rebuild
reconciles every stored value, implicit row ID, sequence and supported extension.
The V2 → V3 catalogue transfer is a separate, deliberately resetting operation.
Do not hand-edit grading tables or restore an old archive over the active V3 file.


V5.0.3.1 backup policy: requested and website-shutdown snapshots share three
`rolling_*.db` slots. Ordinary edits create none. Migration archives and existing
backups remain separate. See [backup and stop workflow](UPGRADE_V5_0_3_1.md).

## V5.1 table columns

Constraints and foreign-key actions are authoritative in `data/schema.sql`.
`identity` is a short display fallback (at most 512 characters), not a second
copy of artwork or preview metadata. Selected theme fallback labels are at most
160 characters. Owner hashes and receipt tokens are not public history fields.

### judgement_rounds

| Column | Type | Null / key | Default |
| --- | --- | --- | --- |
| `id` | INTEGER | Primary key 1 |  |
| `token` | TEXT | Not null |  |
| `owner_hash` | TEXT | Not null |  |
| `mode` | TEXT | Not null |  |
| `rules_version` | INTEGER | Not null | 1 |
| `status` | TEXT | Not null | 'open' |
| `created_at` | REAL | Not null |  |
| `closed_at` | REAL | Nullable |  |
| `answer_hash` | TEXT | Nullable |  |
| `themes_reviewed` | INTEGER | Not null | 0 |

### judgement_items

| Column | Type | Null / key | Default |
| --- | --- | --- | --- |
| `round_id` | INTEGER | Primary key 1 |  |
| `slot` | INTEGER | Primary key 2 |  |
| `song_key` | INTEGER | Not null |  |
| `song_id` | INTEGER | Nullable |  |
| `identity` | TEXT | Not null |  |

### spotlight_allocations

| Column | Type | Null / key | Default |
| --- | --- | --- | --- |
| `round_id` | INTEGER | Primary key 1 |  |
| `slot` | INTEGER | Primary key 2 |  |
| `points` | INTEGER | Not null |  |

### vibe_placements

| Column | Type | Null / key | Default |
| --- | --- | --- | --- |
| `round_id` | INTEGER | Primary key 1 |  |
| `map_key` | TEXT | Primary key 2 |  |
| `x` | INTEGER | Not null |  |
| `y` | INTEGER | Not null |  |

### vibe_themes

| Column | Type | Null / key | Default |
| --- | --- | --- | --- |
| `round_id` | INTEGER | Primary key 1 |  |
| `tag_key` | INTEGER | Primary key 2 |  |
| `tag_id` | INTEGER | Nullable |  |
| `label` | TEXT | Not null |  |
