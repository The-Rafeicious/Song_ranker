# Song Ranker — page layout and styling

Read this before changing a page or page group. It records the user's accepted
V3.4 direction; later user corrections take priority. Update the relevant rule
when a correction is adopted, then use it on the next pages. Each page can have
a different composition while sharing these elements. Global Stats was the first
page converted, in V3.4.1. V3.4.2.1 applies the chosen shared baseline across the
site; later page updates can still adjust their individual composition.

## Approved shared baseline — V3.4.2.1

Selected by the user from the Style Previews pack:
**T2 · F2 · W3 · A3 · D2 · R3 · G2 · C1 · B1 · H1 · N1**.
Desktop was the comparison width, not a restriction to desktop-only styling.

| Code | Accepted choice |
| --- | --- |
| T2 | 44 px page titles, 30 px section/ranking titles, 18 px metadata, 16 px body text and 36 px primary values |
| F2 | Arial, with Helvetica and sans-serif fallbacks, across public and developer UI; code/data snippets may retain monospace |
| W3 | 900 heading/ranking title weight, 800 text links and linked metadata |
| A3 | 120 px main ranking covers and Global Stats podium covers on desktop; all six width/height constraints agree |
| D2 | 24 px main panel/row padding and 20 px major gaps; retain tighter inset spacing |
| R3 | 24 px outer panel corners, 18 px inner group corners; artist circles and icon shapes keep their geometry |
| G2 | Existing rank-dependent and mode glows, including Top/Bottom falloff |
| C1 | #1e1e1e base panels and #242424 soft insets; preserve semantic mode washes, borders, outcome states and the live recent-mode blend |
| B1 | Pill-shaped text action/range buttons; cover, icon, scope and drag controls retain their functional shape |
| H1 | Centred page/panel headings, actions on the right; narrow headers put actions on the following right-aligned line |
| N1 | Single-line ellipses for variable names/metadata; complete text stays in the DOM and existing title attributes; scores/outcomes remain separate |

`static/css/site_baseline.css` loads last in the shared base template. It owns
these tokens and common component overrides; use it for future shared changes
instead of duplicating this baseline in every page stylesheet. Do not force
120 px onto profile/game hero covers or dense record/table thumbnails: the
preview's cover choice controlled main ranking rows, while those other roles
had their own sizes. Keep existing larger hero art and smaller record art.

Below 760 px, primary ranking covers are 88 px, titles/metadata/scores use
26/16/32 px and panel padding becomes 20 px. Below 520 px, use 72 px covers,
22/15/28 px ranking type, 32 px page titles and 18 px panel padding. The cover
and rank span the two copy/score rows so their vertical clearance stays equal.
Colours, data order, layouts and game/audio behavior remain page-specific.

## Shared owners — V3.4.3.3

Keep a single owner for common rules; update it before adding a page override.
All eight existing stylesheets and six scripts were reviewed during this patch.

| Owner | Responsibility |
| --- | --- |
| `static/css/style.css` | Core layout foundation, the semantic colour values and page-tone variables. |
| `static/css/site_baseline.css` | Approved font/type scale, ranking geometry and six cover constraints, common corners/padding, centred headers, pill actions and name ellipses. It remains the last stylesheet. |
| `static/css/components.css` | Shared joined metric rows, responsive divider placement and dashboard surface glows. |
| `static/css/mode_stats.css` and `templates/mode_stats_components.html` | Shared detailed-mode dashboard rows, insets, metrics, artwork, bars, text links and formatting macros. Page files provide accents and specialised states. |
| Page/mode stylesheets | Their composition, game/reveal states, specialised artwork and mode text-colour utilities. Keep text utilities in their established cascade order. |
| `static/css/compat.css` | Isolated legacy selectors; retain required legacy behaviour and intentional browser fallbacks. |
| `static/js/ui.js` | Shared DOM selectors, escaping, one-decimal ratio display, field totals, entity labels/colours and scrolling-banner headers. Load first among deferred scripts. |
| Feature scripts | Their requests, state transitions, calculations, game actions, audio handoffs and cancellation rules. |

Shared CSS load order is compatibility → optional page CSS → foundation →
special modes → Overall → components → approved baseline. JavaScript loads
`ui.js` before preview, feature and page scripts. Do not copy its helpers into
new modules. Different request timeouts, grading and cancellation behavior are
feature-specific; keep those contracts in their feature modules.

Use **`joined-metrics`** for a single framed row of centred data. Its default is
three fields; declare `data-columns="2"` or `data-columns="4"` for other counts.
Home keeps three fields on phones. Four-field Global Stats groups become two
columns below 760 px, with no vertical line before the first field of either
row and a quiet horizontal boundary between rows. Dividers use the parent
`--section-color`, falling back to the surface accent. Separate record cards,
artwork galleries and independently framed comparison boxes are not joined rows.

Every main Home/Global Stats panel, collection/mode total, game-mode card,
scrolling-banner card and Overall leader card uses one soft glow rule in
`components.css`: 26 px at 16% of its accent, plus the existing dark depth
shadow. Glows follow the border hue, including the deeper Shelves border shades.
Recent Mode Results uses its live visible-mode blend; an empty feed is neutral.
Inner data groups stay quieter. Rank-dependent glow falloff on ranking boards
is unchanged. Future page conversions can opt into **`dashboard-surface`**
and provide `--surface-accent` rather than invent another shadow declaration.

Remove earlier declarations only when the same selector, responsive context
and priority already supersede them. Preserve intentional fallback sequences,
separate states and distinct responsive layouts. Do not accumulate patch layers
for headers, cover sizing or joined-row boundaries now owned above.

## Composition

- Keep the existing page title/navigation unless the user asks to change them.
- Use the available width for larger text, artwork and meaningful data. Avoid
  large empty gaps, oversized padding, repeated totals and redundant labels.
- Put primary statistics first, supporting values below and records/activity
  later. Major dashboard sections each occupy a full row; useful comparisons
  inside a section may use columns that collapse on smaller screens.
- Reuse dark panels, thin accent borders, restrained glows and rounded corners.
  The shared baseline uses 24 px panel padding and 20 px between major sections;
  narrow screens reduce these to 18–20 px. Do not invent a separate card language
  for each new statistic.
- Centre summary counts and their labels. Keep record/list names aligned with
  artwork and scores aligned at the far end of the row. Numbers and their labels
  have separate lines, except small units beside a record's number.
- Centre box headings against the full box width, with links/actions on the
  right. Use equal left/right header gutters on desktop; on phones keep the
  title centred and place the right-aligned action on its own line when needed.
- Make the start/end of each data row/group apparent with a quiet rounded border
  and dark background lightly tinted in the parent section's colour. Nested
  boxes are welcome when they organise data or fill empty space; their contrast
  should stay below the main panel's border/glow.

## Type and hierarchy

| Element | Desktop shared baseline | Narrow-screen behavior |
| --- | --- | --- |
| Page title | Existing 44 px title | Retain existing responsive title rules |
| Section title | 30 px | 27 px where needed |
| Subsection title | 22–23 px | Allow wrapping |
| Primary value | 36 px, heavy weight | 25–32 px, fit the available width |
| Supporting value | 28–34 px | 24–27 px |
| Entity link | 19–24 px | 17–21 px with wrapping |
| Label / context | 14–17 px | Remain readable; avoid tiny text |

Use short labels. Show useful denominators, track counts and saved results,
not an explanation of the implementation. Use single-line ellipses for variable names/metadata when space runs out, with
the full text retained in the DOM and a title attribute. Keep scores, counts and
outcomes in separate wrapping fields so they stay visible. Avoid horizontal page scroll.

## Colour and interaction

| Meaning | Existing token |
| --- | --- |
| Song name | `--song` green |
| Artist name | `--artist` blue |
| Album name | `--album` purple |
| Tag name | `--tag` amber |
| Voting / Elo | `--standard` orange |
| Blind voting | `--blind` mint |
| Trivia / recognisability | `--recognition` gold |
| Tournament | `--tournament` pink |
| Elo Guesser | `--guesser` red-orange |
| Album Shelves | `--shelves` mauve, `--shelves-deep` aubergine |
| Overall | `--overall` warm white with the existing mode spectrum |

Keep entity names in their entity colour; statistics, headings, bars and
supporting metric labels use the relevant mode's colour. Errors and losing
vote results can use the existing danger colour. Overall leaders already have
the accepted artwork → name → percentage → bar layout; preserve it.

Text links underline on hover and keyboard focus, with a clear focus outline.
For statistical records and voting leaders, link the entity's name, not the
whole row or box. Artwork/counts should not quietly become separate hit targets.
Keep visible previous/next/play controls labelled for their actual page/entity.

## Artwork and rows

- Songs and albums use square artwork; artists use circles. Use the existing
  artwork fallback and image-error behavior. Never stretch an image.
  Set width, height and their minimum/maximum constraints together. Global Stats
  uses `--stats-art-size` for all six dimensions, preventing an older shared
  `max-width` from narrowing a taller cover. Disable flex shrinking/stretching.
- Global Stats list artwork is 72–80 px on desktop, with 120 px podium covers;
  dense collection/vote records use 52–60 px. Scale to 44–72 px on phones.
- Use flexible name columns (`minmax(0,1fr)` / `min-width:0`) and fixed artwork
  columns. Long names truncate without pushing scores offscreen; full titles remain
  available on hover. Result chips wrap instead of hiding important numbers.
- Collapse multi-column comparisons on tablets/phones; do not remove artwork
  just to preserve a cramped desktop column arrangement.
- Labels/counts stay useful when there are no results: show a short empty state,
  zero for an actual count and `—` for a rate without a denominator.

## Global Stats reference

The accepted major order is: top collection/mode totals, Collection Records,
Overall Stats, Voting Results (including Frequent Matchups), Elo Distribution,
Recognisability, Tournaments, Elo Guesser, Album Shelves, Artist Average Elo,
Album Average Elo, Top Tags, Recent Mode Results.

- Top totals have two rows of four cards. The second row follows the mode
  sections: Trivia, Tournament, Elo Guesser, Album Shelves.
- Every joined metric group, including dynamically mounted Overall, uses the
  shared dividers. Use two/three/four fields as appropriate and reset divider
  placement when four fields wrap to two columns.
- Overall keeps tested songs, evidence and active modes; its mean percentile is
  omitted. Keep one in-section link to Overall rankings and the existing leaders.
- Frequent Matchups shows three pairs. Offer Show five only when at least four
  pairs have repeated encounters. Elo bands are 50 points wide, in their own
  framed group above the separate number-stat group. Omit the average Elo label.
- Collection records include distinct proper albums per artist and album track
  counts. Singles/unknown albums stay outside proper-album records and averages.
  Use three cards per desktop row; centre a final row of two as a pair between
  the columns above. Collapse to two cards on tablets and one on phones.
- Recognition misses describe the actual track/artist/album being tested. Raw
  incorrect guess text is not saved, so do not present a made-up wrong-guess list.
  Artist/album summaries follow current catalogue links and saved field totals;
  a collaborative track can contribute to each of its linked artists.
- Tournament totals show unfinished brackets inline only when nonzero, plus
  32/16/8-track counts. Show the latest podium and at most five recent champions.
- Artist and album averages each show at most five entries. Top Tags shows up to
  ten linked tags. Recent results mix all modes by completion time; one tournament
  or Shelves round is one item, regardless of its internal matches/track placements.
- Trivia's stored unit is a completed round, not a separately recorded session.
- The Recent Mode Results panel blends only the colours represented in its visible
  rows, weighted by their occurrence counts. A single-mode list keeps that mode's
  colour; an empty list is neutral. Recompute the mix when entries/visibility change.
  Each row retains its own mode colour, with entity names in their entity colours.
- Recent Shelves rounds identify the saved albums and show actual points/available
  points, percent earned, correct album placements and order comparisons. Do not
  represent a ten-track round with a random single song. Preserve saved shelf slots
  when albums are deleted; display missing identities without broken links.
- Tournament results include champion, bracket size, saved matches/points and
  scope. A blind tournament is still pink Tournament; Blind Audition is mint.
- Elo Guesser results identify the chosen track and frozen comparison ratings,
  rather than today's Elo. Trivia exposes only the fields available in that round.
  Correct/perfect outcomes use green and misses use danger red; mode labels and
  other result figures retain the mode's accent.

## Standard Rankings reference — V3.4.2 / V3.4.2.1

The Songs, Artists, Albums and Tags standard ranking boards share this baseline.
Preserve the rank-dependent glow falloff, entity-coloured Top/Bottom switch,
simple centred category selector with its active underline, and existing voting
stat arrangement. Keep Elo orange, Blind mint and collection Impact in the
entity colour. The V3.4.2 content/link fixes remain specific to these boards;
the chosen shared baseline now also styles other ranking groups.

- Entity titles always use their own colour, including before hover. Hover and
  keyboard focus underline the text. Song artist/album metadata uses bold linked
  blue/purple names; album rows show bold blue artist links from actual artist
  relationships, including collaborators and names containing commas.
- Desktop titles are 30 px/900, metadata 18 px with linked names at weight 800,
  voting figures 15 px, primary scores 36 px and score labels 13 px. Covers are
  120 px. Equal 24 px vertical padding and centred grid alignment keep the cover
  the same distance from the top and bottom, even when stats wrap.
- Below 760 px, use 26 px titles, 16 px metadata, 14 px voting figures, 32 px
  scores and 88 px covers. Below 520 px, use 22/15/14/28 px respectively with
  72 px covers. The score moves below the text, while the cover/rank span the
  two rows and remain vertically centred. Keep all cover dimensions constrained
  together; artist art remains circular and tag art remains square.
- Long titles/metadata retain single-line ellipses and full title attributes.
  Counts and scores stay in their existing separate fields.

The separate Style Previews ZIP offers labelled experiments and a reusable demo
template. Its original default was B. The custom codes recorded above are now
approved and applied; other preview alternatives remain proposals. Record later
corrections here before applying them in a future page update.

## Home reference — V3.4.3 through V3.4.3.3

Below Ways to Play, keep exactly three collection total cards: Songs, Artists
and proper Albums. Omit the Tournament total from this group. Keep all three
in one row at every width, with centred labels/values, Arial, 36 px/900 values
and 18 px/800 labels on desktop (28/16 px on phones). Each card uses the
shared corner/padding baseline and retains its entity colour. Large counts can
wrap within their own card without pushing the row offscreen.

The four mode summaries remain beneath Overall.
Keep their order: Trivia Records, Tournament Records, Elo Guesser, Album Shelves.
Each mode has one full-width panel, using the approved Arial/medium type,
24 px outer corners/padding, centred header with Stats link right, existing
mode glow/colour and three centred metrics in **one joined inset row** with
quiet 18 px corners and subtle vertical separators. Numbers and labels stay
on separate lines; keep all three columns at every width. On phones the panel
padding becomes 18 px and primary values 28 px; labels may wrap inside their
own column. Below this row, use a full-width 14 px rounded bar in the mode
colour, with its label/rate above and the underlying counts below. Keep the
shared 36 px values and 17 px labels on desktop (28/16 px on phones).

The three fields and bar are now:

| Mode | Joined row | Bar |
| --- | --- | --- |
| Trivia Records | Best score · Best streak · Tested tracks | Total correct song/artist/eligible album fields divided by total available fields; pool counts rather than average song percentages. |
| Tournament Records | Completed · Tracks entered · Podiums | Completed 32/16/8-track bracket distribution, largest first, in three pink shades with a count/share legend. |
| Elo Guesser | Correct picks · Best streak · Wrong guesses | Correct completed guesses divided by completed questions; a pair counts as one question. |
| Album Shelves | Rounds · Albums played · Perfect shelves | Correct relative-order comparisons divided by eligible ordering comparisons; separate from weighted points and album membership. |

Tournament entries count saved size/entry slots across completed brackets,
including repeat song appearances. Pending brackets do not affect this panel.
Legacy missing sizes may use saved entry counts; display an unavailable total
if neither exists. The three-way bar is normalised over supported bracket
sizes; explicitly show any excluded other/missing sizes beneath it. Albums
played means distinct surviving album IDs saved in completed Shelves rounds,
so later track moves do not change historical participation. Empty rates show
an em dash and an unfilled bar with short guidance, rather than a made-up 0%.
Do not duplicate another page's detailed tables in these home summaries.

All home scrolling banners use **up to ten entries**, including Top Tracks,
Top Artists, Top Albums, Recognisability, Champions, Elo Guesser and Album Shelves.
The common limit is `HOME_BANNER_LIMIT` in `static/js/site.js`, passed to the
special-mode banner builder. Preserve their existing eligibility, sort/order,
empty states, links, controls and auto-scroll loop. This limit is for home
banners; full ranking pages keep their own Top/Bottom twenty limits.

Keep the title, game links, collection totals and Overall box in their current
positions. Scope home composition in `static/css/home.css`; joined rows and
main-box glows are shared in `static/css/components.css`, while the approved
type/geometry baseline remains in `static/css/site_baseline.css`.

## Match History reference — V3.4.4

Keep the selectors above the history list. A shared versus row places the two
covers beside the central VS, with the song/artist/proper-album names outside
on desktop. Names link independently and underline on hover/focus; artwork and
whole rows are not links. Winner songs are green, losers red, artists blue and
proper albums purple. Saved dates sit below VS; frozen before/after Elo belongs
to that saved result, with an explicit current-Elo fallback for older rows.
Standard/blind colours wash in softly from the row edges. Keep the same row
composition in Global Stats Frequent Matchups, whose aggregate pairs show
current Elo and encounter counts rather than a made-up single-match outcome.

## Recognisability Stats reference — V3.4.5

Keep the existing page title and Play Trivia action. Major panels occupy their
own rows, in this order: Trivia overview, Round results, Collection coverage,
Most recognised tracks, Least recognised tracks, Artist answers, Album answers,
Recognition by tag, Recent Trivia. Use `dashboard-surface` with the recognition
accent for every main panel; use shared joined metrics and their dividers for
related figures. Fields and comparisons are quiet inset groups. All statistics,
bars and labels remain gold; entity names use their own semantic colours.

The overview puts four summary figures above a full-width pooled field-accuracy
bar, then the song/artist/eligible-album field cards. Correct and missed counts
share a divided row, with correct-answer timing below. Round results separate
outcome counts/a stacked split from points and 7/30-day activity. Coverage is
explicitly about tracks with current audio previews. Empty rates/timings use an
em dash; an unknown saved result is distinct from a miss or an ineligible album.

Track lists retain ten results, with five visible and five expandable using
native keyboard-accessible details. They use the shared 120/88/72 px ranking-art
scale and 30/26/22 px titles; scores move below the names on phones. Artist/album/
tag comparisons show five highest-accuracy and five most-missed records, inside
one full-width main panel per category. These paired comparisons stack below
1050 px; field cards stack below 760 px. Dense category/recent art is 72 px,
64 px on phones. Constrain all six art dimensions; artist art stays circular.

Use actual relationship links, proper albums only, single-line ellipses with
full title attributes and links on names only. Recent Trivia shows ten saved
rounds initially, with the next ten expandable. Each keeps field outcomes,
round points, saved running score/streak and a local-time date. Avoid nested
scrolling lists. Keep less obvious aggregation/timing/eligibility explanations
in the release notes rather than adding long help text to the stats page.

## Tournament Stats reference — V3.4.6

Use the accepted Recognisability dashboard as the reference, with tournament
pink for headings, data, bars and border glows. Entity names keep green/blue/
purple/amber; match losses stay red. Keep the title and Play Tournament action.
The full-width section order is overview, latest podium, bracket breakdowns,
match activity, collection coverage, track records, artist records, album
records, tag records, seed patterns, bracket history. Frequent summaries come
first; detailed records and individual rounds sit lower down.

The overview joins bracket count (unfinished count inline only when nonzero),
match decisions and track-entry slots. A full-width bar shows completion. Show
the latest top-three podium with 120/88/72 px square covers, centred names and
actual bracket points; previous champions form a compact list of at most five.
Sizes, visibility and scopes have their own quiet, divided rows and pink stacked
bars. A blind tournament stays pink. Distinguish bracket matches from bronze
playoffs; stage names follow saved round numbers and bracket sizes, never the
last currently created round. Keep activity counts separate from stage counts.

Track records are six compact record cards, rather than Top/Bottom boards.
The existing full mode rankings have a link. Artist/album/tag sections show at
most five entries with titles, podiums, points, track and bracket counts. Only
proper albums are linked. Seed patterns use saved seeds, with short labels and
sample denominators; detailed definitions belong in release notes.

History uses native expandable details, ten brackets per page, active brackets
first. Existing `?tournament=ID` links select the correct archive page and open
that bracket; archive links include its anchor. Each bracket keeps its scope,
blind setting, saved matches/results/points/dates and a link to open the game or
podium. Missing/legacy data is explicit, with no guessed identity or result.
Artist art stays circular; all cover sizes constrain all six dimensions. Dense
match art is 52 px (44 px on phones); text and results wrap into their own space.

## Elo Guesser Stats reference — V3.4.7

Use the accepted Recognisability/Tournament dashboards, with Elo Guesser's
red-orange for section headings, figures, bars, borders and soft glows. Entity
names retain their semantic colours. Main panels each occupy one full row:
overview, recent form, collection coverage, Elo gaps, card choices, top tracks,
tracks to practise, artist records, album records, tag records, frequent
comparisons, guess history. Keep the title and a Play Elo Guesser action.

The overview joins completed/correct/wrong/best-streak figures above a full-width
accuracy bar. Four-field groups become two columns on phones, with dividers
reset between rows. Recent form uses current streak, longest miss run and active
days, then the latest ten and rolling 7/30-day accuracy groups. Coverage refers
to finite, different-rated live tracks, with no audio requirement. Gap rows use
short, explicit ranges, a bar and the correct/total/wrong counts; their supporting
records remain below. First/second card labels describe the saved offered order,
so they still make sense when the game stacks its cards on a phone.

Top/practice tracks retain ten results, five visible and five in native details,
using shared 120/88/72 px art and the accepted responsive text scale. Category
records show five high-accuracy and five most-missed entries in quiet insets;
comparisons stack below 1050 px. Pool appearances rather than averaging rates.
Keep denominators visible; explanations of pooling and eligibility live in the
release notes. Proper albums only; artist covers remain circular.

Repeated pairs show at most five comparisons. History has ten native expandable
results per page, newest first, with the first open. Keep the chosen track,
result/points and date in the summary; show both saved ratings, pick/higher-Elo
labels and the running streak inside. Correct pick labels use green, wrong
labels red; other stats stay red-orange. Song links stay green independently of
the answer. Covers flank the centred VS on desktop, with names outside them.
Below 760 px, the two tracks stack around the VS divider, retaining 64 px art
and readable metadata. All six art constraints agree. Pagination, details and
page actions have at least 44 px touch targets. Full entity text is available
through the expandable result/name links, not only a hover title.

Do not use current Elo to rewrite old answers or expose pending questions/tokens.
Missing identities stay unlinked; unavailable rates use an em dash. This page
is a read-only report; changes to its visuals or aggregates must not alter game
selection, scoring, Overall, other mode dashboards or preview behavior.

## Album Shelves Stats reference — V3.4.8

Use the same shared detailed-mode dashboard as Recognisability, Tournament and
Elo Guesser. Shelves data/headings/bars use mauve; borders and soft glows use the
existing deeper aubergine family. Entity names retain green/blue/purple/amber.
Each main panel gets one row, in order: overview, round results, recent form,
round formats, collection coverage, top tracks, tracks to practise, albums
played, artist records, tag records, optional placement breakdown, round history.

Keep **relative track order** as the primary full-width percentage bar above
the later points/placement details. Overview figures are completed rounds,
track appearances, albums played and perfect rounds. Points keep their actual
earned/available denominator; they are not the ordering percentage. Short
rolling-window/format groups pool comparisons and keep counts visible. Join
related figures with the shared quiet dividers; four-column groups become two
columns on phones. Break the long page heading/action onto separate lines by
1050 px, with the action on the right below the centred title.

Track lists keep ten entries, five visible/five expandable, with shared
120/88/72 px covers and linked artist/proper-album metadata. Practice entries
must have missed ordering comparisons. Album/artist/tag records show five
high-accuracy and five most-missed entries. All played albums remain accessible
through a native expandable list with ten per page; avoid nested scrolling.
Artist art stays circular; all other covers remain square with all six sizes
constrained. Names link independently and underline on hover/focus.

Round history has ten native expandable entries per page. Open the first by
default, or the selected `?round=ID` on its correct page. The summary shows the
round/shelf count, date, ordering rate, outcome and points. Inside, give each
saved shelf a quiet inset with its album art/title, ordering/points totals and
tracks in original saved track-number order. Retain submitted shelf/position
and individual points. Correct labels are green, wrong album/order labels red,
and other result data mauve. Song links keep their own green independently.
Keep frozen shelf identity/track number separate from current profile metadata;
missing identities stay unlinked and separate saved shelf slots are retained.

Saved shelves stack below 1100 px, comparison/format/window groups below 1050
px. Dense covers become 64 px on phones; metadata stays readable and important
scores wrap in their own space. Details, pagination and page actions retain
44 px touch targets. Full names remain in accessible text/name links. Empty
rates use an em dash; unavailable history does not become a zero score or a
perfect round. Definitions and legacy scoring details belong in the release
notes. These reports do not change game selection, scoring or previews.

## Detailed-mode shared components — V3.4.6 through V3.4.8

Recognisability, Tournament, Elo Guesser and Album Shelves Stats share
`mode_stats.css` and the formatting
macros in `mode_stats_components.html`. The accepted Recognisability values,
links, section order and visual scale stay the same. Page wrappers supply
`--section-color`, `--surface-accent`, `--mode-stats-border`, `--mode-stats-rule`
and `--mode-stats-divider`; avoid copying a new dashboard's base geometry.
Use the existing shared `joined-metrics` and `dashboard-surface` components.
Page styles own field states, podiums, bracket rounds, saved shelves and other
unique content. Numeric formatting is shared through the `number` macro too.

## Phone use — V3.4.6.1

Phone layout is a required part of every subsequent page/page-group update.
The user already uses modes and rankings successfully from a phone; preserve
those interactions while improving each page. This hosting patch changes no
page composition or CSS. Keep the approved type, geometry, colours and artwork
rules, using their existing smaller-screen sizes rather than shrinking an
entire desktop page.

- Check 320, 360, 390 and 430 px portrait widths, plus compact landscape and a
  tablet width. Include populated/empty states and unusually long names. Check
  readable wrapping, browser zoom and no document-wide horizontal overflow;
  deliberately wide tables may use a clearly bounded local scroller.
- Main dashboard sections stack when needed. Joined metrics follow the shared
  component rules, including Home's three-column totals. Important values and
  outcomes keep their own space rather than disappearing behind an ellipsis.
  Keep covers square with all six dimensions constrained, and artists circular.
- Use roughly 44 px touch areas for action/icon controls, with space between
  adjacent controls. Retain clear selected, disabled, loading and focus states.
  Keep text-entry inputs at least 16 px on phones; check selectors, sliders,
  volume, play/pause/skip and submit/next controls using touch as well as keys.
- Navigation, menus, dialogs and expandable history must fit the viewport and
  remain scrollable. Place actions beneath headings when the shared header
  pattern needs more room. Keep a usable close/back action in dialogs.
- Retain ellipses and full accessible names on variable text, but do not make
  essential information or actions depend on hover. Full entity details should
  remain available by following the name link or opening an explicit detail.
  Give icon-only controls accessible labels; keep visible text on core actions.
- Preserve non-drag alternatives, including Album Shelves menus/up/down
  buttons. Confirm game selection, answering, next rounds and preview controls
  remain usable on touch devices. New audio must respect browser interaction
  requirements; do not assume desktop autoplay permission on a phone.

Record what was actually checked in `VALIDATION.md`. Viewport/DOM checks help
catch overflow and missing controls, but do not claim an on-device Safari or
Android playback/paint check unless one was performed. The user's successful
phone use is the current baseline, not a substitute for checking later edits.

## Implementing later page updates

Use shared components/tokens where their behavior fits. Scope a page's new CSS
for individual page composition changes; keep the approved common baseline
shared across the site. For this reference,
see `templates/global_stats.html`, `static/css/global_stats.css` and the Overall
global summary in `static/js/overall.js`. The data projection is read-only in
`global_stats_data.py`; visual patches do not change scoring rules or add counters.

Check representative populated and empty states, long names, keyboard links,
the phone checklist above, tablet rules and meaningful data calculations. Keep the supplied database
out of validation writes and deliverable ZIPs. Change `version.py` for each patch.
The V3.4 styling rollout's notes all go in `update_logs/V3_4_UPDATE.md`, under
the exact patch number; do not create a separate notes file for every page.


## Mode Rankings — V3.4.9

Overall, Recognisability, Tournament, Elo Guesser and Album Shelves use the
standard ranking board rather than miniature stats dashboards. Share navigation
and row markup through `SongRankerUI.modeRankingControls` / `modeRankingRow`;
reuse `rankingMetadata` from the standard boards and `standard_rankings.css`.
Keep category links underlined when active, one Top/Bottom twenty switch,
mode-coloured score/glow, entity-coloured titles and bold linked metadata.
No secondary metric tab row. Overall retains its existing Tags category too.

Primary order: Overall score; pooled recognised-field percentage; Tournament
championship count; correct-pick appearance percentage; relative track-order
percentage. Show evidence/sample counts beside these, not separate rankings for
points, second/third places or every possible statistic. Existing deep links
with an obsolete metric resolve to the mode's main ranking. Keep detailed stats
on their dedicated dashboards. Tournament ties use podiums, match wins, entries,
then name; rate ties use the available sample count then name. Top/Bottom reverse
the same deterministic board. Untested records and non-proper albums stay out.

Use catalogue metadata/artwork even when Overall returns a minimal score record.
Do not split artist names on commas. Omit singles, unknown or missing albums in
song metadata. Preserve the standard 120/88/72 px cover constraints and type
scale. On phones, context counts wrap and score labels can move onto a new line;
never truncate the sample count or force horizontal scrolling. Category links
wrap and have at least 44 px height. Rankings remain at twenty rows per view;
the home banners' ten-entry limit does not apply here.


## Mode ranking correction — V3.4.9.1

All five mode boards offer Songs, Artists, Albums and Tags. Tags pool the saved
mode counters of their linked tracks, using the same denominators as the other
collections. Tournament's primary order is total saved points, displayed to two
decimal places, replacing titles. Existing tie-breaks remain podiums, wins,
entries, name. Active category links keep the underline and add a soft glow in
the entity colour: green song, blue artist, purple album, amber tag. Row scores,
rank glows and Top/Bottom switching retain the mode colour. Category links
continue to wrap with 44 px targets on phones.


## Search reference — V3.4.10 through V3.4.10.2

The header search is unchanged. The main Search page uses one controls panel,
entity-coloured category pills with result counts, live search, rating/name/random sort,
clearable tag scope and forty-card Load more increments. Preserve the catalogue
matching/URL query behavior. `search.js` owns this page's state, result markup,
achievement rules and resize handling; `search.css` owns its composition. Load
both only on Search. Keep shared baseline tokens and dashboard surface glows.

All four categories use the same two-column desktop card grid (one column below
1100 px). Cards are articles with name/metadata links rather than nested links
inside a whole-card link. Names keep entity colours; song scores use Elo orange,
collection scores use their entity colour. Metadata is bold linked artists and
proper albums from actual relationships. Tags use square # artwork, description,
song count, Impact and achievements; artists remain circular. Covers constrain
all six dimensions to 96 px desktop / 72 px phone. Titles are 26/22 px,
metadata 18/15 px, scores 32/28 px. Names/descriptions truncate with full titles;
counts and scores remain separate. Phone cards move the score below copy.

Achievements use **one row**, at most three whole badges, prioritised before
rendering; hide badges from the end when the card narrows and restore on resize.
Championships rank first, then perfect mode rates, silver/bronze, other high mode
rates and strong voting records. Show only the best tournament placement class.
Use each mode's colour. Rate rules: Trivia >=90% with >=2 eligible fields;
Guesser >=90% with >=2 track appearances; Shelves relative order >=90% with
>=6 comparisons; standard/blind voting >=90% wins with >=5 appearances in that
voting mode. No achievements for ordinary activity or unavailable rates.
Collections pool linked-track numerators/denominators, never percentages;
untested tracks add no rate evidence. Count-based podium badges sum track
placements, including multiple tracks in the same collection/bracket. These
are achievements from saved results, not new scoring or global streaks.

V3.4.10.1 places total/shown results between the category buttons and Sort.
The toolbar uses three columns on wide screens, then categories above the
count/sort pair, then category → count → sort on phones. V3.4.10.2 replaces
the native select with a custom button/listbox so the open menu also follows
the shared styling: accent-bordered pill trigger, quiet rounded dark popup,
mode-tinted hover/focus/selected rows and a selected checkmark. Keep the trigger
48 px and options at least 46 px, with clear focus outlines.

The button exposes its current label and expanded state. Opening focuses the
selected option. Support arrows, Home/End, first-letter navigation and Enter/
Space selection; Escape restores trigger focus, Tab exits naturally, and outside
click/focus closes without stealing focus. Open upward when space below is tight;
constrain the popup to the viewport and close on resize. Use the shared page
accent and inset radius, with no native browser option popup or global dropdown
restyling. Search owns this small three-option control.

Empty searches default to Random, with one shuffled entity order per category
per visit. Load more and category round trips preserve that order; reselecting
Random after another sort requests a new shuffle. Query edits select Highest
rating when nonblank and Random when cleared. Explicit dropdown choices and
URL sort choices remain usable; query links without a sort default to Highest
rating. Persist all sort choices in the URL, including Highest rating on an
empty search. Reloading a random view produces a fresh shuffle.


## Entity profiles — V3.4.11 / V3.4.11.1

Song, Album, Artist and Tag profiles share `profiles.js` for key-stat markup,
mode summaries, visible detail groups and preview captions, and `profiles.css` for
profile-only composition. Load these only on the four entity routes. Player
state, transports, queues and track ordering remain in site.js; Overall still
uses its shared renderer/calculation and Mode balance dropdown.

The order is hero → four key stats → Overall → collection highlights (where
available) → Voting → Recognisability → Tournament → Elo Guesser → Album Shelves
→ collection albums → track list / recent matches as applicable. Overall and its
loading/error/retry surface mount after `.profile-key-stats`, replacing their
former position directly below the hero. Keep key stats in four columns on
wide screens and two on phones, with centred values/labels and semantic glows.

Keep every entity name inside `.profile-copy`, beside its artwork on desktop.
The tag title is not a direct grid child or a separate centred row above the
artwork. Hero artwork is 240 px desktop / 200 px tablet and phone, constrained
in all six dimensions; artists remain circular. Below 600 px, stack artwork and
copy with a centred title. Preserve full accessible titles and ellipses; tag
prose can wrap. Song metadata and track lists omit non-proper/missing albums.

Each mode has one full-width, mode-coloured panel with a soft border/glow,
centred header and links right. Show the useful counts in shared joined rows,
then a full-width rate where relevant. Show field accuracy, voting splits,
podiums/brackets and Shelves placement/points in quiet open inset groups.
Only Overall retains its expandable Mode balance section. Avoid duplicate
headline/secondary figures; Tournament uses points/brackets/podiums above the
first/second/third row. Untested rates show
an em dash; zero activity counts stay zero. Use two-column wrapping for
four-field groups through the shared component. Three-field figures may scale
to 20–25 px on small phones so denominators do not crowd the row.

Use saved, pooled counters, not averages of percentages. Tournament points,
titles and podiums are the main figures; further breakdowns retain bracket count,
win rate and deep links. Guesser counts track appearances, and Shelves leads
with relative track order rather than points percentage. All four collections,
including Tags, link to the corresponding mode ranking category. No invented
per-entity global streaks, sessions or perfect-round records.

Collection preview information sits inside the cover as a sibling overlay to
the play button, not a separate box or a nested link/button. Show only the linked
track name and small index/count once a track has been chosen. No duration,
artist or initial Preview mix caption. Keep text legible over artwork, preserve
artist circles, and leave play/skip controls usable. Song profiles have no loop
caption; playback itself is unchanged. Skip controls keep 44 px targets and
track-list controls 48 px, with 72 px covers (56 px phone) and separate scores.
Albums and recent matches are visible without an expansion control; full
History stays linked. Link names rather than whole highlight/gallery cards.

Artist/Album tag chips are sorted by the number of distinct linked songs with
that tag, descending, with name/ID tie-breaks. Display their matching counts.
Fit only the first two rows at the available width, hide the rest from keyboard
focus, and restore on resize. Keep uniform 36 px chips / 8 px row gap and a
quiet two-row overflow fallback. Song tags remain unrestricted; Tag profiles
have no related-tag list. Do not apply the row limit to either of those pages.

Metric values explicitly use `--section-color` (with page-colour fallback).
Inheritance alone is insufficient because the older `.mini-stats b` rule sets
Tournament pink directly. Profile-scoped value rules must beat that rule, while
labels stay muted and Blind subgroups keep their mint section colour. Top key
stats retain their existing entity/Elo colours. Review the actual CSS load order
when verifying semantic colours, including expanded/open inset groups.
