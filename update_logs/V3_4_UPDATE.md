# V3.4 — Page layouts and style standardisation

This release is being applied page by page. All V3.4.x styling patches are
documented here, with shared decisions in `README_PAGE_STYLE.md`.

## V3.4.1 — Global Stats

- Full-width sections in the requested order, larger artwork/type, centred
  summary values and tighter spacing. Added top counters for Trivia rounds,
  tournaments, Elo Guesser rounds and Shelves rounds, in their page order.
- Collection Records adds most proper albums by an artist and biggest album.
  Text names are linked and underline on hover/focus; record boxes are not links.
- Overall drops its mean percentage, enlarges/centres the three useful totals
  and uses one rankings link. Its existing song/artist/album/tag leader cards
  stay in place with the same artwork/name/score/bar layout.
- Voting leaders link song names only. Frequent Matchups moves into Voting
  Results: three by default, with Show five when four or more pairs repeat.
- Elo Distribution uses 50-point bands. Unplayed tracks, weekly votes and
  preview counts have their own number/label lines in the Elo colour.
- Recognisability gains field cards, song-answer and distinct-track miss counts,
  most-recognised artwork and the three most-missed actual artists/albums.
  The database saves correctness, not wrong guess text. Trivia totals count
  completed rounds; no separate session/game count is stored.
- Tournaments show a bracket total, an inline unfinished count only when needed,
  32/16/8-track totals, the latest podium with covers and five recent champions.
- Elo Guesser adds wrong picks, current/best streaks, tested tracks and most
  tested/missed track records. Shelves adds album/ordering accuracy, perfect
  rounds, placements, albums played, best points and album records.
- Added the top five Artist Average Elo entries along with the existing top-five
  Album Average Elo section, in separate full rows. Top Tags increases to ten.
- Replaced vote-only recent matches with the latest ten saved results across
  votes, Trivia, Tournament, Elo Guesser and Shelves. Each completed tournament
  or Shelves round counts once. Dates display in the browser's local timezone.
- Added the dedicated page-style README and a project instruction to consult it
  for future designs while following subsequent user corrections.

### Apply

Apply this edited-file patch over **V3.3.5.1**, restart and hard-refresh. The
footer shows **V3.4.1**. No database migration or scoring change is included.

### Validation

The Global Stats projection is read-only and tested against empty and populated
fixtures, album exclusions, shared artists, Elo boundaries, repeated pairs,
saved misses, mixed timestamp formats and one-result-per-mode activity units.
The original database is unchanged. Current verification totals and environment
limits are recorded in `VALIDATION.md`.

## V3.4.1.1 — Global Stats layout corrections

- Fixed the vertical cover shapes: an inherited 48 px maximum width remained
  after the previous resize. Width/height and all min/max constraints now follow
  one artwork size. Covers stay square, artists circular, and images retain
  their existing cover crop.
- Data rows/groups now have subtle rounded frames tinted to their parent box,
  including separate Elo-band and number-stat groups. Nested records keep the
  same restrained colours.
- Box/subsection headings are centred, with links and controls on the right.
  Narrow screens keep the title centred and the action right-aligned below it.
- Removed average Elo from the distribution header. Artist/album average lists
  remain useful and are unchanged.
- Collection Records uses three cards per desktop row and centres the final
  two-card row; tablet/phone layouts use two/one cards.
- Updated the shared page-style README with these accepted corrections.

Apply over **V3.4.1**, restart and hard-refresh. The footer shows **V3.4.1.1**.
This edited-file patch changes presentation only; data, scoring and previews
are unchanged. Validation details are in `VALIDATION.md`.


## V3.4.1.2 — Long text and mixed-mode recent results

- Variable names and artist metadata now use ellipses when they exceed their
  space. Full text remains in the DOM/title attributes. Scores, counts and
  outcomes stay in separate wrapping fields so useful results are not cut off.
- Recent Mode Results blends the colours of its currently visible modes,
  weighted by row counts, across the background, border, glow and heading.
  A single-mode list keeps that mode's colour; empty lists are neutral. The mix
  recalculates on list/kind/visibility changes and page restoration, without
  extra API polling. Individual rows retain their own mode accents.
- Shelves entries name their saved albums and show track/album counts, actual
  earned/available points, percent earned, correct album placements and order
  comparisons; perfect rounds are marked. Deleted albums keep their saved shelf
  positions/counts and display as removed instead of linking to missing pages.
- Tournament entries include champion, size, saved match/point totals and scope,
  with a blind-bracket flag where applicable. Blind tournaments retain the
  Tournament colour; Blind Audition retains mint.
- Elo Guesser entries identify the pick, higher-rated track and saved comparison
  Elo, with the correct/wrong result. Trivia entries show eligible field outcomes.
  Entity names and outcome states keep their respective colours.
- Updated the shared styling guide with these safeguards and activity rules.

Apply over **V3.4.1.1**, restart and hard-refresh. The footer shows **V3.4.1.2**.
There is no migration or change to game scoring, Overall or preview playback.
Read-only activity projections now expose more of the already saved results.

## V3.4.2 — Standard ranking boards

- Songs, Artists, Albums and Tags ranking titles always use their entity colour
  and underline on hover/keyboard focus. Song artist/album links are now bold.
- Album artist names are bold blue links, resolved from actual linked artists
  rather than splitting a display name. Collaborative artists remain separate
  links, including names that contain commas.
- Increased desktop row titles to 30 px, metadata to 18 px, voting figures to
  15 px and scores to 36 px. Covers grow to 104 px, remain square/circular, and
  stay vertically centred with equal top/bottom clearance. Tablet/phone sizes
  scale together; narrow-screen scores sit beneath the text.
- Preserved the rank-weighted glows, coloured Top/Bottom buttons, underlined
  category selector and current stats/order. Added these accepted choices to
  the page styling guide. Other ranking groups retain their own styles.
- Supplied a separate offline Style Previews ZIP with three starting presets,
  labelled individual options, comparison specimens, common components and a
  reusable page template. These are choices for future updates, not automatic
  app-wide changes. Its default B matches the new ranking type/art baseline.

Apply this edited-file patch over **V3.4.1.2**, restart and hard-refresh. The
footer shows **V3.4.2**. No database, scoring, ranking order or preview playback
change is included. Validation details are in `VALIDATION.md`.

## V3.4.2.1 — Chosen shared styling baseline

- Applied the user's selected preview codes across shared site components:
  **T2 · F2 · W3 · A3 · D2 · R3 · G2 · C1 · B1 · H1 · N1**.
- Arial UI, heavy headings and links, 120 px desktop ranking/podium covers,
  24 px main padding, 20 px major gaps, 24 px outer/18 px inner corners and
  softer grey insets. Text actions use pills; headings centre with actions right.
- Medium text scale uses 44 px page titles, 30 px ranking/section titles,
  18 px metadata, 16 px body and 36 px primary figures. Responsive
  sizes preserve room for covers, names and separate scores on phones.
- Retained the existing glow strength, entity/mode colours, mode washes and
  recent-mode blend. Long names use single-line ellipses. Profile/game hero art,
  dense thumbnails and functional icon/cover/drag controls keep their own sizes.
- Recorded the selected codes and their scope in `README_PAGE_STYLE.md`, with
  one shared stylesheet loaded after page styles for future consistency.
- Standard ranking links, ordering, filters, stats and controls are preserved.
  No scoring, database or preview playback changes are included.


Apply over **V3.4.2**, restart and hard-refresh. The corrected release label is
**V3.4.2.1**. These notes now belong to the V3.4 release family.

## V3.4.3 — Home mode summaries and banner limits

- Trivia, Tournament, Elo Guesser and Album Shelves summaries beneath Overall
  now occupy one full-width row per mode. Existing figures, labels, mode order
  and Stats links remain in place.
- Applied the approved styling: Arial, centred headings with links on the right,
  36 px metric values, quiet framed/centred metric cards, 24 px outer corners
  and main padding, 18 px inset corners and existing mode colours/glows. Phone
  layouts reduce padding/type and centre the final metric below a two-card row.
- All seven home scrolling banners now show up to ten entries. Top Tracks,
  Artists and Albums already used ten; Recognisability, Champions, Elo Guesser
  and Album Shelves now share that limit. Their ranking/eligibility rules,
  navigation, empty states and scrolling behavior are preserved.
- Updated the page styling README with these home-specific decisions. Other
  page layouts and Top/Bottom twenty ranking boards retain their limits.

Apply the edited files over **V3.4.2.1**, restart and hard-refresh. The footer
shows **V3.4.3**. No database migration, scoring or audio change is included.
Validation details are in `VALIDATION.md`.

## V3.4.3.1 — Home collection totals and version correction

- Removed the Tournament total beneath Ways to Play. Songs, Artists and Albums
  stay together in one row, including on narrow screens, with centred content.
- Applied the approved Arial/medium type: 36 px heavy values and 18 px bold
  labels on desktop, 28/16 px on phones, with the shared padding/corners.
  Albums continue to exclude singles/unknown albums in the existing count.
- Corrected the previous shared baseline/home release labels to V3.4.2.1 and
  V3.4.3, and this patch to V3.4.3.1. Their full notes are consolidated here;
  the notes index, styling guide, README, footer and asset versions agree.
- The two superseded note paths now point here, so copying the patch replaces
  their incorrect contents. Those forwarding files may be deleted afterwards.
- Preserved the four mode-summary rows, their data, and the ten-entry home
  banners. No database, ranking, scoring or audio change is included.

Apply over the previous home update, now labelled **V3.4.3**. Restart and
hard-refresh; the footer shows **V3.4.3.1**. Checks are in `VALIDATION.md`.


## V3.4.3.2 — Home mode figures and percentage bars

- Each of the four home mode panels now has three centred figures in one joined
  inset row, with a full-width rounded bar below. Rows stay three columns on
  phones; shared fonts, mode colours, headers and Stats links are retained.
- Tournament **Champions** is replaced with **Tracks entered**: entry slots
  across completed brackets, counting each repeat appearance. Its three-part
  bar shows the share of completed 32-, 16- and 8-track brackets, with distinct
  pink shades and a count/percentage legend. Other or unavailable bracket sizes
  are identified beneath the bar; missing legacy entry totals show an em dash.
- Recognisability gains **Fields correct** across all song/artist/eligible album
  fields. It pools correct and available counts; unavailable album fields do
  not reduce the result.
- Elo Guesser replaces its accuracy figure with **Wrong guesses** and moves
  **Correct guesses** percentage to the bar. Completed questions count once,
  using their saved answer facts.
- Album Shelves replaces weighted points percentage with **Albums played**,
  counting distinct surviving albums saved in completed rounds. Its bar shows
  **Relative track order**, based on correct/eligible ordering comparisons.
  Later catalogue moves do not alter saved album participation.
- Empty rates show an em dash with an unfilled bar and concise guidance. The
  joined row and bars are recorded in the styling guide for later page work.

Apply over **V3.4.3.1**. Restart and hard-refresh; the footer shows **V3.4.3.2**.
The patch contains edited files and these grouped notes only. No database,
game scoring, schema or audio changes are included. Checks are in `VALIDATION.md`.


## V3.4.3.3 — Shared dashboard styling and code cleanup

- Added the Home-style thin separators to every joined Global Stats metric
  row, including the dynamically loaded Overall figures. Two-, three- and
  four-field groups share one component. Four-field groups reset the divider
  at the start of each wrapped phone row and add a quiet boundary between rows.
- Every main box on Home and Global Stats now has the same soft glow in its
  border/accent hue. This covers panels, top counters, game-mode cards, banner
  cards and Overall leader cards. Recent Mode Results follows its current
  visible-mode colour blend; empty results use a neutral glow. Inner groups
  retain quieter borders.
- Added `static/css/components.css` for shared rows/glows. The approved baseline
  now supplies standard ranking geometry and centred headers without repeated
  page copies. Semantic palette values and page-tone variables are defined in
  the foundation stylesheet; text-colour utilities retain their cascade order.
- Reviewed all eight existing CSS files and all six existing JavaScript files.
  Removed 22 identical CSS declarations and 114 superseded declarations, plus
  redundant ranking/header copies and dashboard-specific shadow overrides.
  Responsive rules, distinct states and intentional browser fallbacks remain.
- Added `static/js/ui.js` for shared DOM/escaping helpers, ratio formatting,
  field totals, entity labels/colours and scrolling-banner headers. Reused them
  in the main site, Overall, special-mode and Trivia scripts. Feature request,
  scoring, game-state and preview/cache behavior is retained.
- Updated the styling guide with component ownership, load order and rules for
  later pages. Existing figures, banners, section order and ranking glow
  falloff are preserved.

Apply over the supplied **V3.4.3.2**. Copy all edited files, including the new
`components.css` and `ui.js`, then restart and hard-refresh. The footer shows
**V3.4.3.3**. Notes stay grouped here under V3.4. The patch excludes databases
and validation fixtures; check results and limits are in `VALIDATION.md`.

## V3.4.4 — Match History

- Standardised the history rows: outer song/artist/proper-album information,
  square artwork beside a central VS, and the saved date underneath VS.
- Winner song names are green, losers red, with blue artist links and purple
  proper-album links. Names underline on hover/focus; long names truncate.
- Standard/blind matches use soft mode-colour edges. The existing selectors
  stay above the list. Saved Elo changes appear when available; older entries
  explicitly identify current Elo.
- Applied the same versus composition to Global Stats Frequent Matchups, with
  current Elo and encounter counts for those aggregate pairs.

Apply over **V3.4.3.3**, restart and hard-refresh. The footer shows **V3.4.4**.
No scoring or database change.

## V3.4.5 — Recognisability Stats

- Applied the approved font, type scale, centred headings/right-hand actions,
  full-width panels, soft gold border glows, quieter inset sections and joined
  metric rows with separators. Artwork has matching width/height constraints;
  artists remain circular. Entity names keep their colours and underline on
  hover/focus; only text names are linked.
- Added pooled overall field accuracy, separate song/artist/album accuracy,
  correct/missed counts and average correct-answer time with sample counts.
- Added all-fields/some-fields/no-fields round outcomes with a stacked split,
  lifetime round points, average points per round and rolling 7/30-day activity.
- Added preview-ready collection coverage: tracks with audio, already tested
  and still to try, plus a full-width tested-share bar.
- Kept ten most/least-recognised tracks, with five initially shown in each and
  five expandable. Added top-five highest-accuracy and most-missed actual
  artists, albums and tags. All lists show useful counts beside their rates.
- Recent Trivia keeps song/artist/proper-album links, field outcomes, earned
  points, saved running score/streak and local-time dates. Ten rounds show
  initially, with ten earlier rounds expandable; no nested scrolling area.
- Replaced the old shared loader for this page with a dedicated read-only
  snapshot. Lifetime calculations scan every completed round, rather than
  deriving new records from the loader's latest-100 history window. The game,
  grading, preview playback and Overall calculations are unchanged.
- Removed 49 obsolete selectors for the replaced stats layout from the shared
  stylesheet. Other pages retain their existing styles. Updated the page-style
  guide and added in-memory data regressions.

### How the figures are calculated

**Field accuracy:** correct song, artist and eligible album fields divided by
available fields. Counts are pooled, not averaged from rounded track rates.
Song and artist each offer one field per adjusted attempt; albums use their
saved eligible-attempt count. Songs without an album opportunity are not
penalised. Saved round eligibility remains authoritative even if catalogue
albums later change. These are actual correct-answer rates, not Overall
percentiles or the weighted player-point score.

**Adjusted totals versus saved rounds:** field accuracy, track rankings and
entity summaries include existing developer corrections from `trivia_stats`.
Completed-round counts, outcomes, timing, points and recent activity use the
actual saved detailed rounds. Corrections cannot invent a timestamp, speed or
round outcome. Defensive display clamps keep malformed negative/excessive
counts within eligible opportunities; no stored data is edited.

**Round outcomes:** all eligible fields correct is a perfect round, including
both fields on a no-album round. One or more correct, but not all, is partial;
zero correct is a miss. Missing correctness data is shown separately as result
unavailable. Unfinished rounds are excluded. The database stores rounds, not
separate Trivia sessions, so no session/game count is inferred.

**Answer time:** the mean elapsed active-preview time when a correct field was
submitted, measured from the start of that round; it is not time spent typing
that particular answer. Saved pause time is already excluded by the game.
Only correct answers with finite saved times from 0 through 30 seconds count;
zero is valid. Wrong, unavailable and untimed answers do not lower the mean.
The sample count is shown beneath each field's average.

**Points:** reconstructed with the unchanged Trivia formula: song 50%, artist
20%, album 30%, with absent album weight redistributed across the two other
fields. Each correct field earns its weight times `1 - elapsed_seconds / 120`.
Thus a correct answer at 30 seconds earns 75% of that field's weight. A complete
round is worth at most one point. Total points sum rounds; average points divide
by the rounds with complete results and valid timings for their correct fields.
Incomplete/untimed results remain in history but are excluded from these point
figures, with a short coverage count when necessary. Best player score and best
streak remain the saved global records, so they need not equal lifetime points.
A streak advances when any eligible field is correct, as before.

**Entity records:** artist accuracy uses the artist field; album accuracy uses
eligible album fields on current proper-album links; tag accuracy pools all
eligible fields of its linked tracks. Each track contributes once to each
linked entity, even with duplicate relationships. Collaborations/multiple tags
can contribute to several separate groups, so group totals should not be added
together. Singles/Unknown Album entries do not become album records. Catalogue
edits can change category membership; historical guessed text is not saved.
"Most missed" ranks actual tested identities by missed-field count, not by
which wrong names were typed. Rates rank by their unrounded ratio, then exposure
and name, while visible percentages use one decimal place.

**Coverage and activity:** playable means a current nonblank audio-preview URL;
coverage is tested playable tracks / all playable tracks. Previously tested
tracks which no longer have a preview are counted separately. Seven/thirty-day
figures use rolling windows ending at the server's current time; future dates
are excluded. Recent rounds sort by saved completion time, then ID. Missing
identities remain unlinked history fallbacks. Empty counts are zero; a rate,
mean or points figure without the required evidence shows an em dash.

### Apply

Apply this edited/new-file patch over **V3.4.4**, restart and hard-refresh.
The footer shows **V3.4.5**. Keep your own database; this update adds no migration,
stored counters or scoring changes. Validation details are in `VALIDATION.md`.

## V3.4.6 — Tournament Stats

- Replaced the old Top/Bottom tournament board with a stats dashboard based on
  the accepted Recognisability page. All major sections have their own row,
  centred headings, right-hand actions, joined/divided metrics, quiet insets,
  constrained covers and the shared pink glow. Entity names retain their own
  colours, with text-only links and hover/focus underlines.
- Put bracket count, decided matches, track entries and completion first,
  followed by the latest podium with covers, earned bracket points and up to
  five previous champions. Unfinished count appears beside brackets only when
  needed; records are not padded with repeated championship/podium totals.
- Added all-bracket size, blind/non-blind and scope distributions, each with
  counts and a stacked pink bar. Added stage counts, bronze versus bracket
  match totals, recorded points and rolling 7/30-day activity.
- Added current-collection participation and distinct champions, six compact
  track records, and five artist/album/tag records with titles, podiums, points,
  tracks and bracket counts. Full tournament rankings remain one link away.
- Added seed patterns: top-seed/top-half/bottom-half champions, top-half title
  share, higher-numbered seed wins and the highest-numbered champion seed.
- Bracket history now has ten expandable native details per page, with active
  brackets first. Existing song/profile `?tournament=ID` links open that bracket
  on the correct archive page. Full recorded rounds, scope, visibility, outcomes,
  points and dates remain available, plus links to the saved game/podium.
- Round labels follow the saved stage, so an unfinished quarter-final is no
  longer labelled Final merely because later rounds have not been created.
  A bronze playoff is displayed separately from the final.
- Extracted the common detailed-stats layout and formatting into shared CSS and
  Jinja macros. Recognisability keeps its accepted data, links and appearance.
  Removed the obsolete tournament board renderer and its private event handlers;
  game, scoring, preview and ranking APIs keep their existing behavior.

### Data definitions and saved-history limits

**Brackets and entries:** totals cover all saved brackets, including unfinished
ones. A completed bracket means the saved status is `completed`; a champion ID
alone does not finish an active bracket. Track entries sum declared bracket
sizes, falling back to saved entry rows when size is missing. Repeat appearances
count again. If neither exists, the page shows a lower bound or an unavailable
figure and discloses the missing brackets. The size/scope/visibility bars use
all brackets as their denominator, with unknown/other groups retained.

**Matches and points:** a decided match is a saved completed match row, including
bronze playoffs and decisions in unfinished brackets. Counts and stage shares
come from recorded rows, not an assumed complete tree. Stage is derived from
bracket size and saved round number; third-place matches retain their own label.
Points are the actual saved awards, not recalculated from current Elo or from a
new formula. Invalid/missing point values are omitted and counted explicitly;
real zero points remain zero. Podium points are earned in that bracket alone,
with an em dash when the player's result/point evidence is unavailable.

**Podiums and records:** completed brackets can recover a missing champion/
runner-up from an exact recorded final, or third/fourth from an explicit bronze
playoff. Existing nonmissing placement fields remain authoritative. These
fallbacks are applied only to this read-only report, not written to history or
used to change Overall, the game, the full ranking API or other pages. Older
header-only champions remain usable; missing detailed rounds do not become
invented wins or points. Song achievements otherwise use the shared tournament
projection. Best win-rate record requires at least three saved match appearances,
shown on its label; it is a record, not an inferred ability score.

**Collection records:** participation combines surviving songs in saved entry
rows, match participants and completed placements, counting each song/bracket
once. Coverage divides those different current songs by the current collection;
no audio requirement is applied because non-blind tournaments allow every song.
Artist/album/tag records follow current catalogue relationships. Duplicate links
do not multiply results. A collaborative or multi-tag track can contribute to
several separate groups, so group totals should not be added together. Proper
album records exclude singles, Unknown Album and absent album links. Groups
sort by titles, podiums, points and bracket count, with up to five shown.

**Seed patterns:** smaller saved seed numbers are nearer the top of the seed
list; this list also uses selection noise and spreads prior champions, so it is
not a frozen Elo ranking. Top/bottom half is relative to each bracket's own
size. Championship shares use only completed winners with a valid saved seed.
The match share uses completed decisions with both valid, distinct saved seeds;
a winner with the larger number counts as a higher-numbered seed win. Bronze
playoffs count too. Missing seeds do not become losses. The highest-numbered
champion record reports its literal saved seed and bracket size, not a claimed
hardest win. Historical Elo snapshots, active play time and vote response times
are not recorded for tournament matches, so those figures are not invented.

**Dates and archive:** rolling windows use actual completion/played timestamps,
not creation dates, and exclude future events. Archive order uses the last
available saved date, with active brackets first; legacy date fallbacks do not
enter completion-window totals. Display dates use the browser's local timezone.
A selected older bracket opens on its own archive page; missing IDs get a short
message. Missing songs/scopes stay unlinked, and empty rates show an em dash.

### Apply

Apply these edited/new files over **V3.4.5**, restart and hard-refresh. The footer
shows **V3.4.6**. Keep the existing database and backups. No migration, stored
counter, gameplay, scoring or preview change. Verification is in `VALIDATION.md`.

## V3.4.6.1 — Private LAN phone hosting

- Kept the uploaded launcher's LAN listening behavior, port 5000 and specific
  phone allow-list. Loopback access includes IPv6. The phone/device list, bind
  address, port and optional local hostname can now be set through environment
  variables rather than editing Python. The README explains which computer IP
  goes in the phone browser and which phone IP goes in the allow-list.
- Replaced Flask's development server with Waitress, with debug and exposed
  tracebacks disabled, untrusted forwarding headers cleared and a 4 MiB request
  limit. Updated requirements for current Flask and Waitress; Windows installs
  no longer try to install Gunicorn. Existing Git startup behavior is retained.
- Moved the checks into shared app setup, so an imported WSGI app keeps the
  same policy. Only loopback or explicitly allowed direct peers can connect;
  forwarded headers cannot grant access. Host validation permits private
  numeric addresses, localhost and explicitly configured names.
- **System Access and developer APIs are now computer-only**, through a
  loopback address, even for an allowed phone or a valid admin cookie. The
  existing PIN and its environment override are unchanged. Public modes,
  rankings, saved results and previews remain available to the allowed phone.
- Replaced the published session-key fallback with an installation-specific
  random key in `instance/session_secret`, excluded by `instance/.gitignore`.
  File permissions are restricted where supported. A configured
  `SONG_RANKER_SECRET` must be at least 32 characters; use a stable random value.
  First-time key replacement signs browsers out and may require starting a new
  browser-bound unfinished round. It does not delete saved database history.
- Added same-origin Origin/Referer checks, Fetch Metadata checks when present,
  a form token for Dev login and JSON-only mutation requests without CORS
  access. The two legacy GETs that create Trivia rounds/tournament brackets
  require the app's JSON header; HEAD is blocked for those actions. The shared
  request helper supplies that header. Native audio/Range requests are exempt
  from the mutation-header requirement. Added HttpOnly/SameSite=Lax cookies,
  frame blocking, nosniff, same-origin referrers and no-store for Dev responses.
- Updated the main README with installation, LAN troubleshooting, settings,
  key handling and the direct private-Wi-Fi scope. The IP list is device
  filtering, not user authentication, and can change with DHCP. HTTP remains
  unencrypted; this is not an internet-hosting setup. Do not add port forwarding,
  public tunnels or a reverse proxy to this configuration.
- Added required phone checks to the styling guide for subsequent page updates:
  portrait/landscape widths, touch targets, long names, navigation/dialogs,
  readable metrics, preview controls and alternatives to drag/hover. Existing
  accepted modes/rankings remain the baseline. No visible layout/CSS change,
  score adjustment, database migration or replacement database in this patch.

### Apply

Apply these edited/new files over **V3.4.6**, keeping the database, backups and
any private instance key. Install the updated dependencies before restarting:

```sh
python -m pip install -r requirements.txt
python main.py
```

Hard-refresh both browsers. The footer shows **V3.4.6.1**. Use
`http://127.0.0.1:5000` on the computer and `http://COMPUTER-LAN-IP:5000` on the
allowed phone, on the same trusted private network. The supplied phone IP
remains the default; set `SONG_RANKER_ALLOWED_IPS` if it changes. See the main
README for PowerShell/macOS/Linux examples and computer-only settings.

### Review and verification

The review addressed the launcher's network exposure, shared session key,
developer access, cross-site request handling and preview/API compatibility.
It is a scoped LAN review, not a penetration test or a public-hosting claim.
`VALIDATION.md` records the project/security tests, actual loopback HTTP checks,
simulated phone/game flows and remaining on-device verification limits.

Implementation references: [Flask's Waitress deployment guide](https://flask.palletsprojects.com/en/stable/deploying/waitress/),
[Waitress server settings](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html),
[Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/)
and [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## V3.4.7 — Elo Guesser Stats

- Rebuilt `/elo_guesser_stats` as a detailed dashboard using the accepted
  Recognisability/Tournament layout and shared mode components. Each major
  panel gets its own row, centred heading, joined/divided figures, quiet insets,
  correctly constrained covers and a soft Elo Guesser red-orange glow. Entity
  names retain their own colours, bold text links and hover/focus underlines.
- Put completed guesses, correct picks, wrong guesses, best streak and overall
  accuracy first. Added current streak, longest miss run, active days and
  accuracy for the latest ten guesses and rolling 7/30-day windows.
- Added current collection coverage, accuracy across five saved Elo-gap bands,
  average correct/wrong gaps, closest successful pick and widest missed gap.
  Added first/second-card pick counts, success rates and selection shares.
- Kept top tracks and tracks to practise, now as full-width panels with larger
  covers, linked artist/proper-album metadata and explicit appearance counts.
  Each keeps ten results: five visible, five expandable. Practice entries must
  actually have at least one wrong appearance.
- Added artist, proper-album and tag records, each with up to five highest-
  accuracy and five most-missed entries. Added up to five repeated comparisons
  with pooled accuracy, number of guesses and average saved Elo gap.
- Added full paginated history: ten expandable results per page, newest first,
  with the first open. Summaries identify the chosen track, result, points and
  completion date. Details show both covers, song/artist/proper-album links,
  frozen Elo ratings, your pick, the higher-Elo track, gap and running streak.
  History is no longer limited to the latest thirty questions.
- Desktop comparisons keep covers beside the central VS and names outside.
  On phones, tracks stack around the VS divider. Metric groups, gap rows,
  expandable records and pagination use the shared responsive scale, with
  44 px touch targets on actions/details. Long names keep ellipses and complete
  accessible text; opening a result/name link supplies a touch alternative.
- The report renders from a single read-only snapshot. Removed the obsolete
  client-rendered Elo Guesser stats branch; Album Shelves keeps its existing
  renderer. Game selection, points, Elo, Overall calculations, ranking APIs,
  previews, cache behavior and V3.4.6.1 LAN protections are unchanged.

### Data definitions and saved-history limits

**Questions and appearances:** overall accuracy counts a completed question
once. A valid saved comparison has two different finite ratings and a recorded
choice of card 1 or 2. Correctness comes from those frozen ratings, not current
song Elo. Both offered living tracks receive one appearance and the same
correct/incorrect outcome, as in existing mode rankings. A wrong question is
therefore one wrong user guess and two wrong track appearances, when both tracks
still exist. Appearance counts are deliberately labelled separately.

**Collection records:** artist/album/tag figures pool their current linked
tracks' correct and total appearances; they do not average percentages. A
comparison between two tracks from the same group contributes two appearances.
Collaborations and multiple tags can contribute to separate groups, so group
totals must not be added together. Duplicate relationships count once per track.
Proper albums exclude singles, Unknown Album and missing/blank album links.
Accuracy ties favour more appearances, then name/ID. Most-missed records sort by
wrong appearances, then exposure. Practice tracks sort by lowest accuracy, then
greater exposure; untested and perfect-only tracks are omitted.

**Coverage:** eligibility mirrors the current game pool: tracks need a finite
numeric Elo and another track with a different rating. Audio is optional. If
all ratings are equal there is no playable pair, so coverage has no denominator.
Previously tested tracks outside the current eligible pool are disclosed
separately. Deleted tracks keep their saved question outcome but cannot receive
current collection links/appearances or enter repeated-pair records.

**Gap and choice patterns:** gap is the absolute difference between the two
saved ratings. Bands are below 25, 25 to below 50, 50 to below 100, 100 to below
200, and 200 or more. Fractional gaps are assigned before display rounding.
Average/closest/widest values use raw gaps and display one decimal place.
First/second card refers to offered order, not the correct song, artist order
or a permanent preference for one track. On phones this can be above/below
rather than left/right. Shares divide by valid completed picks; their accuracy
uses only questions where that card was chosen. No confidence/causation claim
is made from a small sample.

**Repeated comparisons:** swapped offer positions still form one pair. Only
surviving, distinct tracks with at least two valid saved comparisons appear.
Pairs sort by question count, then wrong guesses and stable names/IDs; displayed
track order is stable catalogue order, not an implied winner or original slot.
Ratings can differ across repetitions, so this group shows their average saved
gap instead of inventing a single historical rating pair.

**Dates and form:** rolling windows use the saved completion timestamp and
exclude future timestamps. Latest-ten form uses the ten most recent saved
completed questions and shows the actual sample count. Active days count
distinct UTC completion dates up to now; rendered dates use the browser's local
timezone. Streaks follow dated completion order with ID as the tie-breaker.
An ungradable dated result breaks a sequence without becoming a wrong guess.
Undated results remain at the end of history, ordered by ID; they are excluded
from streak/day/window counts and make the current streak unavailable. Best
streak and longest miss run then describe dated results, with a short notice.

**Missing data:** pending questions and their tokens never enter the report.
Unknown/invalid snapshots remain visible as unavailable results and count in
the saved-completion total; they are excluded from accuracy, gap/choice patterns
and track/group appearance totals. True zero rates remain zero; absent
denominators use an em dash. The old game schema does not record active answer
time, listening time or pause intervals: elapsed time between opening a pair
and submitting is not presented as reaction speed. No new counters or guessed
history are stored.

### Apply

Apply these edited/new files over **V3.4.6.1**, restart and hard-refresh the
computer/phone browsers. The footer shows **V3.4.7**. Keep the existing database,
backups and private instance key. Requirements and schema are unchanged from
V3.4.6.1. Shared page rules are in `README_PAGE_STYLE.md`; current checks and
verification limits are in `VALIDATION.md`.

## V3.4.8 — Album Shelves Stats

- Rebuilt `/album_shelves_stats` using the accepted Recognisability, Tournament
  and Elo Guesser dashboards. Main panels each occupy one row, with centred
  headings, joined/divided figures, quiet insets, the shared type/cover scale
  and a soft aubergine glow. Shelves figures remain mauve; entity names keep
  their own colours and text-only links with hover/focus underlines.
- Put completed rounds, track appearances, albums played and perfect rounds
  above the full-width **relative track order** bar. Points retain their actual
  earned/available denominator in the later results section. Album placement
  remains in an optional expandable breakdown.
- Added perfect/partial/no-point result splits, total/available points, average
  points, a link to the best saved round, current/best perfect streaks, active
  days and latest-ten/rolling 7-/30-day ordering performance.
- Added two-/three-album format comparisons and current playable album/track
  coverage. Eligibility includes the actual ten-track-round feasibility rule,
  rather than treating every numbered track as playable.
- Updated top/practice tracks to full-width shared rows with larger covers,
  linked artist/proper-album metadata and comparison/appearance counts. Each
  keeps ten entries, five visible and five expandable. Practice entries must
  have missed ordering comparisons.
- Added album/artist/tag ordering records, with five highest-accuracy and five
  most-missed entries. Every played album remains accessible through a native
  expandable list with ten per page; the old internally scrolling list is gone.
- Added full round history, ten expandable rounds per page. Details retain
  each saved shelf, album artwork/name, original track numbers, submitted
  shelf/position, individual points and order results. The first round opens
  by default; `?round=ID` opens an older selected round on its correct page.
  Deleted identities stay unlinked without merging different saved shelf slots.
- Added phone compositions for the longer heading, comparisons, metrics,
  saved shelves and result text. Important values wrap separately from variable
  names; native details, page actions and pagination have 44 px touch targets.
  Correct item labels use green; wrong album/order labels use red.
- Reused the existing grading function. Extracted the existing eligibility
  query for the game and report to share, preserving the picker's conditions
  and random behavior. Removed the obsolete client stats renderer and 53
  retired stats-only CSS selectors. Shared numeric formatting also serves
  Guesser without changing that page's output. Other dashboards, game actions,
  scoring, Overall, previews/cache behavior and LAN hosting are unchanged.

### Data definitions and saved-history limits

**Ordering and points:** the primary percentage pools correct ordering
comparisons divided by eligible comparisons, not an average of track/album/
round percentages and not weighted points earned. A selected track is compared
with the other selected tracks from its saved album shelf. Each direction is
counted, matching the existing game and mode rankings: a pair can contribute
one comparison for each of its two tracks. Both tracks must be on the correct
album shelf for their relative order to count. Repeated appearances count again.

Points still use the existing **0.5 album-placement + up to 2.5 relative-order**
formula per track. Legacy singleton shelves have no ordering question and only
a 0.5-point denominator. A ten-track saved round can therefore have fewer than
30 available points; no free order points or fabricated missing tracks are
added. Legacy saved track counts are reported as recorded. A perfect round
earns all its actual available points. Best round sorts by earned points, then
earned share and saved completion order; it is a literal points record, not a
new difficulty-adjusted score. Displayed point values use up to two decimals.

**Track outcomes:** fully correct, wrong album and order affected are exclusive
categories over graded appearances. Order affected means correct album but
less than full ordering credit. This can include a misplaced counterpart, not
only the track's own submitted position. These categories are not extra
penalties. Practice sorts by lowest ordering accuracy, then more comparison
evidence; perfect-only, untested and singleton-only tracks are excluded.

**Frozen facts and collection links:** grading uses saved album slots, original
track numbers and submitted slots/positions. Moving or renumbering a track
later does not rewrite those facts. Album participation/records follow saved
album IDs, while song/artist/tag names, artwork and profile links follow today's
catalogue. Artist/tag records pool current linked living songs' appearances;
collaborations/tags can contribute to several groups and must not be added
together. Duplicate relationships do not multiply totals. Album records pool
their saved appearances, including a removed song's still-known album.

Albums played counts surviving saved album IDs, matching the existing home
summary. All played albums remain in the full list; only current proper albums
receive album links or enter high/low album records. Singles, Unknown Album and
blank/missing albums are unlinked. If album identity has been deleted, history
retains separate saved shelf slots and their numerical results. Missing shelf
appearances cannot be deduplicated into an invented lifetime album count.

**Eligibility and formats:** the report shares the picker's proper-album/
unique-positive-integer track-number query, with at least two eligible tracks
per album. A counted album must also fit some feasible two-/three-album selection
supplying ten tracks. Coverage excludes historical tracks/albums outside that
current pool and reports them separately. Audio is optional. Two-/three-album
breakdowns use the number of saved shelf slots, so deleting album IDs does not
change the saved format. Other saved formats remain explicit.

**History and activity:** all saved completed rounds feed lifetime totals;
only displayed album/history lists are paginated. Pending rounds and their
tokens are excluded. Rolling windows use completion timestamps and exclude
future timestamps. Latest-ten form shows its actual saved sample. Active days
use distinct UTC completion dates up to now; display dates use the browser's
local timezone. Perfect streaks follow dated completion order, with ID as the
tie-breaker; nonperfect/ungradable rounds break a run. Undated rounds remain
at the end of history, are excluded from time/streak counts and make the
current streak unavailable. No active-answer timing is recorded or invented.

**Unavailable results:** empty details, unsupported rules, incomplete answers
or inconsistent slot/position/number facts remain visible as unavailable.
Their saved completion/track/album participation facts are retained, but they
are excluded from scoring/ordering totals and record rates. This does not turn
them into zero-point or perfect rounds. Zero is shown for a genuine zero;
rates without a denominator use an em dash. No stored counters or history
rewrites are introduced.

### Apply

Apply these edited/new files over **V3.4.7**, restart and hard-refresh computer
and phone browsers. The footer shows **V3.4.8**. Requirements/schema are unchanged.
Keep the existing database, backups and private instance key. Layout rules are
in `README_PAGE_STYLE.md`; verification and limits are in `VALIDATION.md`.


## V3.4.9 — Shared mode ranking boards

- Standardised Overall, Recognisability, Tournament, Elo Guesser and Album
  Shelves rankings using the accepted standard board: larger square covers
  (circular artists), coloured/bold linked metadata, underlined category links,
  Top/Bottom twenty switching and rank-dependent mode glows.
- Removed the extra metric-tab rows. Each mode has one main order: Overall
  score, Recognisability, tournament titles, Guesser accuracy and Shelves track
  order. Compact sample counts, podiums/wins or evidence/mode coverage give the
  number context. Detailed dashboards and scoring systems are unchanged.
- Recognition pools correct/available saved fields. Guesser counts track
  appearances (a question contributes to both participating tracks). Shelves
  pools correct/eligible relative-order comparisons, not weighted points or
  album membership. Artist/album rates pool their tracks rather than averaging
  track percentages; collaborations contribute to each linked artist.
- Tournament titles tie-break on podiums, match wins, entries and name; rate
  ties use sample size then name. Bottom reverses the same board. Untested
  entries and singles/unknown albums stay excluded. Existing metric query
  links open the main board and are normalised without the obsolete metric.
- Overall retains Songs, Artists, Albums and Tags; the other modes retain their
  three entity categories. Artist/album links use catalogue identities and song
  album metadata omits singles/unknown/missing albums. Counts wrap on phones,
  long names use the shared ellipses, and score labels can wrap beneath values.
- Shared navigation/row helpers avoid maintaining five separate page layouts.
  Styling guidance updated. Database, game logic, audio and security unchanged.

Apply edited/new files over **V3.4.8**, restart and hard-refresh. The footer
shows **V3.4.9**. Validation and its limitations are recorded in `VALIDATION.md`.


## V3.4.9.1 — Tournament points and tag boards

- Tournament rankings now order by saved tournament points, shown to two decimal
  places. Supporting podium/win/entry counts stay compact; existing tie-breaks
  apply when points are equal. No scoring formula changes.
- Added Tags to Recognisability, Tournament, Elo Guesser and Album Shelves,
  alongside Overall's existing Tags category. Tag records pool linked tracks'
  counters; recognition/guess/order rates use pooled denominators, not averages
  of track percentages. Tracks can contribute to each tag they belong to.
- Active Songs/Artists/Albums/Tags selectors now underline and softly glow in
  their own entity colour on all five boards. Top/Bottom controls and ranked
  row glows retain the mode colour. Phone wrapping is preserved.

Apply over **V3.4.9**, restart and hard-refresh. Footer: **V3.4.9.1**.
Database, game logic and audio unchanged.


## V3.4.10 — Search cards and achievements

- Standardised the main Search page with the approved fonts, rounded dark
  panels, semantic colours, soft entity glows, larger constrained artwork and
  phone sizing. Header search markup and catalogue matching are unchanged.
- Songs, Artists, Albums and Tags now share a card grid. Entity names and actual
  artist/proper-album metadata are separate links; single/unknown/missing albums
  are omitted from song metadata. Tags show # artwork, description, song count,
  Impact and earned badges instead of the previous compact text list.
- Added per-category result counts, Highest rating / Name A–Z sorting, and useful
  empty states. Search stays live, retains tag scope/deep-link query state and
  loads forty more results per action. Sort choice is saved in the page URL.
- All four entity categories can earn a single row of up to three achievement
  badges. Whole badges are fitted to the available width and restored on resize.
  Priority is championships, perfect mode rates, silver/bronze, other high mode
  rates, then strong voting records. Only the highest podium class is shown.
- Trivia badges require >=90% saved eligible-field accuracy (>=2 fields);
  Guesser requires >=80% correct track appearances (>=2 appearances); Shelves
  requires >=85% relative-order accuracy (>=6 comparisons). Standard and blind
  voting badges require >=75% wins across >=5 appearances in that mode.
  Sample counts remain in badge titles. These thresholds reward strong results
  without requiring perfect lifetime records or adding badges for mere activity.
- Artist/album/tag badges pool linked tracks' saved results. Guesser questions
  count as an appearance for each participating track; collection tournament
  counts sum track podiums, not distinct winning brackets. Recognition uses
  eligible fields, and Shelves uses relative-order comparisons, not points or
  album-placement rate. Untested tracks contribute no denominator. No invented
  entity-level streaks, perfect rounds or Overall results are added.
- Moved search state/rendering into a Search-only module and removed obsolete
  tag-list/badge CSS. Updated the styling guide. Game/scoring/audio/security and
  the supplied database are unchanged.

Apply over **V3.4.9.1**, restart and hard-refresh. Footer: **V3.4.10**.
Validation details and visual-check limitations are in `VALIDATION.md`.


## V3.4.10.1 — Search badges and browsing controls

- All percentage badges now require **at least 90%**: Trivia, Elo Guesser,
  Shelves relative order, standard voting and blind voting. Existing minimum
  sample counts, pooled calculations, podium badges and single-row priorities
  are unchanged.
- Restyled the native Sort selector with a rounded inset, accent border/chevron,
  clear keyboard focus and a 48 px touch target. Total/shown results now sit
  between the category controls and Sort. The toolbar stacks in that order on
  phones without changing the card grid.
- Added Random and made it the default when opening Search without text.
  Fisher–Yates shuffles the category's records once per visit; filtering and
  Load more use that stable order, avoiding repeated/skipped cards. Category
  round trips retain their order. Selecting Random after another sort reshuffles.
- Entering or editing a nonblank query defaults to Highest rating; clearing
  it restores Random. Explicit name/rating/random choices remain available,
  including in the URL. Query links without an explicit sort use Highest rating.
  Reloading Random creates a fresh ordering rather than storing a random seed.
- Updated the styling guide and tests. Header search, matching, game scoring,
  audio, security and database are unchanged.

Apply over **V3.4.10**, restart and hard-refresh. Footer: **V3.4.10.1**.


## V3.4.10.2 — Styled Search sort menu

- Replaced the native Sort select with a custom button/listbox. The open menu
  now matches Search's dark rounded panels, accent border/glow and entity colour,
  with highlighted hover/focus/selected rows and a selected checkmark.
- Kept all three sort choices and existing Random/query/pagination behavior.
  The popup opens on the selected option and supports arrows, Home/End,
  first-letter navigation, Enter/Space, Escape and Tab. Selection restores focus
  to the trigger; outside click/focus dismisses without moving focus back.
- Added 48 px trigger / 46 px option targets, viewport-constrained popup sizing,
  upward opening when needed and closure on resize. Other dropdowns and the
  header search are unchanged. Updated the styling guide and checks.

Apply over **V3.4.10.1**, restart and hard-refresh. Footer: **V3.4.10.2**.
No database, scoring, badge threshold, audio or security changes.


## V3.4.11 — Song, Album, Artist and Tag profiles

- Standardised the four entity pages with shared profile components, full-width
  mode panels, semantic colours/glows, larger readable text, joined metrics,
  constrained artwork and smaller-screen layouts. Added one shared profile
  renderer/styles file instead of separate copies for each entity.
- Swapped the top sections: the four key figures now follow the hero, with
  Overall below them. Overall's score calculation and Mode balance dropdown
  remain intact, including loading/error/retry behavior in its new position.
- Moved tag names into the hero metadata column rather than a separate row above
  the artwork. Entity titles, linked artists/proper albums, tag description and
  collection facts stay inside the hero. Album/artist relationships retain whole
  collaborator names. Hero artwork stacks above copy on phones.
- Tidied preview captions into compact insets with a clear preview count/index,
  duration and linked track title/artist. Kept visible 44 px previous/next
  controls, 48 px track play targets and existing loop/queue/failure behavior.
  No autoplay, timing, crossfade or transport changes.
- Each mode shows bite-sized figures first. Voting has wins/losses/appearances
  and a win-rate bar, with Non-blind/Blind splits expandable. Recognisability
  shows rounds, tested tracks, fields correct and accuracy, with field-level
  details expandable. Tournament leads with points, titles and podiums; further
  podiums, bracket count, match wins and linked bracket history are expandable.
  Guesser shows correct/wrong appearances and accuracy. Shelves leads with
  relative order, appearances, correct placements and points; membership and
  available-point rates stay in its expandable detail.
- Collection rates pool saved track numerators and denominators. Guesser
  counts both participating tracks when both belong to the collection;
  tournament points/podiums sum linked-track outcomes, while bracket count is
  distinct saved participation. This differs from counting a whole question or
  completed bracket only once on the global dashboard. No entity streaks or
  perfect rounds are invented. Scheduled matches do not add to win rates.
- Recognition headline totals retain saved legacy/manual totals; modern song,
  artist and eligible-album field breakdowns use their saved field counters and
  can differ from legacy totals. Shelves points retain their actual available
  denominator, including older singleton shelves. Missing rates show an em dash.
- Compact collection highlights avoid duplicating the same single track twice.
  Albums and up to ten recent song matches can be expanded; full History stays
  linked. Album track ordering and existing preview controls are preserved.
- Updated styling guidance. Database, mode scoring, audio controllers and LAN
  security are unchanged. Validation and visual-check limits are documented.

Apply over **V3.4.10.2**, restart and hard-refresh. Footer: **V3.4.11**.


## V3.4.11.1 — Profile colours, cover captions and open stats

- Fixed stat-value colours: the legacy `.mini-stats b` rule explicitly set pink,
  overriding inherited panel colours. Profile metric values now explicitly use
  their section accent. Voting/Trivia/Guesser/Shelves regain orange/gold/red/
  mauve, Tournament stays pink, and Blind subgroups retain mint.
- Moved Album/Artist/Tag preview information into the artwork. It shows only
  the linked selected track name and a small position/count, with no duration,
  artist line or initial preview caption. Kept it outside the cover's play button
  so title navigation and play/skip controls remain separate. Artist art remains
  circular. Removed the song profile's loop caption and the extra preview-count
  fact. Audio playback and queue behavior are unchanged.
- Artist/Album tags now prioritise distinct songs from that profile sharing each
  tag. Chips show the count and fit the first two rows, adapting on resize; ties
  use name then ID. Song tags are unchanged and Tag pages have no related-tag
  list. Hidden chips are also removed from keyboard navigation.
- Removed profile expansion controls from voting splits, field accuracy,
  podiums/brackets, Shelves details, album lists and recent matches. The data is
  directly visible in quiet inset groups. Overall's Mode balance dropdown stays.
  Tournament uses points/brackets/podiums at the top, with first/second/third
  below, avoiding the repeated title count. All saved bracket rows are visible;
  recent song matches keep their existing ten-result limit and full History link.
- Updated the shared style guide and regression checks. Database, game scoring,
  audio controllers and security are unchanged.

Apply over **V3.4.11**, restart and hard-refresh. Footer: **V3.4.11.1**.
