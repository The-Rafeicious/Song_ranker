# V3.3.4 — Overall Stats

This file groups the three-part release and its later hotfixes. The earlier
sections describe their historical release behavior; subsequent sections record
the changes applied by each patch.

## Install

Apply over **V3.3.3.2**. Stop the app, copy the supplied `Song_ranker` contents over
your existing project, restart with `python main.py` and hard-refresh the browser.
The footer shows **3.3.4**. Keep your database and backups; neither is included.
No migration or score column/table is needed. Schema remains **8**.

## Pages

- **Mode Rankings → Overall** opens `/overall_rankings`: songs, artists, albums and
  tags, top/bottom twenty, composite score bars and evidence. Unmeasured records
  do not rank; singles are excluded from the album category. Sorting uses full
  precision and displayed percentages round to the nearest two decimal places.
- Each song/artist/album/tag profile has an Overall card just beneath its identity
  panel: a large percentage, spectrum bar, evidence, tested modes/track counts and
  an optional mode balance. Existing profile names stay beside their artwork.
- Global Stats has the same Overall styling with the average tested song,
  library evidence and leaders across all four entity types.
- Home has one Overall Leaders panel with the top song, artist, album and tag.
- **Dev → System → Overall calculator** shows policy/allocated mode shares and each
  metric's contributing weight, population average, prior and appearances. Search
  a song for its raw values, adjustments and confidence. Refresh ratios rebuilds
  the read-only calibration; it does not rewrite music or result records.
- Ranking percentage formatting also uses two decimals in the existing voting,
  recognition and special-mode ranking displays.

The visual accent uses a warm-white percentage and a spectrum of the mode colours.
The same panel, bar and evidence layout is shared across pages.

## Contributions

Policy shares are deliberate defaults, not values learned from a ground-truth
definition of a "best" song. Core preference data accounts for 48%, recognition
and tournament performance for 36%, and the two newer knowledge modes for 16%.
The table gives the allocation **when all metrics have results**.

| Mode | Mode share | Metric | Share of the complete Overall total |
| --- | ---: | --- | ---: |
| Elo | 24% | Current Elo | 20.40% |
| Elo | — | Peak Elo | 3.60% |
| Non-blind voting | 12% | Win rate | 12.00% |
| Blind voting | 12% | Win rate | 12.00% |
| Recognisability | 18% | Song recognition | 8.10% |
| Recognisability | — | Artist recognition | 2.70% |
| Recognisability | — | Album recognition | 4.50% |
| Recognisability | — | Perfect saved rounds | 2.70% |
| Tournament | 18% | Match win rate | 5.40% |
| Tournament | — | Podium achievement | 8.10% |
| Tournament | — | Completed-entry points / 7 | 4.50% |
| Elo Guesser | 7% | Correct comparisons | 7.00% |
| Album Shelves | 9% | Relative track order | 7.50% |
| Album Shelves | — | Correct album | 1.50% |
| **Total** | **100%** | | **100.00%** |

A mode with no measured results anywhere has zero allocated weight; available
modes share the total proportionally to their policy shares. Within each mode,
globally unavailable metrics similarly release their share to measured metrics.
An individual song's missing but applicable inputs remain neutral. A structurally
inapplicable album field on a single is omitted and the remaining recognition
fields share that song's recognition allocation. The Dev song breakdown shows
this actual per-song allocation.

Win/loss totals and number of matches supply rates and confidence, rather than
earning an extra volume bonus. Elo rank/impact, aggregate recognition, podium
totals and Shelves points derive from the above inputs and are not counted again
as independent achievements. Dates, titles, artwork and tag descriptions have no
performance weight. Global user high scores and cross-song streaks stay in their
existing pages; they cannot fairly be assigned to a particular song.

## Calculation

For rate metric `r`, the population baseline `mu` pools its participating songs'
effective appearances. Shelf order uses track appearances as evidence, preventing
four pair comparisons in one round from masquerading as four independent rounds.
For finite scaling, the rate baseline is bounded to `[0.05, 0.95]`:

```
relative(r, mu) = 0.5 + 0.5 * (r - mu) / (1 - mu)   when r >= mu
                  0.5 * r / mu                    when r < mu
normalised      = 0.60 * actual_rate + 0.40 * relative_rate
```

Thus the population average matters, while widespread strong results still carry
their actual success rather than automatically turning into a 50% success score.
Current/peak Elo use one snapshot per tested song and a logistic transform:

```
normalised_elo = 1 / (1 + exp(-(elo - population_mean) / (1.5 * spread)))
spread        = max(40, population_standard_deviation)
```

Counts only supply confidence. Elo uses recorded match exposure; voting uses its
mode's valid matches; recognition uses available field attempts; Guesser uses
per-song comparison appearances. Shelf order uses offered-track appearances.
Podiums and normalized points use completed entries; unfinished brackets cannot
award placement credit. Tournament match wins can count while a bracket is active.
Completed-entry points are normalized by the mode's 7-point champion maximum.
Podium credit is first `1`, second `0.65`, third `0.35`, adjusted for bracket size
as `1 - (1 - credit) ** (log2(size) / 3)`, with eight tracks as the reference.

For each metric, typical exposure determines its prior strength:

```
prior       = clamp(2 * sqrt(mean_effective_appearances), 4, 20)
confidence  = appearances / (appearances + prior)
adjusted    = 0.5 + (normalised - 0.5) * confidence
```

Unknown inputs have zero confidence and a neutral adjusted value of 0.5.
For a song, combine its adjusted metrics using their allocated shares:

```
raw_score    = sum(weight * adjusted_metric)        # weights sum to 100
evidence     = sum((weight / 100) * confidence)     # 0..1
Overall      = raw_score * (0.75 + 0.25 * evidence)
```

If evidence is zero, Overall is unknown and displays a dash. One perfect attempt
gets much less confidence than repeated near-perfect results. Missing active
modes do not become zeros or free successes, and high-volume modes cannot take
over their allocated shares. The percentage is a personal composite of preference,
recognition and game outcomes, not a literal win probability.

## Albums, artists and tags

Each distinct currently linked song contributes once and equally. Unmeasured
linked songs contribute a conservative `37.50`, the zero-evidence neutral prior.
These entities also use a small-collection prior:

```
mean_score      = average(distinct song scores, substituting 37.50 for unknowns)
effective_songs = sum(each song's evidence / 100)
group_confidence= effective_songs / (effective_songs + 2)
entity_Overall  = 37.50 + (mean_score - 37.50) * group_confidence
```

All-unknown or empty collections remain unknown. This is an average with confidence,
not an accumulating impact total: larger catalogues need consistent song results
and do not gain points merely from their raw song count. A tiny collection's result
is more conservative. Entity confidence and tested/total tracks are visible.

## Calibration and freshness

All scores use a fresh, consistent read-only database snapshot whenever an Overall
view or detail is loaded, including when returning from browser Back. Calibration
parameters stay in a bounded server-memory cache. Compact weights, metric priors/
averages, the rate blend, coverage ratio, group prior and calibration version are
stored in the session without putting all song results in the cookie.

Calibration initializes on first use after startup or in a fresh session. It then
refreshes after 30 minutes, or when any metric gains **25 appearances or 5% of its
previous total, whichever is larger**. A new active metric/mode, reduced counts,
same-count statistical corrections or catalogue membership changes refresh it
immediately. Dev provides a manual refresh. Between these refreshes, newly recorded
answers still change the next calculated score using current facts; only the
population calibration waits for its threshold.

There are no score fields, migrations, audit logs or downloaded audio. The supplied
389-song snapshot calculated in roughly 16–31 ms during local checks, so database
score caching was unnecessary. This timing is environment-specific; very large
histories will cost more because their existing projections also need reading.

## Verification

**107 backend tests** passed, including 13 new Overall tests for evidence, missing
modes/fields, singles, means, group deduplication, untested-track dilution, small
collections, live scores, recalibration, fixed shares, tournament completion/size,
session cookie size, authentication and read-only database behaviour.

**55 Overall interface checks** and **351 existing Shelves interface assertions**
passed with a copied database and controlled media/timers. These cover all profile
types, home/global leaders, category/view selection, two-decimal ranking output,
Dev weights/inspection/recalibration, unknown records and Back refresh, as well as
the existing Shelves/audio behaviour. JavaScript syntax and all three shared
stylesheets parsed successfully.

The original database is untouched. Actual Apple audio and graphical rendering
were unavailable; interface checks validate DOM, events and structure rather than
pixel-level layout or real playback.

## Patch V3.3.4.1

### V3.3.4.1 — Overall layout and developer inspection

This patch tidies the Overall views and expands their developer diagnostics.
The scoring policy, calculations, game modes and database schema remain as in V3.3.4.

#### Overall Rankings

- Removed the rainbow emoji from the Overall navigation link.
- Centred both category and top/bottom-twenty selector rows, with larger buttons
  and more space between and around them.
- Retained category colours, two-decimal percentages and existing ranking order.

#### Song, artist, album and tag profiles

The Overall panel stays in its existing position with the same header. Its score
is now centred between the larger evidence/confidence and participation labels,
above a progress bar spanning the panel's full content width.

Mode balance uses two larger stat boxes per row. An odd final box spans its own
row. The existing sequence is unchanged: Elo, non-blind voting, blind voting,
recognisability, tournament, Elo Guesser and Album Shelves, omitting inactive modes.
The two-column order also remains on narrow screens, with reduced padding.

#### Home and Global Stats

Both Overall Leaders panels use larger vertical cards: artwork, coloured name,
then percentage and progress bar. The redundant song/artist/album/tag caption
has been removed from populated cards. Long names can use two lines and retain
full-name hover text. The tag symbol now has a fixed size and centred line box
inside the enlarged artwork tile, preventing the old cropped appearance.

#### Dev → System → Overall calculator

The existing panels, tables, refresh control and expandable methodology remain.
The page now explains policy versus allocated weight, population averages,
evidence units, prior strength, normalisation, coverage, collection confidence
and calibration freshness. Song metric tables also name the mode and show each
metric's weighted points, making identical metric labels easier to distinguish.

The lookup switches between songs, artists, albums and tags. Artist/album/tag
inspection shows the mean with untested-song priors, effective song count,
confidence calculation, and every distinct linked song's actual and counted
score, evidence and tested-mode count. Select a linked song to inspect its
individual metrics. Empty and entirely untested collections remain unknown;
singles are inspectable but remain excluded from album rankings and leaders.
Changing categories clears the previous detail and ignores an outstanding old
lookup. Manual refresh keeps the selected lookup category.

The extra collection fields are only emitted by the existing details API.
The standard Overall response and all calculated scores remain unchanged.

#### Installing

1. Stop the app.
2. Copy the files inside this ZIP's `Song_ranker` folder over the corresponding
   files in your existing project. Keep your existing database, backups and
   local configuration; do not delete or replace your whole project folder.
3. Restart the app and hard-refresh the browser. The footer should show V3.3.4.1.

This source release includes no database, database backups, personal exports,
Git history, editor settings or compiled caches. No migration is required.

#### Verification

Eight new backend regression tests and 119 DOM/interface assertions passed.
The complete standard calculator output was compared with the supplied V3.3.4
calculator across 497 songs, 60 artists, 148 albums and 52 tags: scores, rankings,
leader selections and summaries matched exactly. Page routes, all four details
lookups, authenticated recalibration, JavaScript syntax and shared CSS parsing
also passed. The supplied database was verified byte-for-byte unchanged.

Chromium could not run in this environment. Interface checks exercise real
Flask responses, DOM structure, computed desktop styles and user events; they
do not verify pixel rendering, mobile geometry or actual Apple artwork/audio.


## Patch V3.3.4.2.1

### V3.3.4.2.1 — Realistic Overall endpoints

First and last place no longer automatically appear as 100% and 0%.
Ordinary standings retain a wide **2–98%** spread around 50%:

```
displayed Overall = 2 + 0.96 × original rank percentile
```

Only an underlying evidence-adjusted composite of exactly 100 or 0 can display
that absolute endpoint. A near-perfect or near-zero composite still uses the
ordinary display range. A loss, missed podium or insufficient evidence in an
included input keeps that composite from being perfect. A finite Elo rating
has no absolute maximum, so being the strongest Elo song cannot certify 100%.

The scale is applied to songs, artists, albums and tags. Category ordering,
composite scores, adaptive mode allocations, relative evidence and eligibility
rules are unchanged. Ordinary tied or single-record populations retain a 50%
centre. Genuine endpoint exceptions can shift the average slightly; the supplied
catalogue has none and still averages exactly 50% in each category.

Dev now separates the composite, original rank percentile and final Overall
percentage, and explains the 2–98% display scale. The global summary is labelled
“Average adjusted percentile.” Actual metric rates, evidence percentages and
mode weights retain their existing values and display rules.

#### Verification

46 backend tests and 119 DOM/interface checks passed, including seven new hotfix
checks for imperfect leaders, almost-zero/almost-perfect composites, real
endpoints, ties, incomplete evidence, missed podiums and unknown records.

Against V3.3.4.2 on the full supplied catalogue, every composite, contribution,
evidence value, mode/metric calibration and entity ordering matched. Measured
songs (456), artists (55), eligible albums (61) and tags (52) now each display
2–98%, averaging 50%. All four details APIs and page version labels passed.
The original supplied database remains byte-for-byte unchanged.

JavaScript syntax and CSS parsing pass. Graphical Chromium and actual Apple
playback are unavailable here; interface checks verify DOM/events rather than
pixel rendering or real media. The calculator math is checked directly.

#### Installing

Stop the app, copy the ZIP's `Song_ranker` files over the matching files in your
current project, then restart and hard-refresh. Keep your existing database,
backups and local configuration. The footer should show V3.3.4.2.1.
This source release includes no database or migration.


## Patch V3.3.4.2

### V3.3.4.2 — Relative Overall percentiles and adaptive participation

Overall percentages now describe relative standing across the current catalogue.
V3.3.4.1's layouts, controls, mode order and developer lookups are retained.
Only the calculator, its labels/diagnostics, version and documentation change.

#### Composite first, percentile second

Each song receives an underlying composite from the calibrated inputs of its
eligible modes. Its displayed Overall percentage is then its percentile among
other measured songs, rather than that compressed composite itself.

For a sorted, zero-based cohort of N measured records, a tied group begins at
rank L and contains T records:

```
percentile = 100 * (L + (T - 1) / 2) / (N - 1)
```

A unique lowest composite maps to 0%, and a unique highest composite maps to
100%. The cohort's arithmetic mean is 50%, including tied ranks. Ties share their
midpoint; a lone measured record or an entirely tied cohort receives 50%.
Untested records remain unknown and do not occupy percentile ranks.

Thus 90% means near the top tenth of the measured category, not a 90% success
rate. The same record can move in percentile as the rest of the catalogue changes.
Close composites can be far apart in percentile: the number describes ordering,
not the size of an absolute performance gap. Dev keeps the composite visible.

#### Five adaptive game families

Five families start from equal 20% bases:

| Family | Components | Base |
| --- | --- | ---: |
| Voting | Elo 8%, non-blind 6%, blind 6% | 20% |
| Recognisability | Existing recognition metrics | 20% |
| Tournament | Existing match/placement/points metrics | 20% |
| Elo Guesser | Comparison accuracy | 20% |
| Album Shelves | Ordering and album placement | 20% |

Elo and both vote rates no longer receive three independent family allocations.
Their existing within-mode metric proportions are retained.

For each mode:

```
participation = tested eligible songs / all eligible songs
average_plays = mean game appearances among tested eligible songs
reference     = geometric mean of active families' average plays
                # Voting's family average uses its component base shares.
depth         = average_plays / (average_plays + reference)
support       = sqrt(participation) * depth
```

A family averages its components' support using their base shares. Family weights
follow that support, with no-results families receiving zero. Voting divides its
family allocation between its three components using base share × support.

With K active families, a family's maximum share is `min(100%, 100% / K + 10%)`.
Excess is redistributed proportionally among the remaining families. With all
five families active, voting's three components together cannot exceed 30%.
The same cap is reapplied per song after structurally ineligible families are
removed: four playable families allow at most 35% each, for example.

One mode with sparse participation starts with less influence, gains influence
as more eligible songs and rounds are played, and loses relative influence if
other modes develop while it stands still. Increasing every mode's exposure by
the same factor preserves the relative balance. A single available family uses
the whole allocation; there is no invented evidence from unused games.

Each mode counts its appearances once, not once per metric: vote exposure for
Elo/voting, rounds for recognition, tournament entries for tournament depth,
comparisons for Guesser and offered tracks for Shelves. Metric evidence retains
its appropriate individual units, such as completed entries for podiums/points.

#### Evidence relative to current average and high exposure

The fixed 4–20-appearance prior is removed. For each metric, let A be the average
appearance count among measured eligible songs and H its 90th-percentile count.
If H is not above A, use H = 2 × A to keep a usable upper range.

```
evidence = 0                                      when n = 0
           0.5 * n / A                           when 0 < n <= A
           min(1, 0.5 + 0.5 * (n - A) / (H - A)) when n > A
```

Average exposure gives 50% evidence; half the average gives 25%; the high
reference gives 100%. This is relative participation, not a statistical guarantee
of certainty. A flat population at one play each gives every measured song 50%,
not an artificial 100%. The high reference and maximum observed count are both
shown in Dev.

Scaling a population from 1–2 plays to 10–20 plays preserves the evidence for
songs that keep pace. A song held at its old count loses relative evidence as
the rest of that metric's population accumulates more results.

Rate normalisation still blends 60% actual success with 40% performance against
its population baseline. Elo retains its tested-song distribution transform.
Relative evidence shrinks each normalised input towards neutral:

```
calibrated = 50 + (normalised_percentage - 50) * evidence_fraction
composite  = sum(allocated_percentage * calibrated / 100)
```

There is no second coverage multiplier depressing all composites. Low exposure
reduces the strength of both good and bad signals towards the middle; it does
not pretend an untested result is a failure.

#### Structural eligibility

A song without a proper album has neither an album-recognition input nor an
Album Shelves input. Shelves also requires a positive integer track position,
a unique occupied slot and a proper album with at least two eligible tracks,
matching the game's per-track candidate pool. A blank position, duplicated slot,
single or unknown album is ineligible. Library-wide ten-track round feasibility
is not used to erase otherwise valid historical results.

Blind voting and trivia require a stored audio preview. Remaining mode weights
are rescaled and capped for that song. An eligible but unplayed mode stays neutral
with zero evidence. A song is not graded using its album's ranking or percentile.

#### Artists, albums and tags

Collections average distinct linked songs' **underlying composites**, not their
percentiles. Untested songs contribute a neutral 50. The existing two-effective-
song confidence adjustment is retained:

```
mean             = mean(song composites, substituting 50 for unknowns)
effective_songs  = sum(song evidence / 100)
confidence       = effective_songs / (effective_songs + 2)
group_composite  = 50 + (mean - 50) * confidence
```

Each category then percentile-ranks its own tested composites: artists against
artists, proper albums against proper albums, and tags against tags. Empty and
entirely untested collections remain unknown. Singles/unknown albums do not
occupy album percentile ranks. The mode breakdown handles collections whose
members have different eligible modes and averages each mode over eligible members.

#### Freshness and Dev diagnostics

Every Overall request reads one consistent snapshot and updates participation,
play references, weights and percentiles immediately. The old 30-minute and
25-appearance recalibration delay is gone. Identical calibration parameters may
reuse the bounded memory cache; the session contains only its ID, version and
timestamp. No score columns, migrations, duplicated records or database writes
are introduced.

The developer balance table now includes family, base allocation, tested/eligible
songs, participation, average plays, depth, support and allocated weight. Metric
tables show mean/high/max exposure. Song inspection separates its composite from
its final percentile. Collection lookup shows song percentiles separately from
the composites counted in its mean. All four searches, drill-downs and manual
refresh remain available.

#### Installing

Stop the app, copy this ZIP's `Song_ranker` files over the corresponding files in
your current project, then restart and hard-refresh. Keep your existing database,
backups and local configuration. Do not delete the whole project folder. The
footer should display V3.3.4.2. The ZIP contains source, documentation and tests;
it contains no replacement database, exports, Git/editor data or compiled caches.

#### Verification

39 backend regression tests and 119 DOM/interface assertions passed. Tests cover
full-range/tied percentiles, category cohorts, good/bad outer deciles, adaptive
mode breadth/depth, family caps, immediate changes, young/mature exposure scaling,
songs left behind, structural eligibility, collection reconstruction and compact
sessions. The existing lookup tests were updated for the new neutral/composite
semantics and pass with the new calculation tests.

Full-catalogue invariants, API details, rendered page responses and authenticated
recalibration were checked on a copy of the supplied database. The original was
verified byte-for-byte unchanged. JavaScript syntax and shared CSS parsing pass.
Graphical Chromium and actual Apple playback were unavailable; UI verification
covers DOM structure and events, not pixel geometry or real artwork/audio.

#### Supplied catalogue example

These are live-calculation examples from the uploaded snapshot, not fixed settings.

| Category | Measured cohort | Lowest | Average | Highest |
| --- | ---: | ---: | ---: | ---: |
| Songs | 456 | 0.00% | 50.00% | 100.00% |
| Artists | 55 | 0.00% | 50.00% | 100.00% |
| Albums | 61 | 0.00% | 50.00% | 100.00% |
| Tags | 52 | 0.00% | 50.00% | 100.00% |

| Game family | Current allocated weight |
| --- | ---: |
| Voting (Elo + non-blind + blind) | 29.90% |
| Recognisability | 23.79% |
| Tournament | 12.10% |
| Elo Guesser | 8.04% |
| Album Shelves | 26.17% |

