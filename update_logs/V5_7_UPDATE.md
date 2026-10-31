# V5.7 updates

## V5.7.0 — More song-page mode detail

- Keep the song page's hero, styling, section order, Vibe/Overall cards and replay. Add detail inside the existing mode records, so any song can be explored without finding it at a leaderboard extreme.
- Voting adds full-cohort Blind/Non-blind mode ranks, distinct opponents, best/current win runs, last-ten raw form, recorded Elo movement, ordinary/tournament first-round split and the five most frequent opponents with artwork and artist/album links.
- Trivia adds saved/perfect round counts, latest-versus-previous five-round field accuracy, correct-answer average/fastest timing and five recent recall outcomes. Respect historical field availability; keep saved-round evidence separate from edited lifetime totals.
- Tournament adds completed appearances, first-round exits, library/tag versus artist/album raw match records and five recent finishes with mode, scope and direct bracket links. Competition credit remains unchanged.
- Guesser adds which side was picked, accuracy for close/wider frozen-Elo pairs and five recent comparisons with opponent artwork and metadata.
- Shelves adds perfect track results, wrong-album placements and five recent album/order/point breakdowns. Reuse complete-round grading and album exclusions; unavailable history is explicit.
- Longer lists use closed expandable sections. Background loading, retry, timeout and stale-response handling preserve the existing cover player. Full-history aggregates are independent of the five-row display limits.
- No database migration or changes to saved rounds, ratings, rules or backups.

Validation: all 476 Python regressions, the JavaScript suites (including 180 profile assertions), 58 served developer-page checks, structure and generated function documentation checks pass. Focused coverage verifies full-history aggregation, corrections, field eligibility, frozen Elo, finished/local brackets, whole-round Shelves exclusions, middle-ranked songs, metadata escaping, retry/stale responses and uninterrupted hero playback. A saved 1,128-song backup also passed scoped detail reads. Full checks reached Chromium integration; browser layout/screenshots run in CI because local Chromium is unavailable.

## V5.7.1 — Tournament knockout opponents

- Recent tournament finishes on song pages show who knocked the song out and the round, such as Quarter-finals or Round of 16. Include opponent artwork and linked song, artist and album metadata within the existing finish row.
- Preserve final placement and bracket links. Third-place playoffs do not replace the semi-final knockout opponent; winners have no invented exit. Missing opponent identities remain unavailable and unfinished brackets stay hidden.
- No saved-result, rating or database changes.

Validation: focused backend/API and profile regressions cover knockout stages and opponent links, podium/playoff separation, unavailable opponents and unchanged player behaviour. Full repository checks invoked before the PR.

## V5.7.2 — Expanded artist and album mode records

- Bring the richer song-page mode panels to artist and album profiles, keeping the existing wide layout, semantic styling, Vibe/Overall cards, local-tournament box, track paging and preview queue.
- Add voting form, recorded Elo movement and frequent external opponents; recall trends and timing; tournament entries, finishes and linked knockout opponents; frozen-Elo Guesser difficulty/choice records; and recent Shelves results. Recent rows identify the collection song with artwork and metadata links. Longer lists start collapsed.
- Pool full-history counts and timing samples across distinct current tracks. Keep internal matches explicit: voting track appearances may count both sides, Guesser comparisons count once, and tournament/Shelves track results remain distinct from brackets/rounds. Use the latest ten distinct voting events before pooling appearances.
- Reuse mode-owned builders and one snapshot per profile, with bounded display metadata and no per-track requests. Support empty collections and catalogues beyond 1,000 tracks. Loading/retry/cancellation preserve the preview player. Tags retain their existing summaries.
- No saved-result, rating, rule or database changes.

Validation: all 481 Python regressions, JavaScript suites (including 200 profile assertions), 58 served developer-page checks, structure and generated function documentation pass. Focused checks cover artist/album scope, internal pairs, field-weighted recall, source-song identities, knockout attribution, full-round grading, empty/missing profiles, 1,302-track cohorts and uninterrupted preview queues. Saved-backup checks also verify 199-track artist and 31-track album aggregates. Full checks reached Chromium integration; responsive layout/screenshots run in CI because local Chromium is unavailable.

## V5.7.3 — Isolate local tournament selection history

- Fix local artist/album tournament entries leaking into library/tag exposure support, visibility balance and recent-bracket penalties. Library and tag draws now use competition history only, including when reading older local brackets.
- Local artist and album draws keep adaptive selection based on their own exact collection and scope. Retain the same pool-sized memory, positive soft weights, unique entries and small/full-pool behaviour.
- Local match results no longer adjust library/tag seed ordering. Keep that result-based adjustment for local brackets. Selection diagnostics match the corrected competition evidence.
- Existing saved brackets, results, ratings and Elo policy stay intact. No reset, hard quota, song-specific boost or database migration is needed.

Validation: all 484 Python regressions, JavaScript suites, 58 served developer-page checks, structure and generated function documentation pass. The 45 focused selection/scope/credit/Vibe checks include unchanged library/tag weights, diagnostics and seeded draws after local entries/results, exact local collection isolation, visibility balance and production seed routing. Full checks reached Chromium integration; browser validation runs in CI because local Chromium is unavailable.
