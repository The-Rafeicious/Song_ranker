# Styling guide

Shared design rules and detailed page/tool specifications, organised by where
you need them. Current changes are recorded below; older origin labels are historical.
Original version labels are provenance, not a sequence to reapply. Within each
group, a later correction overrides an earlier conflicting rule. Explicitly
expired passages are historical context; retained detail remains available.

- [Shared foundations](#shared-foundations)
- [Home](#home)
- [Rankings and search](#rankings-and-search)
- [Entity profiles](#entity-profiles)
- [Game screens](#game-screens)
- [Statistics pages](#statistics-pages)
- [Developer tools](#developer-tools)

## Shared foundations

- [Approved shared baseline](#approved-shared-baseline)
- [Shared owners](#shared-owners)
- [Composition](#composition)
- [Type and hierarchy](#type-and-hierarchy)
- [Colour and interaction](#colour-and-interaction)
- [Artwork and rows](#artwork-and-rows)
- [Detailed-mode shared components](#detailed-mode-shared-components)
- [Phone use](#phone-use)
- [Implementing later page updates](#implementing-later-page-updates)


<a id="approved-shared-baseline--v3421"></a>

### Approved shared baseline

*Origin: Approved shared baseline — V3.4.2.1*

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

<a id="shared-owners--v3433"></a>

### Shared owners

*Origin: Shared owners — V3.4.3.3*

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

### Composition

*Origin: Composition*

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

### Type and hierarchy

*Origin: Type and hierarchy*

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

### Colour and interaction

*Origin: Colour and interaction*

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

### Artwork and rows

*Origin: Artwork and rows*

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

<a id="detailed-mode-shared-components--v346-through-v348"></a>

### Detailed-mode shared components

*Origin: Detailed-mode shared components — V3.4.6 through V3.4.8*

Recognisability, Tournament, Elo Guesser and Album Shelves Stats share
`mode_stats.css` and the formatting
macros in `mode_stats_components.html`. The accepted Recognisability values,
links, section order and visual scale stay the same. Page wrappers supply
`--section-color`, `--surface-accent`, `--mode-stats-border`, `--mode-stats-rule`
and `--mode-stats-divider`; avoid copying a new dashboard's base geometry.
Use the existing shared `joined-metrics` and `dashboard-surface` components.
Page styles own field states, podiums, bracket rounds, saved shelves and other
unique content. Numeric formatting is shared through the `number` macro too.

<a id="phone-use--v3461"></a>

### Phone use

*Origin: Phone use — V3.4.6.1*

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

### Implementing later page updates

*Origin: Implementing later page updates*

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

## Home

- [Home reference](#home-reference)
- [Vibe library surfaces](#vibe-library-surfaces)
- [Vibe follow-up](#vibe-follow-up)


<a id="home-reference--v343-through-v3433"></a>

### Home reference

*Origin: Home reference — V3.4.3 through V3.4.3.3*

> **Current exception:** there are six mode buttons. The Vibe library card and combined top-twenty-per-category banner are additional Home surfaces; its limit overrides the older ten-entry banner rule for Vibe only.

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

<a id="vibe-library-surfaces--vibe-map-v107"></a>

### Vibe library surfaces

*Origin: Vibe library surfaces — Vibe-Map-v1.0.7*

Place Home's compact all-song map card immediately below Overall Leaders, and
Global Stats' Vibe summary immediately below Overall. Keep four small maps per
wide row and two columns on phones. Use existing joined metrics and dashboard
glows. The final Home banner mixes the top twenty albums, artists and tags in one
consistency-ordered strip without category pills, using existing shelf cards, scroll buttons and autoplay
ownership. Scores/frames are Vibe red; entity names, artwork shapes and track
counts retain purple/blue/gold/green semantics. Pause scrolling for focus/hover
and honour hidden tabs/reduced motion through the shared owner.

Vibe Map is last in Mode Rankings, with albums/artists/tags and no song tab.
Reuse shared Top/Bottom twenty controls and ranking row geometry, bounded names,
artwork, semantic identity links and red rank-dependent glows. Show mapped/total
counts with consistency; retain absolute ranks on the bottom board. Add context
ranking links to collection profile cards and the dedicated Vibe stats page.
Do not add a performance score or Overall contribution for Vibe Map.

<a id="vibe-follow-up--vibe-map-v1071"></a>

### Vibe follow-up

*Origin: Vibe follow-up — Vibe-Map-v1.0.7.1*

Keep one shared scrolling owner and its arrow controls for the combined banner.
Preserve entity colours/art shapes and Vibe-red frames/scores. Scope coverage
caption margins to the direct caption; the progress fill must fill the track’s
height with no text margin. Include Vibe saves in Global’s activity chart and
recent-results colour blend. One retained update per song is the available
activity unit; do not label it a complete pass or an exhaustive round history.

## Rankings and search

- [Standard Rankings reference](#standard-rankings-reference)
- [Mode Rankings](#mode-rankings)
- [Mode ranking correction](#mode-ranking-correction)
- [Search reference](#search-reference)


<a id="standard-rankings-reference--v342--v3421"></a>

### Standard Rankings reference

*Origin: Standard Rankings reference — V3.4.2 / V3.4.2.1*

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

<a id="mode-rankings--v349"></a>

### Mode Rankings

*Origin: Mode Rankings — V3.4.9*

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

<a id="mode-ranking-correction--v3491"></a>

### Mode ranking correction

*Origin: Mode ranking correction — V3.4.9.1*

All five mode boards offer Songs, Artists, Albums and Tags. Tags pool the saved
mode counters of their linked tracks, using the same denominators as the other
collections. Tournament's primary order is total saved points, displayed to two
decimal places, replacing titles. Existing tie-breaks remain podiums, wins,
entries, name. Active category links keep the underline and add a soft glow in
the entity colour: green song, blue artist, purple album, amber tag. Row scores,
rank glows and Top/Bottom switching retain the mode colour. Category links
continue to wrap with 44 px targets on phones.

<a id="search-reference--v3410-through-v34102"></a>

### Search reference

*Origin: Search reference — V3.4.10 through V3.4.10.2*

The header search is unchanged. The main Search page uses one controls panel,
entity-coloured category pills with result counts, live search, rating/name/random sort,
clearable tag scope and forty-card Load more increments. Preserve the catalogue
matching/URL query behavior. `search.js` owns this page's state, result markup,
achievement rules and resize handling; `search.css` owns its composition. Load
both only on Search. Keep shared baseline tokens and dashboard surface glows.

V5.0.4.3 removes the redundant entity-type badge above each result title.
Keep the category toolbar and entity-coloured title links. Song cards show a
separate gold (`--tag`) line below metadata with their distinct attached-tag
count, including “0 tags” and singular “1 tag”. Other categories have no added
tag-count line. Use consistent 8 px copy gaps (6 px on phones) so names, metadata
and tag descriptions have room without reserving an empty badge row.

V5.0.4.3.1 gives album and artist cards a separate green (`--song`) song-count
line with singular/plural labels. Album metadata retains artist links without
repeating its song count. Artists with proper albums have a separate purple
(`--album`) album-count line; count distinct releases linked through their
songs, excluding Singles. Omit the album line when there are no proper albums.

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
Keep the achievement row at 28 px, non-wrapping, clipped within the card’s
content width and isolated from intrinsic inline sizing. Long title counts or
percentage badges must never widen the card or create another badge row.
Measure whole badges including gaps; an oversized badge is hidden, not cropped.
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

## Entity profiles

- [Shared profile layout](#shared-profile-layout)
- [Independent Elo comparisons](#independent-elo-comparisons)
- [Overall direct display](#overall-direct-display)
- [Entity profile simplification](#entity-profile-simplification)
- [Vibe Map entity cards](#vibe-map-entity-cards)
- [Compact Vibe profile follow-up](#compact-vibe-profile-follow-up)


<a id="entity-profiles--v3411--v34111"></a>

### Shared profile layout

*Origin: Entity profiles — V3.4.11 / V3.4.11.1*

> **Partly expired:** disclosure/listening instructions in this earlier profile specification are superseded by “Entity profile simplification” and the compact Vibe profile rules below.

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

<a id="independent-elo-comparisons--v4003"></a>

### Independent Elo comparisons

*Origin: Independent Elo comparisons — V4.0.0.3*

Keep the existing profile Voting Record panel and key public-Elo/Impact stats.
Add independent mode ratings in its open detail group, using existing two-column
insets, joined metric rows and phone stacking. Non-blind stays orange and Blind
mint. Show rated vote/appearance counts and the first-round tournament subset.
Unplayed mode ratings/gaps show an em dash, even though their internal baseline
is 1200. Artist/album/tag means use the same distinct tracks rated in both modes;
show cohort coverage and keep the existing public Impact metric unchanged.

Voting Stats adds one Independent Elo across modes section after the ordinary
mode comparison. Reuse existing dense record rows and responsive result placement;
show signed raw Elo differences and both stream counts, at most five per direction
with three rated votes in each mode. Describe differences as observed, without
claiming causal bias. No percentile scaling or new ranking order is introduced.
Tournament setup explains new first-round influence before Start; each active
match states full/half Elo influence or points only. Preserve hidden blind
identities, pink tournament styling, points reveals and audio handoffs.

<a id="overall-direct-display--v4004"></a>

### Overall direct display

*Origin: Overall direct display — V4.0.0.4*

All Overall figures/bars use the existing composite percentage directly. Keep
rank separate, with exact ties sharing competition rank and full precision
ordering. Profiles show rank beside relative evidence or collection confidence;
Overall ranking rows use the same standing, including Bottom. The shared
`modeRankingRow` accepts an optional rank for Overall; other mode boards retain
their existing positions. Preserve Home/Global leader geometry and entity colours.
Unknown scores show an em dash and have no numeric progress state.

Keep Mode balance as a native disclosure with its marker, keyboard behaviour
and a 44 px target. Each quiet mode inset shows Adjusted score, Effective weight,
Contribution in points and Relative evidence, with mode-coloured values/bars.
Collection effective weights include confidence; show the neutral share so all
unrounded contributions reconcile with Overall. The confidence prior adds no
tested modes or evidence. Keep the weighted-score/evidence distinction visible.

Use two inset columns on wide screens and one below 760 px; inside each inset,
keep a bounded two-column metric grid with wrapping labels/values. Below 540 px,
the main score spans the card above its two context columns. Reuse the shared
dark panels, corners and typography, preserving 320–430 px usability. Dev lookup
explains direct composites and collection arithmetic without the superseded
percentile transformation. No other page layout is changed in this step.

<a id="entity-profile-simplification--v5041"></a>

### Entity profile simplification

*Origin: Entity profile simplification — V5.0.4.1*

This replaces earlier profile disclosure/listening-summary instructions; other
pages retain their existing reporting. Song, artist, album and tag profiles use
one shared panel structure: heading with stats links, joined summary, primary
rate and useful inline breakdowns. Keep Non-blind/Blind Elo cards, recognition
fields, podium counts and shelf rates visible. Remove repeated explanations,
per-bracket history, nested independent-rating disclosures and profile listening
diagnostics. Overall alone retains Mode balance, with figures and short labels
but no explanatory paragraphs.

Artwork, play overlay and player frame must use the same inner corner radius.
Artist hero layers remain circular, including clipping; song/album heroes retain
rounded corners. Preserve the over-art playback controls and current hero sizes.

Tag album lists begin with six cards and expand by six. Artist, album and tag
song lists begin with thirty rows and expand by thirty. Put Show more centred
at the bottom of each list and remove it when exhausted. Expansion appends rows
to preserve active previews; the hero queue still includes every linked preview.

<a id="vibe-map-entity-cards--vibe-map-v106"></a>

### Vibe Map entity cards

*Origin: Vibe Map entity cards — Vibe-Map-v1.0.6*

Centre the selected identity block at the top of the reusable song card,
including its metadata. Song profiles use that same compact radar/matches card
immediately above Overall. Album, artist and tag profiles use the same red mode
panel in that position, with consistency and fully mapped/total counts first;
show partly mapped counts when nonzero. Place four small maps in two rows of two,
including on phones, and cap the combined grid at 480 px. Keep endpoint labels
readable, use fixed 11 px dots (larger than the main stats dots), retain exact
positions and show track names on hover. No disclosure or explanatory blocks.

Vibe cards load independently of Overall and never remount the hero preview.
Show short retry states locally. Missing maps are absent points; consistency
requires two fully mapped tracks and uses the existing dashboard definition.

<a id="compact-vibe-profile-follow-up--vibe-map-v1061"></a>

### Compact Vibe profile follow-up

*Origin: Compact Vibe profile follow-up — Vibe-Map-v1.0.6.1*

Hide the profile panel completely, including its loading placeholder, until a
song has four placed maps or a collection has two fully mapped members. Keep
its hidden anchor for stable placement above Overall; unknown/failed requests
still get a short local retry state. The main stats inspector retains partial
maps and the selected identity. Dedicated song cards omit that duplicate identity.

Collection maps occupy one row of four above 760 px, capped at 960 px across;
narrow screens keep two columns for readable labels. Keep every caption aligned,
small charts and fixed 11 px dots. Display Connection's low Y pole as Budding
rather than Casual, using a presentation override only; keep stored definitions,
map keys, generation, coordinates and similarity unchanged.

## Game screens

- [Shared game layout](#shared-game-layout)
- [Challenge runs](#challenge-runs)
- [Final V4 pacing](#final-v4-pacing)
- [Game screen refinements](#game-screen-refinements)
- [Vibe Map play screen](#vibe-map-play-screen)


<a id="game-screens--v3413"></a>

### Shared game layout

*Origin: Game screens — V3.4.13*

Standard Vote (Non-blind and Blind), Trivia, Tournament, Elo Guesser and Album
Shelves share game-only `gameplay.css` and `gameplay.js`, included only on those
five routes. Keep the established stylesheet order and approved baseline last.
The game stylesheet owns play-screen composition, controls and outcome states;
`GameplayUI` owns the Tournament scope menu. Game modules still own requests,
selection, scoring, reveal sequencing and audio handoffs. Rankings, profiles,
Search and dashboards do not load these game assets.

Keep mode-coloured headings, primary actions, focus and VS indicators. Entity
names remain green/blue/purple, Elo orange, Tournament points pink and Shelves
points mauve. Winner/correct cards use green borders and the shared soft glow;
loser/incorrect cards use danger red. Result buttons remain legible when locked.
Anonymous covers follow the current mode, including pink in blind tournaments.
Covers remain square, with a 355 px maximum on pair games and 230 px on Shelves;
constrain all six child artwork dimensions together. Touch play/pause overlays
remain visible without hover. Below 700 px, pair games stack with a centred VS.
Retain the automatic next-round timing and offer an explicit Next action too.

Tournament setup uses native radio groups in quiet inset choice cards for
8/16/32 tracks and Non-blind/Blind type. Scope uses a styled button/listbox for
Whole library, Artist, Album and Tag, followed by the existing searchable scope
picker. Keep eligibility counts, disabled ineligible results, selected state and
start readiness visible. Both bracket types retain Tournament pink. The popup
has 54 px rows, arrows/Home/End/typeahead/Enter/Space, Escape focus restoration,
natural Tab exit, outside dismissal and upward opening near the viewport edge.
Do not change tournament seeding, size eligibility, points or saved brackets.

Trivia keeps current and best run figures beside the cover on desktop, with
gold values and readable wrapping. Below 760 px, put the 200 px square cover
above the two metric columns. Use entity-coloured field labels, consistent
correct/error accents and at least 16 px inputs. Reveal answers is an explicit
touch action calling the existing round-finish path; keep start/pause, timing,
field checking, scoring and automatic progression intact.

Shelves placement menus and up/down actions remain non-drag alternatives with
44–46 px targets, readable menus and bounded/upward popups. Three shelves stack
below 1050 px; two stack on smaller tablets. Use larger square album artwork,
quiet aubergine borders and mauve mode figures. After reveals, correct actual
track numbers are green; incorrect submitted positions remain red beside them.
Both use the same compact 14 px/900 type, with a full accessible position label.

Reveal albums in their displayed order, with tracks in each album's actual
track-number order. Count each revealed track's saved points on that album's
cover only. When that album's last reveal finishes, add its unrounded subtotal
to the main score, finish that count, then reveal the next album. Show progress
and Added to total on completed album covers. Handle zero totals and two/three
albums; final displayed points equal the saved result. Count animations and
pending transfers must stop on cancellation/page exit. Reduced motion removes
flips/pulses/count animation while retaining the same sequence. Scoring,
per-track denominators, preview buffering and fades remain unchanged.

<a id="challenge-runs--v4006"></a>

### Challenge runs

*Origin: Challenge runs — V4.0.0.6*

Trivia and Elo Guesser retain their accepted game composition, controls, semantic
colours and reveal timing. Show the active streak requirement above Trivia's
timer, with a quiet separate classic-record line. Challenge best score/streak
are the primary records; an unfinished classic round is explicitly labelled
Classic and explains that the next question starts a challenge. Artist points
can remain green while the requirement failure ends the streak. Keep both
facts visible, with the existing manual Restart/Next action.

Guesser keeps its two cover cards and four counters; label challenge streak and
best, explain that pairs get closer, and show the classic best separately.
`gameplay.css` owns the small wrapping `.challenge-note`; retain at least 16 px
requirement text, bounded flex children and no extra nested card. No control or
answer state depends on hover. Phone/desktop game layout and preview ownership
remain as in V3.4.13.

Home and detailed/global stats lead with challenge bests and use a quiet caption
for classic records. Accuracy continues to include both rules. Saved history
labels Classic/Challenge and uses that round's own stored streak. Missing frozen
Trivia identities stay readable without fabricated entity links. Developer
manual record edits explicitly refer to classic records; challenge bests come
from completed runs.

<a id="final-v4-pacing--v400--step-8"></a>

### Final V4 pacing

*Origin: Final V4 pacing — V4.0.0 / step 8*

Keep the approved five game compositions, colours, controls and scoring. A
collapsed Round pacing disclosure sits above the game, outside the replaced
main content, and persists through round renders. Standard remains the default;
Quick and Prepare next round have native labelled controls, 16 px text and
44 px targets. Use quiet shared dark panels, 18 px corners and wrapping fields;
stack settings on phones. Settings apply only on the game routes.

Quick shortens result waits and per-track reveals without removing any saved
outcome or album-to-total transfer. Reduced motion still suppresses animation.
The prior result stays visible while the next JSON question loads; disable
repeat advance clicks and show a readable retry error. Preparing a question
starts neither audio nor the Trivia clock. Hidden tabs suspend result progression;
active Trivia requests a pause and resumes only after a deliberate action.
Keep all pair games/Shelves silent on fresh entry and preserve continuous audio
only within an already started Trivia run. Shared flow timing lives in
`round_flow.js`; audio/caching remains with the existing preview owners.

<a id="game-screen-refinements--v411"></a>

### Game screen refinements

*Origin: Game screen refinements — V4.1.1*

Keep play screens concise: retain identities, scores, errors, live progress,
eligibility and a short frozen Trivia streak target. Put general rule/policy,
keyboard and historical-record explanations in the README rather than the mode
layout. Tournament scope options use their names; selection counts and start
readiness still explain what is available.

The result-speed/preparation controls belong in a compact clock disclosure
beside navbar volume, shared by all five games. Keep it outside the play area,
closed initially, keyboard accessible and bounded to the viewport. Escape closes
this menu without invoking a game shortcut. Do not restore a full-width pacing
panel above the title.

Eligible first-round Tournament results show pink points followed by orange
public Elo before/after values and signed green/red deltas on both cards.
Use 7.5 seconds Standard / 4.4 seconds Quick for this two-stage reveal; later,
bronze and legacy points-only matches keep their ordinary wait. Stage changes
replace only score overlays so the playing preview and its pause state survive.
The progress bar and automatic next share the frozen result duration. Next/page
exit cancels pending stage changes. Reduced motion retains the same sequence.

Tab switching keeps requested audio playing. Result presentation timers wait
while hidden, while active Trivia's audio and answer clock continue together.
Explicit pause/stop stays in effect across tab return; actual page navigation
still cleans up owned players and timers.

<a id="vibe-map-play-screen--vibe-map-v1042"></a>

### Vibe Map play screen

*Origin: Vibe Map play screen — Vibe-Map-v1.0.4.2*

Home has six modes, three by two on desktop, two columns on tablets and one on
small phones. Vibe Map is last, labelled 📍 Vibe Map in Home/Game Modes, with
red `--vibe` lighting and song/album/artist identity colours preserved.

The stable song card sits beside the map container's vertical centre. On desktop
it sticks within that container as the page scrolls, centred in the viewport when
possible; compact its cover at shorter viewport heights. Measure actual card
height rather than assuming all titles are one line. Stacked tablet/phone layouts
use normal document flow so the player never covers the graph.

Keep the current map title at the top, followed by concise progress. No placement
subtitle, X/Y sliders, coordinate readouts or N/A button. Retain continuous pointer
and keyboard positioning. X endpoint labels sit inside the graph alongside the
horizontal axis, not below it. Y endpoints stay above/below the graph. Use a soft
central glow, solid axes and a subtle outward axis pulse on placement/movement;
no rigid contour circles. Suppress the pulse for reduced motion.

Save state and its progress bar sit below the song's back/Finish/forward controls,
not at the bottom of the map. Automatic next-map saves remain; completed maps stay
editable until Finish. Never automatically open results. On results, show the
radar and two similarity matches without a raw-value legend or Readjust button.
The existing Finish control becomes Next song. Keep the audio element stable.

Shared radar geometry/styles live in `vibe_charts.js`/`vibe_charts.css`; follow the
API's related-pole order, retain accessible pole labels, and leave missing spokes
as gaps. Entity stats pages place Vibe Map immediately above Overall; future mode rankings put
it last. Those pages are not part of this mode patch.

Generation 2 uses Pace & mood, Sound & impact, Connection and Perspective.
All endpoints are single words; Perspective alone labels its X midpoint Present
just below the central axis. Radar order is Happy, Hopeful, Future, Secure,
Devoted, Powerful, Electronic, Upbeat. Keep all eight dimensions, no raw legend,
and the existing manual Finish → Next song flow.

## Statistics pages

- [Global Stats reference](#global-stats-reference)
- [Match History reference](#match-history-reference)
- [Recognisability Stats reference](#recognisability-stats-reference)
- [Tournament Stats reference](#tournament-stats-reference)
- [Elo Guesser Stats reference](#elo-guesser-stats-reference)
- [Album Shelves Stats reference](#album-shelves-stats-reference)
- [Standard Voting Stats](#standard-voting-stats)
- [Stats and selection health](#stats-and-selection-health)
- [Adaptive Impact](#adaptive-impact)
- [Dev searches, Shelves and combined Elo](#dev-searches-shelves-and-combined-elo)
- [Voting Record balance](#voting-record-balance)
- [Vibe Map dashboard](#vibe-map-dashboard)
- [Vibe Map song inspection](#vibe-map-song-inspection)


### Global Stats reference

*Origin: Global Stats reference*

The accepted major order is: top collection/mode totals, Collection Records,
Overall Stats, Voting Results (including Frequent Matchups), Elo Distribution,
Recognisability, Tournaments, Elo Guesser, Album Shelves, Artist Average Elo,
Album Average Elo, Top Tags, Recent Mode Results.

- Top totals have two rows of four cards. The second row follows the mode
  sections: Trivia, Tournament, Elo Guesser, Album Shelves.
- Every joined metric group, including dynamically mounted Overall, uses the
  shared dividers. Use two/three/four fields as appropriate and reset divider
  placement when four fields wrap to two columns.
- Overall keeps tested songs, evidence and active modes; its mean score is
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

<a id="match-history-reference--v344"></a>

### Match History reference

*Origin: Match History reference — V3.4.4*

Keep the selectors above the history list. A shared versus row places the two
covers beside the central VS, with the song/artist/proper-album names outside
on desktop. Names link independently and underline on hover/focus; artwork and
whole rows are not links. Winner songs are green, losers red, artists blue and
proper albums purple. Saved dates sit below VS; frozen before/after Elo belongs
to that saved result, with an explicit current-Elo fallback for older rows.
Standard/blind colours wash in softly from the row edges. Keep the same row
composition in Global Stats Frequent Matchups, whose aggregate pairs show
current Elo and encounter counts rather than a made-up single-match outcome.

<a id="recognisability-stats-reference--v345"></a>

### Recognisability Stats reference

*Origin: Recognisability Stats reference — V3.4.5*

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

<a id="tournament-stats-reference--v346"></a>

### Tournament Stats reference

*Origin: Tournament Stats reference — V3.4.6*

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

<a id="elo-guesser-stats-reference--v347"></a>

### Elo Guesser Stats reference

*Origin: Elo Guesser Stats reference — V3.4.7*

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

<a id="album-shelves-stats-reference--v348"></a>

### Album Shelves Stats reference

*Origin: Album Shelves Stats reference — V3.4.8*

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

<a id="standard-voting-stats--v3412"></a>

### Standard Voting Stats

*Origin: Standard Voting Stats — V3.4.12*

`/voting_stats` reports Standard Vote's Non-blind and Blind history. Use the
shared mode_stats template macros, joined metrics, record rows and artwork,
plus shared VS geometry. Keep a dedicated read-only reader and one consistent
SELECT snapshot. The page loads its own composition CSS only on this route;
no extra client controller or scoring counters are needed.

Order: overview/mode mix → Non-blind/Blind comparison → activity → coverage →
shared current Elo distribution → saved Elo movement/gaps → track Elo movement
→ track records → across-mode rate differences → frequent matchups → upsets →
artist records → proper-album records → tag records → paged recent votes.
Major panels occupy full rows. Lists show at most five records; recent votes
show ten per page. Keep the data visible rather than adding metric tabs or
expansion controls. Add the page to Stats navigation and profile voting links.

Combined voting/Elo panels use orange; Blind comparison insets, figures and
result labels use mint. Entity names keep green/blue/purple/amber and losing
match names use danger red. Use quiet divided metric rows and existing soft
surface glows, with readable empty/unknown states. Side-by-side comparisons
stack below 1050 px. Record results move below copy on phones; compact VS rows
stack artwork/name on each side of a central VS separator below 600 px, keeping
both covers, ratings, mode and dates. Category artist art remains circular.
All six fixed artwork constraints must agree.

Shared Elo is the current combined rating across both voting modes, not a
separate mode rating. Match gaps, gains, upsets and win rates use saved history;
never substitute today's Elo for missing snapshots. Skip self-pairs and missing
participant IDs, retain unavailable track identities without broken links, and
keep unknown rates unavailable. Collection rates pool saved track appearances.
Use short units/labels on the page and document less obvious denominators,
UTC activity days, sample minimums, streak eligibility and Elo spread in notes.
The recent-history mode filter and pagination do not change lifetime panels.

<a id="stats-and-selection-health--v412"></a>

### Stats and selection health

*Origin: Stats and selection health — V4.1.2*

Keep the six detailed/global dashboards in their existing semantic colours and
dark panel language. Lead with key numbers; use one shared Last 14 days report,
stacked daily activity bars and a percentage line where the denominator is
meaningful. Always retain precise counts, pooled numerator/denominator and an
accessible daily table. Label UTC and the 0–100% line scale, keep zero dates,
break lines for unavailable rates, and disclose supporting calculation notes.
Do not replace missing evidence with 0%. Charts collapse to one column on phones.

All Elo-history displays include eligible first-round tournament events with a
bracket link, origin, Blind/Non-blind mode, half/full influence and saved rating
changes. Keep ordinary voting lifetime/exposure figures separately labelled.
History filters precede pagination/limits. Use the common VS row and a compact,
stacked responsive version inside song profiles; preserve both songs' metadata.

Developer System → Selection health uses shared action sizing, joined metrics,
semantic bars, two-column pool cards and a bounded searchable draw-weight table.
Keep exact percentages beside relative bars and state whether a figure is an
anchor/first-entry share or an album base weight. Coverage labels describe what
is measured. Explanations stay short and identify only meaningful scope limits.
Refresh reads a new snapshot; navigation/late responses cannot replace another
view. Preserve the existing catalogue, game and Overall layouts outside this
stats/health scope. The baseline remains the last stylesheet.

<a id="adaptive-impact--v414"></a>

### Adaptive Impact

*Origin: Adaptive Impact — V4.1.4*

The latest user request replaces the public collection Impact formula while
keeping the accepted board/profile layout, colours, art and controls. Artists,
proper albums and tags use the current-library-relative, breadth-supported mean;
main boards, home shelves, search, profiles and Dev must agree. Show Impact to
one decimal so useful gaps remain visible; sort on full precision. Song Elo and
Overall retain their existing calculations/display. Empty collections retain
search/edit/profile access with `—` for Impact/rank and do not occupy board or
home leader slots. This supersedes earlier keep-Impact-unchanged wording.

<a id="dev-searches-shelves-and-combined-elo--v415"></a>

### Dev searches, Shelves and combined Elo

*Origin: Dev searches, Shelves and combined Elo — V4.1.5*

Dev library/table searches use query and text-action grid columns with bounded
children, individual 44 px fields and natural-width buttons. Apple search uses
query/store/action columns, then a full action row on narrower screens. Source
search dialogs follow the same rules. Do not inherit the generic search form's
42 px round icon button or clipped pill wrapper for these text actions.

Keep table conditions independent by category across navigation and tab reloads;
show the active count, current sort direction and an explicit Clear filters.
Clamping a page after data edits must retain the query/conditions. Column
visibility and editing/actions retain their existing owners and layout.

Shelf subtotal overlays must paint above image layers and stay on the cover.
Count up from the preceding subtotal as each track is revealed, show its point
increment, then transfer that completed album once to the main score. Keep the
existing colours, pacing, audio, exact saved totals and reduced-motion support.

Preference figures combine ordinary votes and first-round tournament Elo in the
matching Blind/Non-blind mode. Preserve origin breakdowns and full/half influence
in history. Relevant profiles and Voting/Tournament Stats have a short summary
and optional bounded round-one history; primary figures stay visible. This
supersedes the earlier ordinary-only lifetime/exposure presentation rule. Keep
legacy stored ordinary counters available and label them explicitly when shown.

<a id="voting-record-balance--v416"></a>

### Voting Record balance

*Origin: Voting Record balance — V4.1.6*

Song, artist, album and tag Voting Records lead with win weight, loss weight and
actual match/track-appearance counts. Wins are green and losses danger red;
combined voting stays orange. Show the weighted win rate and concise effective
sample count, then two equally framed mode cards: Non-blind orange, Blind mint.
Keep mode win rates, outcomes, independent Elo and actual appearances visible.
Collection Elo means retain the shared-track cohort; its detail/limitations live
in a native disclosure. Use one other disclosure for pink first-round tournament
history, mode and full/half counts. Avoid nested details and repeated inset totals.

Preserve actual history dates, saved before/after/deltas, bracket links and both
participants. Tournament Stats shares the compact 64 px paired history rows with
profiles, showing at most four recent first-round events and stacking below
900 px. Use native summaries with 44 px targets and the established dark panels,
joined metrics and responsive geometry. Weight-based rates/evidence identify
selective first rounds as half; actual match counts remain distinct.

<a id="vibe-map-dashboard--vibe-map-v105"></a>

### Vibe Map dashboard

*Origin: Vibe Map dashboard — Vibe-Map-v1.0.5*

Reuse shared mode stats panels, joined metrics, dense artwork rows and formatting
macros with the red Vibe accent. Keep song/artist/album/tag identity colours.
Order coverage, all-track maps, common combinations, axis balance, closest pairs,
contrasts, then album/artist/tag consistency. Show useful evidence counts inline,
without data disclosures or explanatory paragraphs. All four maps stay visible;
one exact-position dot per placed song, one shared density scale. Keep axis
labels at least 12 rendered pixels on phones. Support point
hover and keyboard browsing, including overlapping tracks. Collapse map/pair and
comparison columns on phones, retaining all data and bounded names/scores.

<a id="vibe-map-song-inspection--vibe-map-v1051"></a>

### Vibe Map song inspection

*Origin: Vibe Map song inspection — Vibe-Map-v1.0.5.1*

Heatmap dots are inspection buttons, not immediate navigation links. Mouse,
Enter and Space open a compact Song vibe panel immediately after the maps;
hover and arrow browsing retain the lightweight caption. Keep explicit coloured
song, album and artist links in the selected identity and match rows. Reuse a
compact eight-spoke radar and two closest matches, labelled by shared evidence.
Keep the desktop panel below 450 px tall and stack chart/matches on phones.
Use the shared `vibe_song_stats_panel.html` / `vibe_song_stats.css` layout for
future song-page integration. Missing maps stay gaps. Show short loading/retry
states and protect the latest selection from stale responses. Listening-duration metrics are retired in v5.1.2.

## Developer tools

- [Preference corrections](#preference-corrections)
- [Developer catalogue](#developer-catalogue)
- [Developer tags and previews](#developer-tags-and-previews)
- [Developer tasks and recovery](#developer-tasks-and-recovery)
- [Developer dashboard reference](#developer-dashboard-reference)
- [Missing-information fill](#missing-information-fill)
- [Competition and analysis](#competition-and-analysis)
- [V5.0.1 Apple source visibility](#v501-apple-source-visibility)
- [Source review](#source-review)
- [Stop and backup controls](#stop-and-backup-controls)
- [Source confirmation and bulk alignment](#source-confirmation-and-bulk-alignment)
- [Album import](#album-import)
- [Developer polish](#developer-polish)
- [Song tag capacity](#song-tag-capacity)
- [Database sync status](#database-sync-status)
- [Vibe Dev maintenance](#vibe-dev-maintenance)


<a id="preference-corrections--v4002"></a>

### Preference corrections

*Origin: Preference corrections — V4.0.0.2*

Dev Match History offers Review saved votes using the existing dialog, field,
compact-copy and health-row components. Keep active/voided state, the original
choice, correction notes and a clear restore action. Long names retain full
accessible text; action buttons remain usable on phones. Ordinary voting retains
its accepted card/reveal layout and audio sequencing.

Public Match History reads the active corrected history. Mark a changed choice
as Corrected and affected later rating snapshots as Recalculated, beside the
saved date in the existing quiet text style. Original submitted snapshots stay
in Dev review; never present a reconstructed value as a newly saved original.

<a id="developer-catalogue--v40071--step-7a"></a>

### Developer catalogue

*Origin: Developer catalogue — V4.0.0.7.1 / step 7A*

Scope this subpatch to import cards, source/Single dialogs, quick album tracks
and their Songs/Albums actions. Dashboard/task/Git layout remains for 7C.
`dev_catalog.css` loads only for Dev and follows the shared baseline. Use existing
dark panels, quiet insets, typography and shared developer actions. Keep 16 px
body/input text, at least 44 px action targets, wrapping metadata and bounded
children. Artwork is 80 px wide on desktop and 64 px on phone; image, wrapper
and fallback dimensions agree. Import cards use artwork/details/actions columns,
then two columns with a full-width action row on phones.

Show result counts, hidden library matches and a deliberate Show library matches
control. A verified Apple identity and a possible name match need different text.
Never use a censored title to label audio Cleaned; Unknown is a valid state.
Source review defaults to saving the observation only, with separate opt-ins for
metadata and source album/position. Single review shows carried date/origin and
whether the old album can be removed before the backup/move action. All dialogs
reuse the existing editor dialog, close/reopen correctly and keep error text
visible. Switching panels or completing an older request cannot replace a newer
review. Previews are user-started, with explicit stop ownership on dialog exit.

<a id="developer-tags-and-previews--v40072--step-7b"></a>

### Developer tags and previews

*Origin: Developer tags and previews — V4.0.0.7.2 / step 7B*

Keep this scope within the workbench and direct Songs/Tags/bulk-tag entry points;
the general dashboard and Git panels remain for 7C. `dev_tags.css`/`dev_tags.js`
load only in Dev. Reuse shared panels, joined metrics, controls, artwork and media
ownership. Tag surfaces use amber; song/artist/release names retain green/blue/
purple. Keep 16 px inputs/body, at least 44 px controls and explicit loading,
disabled, error and selected states. All six artwork dimensions agree at 72 px
desktop / 56 px phone. The baseline remains the last stylesheet.

Order: all-library counts/filters/selection → persistent preview player → tag
editor/review → paged songs. Filters use four columns, two on tablets and one on
phones. Tag choices and Before/After groups use two columns, one on phones.
The tag-choice list has a bounded scroller; song/review pages each have twenty
rows. Song cards keep selection/art/name columns; actions move below on narrower
screens. Long names truncate with full accessible text; review metadata wraps.
Touch controls never require hover. Hidden selected songs have a visible count.

Preview controls identify the playing song separately from the edit scope.
Playback/selection must not rebuild during a successful tag save. Single edits
start from the actual current tags; Add/Remove/Replace and the empty-replacement
effect are explicit. Review shows current Before/After sets and changed/unchanged
totals. Input changes discard an obsolete review; switching a dirty single-song
draft needs reset/review or explicit discard. Late requests must preserve the
current panel and report save success separately from a catalogue-refresh failure.

<a id="developer-tasks-and-recovery--v40073--step-7c"></a>

### Developer tasks and recovery

*Origin: Developer tasks and recovery — V4.0.0.7.3 / step 7C*

> **Layout superseded in v5.2.0:** the Dev header and full-width service grid
> replace the taskbar/sidebar described below. Backup and safety behavior remains.

`dev_system.css` and `dev_system.js` load only in Dev. The dashboard defaults to
Tasks & health. Keep the centred page title, always-visible Upload to Git,
Create backup, full export and Lock actions, then grouped navigation beside the
active task panel. Existing library/import/tag/record panels retain their owners.
Use the baseline Arial/type scale, 24 px main panels, 18 px quiet groups, green
system accent and existing entity colours. Joined catalogue counts use shared
four-field metrics. Task cards have 22 px labels and 16 px descriptions.

The sidebar is 230 px desktop, 200 px on smaller desktop and moves above content
below 800 px. Frequent tasks use three/two/one columns; Git explanations and
search/filter controls collapse on phones. Inputs are 16 px, actions at least
44 px and main title 32 px on phones. Long filenames, URLs and extension-object
names wrap; inventory counts and backup actions keep separate bounded columns.

Opening status never fetches a Git remote. Show the branch/target, redacted
remote, cached state and actual outcome. Distinguish check, SQL upload and
restart update. Disabled/busy/retry states remain visible. Keep local backup and
full export available without Git. Competition resets stay in a collapsed group
with their existing typed confirmations. Restore review shows live/backup counts,
whole-database scope and pre-restore safety backup; stale data needs a new review.
Navigation waits while the restore applies. Late requests cannot replace the
current panel or newer catalogue state. Task shortcuts filter without autoplay.

<a id="developer-dashboard-reference--v410"></a>

### Developer dashboard reference

*Origin: Developer dashboard reference — V4.1.0*

Developer controls and dialogs share sizing/layout rules in
`static/css/dev_system.css`; the site baseline still loads last. Keep 44 px
minimum action targets, 15 px button text, 16 px fields, wrapping labels and
visible keyboard focus. Scope these rules to Dev. Do not restore the old 11 px
table-action text inside tall buttons. Group heading actions in a wrapping row
and use a separate selection toolbar rather than placing multiple controls in
the centred heading slot.

Keep Edit visible in record tables. Put other song/album/entity actions in the
row's expandable Actions group; only one group opens at a time. Expansion stays
inside the table and does not create a page-wide action column or a clipped
floating menu. Preserve columns, per-column filters, values and all actions.
Long values keep their complete DOM text and title even when visually ellipsised.

In the tag workbench keep the frequent filters visible and group artist,
release, tag and tag-match filters behind a labelled summary with an active
filter count. Artist/release/tag filters and long entity lists use the shared
searchable picker in `static/js/dev_controls.js`, retaining their native select
as form/state owner. Support keyboard selection, Escape, clear/reset, full
option labels, selected states and narrow screens. Keep all options searchable.
The bounded, keyboard-focusable song list precedes the player/editor; all
selection, review, preview and backup safeguards remain in their feature modules.

<a id="missing-information-fill--v413"></a>

### Missing-information fill

*Origin: Missing-information fill — V4.1.3*

Retain the existing scan/review/backup/apply/report controls and layout. Show
separate counts for local positions, album dates, song dates and Apple source
updates. New song-date/source reviews are native collapsed details with complete
escaped names and exact dates; unresolved counts link to the existing report
flow. New-field-only plans must enable Apply, while no-op plans stay disabled.
Refresh source summaries after a fill so content labels update immediately.

The latest user policy defaults unmarked content to Not explicit. Preserve
Explicit/Cleaned labels when stated, distinguish an assumed default in source
badges, and retain raw unknown observations. Attached genre/tag memberships are
independent and unchanged. Fill-only never changes local art, previews or album
placement. This supersedes earlier Unknown-as-display-default wording.

<a id="v5-competition-and-analysis"></a>

### Competition and analysis

*Origin: V5 competition and analysis*

> **Expired in v5.1.2:** listening measurements and their panels are removed. Vibe Map remains the sixth, descriptive mode.

The fresh V3 competition database carries catalogue data only. Current dashboards
lead with V5 results and do not show Classic/V3 record captions or legacy-anchor
explanations. Empty rates stay unavailable and all history controls remain usable.
Do not render listening-duration panels or placeholders.

Selection health leads with categorical status (New competition, Building evidence,
Poor balance, Uneven, Fair, Good, Excellent), actual mean exposure and dispersion.
Elo spread has a stage-relative reference range and a settling/compact/within/wide
label; it is a diagnostic, not a forced rating target. Exact draw probabilities
stay percentages in the inspector. Quality annotations belong behind Dev song
Actions, with no badge on public song, profile, ranking or game pages.

V5 additions reuse existing colours, rounded panels, joined metrics and at least
44 px controls. Keep the shared baseline last. Place shared additions in v5.css,
not repeated page overrides. Preserve the established mobile stacking, artwork
constraints, keyboard details, full names and visible semantic outcomes.

### V5.0.1 Apple source visibility

Dev Songs offers Apple ID and Apple link under Displayed columns. Keep both
optional by default so the main table remains compact; their values come from
the saved source summary and participate in the existing sort/filter controls.
Use the song colour for the external Apple link, with the full URL in its title.
Apple content continues to show Explicit/Cleaned only when stated by the source,
and Not explicit otherwise. A successful Apple add confirms a saved source ID.

V5.0.2 keeps the read-only source summary live inside Edit. Refresh only that
summary, preserving unsaved fields and focus. A confirmed save with a failed
follow-up refresh uses a saved/reload notice; genuine save errors stay in the
review dialog. Do not show an unknown preview comparison as a definite mismatch.

V5.0.2.1 shows only the current saved source. Remove the previous-observations
disclosure; retain the recording ID, store, advisory flag, URLs and save controls.
Compression is a storage detail and does not belong in the song/source flow.

<a id="v503-source-review"></a>

### Source review

*Origin: V5.0.3 source review*

Show five source choices, with at most ten more inside a labelled native details
control. Keep release, advisory flag, date and Apple identity visible per choice.
Bulk edits owns album moves and source review; tag editing stays in the tag
workbench. The source queue shows progress, previous/skip/review actions, then a
single group review and save. Reuse catalogue rows, semantic entity colours,
44 px action targets and the existing phone stacking rules.

<a id="v5031-stop-and-backup-controls"></a>

### Stop and backup controls

*Origin: V5.0.3.1 stop and backup controls*

Keep Stop app in the developer header action group, using the existing danger
button and wrapping responsive layout. Require a fresh masked PIN, show the Git
destination, and show local/Git outcomes before closing the server. Keep the
final receipt readable in the tab. Routine edit labels must not promise backups.

<a id="v5032-source-confirmation-and-bulk-alignment"></a>

### Source confirmation and bulk alignment

*Origin: V5.0.3.2 source confirmation and bulk alignment*

After choosing a recording, show a green selected state, collapse the alternatives
behind Change selected recording and focus/scroll to confirmation. Keep the
choice reversible and never auto-save. Respect reduced motion for scrolling.
Bulk filter labels use one shared gap and 44 px controls for native and enhanced
selects; align Selected only with the controls. Action and release-link fields
use the same label spacing and existing narrow-screen stacking.

<a id="v5033-album-import"></a>

### Album import

*Origin: V5.0.3.3 album import*

Reuse the editor dialog with a bounded track checklist and labelled native
checkboxes, 44 px targets and song/artist/album colours. New tracks start checked;
library matches start unchecked. Save only on Add selected songs. Show progress
and partial failure counts, and disable saved tracks before retry.

<a id="v504-developer-polish"></a>

### Developer polish

*Origin: V5.0.4 developer polish*

Keep Dev assets in `dev_assets.html` and feature state with its owning module.
Tool search filters the grouped sidebar and restores expansion when cleared.
Use shared 44 px controls, labelled native inputs/selects, clear selected states,
counts, retry actions and one error element per editor. Keep editor scrolling
bounded with its footer visible; do not duplicate a higher-specificity heading
rule that overrides the common centred title.

Album checklists use bounded rows and explicit selection controls. Bulk lists
start at fifty with more available; record archives start at thirty. Search and
filters apply to all loaded records, not only the visible slice. Show selected
items outside current filters and disclose capped choice lists. Match status,
visibility and catalogue entity colours keep their established meanings.
Metadata summaries use four joined metrics and collapsed change reviews; long
names wrap within bounded columns. Desktop/mobile layout uses the existing
breakpoints and shared baseline remains last.

<a id="song-tag-capacity--v5042"></a>

### Song tag capacity

*Origin: Song tag capacity — V5.0.4.2*

Song details and the tag workbench show an eight-tag capacity. Disable only
unselected additions that would exceed the limit; selected tags stay removable.
Count each song’s resulting union for Add, the replacement set for Replace,
and allow unrestricted Remove targets. Typed new names count too. Keep the
capacity message live and disable Review for an overflowing draft. Preserve
choices so the user can fix them; do not silently trim new submissions.

<a id="v505-database-sync-status"></a>

### Database sync status

*Origin: V5.0.5 database sync status*

Show the last database comparison separately from Git code/commit status in
Dev’s Git summary. Remote-ahead, split and failed-validation states need a clear
error-coloured status message. Explain that normal startup checks existing data
after a manual pull, and link split recovery to the existing backup review.
Keep status text escaped and retain explicit upload/stop/restore controls.

<a id="vibe-dev-maintenance--vibe-map-v11"></a>

### Vibe Dev maintenance

*Origin: Vibe Dev maintenance — Vibe-Map-v1.1*

Put 📍 Vibe Map in Dev's Records group. Use existing Dev panels, pagination,
search, number inputs and destructive confirmation patterns; Vibe headers and
map fieldsets are red, song/album links keep their identity colours. Show four
map editors in two columns on desktop and one on phones. Use explicit save,
clear-map, song-delete and mode-reset labels. Never expose an automatic merge
cleanup action in the app: the standalone tool is run deliberately after testing.

### Reviewed Git local choice (v5.1.2)

Use the shared review container and local/remote comparison table. Keep the
explicit `KEEP LOCAL` confirmation next to the apply button, with clear busy and
stale-review states. Keep ordinary upload guards visible after the choice.

### V5.2.0 Dev shell and service home

Dev replaces the main navigation. Left: grouped native page dropdown. Centre:
Lock Dev returns to the app home. Right: library search, Git backup & push, local
backup and a small red ⏻ stop control. App navigation also has the same stop control.
All destinations remain reachable; active page has a visible label and state.
Escape and outside clicks close the menu. Keep the header usable at 390–1800 px;
move actions to a second row before crowding the centre, with search spanning the
phone action row. Use 44 px targets and 16 px search text.

Dev content uses up to 1800 px with responsive gutters, no permanent sidebar and
a compact page heading. Home uses six service containers: full-row library counts,
health, coverage, stored activity, Git and backups. Three columns on wide screens,
two on smaller desktop and one on phone. Use shared surfaces, semantic entity/mode
colours, short labels and explicit service outcomes; avoid explanatory paragraphs
on Home. Detailed usage belongs in DEV_GUIDE.md. Other tool internals remain for
later steps. `dev_shell.css` loads after the baseline only for scoped shell rules.

### V5.2.0.1 Dev shell refinement

Four category dropdowns replace the single menu. Remove header backup actions;
place Stop immediately left of the rightmost search. Keep the central Lock Dev.
Home has no action rows. Library metrics are full-tile buttons to their entity
tables. Health, Git and backups use linked titles and equal-height aligned cards
on desktop, in that order. Coverage and activity stay below. Health owns version
and integrity, Git owns branch/short commit/status, backups owns copy count/latest
time/file size. Do not repeat backup counts in health. The integrity dialog uses
three compact metrics and bounded issue lists; no irrelevant Save button.

### V5.2.0.2 / V5.2.1 maintenance pages

Home is a standalone navigation link outside System. Git replaces the older
explanation panels with independent code/live-database columns, a fresh-check
timestamp, guarded actions, explicit blockers and bounded recent outcomes. Label
cached results; never use code Up to date as a whole-database status. Link guides
in the heading instead of explanatory walls of text.

Database uses a backup workspace and compact health summary, followed by a raw
read-only inspector. Restore review sits beside the backup list on wide screens.
Object selection has a bounded scroller; tabs switch rows/columns/definition in
place. Keep wide data inside its own scroll area, a visible pager and type labels.
Long values open a read-only paged dialog without Save. Protect dialog ownership
and late table requests. Inputs retain 16 px text and actions 44 px targets; stack
workspaces on phones and keep the document width bounded.

### V5.2.2 single-song tag bench

Default to Single song, with an explicit Bulk edit tab and guide link. Put compact
search/artist/album/count/sort filters above a bounded song queue and adjacent
editor. Highlight the selected song in amber. Show every row’s artist, album,
track, tag membership/count and source identity. Use a compact artwork/identity
block with relevant source facts and explicit links in the selected editor.

Checkboxes reflect actual current membership. Keep audio and the progress/seek
line stable through checkbox changes. Existing tags have amber labels; selected
song/artist/album retain semantic colours. Bound the tag list and queue, use short
descriptions with full accessible text, and put Save tags & next beside Skip song.
Keep the save row visible while scrolling choices. Stack the editor before the
queue on phones. Dirty navigation requires explicit discard; no auto-advance on
save failure or unresolved stale data. Bulk keeps its explicit review surface.

V5.2.2.1 gives the editor more width than the song queue. Queue titles may use
up to two bounded lines; album, artist and source facts stay on single ellipsised
lines so no identity field escapes its card. On Dev Home, the Tag Workshop is a
full-width service row immediately below the health/Git/backup row, using the
existing joined metrics and tag/entity colours rather than a new card style.
