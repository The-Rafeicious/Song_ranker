# Library Challenge — standalone mode preview

This is a design and interaction proposal, not a Song Ranker update. The V3.2.7 app, its database and the earlier V3.3 ideas are unchanged. Nothing in this folder connects to Flask, SQLite or Apple.

## Open it

Extract the whole ZIP, then open **`dist/index.html`** in your browser. Keep the `assets` folder beside the HTML files. No installation, server or internet connection is needed.

| File | What to try |
| --- | --- |
| `dist/index.html` | Mode landing page; start a mixed test or an individual round. |
| `dist/play.html` | Play all three rounds. Tick “Add an artist round” on the landing page for a fourth. |
| `dist/stats.html` | Sample overview, round accuracy, partial credit, weak spots and history. |
| `dist/rankings.html` | Most/least known songs, artists and albums, with a minimum appearance count. |
| `dist/profile.html` | Song, artist and album layouts showing where this mode’s stats could sit. |
| `proposed_schema.sql` | Future table proposal only. Do not run this against your current database. |

The library, artwork and historical figures are fictional. Sorting, grading, partial credit, score, streak, progress, answer reveals, restart and navigation work. A preview run lives in memory; refreshing clears it. Stats pages deliberately keep their sample records and do not pretend to save your run. The demo questions are fixed so they are easy to compare across designs. There is no audio playback in this concept.

Drag tracks to a shelf or onto another track to insert before it. You can also choose an album from each track’s selector, use its up/down buttons, or focus a track and press the arrow keys. Release-order cards have the same drag and arrow controls.

## Identity and place in the site

**Library Challenge** uses electric cyan, `#68dfff`. It stays separate from standard orange, blind mint, trivia gold and tournament pink. Songs remain green, artists blue and albums purple. The preview carries across the charcoal panels, multicolour wordmark, centered titles, side glows, rounded controls and larger text. Artist portraits stay circular.

If adopted, add it to Game Modes and its overview to Stats. Knowledge rankings sit within this mode’s navigation, rather than replacing Elo rankings or the existing mode rankings. Profiles get one new cyan panel above recognisability/tournament records. Entity links retain their existing colours. On the home page it would get a cyan mode card, not another explanatory intro box.

## Run format

The default mixed test has one round of each core type: Elo instinct → Album shelves → Release order. Artist connections is an optional fourth round. Individual practice is available for each type. A longer test could repeat this cycle, but keep its length chosen before starting so results are comparable.

Each scored round is worth **0–1 point**, regardless of how many items it contains. A three-round test is therefore out of 3; with artists it is out of 4. Partial credit is calculated before rounding and the UI displays two decimals. A perfect round increases the 🔥 perfect streak. A partial or wrong answer resets it. A cancelled/ineligible question is replaced without costing a point or changing the streak.

Show score and feedback after checking, then let the user advance. This is a knowledge test, not a timed speed test. There is no penalty for taking longer, no automatic audio and no automatic submit. Hide answer-bearing numbers until checking: Elo in the first round, album/track number on unsorted tracks in the second, and dates in the third.

### 1. Elo instinct

Two songs face off. Choose the one with the higher current Elo. Show song names, artists, albums and artwork, but no Elo, peak Elo, rank, wins or other numerical clues before the answer. Reveal both frozen ratings after the pick.

Correct = 1 point; wrong = 0. Freeze `songs.elo_score` when the round starts. An Elo change elsewhere while the question is open must not change the answer. Avoid ties or tiny gaps: initially choose pairs roughly 50–250 Elo apart, with some easier wider gaps. Keep randomness, favour tracks seen less in this challenge and avoid repeating the same pair in a run. If the eligible library is too small, widen the range; never fabricate a comparison.

This is a prediction about rankings, **not a vote**. It never updates Elo, matches played, win rates or ordinary match history.

### 2. Album shelves

Give two or three proper albums and a shuffled pool of two or three tracks from each. The user assigns every track to a shelf, then sorts the tracks within it. Use multiple albums by the same artist where possible, so the artist name does not give the whole answer away. Show the candidate album covers, but do not show an unsorted song’s cover, album or track number.

For the whole round:

```text
album credit = tracks assigned to their correct album / tracks tested
order credit = correct within-album pair comparisons / all eligible within-album pairs
points       = 0.60 × album credit + 0.40 × order credit
```

An order comparison earns credit only if **both** tracks are on their correct shelf and their relative order is right. This prevents gaining free order points by dumping difficult tracks elsewhere. Comparing relative positions avoids penalising every later track because one item was misplaced. If no ordering pairs exist, membership is the only applicable component; ideally do not generate that question in the first place.

Keep real album track numbers. A collected album with tracks 1, 4 and 8 is valid: sort them in that order, and reveal 1, 4, 8 afterwards. Do not renumber them 1, 2, 3. Exclude ` - Single` releases from this round, even if their tracks remain eligible elsewhere. Also exclude missing/duplicate/invalid track positions. If disc numbers are not modelled, do not guess the sequence of an ambiguous multi-disc album.

The preview offers two or three shelves. Changing shelf count starts that question afresh. Profile buttons include the chosen record as a focus, with other shelves as distractors. For an artist with too few albums, the preview uses other artists’ albums; a real implementation should offer that choice explicitly or mark this round unavailable. A separate single-album practice variant could test only track order and award no free membership points.

### 3. Release order

Give four to six songs and ask for oldest → newest. Correct year order should still count when two releases from the same year are swapped.

```text
year credit = correctly ordered pairs from different years / all different-year pairs
date credit = correctly ordered pairs with distinct dates / all distinct-date pairs
points      = 0.60 × year credit + 0.40 × date credit
```

Equal years do not create a year comparison. Equal full dates do not create a date comparison: either order is valid. If one component has no eligible comparisons, give the other component the full weight. If neither applies, replace the question without scoring it. Duplicate IDs or invented/missing items make an answer invalid.

Example: everything is in the right year order, but two 2021 releases are swapped. The year component is still 100%. Only their relevant exact-date comparison is missed. This produces a useful partial result rather than zeroing the whole sequence.

**Date meaning matters.** Your current schema stores `albums.release_date`, not the original first-release date of every song. The preview uses the date of that song’s album/release in the library. This includes single releases when the date is known; singles do not need to be excluded from this round. A remastered or deluxe edition might have a different release date from the original recording. Do not silently call it the song’s first release.

The first implementation should label the challenge “Library release order”, freeze both the chosen date and its source in the round, and skip unknown dates. Avoid filling absent dates with January 1 or sorting an unknown date as the oldest. If only a year is known, compare its year, not an invented day. The supplied playable example uses complete ISO dates; year-only metadata support is part of the proposed backend, not simulated here.

### 4. Optional: Artist connections

One song title, four artist portraits. Select everyone actually credited on it. Hide its album cover, album title and artist metadata. Use the existing `song_artists` relationships, including collaborations. Prefer titles without obvious featured-artist clues. Keep the question about stored credits, not about an assumed lead artist or a musician’s wider biography.

```text
points = correctly selected artists / (credited artists ∪ selected artists)
```

For a song credited to Juniper and Paper Planes: choosing both earns 1; choosing just Juniper earns 0.5; choosing those two plus North Coast earns 2/3. Selecting everything never gives full marks. The preview uses “Open Windows” as a working example. This is the artist idea I would start with because it uses data you already have.

## Stats and rankings

Keep a **knowledge score**, defined as `100 × sum(unrounded round credits) / scored rounds`. Also show completed tests, perfect rounds, partial rounds, best perfect streak and best run. Compare best runs within their preset/length; do not let a single 1/1 practice result replace a 4-round mixed record. Show the denominator and optionally a percentage beside every run score.

The preview overview adds album-membership versus track-order accuracy and year-order versus exact-date accuracy. These component statistics come from actual successful comparisons divided by eligible comparisons, not an average of rounded screen percentages. Confused album pairs, reversed track pairs and mixed-up same-year releases can be derived from saved answers.

Knowledge rankings have most/least known views, up to 20 entries, minimum 5 appearances, and the sample count beside the percentage. At first use one combined view with per-round breakdowns on the profile; a later filter can compare one round type. A track that has never been tested is **unrated**, not 0%. A global combined score can mask a weak sub-mode, so always retain the component breakdown.

For entity-level knowledge, derive one credit per tested song per round:

- Elo: give both compared songs the correctness of that comparison.
- Album shelves: the song’s membership result plus the fraction of eligible order pairs involving it. Use the same 60/40 split; omit unavailable components.
- Timeline: the song’s year/date comparison results, using 60/40 and excluding ties.
- Artist connections: the selected-credit result belongs to the tested song.

An album’s record aggregates its tested songs. An artist’s record aggregates distinct song appearances linked to that artist. A collaboration contributes once to each credited artist, and never twice within one artist’s result. Label these as knowledge of their songs, rather than saying an album or artist “won”. It is fine for these derived entity averages to differ from the equal-weight whole-round score.

On global stats add a compact cyan summary linking to the detailed overview. On song/album/artist pages add the cyan record panel shown here. Search results could show a small knowledge percentage **only after enough attempts**, alongside existing Elo and achievements; do not replace championship badges. Tags can scope a test using `song_genres`, but do not need a new tag attribute.

The sample pages show integration and approximate illustrative records. Existing Elo/trivia/tournament examples are presentation placeholders, not copied from your personal database.

## Proposed database changes

**Two new tables; no mandatory additions to songs, albums, artists or tags.** See `proposed_schema.sql`. It is documentation, not a migration or executable app upgrade.

| Table / attribute | Purpose |
| --- | --- |
| `knowledge_runs.id` | Identifies a test. |
| `knowledge_runs.started_at`, `completed_at` | Run timing, stored as UTC epoch seconds. |
| `knowledge_runs.status` | Active, completed or abandoned. |
| `knowledge_runs.rules_version` | Allows old questions to retain their grading rules. |
| `knowledge_runs.rounds_planned` | Fixes the test’s intended length. |
| `knowledge_runs.context_json` | Optional album/artist/song/tag scope and selected round preset. |
| `knowledge_rounds.run_id`, `ordinal` | Parent run and unique position in that run. |
| `knowledge_rounds.kind` | Elo, albums, timeline or artists. |
| `knowledge_rounds.created_at`, `answered_at` | Round timing. |
| `knowledge_rounds.question_json` | Minimal frozen answer facts and candidate IDs. |
| `knowledge_rounds.answer_json` | Submitted choice/order/artist set; null until answered. |

Different rounds have different shapes, so two compact JSON payloads per round keep this lean. The snapshot is necessary historical data, not an audit log: Elo and metadata can change after the test. Do not copy artwork URLs, audio URLs, current titles, descriptions, running totals, precomputed percentages or full library rows into it. Load current display metadata by ID.

Illustrative frozen question payloads:

```json
{"kind":"elo","tracks":[{"song_id":1,"elo":1394},{"song_id":8,"elo":1458}]}
{"kind":"albums","album_ids":[1,2,3],"tracks":[{"song_id":1,"album_id":1,"track_number":1},{"song_id":2,"album_id":1,"track_number":4}]}
{"kind":"timeline","tracks":[{"song_id":1,"date":"2018-09-14","precision":"day","source":"album_release","album_id":1}]}
{"kind":"artists","song_id":16,"artist_choices":[1,2,3,4],"credited_artist_ids":[1,3]}
```

These show payload shapes, not complete album/timeline questions. Avoid duplicating `kind` inside actual JSON because the SQL row already stores it. Answer payloads can be `{ "song_id": 8 }`, `{ "shelves": { "1": [1,2], "2": [3,4] } }`, `{ "order": [1,13,3,8,11] }` or `{ "artist_ids": [1,3] }`.

Entity IDs inside JSON do not have SQLite foreign keys. The backend must validate them and the payload structure before creating a round. Historical frozen facts remain usable after a record is deleted; its display should say “Deleted track/album/artist”. Validate IDs against the frozen candidate set when checking, not against a newly changed catalogue. The relational run→round foreign key does enforce deletion of a run’s rounds. No user table is needed for a single-user local app.

Derive scores, best runs, streaks and profile aggregates from the two tables using a shared versioned grader. For this local library, Python aggregation over loaded round payloads is adequate; do not require SQLite JSON extensions just to read the mode history. Start without persistent summary tables. Add only a cache if measured performance warrants it, and make it rebuildable from rounds.

### Optional future release metadata

The core preview needs **no new attributes**. If you later want original song release order instead of the library’s album date, consider these nullable song fields:

| Optional field | Meaning |
| --- | --- |
| `songs.first_release_date` | Verified original date (`YYYY-MM-DD`), or year (`YYYY`) if that is all you know. |
| `songs.first_release_precision` | `day` or `year`; must agree with the stored value. |
| `songs.first_release_source` | Provenance such as a manually verified source reference. |

Do not automatically fill these from a deluxe album’s collection date, and do not mix original dates with album dates in a test without an explicit, consistent rule. A future selector would choose the date policy for the entire run. These optional columns are intentionally absent from the supplied SQL proposal.

## Safe implementation outline if you choose it later

1. Back up the database and migrate only the two proposed tables in a new versioned migration. Use parameterised statements and enable foreign keys on every connection.
2. Put question selection, payload validation and grading in a shared `knowledge.py` service. Add routes through the existing app setup; keep `main.py` short. Reuse catalogue reads, entity links, artwork and preview handling.
3. Generate the question on the server; send only the display payload before answering. Store its answer facts privately. The client must not receive the hidden Elo/order/dates or supply its own score.
4. Check and save one answer atomically. Reject duplicate submissions; checking the same round twice must not award twice. Validate album placements as a complete unique permutation of the offered tracks; do the same for the timeline. Artist answers must be unique members of the offered artist set. Candidate counts and payload sizes should be bounded.
5. Freeze comparisons when creating the round, version the grader and retain immutable answered rounds. If a dev correction is needed, void/delete that specific run rather than secretly rewriting unrelated music data.
6. Favour under-tested tracks gently, avoid repeats within a run and keep enough randomness. Select only eligible metadata. Warn about missing track positions/dates in Dev rather than fetching Apple data automatically while playing.
7. Add Dev controls for finding runs by song/artist/album, deleting one run and **resetting Library Challenge history only**. Reuse existing bulk metadata/tag tools. No new verbose audit logging.
8. Derive overview, knowledge rankings, profile panels and the compact home/global-stats integration from the same results. Keep existing Elo, trivia, recognisability and tournament records independent.

Test ties, skipped track numbers, same-date songs, same-year dates, null dates, singles, collaboration credits, deleted records, sparse libraries, duplicate answers and double submissions before adopting it. The proposal SQL has been checked only in an isolated in-memory database; it has not been applied to your app.

## Preview verification

Automated checks cover local navigation/assets, the three core grading rules, artist partial credit, ordering controls, full mixed-test completion, repeat submissions, restart and the sample stats/profile views. A graphical browser render was unavailable in this session, so final visual spacing still needs your browser review.
