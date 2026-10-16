# Song Ranker — rough roadmap to v4

Draft 2 · 13 October 2026 · Open for new ideas

This is a planning draft for the larger update after the v3.4 page-by-page standardisation is finished. Finish those page updates first, then use their final code and database as the starting point. The proposed endpoint is **v4.0** once the agreed stages are complete and checked. Stage letters below are working labels, not committed release numbers or dates.

Based on your ideas file and the supplied v3.4.3.1 source snapshot. Later v3.4 changes will need a fresh check before implementation. This draft makes no app or database changes.

## Proposed direction

Make the app's underlying processes consistent, make selection adapt as the collection develops, and make Overall percentages reflect actual performance gaps. Keep enough randomness for varied play while giving less-played entries a fair chance to catch up. Transition all hardcoded caps, weights, and matchmaking thresholds to self-adjusting dynamic ratios that scale smoothly alongside database growth and active user engagement.

## Stages at a glance

| Stage | Main work | What should be true before moving on |
| --- | --- | --- |
| Prerequisite | Finish the v3.4 page updates. | The accepted layouts and page behaviour are settled; capture a fresh baseline. |
| A — Data cleanup | Audit the database, agree what to remove, and decide how to handle ID gaps. | Retained records and links are intact; any migration has a verified backup and mapping. |
| B — Shared processes | Bring repeated selection, result recording, eligibility and statistics logic together. | The same saved results produce consistent figures across pages, with existing game rules preserved. |
| C — Base & Tournament Elo | Introduce dynamic K-factors (placement phase) and first-round Elo rules. | Each eligible result changes Elo once; new tracks rapidly find their tier; tournament points remain traceable. |
| D — Overall percentages | Replace the evenly stepped display with a continuous score that respects result gaps. | Close performances look close, large gaps remain visible, and the artificial 2–98 range is gone. |
| E — Adaptive selection | Use current distributions, exposure and quality bands across all modes. | Selection stays varied, adapts to changing data, and improves exposure balance in trials. |
| F — v4 release | Check the stages together, tune feedback effects, and document the final rules. | Upgrade checks and representative play pass; release the completed package as v4.0. |

Suggested order: A → B → C → D → E → F. Tournament rules come before final scoring and selection tuning because they change the Elo and exposure data those systems read. Each stage can be split into smaller patches. Revisit this order as new ideas arrive.

## A — Data cleanup

- Inventory catalogue records, history, brackets, knowledge rounds, manual adjustments and stored counters. Compare stored totals with totals derived from results.
- Define what “take out data” means: obsolete fields/tables, abandoned rounds, unwanted test results, duplicate records, or a deliberate reset of particular histories. Keep this undecided until the intended scope is clear.
- Check links, duplicates, invalid values, album track positions, and records that no longer qualify for particular modes. Report ambiguous cases before deciding how to repair them.
- Treat closing ID gaps as a separate migration choice. If wanted, build complete old-to-new maps and update every reference together, including tournament scope IDs, saved rounds and links. Account for open sessions and old URLs. Keeping stable IDs is also an available choice.
- Trial cleanup on a copy, compare retained results and relationships, then verify restoration from backup before applying it to the real database.

**Completion:** every deletion is intentional; retained history still belongs to the right entries; mappings and before/after counts explain the changes.

## B — Shared processes

Build on the existing shared catalogue, Elo calculator and selection helpers. Consolidate common work while keeping each mode's rules explicit:

- One consistent way to build eligible pools and read exposure counts.
- Shared selection tools with mode-specific settings for songs, albums and any artist-based selection.
- A common path for preference results that updates Elo, exposure, peaks and history together where applicable.
- Shared statistics definitions used by Home, Global Stats, rankings, profiles and developer tools.
- Shared protections against saving the same result twice; preserve frozen answers in Elo Guesser and Album Shelves.

**Completion:** representative old results give the same answers before and after the refactor. Change behaviour in later stages so refactoring errors are easier to identify.

## C — Base & Tournament Elo

Your intended starting rule: the first bracket round can affect Elo like a normal preference vote. Later rounds continue to award tournament results without repeatedly increasing global Elo exposure for advancing songs.

- Reuse the shared preference-result process for eligible first-round votes.
- Compare normal Elo, reduced Elo influence and no Elo influence for artist-, album- and tag-restricted brackets. Repeated play inside a small group needs its own evaluation.
- Keep tournament provenance in recent history: bracket, round, blind status and whether Elo changed, with before/after ratings where relevant.
- Link the history event to its tournament match so one vote can support both displays without being counted as two separate events.
- Define how first-round Elo contributes to Overall's voting inputs, avoiding accidental extra weight for the same result.
- Start prospectively. Any recalculation of old tournaments would be a separate decision because it could alter later Elo outcomes.
- **Dynamic Placement Phase:** Introduce a variable K-Factor for Elo swings. Tracks with 0 to 5 matches played should swing by 50-60 points per match to rapidly stretch the library into a healthy 400-600 point spread. After the placement phase, revert to the standard 15-16 point fine-tuning swing.

**Completion:** a first-round result updates Elo and its exposure count exactly once when allowed; retries, later rounds and third-place playoffs follow the agreed exclusions. New database additions rapidly sort into distinct quality tiers rather than bunching near the baseline.

## D — Continuous Overall percentages

The current code already calculates an evidence-adjusted composite. Its final percentile display produces the predictable spacing and ordinary 2%/98% endpoints.

- Prototype displaying the existing composite directly, then compare it with a blend of continuous performance and relative standing. Choose based on actual examples rather than fixing a formula now.
- Preserve meaningful gaps: almost equal results should receive almost equal scores; substantially different results should show a larger difference.
- **Implement "Micro-Spacing":** Find the true high and low raw scores in the live database, stretch that exact range to fit the 0–100 scale, and place songs exactly where they naturally fall. This creates organic, non-repeating decimals while ensuring the top and bottom songs always hit the visual maximums.
- Allow the full 0–100 scale. Decide whether endpoints mean absolute performance or the current collection's extremes. Stretching every collection's minimum and maximum to 0/100 would force the endpoints again, so it does not fully solve your stated aim.
- Keep score, rank and evidence as distinct concepts. Preserve ties, sensible treatment of sparse results, and unknown scores for untested entries.
- Apply the agreed interpretation consistently to songs, artists, albums and tags; retain protection against tiny collections dominating on very little evidence.

**Completion:** compare examples with close scores, large gaps, ties, one tested entry, sparse data and an outlier. The final percentages should remain understandable as the collection changes.

## E — Adaptive selection for every mode

Use a shared selection framework that learns from current distributions while respecting each game's eligible pool.

- Replace fixed exposure and rating-gap scales with references derived from current data. Use stable defaults when there is too little data to calibrate.
- **Main Matchmaking (Standard/Blind/Tournament):** 
  - Replace the hardcoded `12` match-gap divider with the live `mean_matches` across the database to ensure experience parity scales.
  - Replace the hardcoded `110` target Elo shoulder with the live database standard deviation (`elo_spread`), allowing the algorithm to hunt for appropriate challengers no matter how tight or wide the ratings get.
  - Apply an aggressive priority boost to tracks with strictly `0` plays to clear backlog queues faster.
- **Trivia Adjustments:**
  - Introduce dynamic question values derived inversely from global recognition rates (e.g., if Title is heavily recognized but Album is not, Album automatically commands a higher share of the score).
  - Transition the 30-second speed bonus ceiling to an adaptive timer based on the live average completion time.
- **Elo Guesser Adjustments:**
  - Replace the hardcoded 40–250 Elo gap window with a dynamic window that scales using the database's standard deviation.
  - Compare a song's Guesser exposure against the live average of Guesser plays rather than penalizing raw play counts.
- **Album Shelves Adjustments:**
  - Transition the hardcoded 5-round album cooldown to a percentage of total eligible albums, preventing matchmaker starvation in small libraries.
  - Weight album selection dynamically against the live average of shelf attempts, naturally prioritizing newly added albums until they catch up to the baseline.
- Draw across **excellent / good / mid / bad / terrible** bands. Decide whether these represent relative position or score thresholds; do not force identical band sizes or distribute tied entries arbitrarily.
- Give underplayed entries more opportunities, and softly favour similar exposure levels in pairings. Aim for comparable opportunity, not exactly equal counts after every round.
- Mix close comparisons, comparisons across bands and broader random draws. Keep a nonzero chance for eligible entries and soften repeat limits when pools are small.
- Balance exposure within each mode as well as across the collection. Restricted pools should use local balance without automatically redefining global quality bands.
- Apply appropriate rules to Standard/Blind, Trivia, tournament entry draws and seeding, Elo Guesser, and album/track selection in Shelves. Preserve preview requirements, non-tied Guesser ratings and feasible Shelves rounds.
- Recalculate as saved results or eligibility change, with enough smoothing to avoid sharp shifts after a single result.

**Completion:** run repeatable simulated draws before normal play. Check exposure spread, variety, repeats, band coverage and small-pool fallbacks, then tune again with the new tournament rules active.

## F — Finish and release v4

- Check upgrade and restore paths using the final v3.4 baseline.
- Play representative rounds in every mode, including restricted/blind tournaments and resumed rounds.
- Check agreement between histories, totals, profiles and rankings after edits or deletions.
- Evaluate the feedback loop: selection changes exposure, exposure changes evidence and scores, and scores influence future selection. Adjust any self-reinforcing bias found in trials.
- Update the calculator explanations and release notes to match the chosen rules, then set the public version to v4.0.

## Decisions to develop later

| ID | Open decision | Needed by | Current status |
| --- | --- | --- | --- |
| Q1 | Which data should be removed or reset? | A | Open |
| Q2 | Compact all IDs, selected entity IDs, or retain stable IDs? | A | Open |
| Q3 | How should restricted first-round tournaments affect global Elo? | C | Open; compare full, reduced and disabled influence |
| Q4 | Should tournament Elo also contribute to voting-rate inputs in Overall? | C/D | Open; count each event deliberately |
| Q5 | What do Overall's 0% and 100% mean? | D | Open; no forced 2%/98% endpoints |
| Q6 | How should the five quality bands be defined for each entity type? | E | Open |
| Q7 | What mix of close, cross-band and broad random selection feels best? | E | Open; tune from trials |
| Q8 | Should any new rules recalculate old results? | Before release | Suggested starting point: future results only |

## Space for new ideas

Keep new ideas here until they have enough detail to place in a stage. This avoids making every new suggestion a requirement for the first v4 release.

| Idea ID | Idea / intended benefit | Suggested stage | Dependencies or open questions | Status |
| --- | --- | --- | --- | --- |
| N1 | Spotify Listening Priors / Jumpstart new database additions based on external listening volume | C | Requires an import script mapping Spotify data to the Elo baseline | Proposed |
| N2 | Add next idea here | To decide | To decide | Proposed |
| N3 | Add next idea here | To decide | To decide | Proposed |

Useful status values: proposed, exploring, agreed, deferred, completed. For each agreed idea, add one sentence describing how we will know it works.

## Notes from the supplied source

- `overall.py` already adapts mode weights and evidence, then `apply_percentiles()` replaces the continuous composite display with rank spacing between 2 and 98. Stage D targets that last step and evaluates whether earlier scoring also needs adjustment.
- `selection.py` shares basic exposure weighting, standard pairing and tournament draws. Guesser and Shelves still contain separate selection rules; Trivia uses the shared exposure helper.
- `games.py` currently updates Elo for Standard/Blind votes; tournament votes record independent tournament results.
- The older `is_tournament_match` flag is migrated into `history.mode` by `mode_schema.py`. The v4 design should extend the current history model rather than assume the old flag is still present.
- The supplied database passes SQLite integrity and declared foreign-key checks. These checks do not cover every semantic rule or the polymorphic tournament scope reference; a cleanup audit is still needed. Repeat checks against the final v3.4 database.

## Draft history

| Date | Change |
| --- | --- |
| 13 October 2026 | Refined Stage C, D, and E to include fully self-adjusting logic, micro-spacing for decimal outputs, and dynamic mode constraints. |
| 13 October 2026 | First rough plan from the five supplied ideas; staged after completion of v3.4. |