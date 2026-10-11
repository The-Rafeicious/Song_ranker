# Song Ranker · Mode ideas

These are ideas, separate from the V3.2.3 scroll patch. Open **index.html** in a
browser, then choose a design. Each HTML file has its CSS and JavaScript inside
it and also works on its own. Keep the five files together for navigation.

The tracks/artwork are fictional. Playback bars simulate audio; no actual preview
is downloaded or played. Nothing connects to your Flask app or database. Build a
Set can keep sample sets in this browser's local storage only.

## At a glance

| Concept | What you do | Result | Proposed colour |
| --- | --- | --- | --- |
| Test Your Knowledge | Name hidden tracks from one artist or album | Song accuracy; optional album accuracy | Trivia gold, with blue/purple scope details |
| Clip Ladder | Name a song from 1, 3, 7 or 15 seconds | Up to 1 point per track; streak | Trivia gold |
| Higher or Lower | Guess which of two tracks has higher Elo | Correct guesses and streak | Elo orange |
| Build a Set | Draft five tracks, then arrange the running order | A saved set; no competitive score | Set copper (new accent) |

I'd implement Test Your Knowledge first: it fits the existing profile pages and
preview library. Clip Ladder is the strongest next new mode. Higher or Lower is a
small, easy addition. Build a Set adds something different if you want a mode
that produces a useful playlist rather than more statistics.

## 1. Test Your Knowledge

**Template: knowledge.html**. The opening screen shows an album/artist profile
with a **Test your knowledge** button. Try both scope tabs; artist tests can add an
optional album question. Juniper has two sample albums so that question makes
sense. The actual app would add this button to the existing profile, not replace
its stats or player.

### How it would work

- Album scope: the album and artist are already known, so only ask for the song.
  Artist scope: only ask for the song by default; optionally ask for the album
  when there are multiple proper albums to choose from.
- Draw songs without repeats, only from that selected album/artist and only with
  playable previews. Finish the set when all eligible songs are tested, or use
  a chosen length such as 5/10/all. Fewer than five tracks is still a valid test.
- Hide the individual artwork and track identity until the answer is checked.
  Keep the chosen context visible. Use the existing 30-second timer, fuzzy typo
  matching, blur/Enter checking, input flips, pause/resume and ending snippet.
- One song correctness point per round, reported as an accuracy percentage. An
  optional album answer gets its own accuracy; it does not dilute song accuracy.
  Artist answers are absent because the artist is given. Singles/unknown albums
  make the optional album answer not applicable, saved as NULL, not incorrect.
- A completed test shows the missed tracks and lets you retry those or start a
  fresh test. The mockup demonstrates a three-track album and five-track artist
  test, answer checking, reveal, next track and restart; it doesn't implement
  production fuzzy matching, timed pause/resume or the missed-only retry.

### Alongside main trivia

Keep these results separate. Giving the artist/album as a hint would make global
recognisability less comparable. Existing `trivia_rounds`, recognition denominators,
main trivia high score/streak, Elo and tournament results stay unchanged.
A small **Knowledge tests** section could show last/best song accuracy and attempts
on that specific artist/album page. Search and rankings need no new badge initially.
No new large stats page is necessary.

### Data needed

Use the proposed shared `challenge_runs` / `challenge_rounds` below, with mode
`knowledge`, the chosen artist or album ID, song correctness and nullable album
correctness. Known fields aren't recorded as correct answers. There is no need
for another per-song running total or an event/audit table. Aggregate saved rounds
when displaying a profile's results. Dev should let you delete a test or clear
knowledge-test results separately from main trivia.

## 2. Clip Ladder

**Template: clip_ladder.html**. Play the first second, type the title, or unlock
more of the same preview. The artwork and metadata appear after the round.

### How it would work

- Use an existing preview URL; start at the same position each time and stop at
  1, 3, 7 or 15 seconds. The longer rungs include the earlier audio; do not
  splice/download/store another audio file.
- Correct at each rung earns **1.00 / 0.75 / 0.50 / 0.25** points. Unlocking more
  reduces the available reward. A wrong submitted answer unlocks the next rung;
  a wrong answer on the final rung or Give up earns zero and ends the streak.
- Use the existing fuzzy matcher, but grade on Enter/Check. Blur should not
  consume a limited guess. Replay the current unlocked length without reducing
  points. Disable guessing/extra-clip controls after the answer is finalized.
- Start the next track manually; keep a compact run score and streak. Missing or
  failed previews are skipped with no loss of score/streak. The prototype's
  audio is simulated, but unlocking, checking, scoring, reveal and next all work.

### Data needed / stats

Shared challenge tables, mode `clip_ladder`, target song, highest unlocked rung,
correctness and elapsed time. Derive points from rung and rules version. No raw
wrong-answer strings, playback logs or repeated totals are needed. A compact
summary on trivia stats could show best run, streak and first-second accuracy,
clearly labelled Clip Ladder. Do not mix it into normal recognition or Elo.
Dev can clear these results independently. Server-side grading should lock the
rung/answer once checked, so duplicate clicks can't earn extra points.

## 3. Higher or Lower

**Template: higher_lower.html**. Two known songs, both with cover previews and
metadata. Choose the one you think is ranked higher. Neither Elo is visible until
you commit; then show both scores and whether your guess was right.

### How it would work

- Pick varied pairs with a useful Elo gap; avoid repeated pairs and exact ties.
  Let songs that have been ranked enough appear more often, so the question has
  a meaningful answer. Keep selection random rather than always choosing extremes.
- Freeze both Elo values at round creation. Grade against that snapshot, even if
  another tab casts a vote before you answer. A tie keeps the streak and is not
  counted as a scored round. If one song is deleted, cancel the round.
- One point per correct guess and a consecutive-correct streak. Cover previews
  are optional; do not require audio for eligibility. This is a guess about your
  existing rankings, so it never changes either song's Elo or match count.
- The prototype demonstrates five rotating pairs, cover-play states, hidden Elo,
  choice locking, score/streak changes, reveal and next pair. It uses fixed sample
  values rather than running a real Elo draw.

### Data needed / stats

Shared challenge tables, mode `higher_lower`, two song IDs, both Elo snapshots,
correctness and elapsed time. Those two snapshots are useful historical facts,
not duplicate current ratings. No actual standard-vote history row is written.
Show best score/streak and overall guess accuracy in a small Elo-stats section
if useful; no effect on existing song/artist/album leaderboards. Dev can reset
these guesses separately.

## 4. Build a Set

**Template: build_a_set.html**. Choose between two tracks until you have five, then
move them up/down to form the set's running order. Replace a choice if it doesn't
fit. Try the optional cap of two songs per artist, then keep or reopen a sample set.

### How it would work

- Draw from the full library, an artist/album/tag, or your selected favourites.
  Start with five slots; 3/5/8 are reasonable choices later. Present two candidates
  for each empty slot, optionally with an artist limit to create variety.
- Offer only unpicked songs that meet the chosen constraints. Validate the pool
  before starting and when changing a limit, so the draft cannot get stuck.
  If only one eligible candidate remains, let it fill a slot directly.
- Keep the queue visible, allow previews, then arrange/replace songs at the end.
  Save a name and order. A later useful addition is opening the set as a looping
  preview queue, using the existing album-player behaviour.
- No user points, wins, Elo changes or tournament achievements: choices are about
  the particular set. Do not quietly turn those context-specific choices into votes.
- The standalone prototype can keep the latest 20 sample sets in local storage.
  In the real app, use SQLite so sets survive a browser reset. This proposed
  mode uses its own copper accent; blind voting retains teal. Artist, album and
  song labels retain their existing entity colours.

### Data needed / stats

Add `saved_sets(id, name, created_at)` and
`set_tracks(set_id, position, song_id)`. Use `(set_id, position)` as the key and
`UNIQUE(set_id, song_id)` to prevent duplicate tracks. Song references can use
`ON DELETE SET NULL` to preserve an empty slot when the library is edited; set
removal cascades its slots. The order is a local set position, not the song's album
track number. Gaps can be displayed safely and reordered when the set is edited.
Keep unfinished drafts in browser/session state; only write a set when saved.
No pick-by-pick history, ranking page or scoring totals are needed. Dev can rename,
reorder or delete sets; library changes should show missing slots clearly.

## Shared schema proposal for the scored concepts

**Proposal only — this ZIP includes no migration and changes nothing.** Two small
normalized tables can support the first three concepts without adding three more
history systems. Set-building uses its own two tables because it stores ordered
collections, not correctness.

| Table | Suggested fields | Why |
| --- | --- | --- |
| `challenge_runs` | `id`, `mode`, `rules_version`, nullable `artist_id` / `album_id`, `album_question_enabled`, `started_at`, nullable `completed_at` | A run and its rules/context; at most one scope FK is set |
| `challenge_rounds` | `id`, `run_id`, `round_index`, nullable `song_id`, nullable `other_song_id`, nullable `correct`, nullable `album_correct`, nullable `rung`, nullable `elo_a` / `elo_b`, `elapsed_ms` | One finalized outcome per round; only fields relevant to its mode are populated |

Use foreign keys; cascade rounds when their run is deleted. Scope/song references
can be set NULL on deletion, with a clear missing-record label. An artist/album
knowledge run whose scope has been removed must be shown as an unavailable scope,
not silently reclassified as global. Add `UNIQUE(run_id, round_index)` and an index
on `(mode, artist_id, album_id)` for profile summaries. Apply CHECK constraints
for mode, booleans and valid rungs. Higher-or-Lower outcomes with equal snapshots
are unscored/NULL; pending/skipped/deleted rounds must not be mistaken for correct.
An explicit skipped outcome flag is optional if you want to distinguish skips
from wrong answers in Dev.

Keep active rounds in the existing session lifecycle. If rounds need to survive
restart, reuse the existing trivia timer's ready/active/completed lifecycle and
pause fields in a dedicated active-round record; don't also append timer events.
Persist the chosen target and grading lock server-side, including the snapshots
for rating guesses. Keep answers hidden until grading. Derive summaries and
points from finalized rounds; store no duplicated per-song counters or audio logs.
Rules version keeps older rung scoring interpretable if points change later.

Before a real implementation, add a backed-up migration, validation and Dev
controls together. Existing reset buttons should keep these proposed modes intact
unless the user chooses a new mode-specific reset; a full competition reset can
explicitly include the scored concepts. Saved sets should survive competition
resets, because they are library collections.

## Prototype limits

These HTML files demonstrate layouts and interaction only. They don't implement
API access, server validation, fuzzy matching, real audio, active-round recovery,
or shared high-score persistence. Sample images are CSS artwork, not real covers.
The production version should reuse the actual shared banner/styles/player,
trivia helpers and database connection, and maintain the site's existing colour
roles and all current features.
