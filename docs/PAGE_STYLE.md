# Song Ranker styling guide

This is the current V5.3.7.1 contract. Change the owning shared rule before adding a
feature exception. Older layout instructions and patch chronology remain in Git
history and `update_logs/`; they are not alternative implementations to restore.

## Shared design

| Element | Contract | Owner |
| --- | --- | --- |
| Font | Arial, Helvetica, sans-serif; 16 px body and fields | `site_baseline.css` |
| Headings | 44 px page title; 30 px section title; weight 900 | `site_baseline.css` |
| Metadata / primary values | 18 px / 36 px desktop | `site_baseline.css` |
| Surfaces | Page `#101010`; panels `#1e1e1e`; quiet insets `#242424` | `style.css`, `site_baseline.css` |
| Spacing | 24 px main panels; 20 px major gaps; retain tighter nested spacing | `site_baseline.css` |
| Corners | 24 px panels; 18 px nested groups; preserve circles/icon/drag geometry | `site_baseline.css` |
| Actions | Pill text buttons; at least 44 px touch targets; visible focus | shared CSS, feature controls |
| Headers | Centre headings across the panel; actions right; wrap below on narrow screens | shared baseline/components |
| Variable names | Single-line ellipses unless the feature specifies a bounded two-line title; full DOM text/title retained | shared baseline, feature owner |
| Main ranking covers | 120 px desktop; all min/max/width/height constraints agree | shared baseline |
| Other artwork | Keep larger profile/game heroes and smaller table/record thumbnails | feature owner |
| Glows | Preserve rank-dependent falloff; shared dashboard surfaces use the semantic accent | `components.css` |

Below 760 px use 88 px ranking art, 26/16/32 px ranking title/metadata/value and
20 px main padding. Below 520 px use 72 px art, 22/15/28 px ranking type,
32 px page titles and 18 px main padding. Cover/rank span both copy and score
rows. Layouts must fit 390 px phones through 1800 px desktop without document
horizontal overflow. Wide data tables scroll inside their own container.

Scrollbars share one owner in `site_baseline.css`: dark tracks, rounded thumbs,
12 px horizontal/vertical rails and page/entity/mode accent colours. Existing page
palette rules also expose their colour on the root so the viewport matches inner
scroll regions, including Vibe's independent pages. Record shelves keep their own
semantic accent through `--scrollbar-accent`. Use standard scrollbar colours where
pseudo-elements are unavailable. Forced-colour mode keeps native browser controls;
CSS does not change scroll behaviour, keyboard access or overlay visibility.

## Semantic colours

Use variables from `style.css`, not a newly invented page palette. Mode colours
explain activity/results; entity colours explain catalogue identity. A song link
inside a mode card retains the song colour.

| Meaning | Token | Value |
| --- | --- | --- |
| Song | `--song` | `#1db954` |
| Artist | `--artist` | `#5b9bff` |
| Album | `--album` | `#bf77ff` |
| Tag | `--tag` | `#ffb833` |
| Non-blind / Blind | `--standard` / `--blind` | `#f0a35b` / `#55d6c2` |
| Trivia | `--recognition` | `#f2d34f` |
| Tournament | `--tournament` | `#ff78a6` |
| Elo Guesser | `--guesser` | `#ed7863` |
| Album Shelves | `--shelves` / `--shelves-deep` | `#af89bd` / `#592862` |
| Vibe Map | `--vibe` | `#ed6573` |
| Overall | `--overall` | `#f5ead8` |
| Error / destructive action | `--danger` | `#ff6675` |

Quiet borders/washes can use related shades. Missing evidence displays unavailable,
not a fabricated zero. Selected/loading/disabled/error/result states must remain
visually distinct and accessible without colour alone.

## Asset and component ownership

`templates/assets.html` is the only stylesheet/script registry. Its macros load:

1. Core `style.css`.
2. The requested feature styles.
3. Shared `components.css`.
4. Approved `site_baseline.css`, always last.

Feature rules must be scoped to their page/component. There is no legacy sheet,
version-named sheet or second developer asset list. All asset URLs use the single
`APP_VERSION`; the independent Vibe definition version is data metadata.

| Owner | Responsibility |
| --- | --- |
| `style.css` | Palette, navigation, core controls, layout primitives and shared mode/Overall surfaces |
| `components.css` | Joined metrics, dashboard glows, paired records and the shared stop button |
| `site_baseline.css` | Approved type, spacing, corners, headers and main ranking geometry |
| `reports.css` | Shared report/dashboard geometry, visualisations and scoped mode report compositions |
| `profiles.css` | Song/collection heroes, album queues and paged track/release lists |
| `vibe.css` | Shared descriptive radar, profile and library summary presentation |
| `developer.css` | Common Dev forms, system/database/record tools and Vibe maintenance |
| `dev_workspace.css` | Dev navigation, Home/section/guide layouts and inline editor placement |
| `dev_catalog.css` / `dev_tags.css` | Catalogue/source-review and tag-workbench compositions |
| Remaining feature styles | Home, search, rankings, history, gameplay and the Vibe play workspace |
| `components.html` | Shared artwork, rows and catalogue presentation macros |
| `mode_stats_components.html` / `stats_visuals.html` | Shared report figures, formatting, activity and charts |
| `profile.html` | One named-collection profile shell for artists, albums and tags |
| `dev.html` | Shared focused Dev shell, navigation context and inline editor slot |
| `app_page.html` | One dynamic shell for Home, rankings, song profile, search and tournament setup |

Use `joined-metrics` for one framed row, declaring `data-columns="2"` or `"4"`
where needed. Home retains three columns on phones; four-field groups become two
columns below 760 px with appropriate quiet row/column dividers. Independent
cards and galleries are not joined metric rows.

## Page composition

Home uses six clear mode choices, joined catalogue totals, Overall leaders,
compact Vibe summaries and bounded record shelves. Record shelves have the shared
centred heading and labelled scroll actions. Keep counts/data distinct from
navigation and avoid repeating the same metric in adjacent panels.

Rankings share category/range controls, absolute standing, semantic record links,
bounded names and separate values. Impact uses collection evidence; song rankings
use Elo. Mode boards use the common renderer and preserve their own eligibility
and evidence labels. Vibe ranks collections only, top/bottom twenty.

Search has one query and clear entity choices; preserve complete labels, tag
counts and proper-album counts. Collection profiles share one shell and renderer.
Artists retain circular artwork; albums/tags keep their established geometry.
Show six initial tag albums and thirty collection tracks with Show more. Place
ready Vibe cards above Overall and keep the hero player stable while cards load.

Game screens share consistent cover/reveal geometry. Keep identities hidden until
allowed by the current round, outcomes explicit, and automatic/manual advancement
consistent with the selected result speed. Playback, grading and cancellation
remain with each mode. Do not change saved rules to achieve a visual alignment.
Vibe uses four continuous graphs, red accents, keyboard/pointer placement and its
own resumable stage controls; it has no performance score.

Detailed reports share centred headers, joined metrics, compact record rows,
meaningful charts and page-bound histories. Trend counts and pooled rates come
from one read snapshot. Retired listening measurements have no placeholder UI.

## Developer controls

Dev uses four visible primary links: Home, Library, Mode edits, Tools & systems.
Task pages show visible links within their section; no category dropdowns. Lock,
Guides, Stop and library search remain reachable in the shared header. Native
small selects remain native; searchable controls are reserved for long entity
lists. Use 44 px targets and 16 px input text. Phone section links scroll inside
their own row without document overflow.

Home has linked library totals, three aligned summaries (health, Git/backups,
attention), and three groups linking to every task. Status/data and navigation are
distinct. Home uses cached/local Git information; Git sync owns fresh comparison.
Keep explanations in the readable Guides page, linked from every Dev header.

Routine editors are in-page: a sticky adjacent column on wide screens, above the
task below 1100 px. The field body scrolls and the action footer stays visible.
Unsaved record/tag drafts require explicit discard on task changes. Existing review
receipts, typed confirmations, restore locks and stale-response guards still apply.
`dev_workspace.css` owns navigation, section/guide layouts and editor placement;
`developer.css` owns shared controls, record/system/Vibe compositions. Catalogue and
tag-specific layouts stay in their existing owners. Remove superseded layout rules
when changing a contract; do not append another version layer.

Songs/artists/albums/tags use one compact table engine. IDs/artwork have narrow
fixed columns; names/relationships receive flexible width. Search stays beside
Filters and Columns in the top toolbar, wrapping on phones. Filters and column
checklists expand in flow; filter entry uses Field, Match and Value with suggestions
from saved rows. Applied conditions appear as individually removable chips. Keep
Clear filters separate from Reset order. Enter applies a filter and closes its
panel. Provide row-count choices, a page input and paging above/below the table.
Catalogue and database rows use the page's vertical scroll; wide tables retain
horizontal scrolling. Keep Actions reachable at the right edge. Edit remains
visible; More opens one body-level, viewport-bounded menu with keyboard navigation,
Escape/focus restoration and dismissal on scrolling or task changes.

All editors share the same form/heading/error/action skeleton. Dev mounts that
skeleton in the inline workspace; public Stop retains its modal presentation. Group related
fields, use 16 px inputs, keep the footer visible with bounded body scrolling and
show one error region. Read-only inspections omit Save. Preserve pending user
fields when a source summary refreshes; late replies must not replace another
dialog or the active task. Confirmed saves with a failed refresh report saved/reload
separately from actual save failures.

Tag Workbench defaults to Single song, with Bulk edit explicit. A bounded queue
sits beside a wider editor; editor precedes queue on phones. Queue rows show song,
artist, album, position, tags/count and source facts. Selected rows glow amber.
The selected card contains its artwork. Names are bounded with full title text.

Checkboxes reflect current memberships and enforce eight tags while leaving
selected tags removable. Keep seek/loop preview audio stable through checkbox
changes. Preview quality is reachable beside the current player. Save tags & next
sits beside Skip song; dirty navigation needs explicit discard, and failed/stale
saves do not advance. Bulk preserves Add/Remove/Replace, visible selection scope
and explicit before/after review.

Apple/source/metadata tools reuse catalogue rows, semantic colours, native inputs
and shared editors. Album imports use bounded, labelled checklists: new songs
checked, existing matches unchecked. Save only selected songs and retain partial
success receipts. Source-only changes preserve local metadata/relationships;
metadata replacement is explicit. Fill-only scan → review → apply remains guarded.

Database inspection, backups/restore, Git, resets and exports have separate focused
pages with compact status summaries and bounded workspaces. Separate
code status from live-database status and identify cached/fresh checks. Git comparisons
show full wrapping hashes, numbered devices/time and native whole-copy selection;
switching copies clears typed confirmation. Opening a choice collapses the duplicate
status detail above it. Storage compaction sits with Git actions. Database tables use page vertical scrolling and local horizontal overflow;
long values and backup restore reviews retain bounded review areas.
Vibe maintenance uses a bounded song queue beside the editor (above the queue on
phones). Four direct map selectors expose one coordinate group at a time, retaining
all unsaved map fields; Save remains visible below the bounded fields. Destructive
resets/restore/keep-local retain their existing typed reviews and stale checks.
Stop keeps one fresh masked PIN, explicit backup/Git outcomes and an acknowledgement
before server exit. Do not add automatic reset/cleanup behavior.

## JavaScript ownership

`ui.js` owns DOM selectors, escaping, entity semantics, search/identity policies,
shared ranking rows and banners. `preview.js` owns playback coordination and the
persisted global volume, including Dev pages without a volume slider.
`gameplay.js` owns shared geometry and RoundFlow timing/cancellation.

Feature controllers own their state, eligibility, requests and late-response
checks. `site.js` assembles catalogue pages and shared navigation/editors; static
reports and independent modes must not fetch the catalogue just to initialise
the shell. Developer record controllers live in `dev_records.js`; database and
selection companions live in `dev_system.js`. Vibe chart/profile rendering lives
in `vibe_charts.js`. Do not copy helpers into a new patch file.

Before a PR, run `python tools/check.py all`. Update this guide when an accepted
shared contract changes and regenerate the function index after moving definitions.

Album positions use the shared disc/track formatter. Multi-disc releases remain
one album card/shelf, with a disc-count caption. Disc and track fields sit together
in the shared song editor; bulk album moves accept an optional destination disc.
Never expose the correct positions before the Shelves answer reveal. Preserve
compact position badges and wrapping full accessible labels on phones.

If guide formatting is unavailable, show a wrapping escaped-text article at full
reader width and an in-flow repair notice. Do not render an empty contents column
or leave a loading/error screen in place of the guide. Normal formatted guides
retain the shared contents/article layout.

Shelves reveals derive red depth from the fraction of failed order comparisons,
with wrong-album cards at maximum depth and fully correct cards retaining green.
Preserve the explicit correction, comparison counts and points beside the colour.
Only a completed perfect reveal shows the compact green Perfect shelves badge;
its glow runs once, with no motion in reduced-motion mode. No confetti or audio.
