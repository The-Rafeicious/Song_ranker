# Data Analysis feature guide

Open **Data Analysis** from Home or the Stats menu. This is a read-only view of the current database. It does not predict future favourites, change ratings or write game results. The attached day-one report informed the analysis topics; its historical numbers are not embedded in the page.

## Choose a record

Choose Song, Artist, Album or Tag, then a record. Changing type reloads the record list. An optional comparison selects a second record of the same type. Artist selections include collaborations once per distinct track. Album and tag selections use current catalogue membership. Every record name in result tables links to its catalogue page; brackets link to their replay workspace. Tag descriptions appear with tag relationships.

## Scores and comparisons

The identity panel shows the **official Overall** score and evidence from the production calibration. The comparison table's **mean measured Overall** is a different descriptive number: the arithmetic mean of member songs with an actual score. It excludes untested songs; it is not the official collection scoring formula. Public Elo averages only songs with effective Elo appearances. Scored modes is an average count of the production Overall modes, including the separate voting views; the breadth panel instead groups these into five game families.

Rates pool correct/winning outcomes over opportunities. They are not averages of track percentages. Every rate shows its numerator and denominator. Voting retains saved Elo influence, including half-weight tag first rounds. Track appearances within an entity can count both sides of an internal match. Daily activity and event source totals count each event once. Comparisons can overlap in membership, so they are not independent samples. Percentage differences use percentage points; they are descriptive, not significance tests.

## Charts and track explorer

Choose a chart, a metric and optionally a Y metric, then press Analyse. The minimum Elo appearances control filters chart points and the track explorer only; it does not filter the performance summaries. Comparison tracks are included in the chart and explorer and deduplicated by song ID.

- **Track performance:** highest ten and lowest ten measured values, without repeating a track. Lengths are relative to the largest displayed absolute value. The chart is bounded even for large collections.
- **Compare two metrics:** all member tracks with both measurements; hover or focus a point for exact values, and follow its link to the song. Axes use the selected data's observed range. The plotted relationship is not a causal claim.
- **Daily voting activity:** the latest 90 dates with saved preference events, once per event. Dates without events are not displayed, and undated records are omitted. It is a count chart, not a win-rate timeline.
- **Song Elo trajectory:** saved post-event public ratings in effective event order. The horizontal axis is event order, not elapsed time. Only songs support this view. Corrected/replayed snapshots reflect the current effective history; deleted history cannot be reconstructed.

The track explorer sorts descending by the chosen metric and pages through all measured tracks in groups of thirty, preserving the filters. Missing measurements display as unavailable and do not enter charts. A zero with a recorded denominator is a real zero.

## Library benchmarks

For every chart metric the page shows the number of measured library tracks, arithmetic mean, median, and observed 10th/90th percentile values. The latter use the sorted observation at floor((N−1)×fraction). The selection percentile is the fraction of measured library songs at or below the selected member-song mean, including ties. Benchmarks compare songs, not similarly sized collections, and are not confidence intervals. Count metrics include zero counts; rate/score metrics require evidence.

## Evidence depth

Each game family shows tested songs, repeat-tested songs, opportunities/appearances and member count. Voting, Trivia, tournament entries, Shelves and Guesser have different observation units. Their totals must not be added as if independent. The breadth distribution counts the number of scored families each song has evidence in, including zero. Vibe is descriptive and never adds a scored family.

## Opponents and sources

The source split separates ordinary/tournament origin and Non-blind/Blind visibility. Opponent rows include external opponents only, with raw wins/losses and total saved Elo weight. Up to twenty most-played opponents are displayed. The recent preference table shows the latest thirty effective events, visibility/source, entity links and saved before/after Elo. A win over a higher-rated opponent uses saved pre-match ratings, excludes ties and missing snapshots, and counts only wins by selected tracks over external opponents; its denominator is selected-side wins with unequal known ratings. It is not the rate across all opportunities to cause an upset.

## Tournament analysis

Competition rates, points and achievements use the shared production scope policy: library and tag full credit, artist/album zero. The separate artist/album record pools completed local brackets with full raw credit. Local results do not enter Overall. The route table shows the last twenty stored revealed match rows involving the selection, including round, scope, winner, loser and saved points. Unfinished Blind brackets do not reveal identities in this table. Match rows and entries are different units; missing historical entry rows cannot be invented.

## Recognition and shelves

Recognition separates title, artist and eligible album correctness. Correct-answer timing shows mean, median and sample count for finite nonnegative saved seconds. Wrong answers do not enter those timing means. Full completed Trivia rounds are read for analysis rather than the catalogue's recent-round preview. Shelf placement and relative order retain their separate denominators and production exclusions; the same directed ordering relation can contribute to two track records. Guesser uses completed-round accuracy. More detailed game-specific reports remain available in Stats.

## Overall, relationships and Vibe

Overall contributions show production mode scores, evidence and allocated weights. No extra scoring system is introduced. Relationship sections list linked artists, albums and tags with distinct member-track counts and tag descriptions. Vibe lists saved status and coordinates for the first thirty selected tracks across their maps; coordinate values are descriptive, not a performance ranking. The full selection remains available through the existing Vibe and entity pages.

## Snapshot and limits

All catalogue and result inputs are read within the shared collection read transaction, and Overall is evaluated from that same data. Another tab's later results appear on refresh. The page is not a historical snapshot comparison, and it does not store custom dashboards. Bounded charts, opponent rows, route rows and the Vibe preview keep the page digestible; the track explorer is paged. No future-performance estimates, statistical significance, causal conclusions or automatic leaderboard corrections are claimed.

## Visual navigation (V5.6.2.1)

Search each selector by typing into its menu. Record options include artwork. Changing the record, comparison or minimum evidence refreshes the available chart choices. Charts and axes with insufficient compatible evidence are disabled. Scatter requires different axes, two shared tracks and variation on both axes; Elo trajectories require two saved points and a song selection. Invalid direct chart links fall back to bars with a status message. When no measured data exists the empty state stays explicit.

Overview, Games, Relationships and Records views organise the page without deleting data. Rate, percentile, coverage, timing and contribution bars open exact figures when clicked or activated with the keyboard. Full raw tables remain in disclosures. Song references include cover art and linked artist/album metadata.
