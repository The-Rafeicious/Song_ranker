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
