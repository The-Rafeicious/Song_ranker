# V5.5 — tournament brackets and evidence

V5.5.0 makes artist/album tournaments points-only, retains full first-round Elo
for whole-library tournaments and half for tags, and improves bracket viewing.

- Startup backs up affected databases before voiding historical artist/album
  preference influence and rebuilding Elo/evidence. Match facts, bracket points
  and podiums remain. Retirement commits atomically and does not repeat.
- Saved/live brackets use connected interactive trees, direct round navigation,
  highlighted track routes and a useful inspector. Pending Blind identities stay
  hidden; a non-JavaScript match-list fallback remains.
- Finishing a tournament saves the result, animates each side through elimination
  and advancement, then reveals the podium. Skip, replay and reduced-motion support
  keep the sequence optional and accessible.
- Replay audio draws from the final eight quarter-final entrants (four actually
  reach semi-finals), follows the current side and loops through one shared player.
  No bulk preloading; cached clips are reused where available. Missing/blocked
  audio does not block the replay. Sound off persists through the podium handoff.
- Tournament Stats retains its layout, corrects semantic colours, adds points-only
  and entry-depth context, and removes duplicate Elo-history and activity figures.
- Schema remains 21. Tournament points/placements and unrelated game rules stay.


## V5.5.1 — per-album Shelves exclusion

- Add **Exclude from Album Shelves** to the existing album editor and an
  Included/Excluded column/filter in the Dev album table.
- Flagged albums keep their normal identity, songs, artwork and other modes. New
  Shelves questions and current eligibility omit them; saved rounds and results
  remain available. Unchecking restores normal eligibility.
- Schema 22 adds one default-off integer flag per album, with a verified pre-upgrade
  backup and atomic migration. Older databases/dumps remain included by default;
  backups, exports, rebuilds and sync preserve explicit flags.
- This allows grouped placeholder releases instead of separate Single album rows;
  it does not automatically merge records or compress existing data.

## V5.5.2

Excluded albums keep their album identity, but skip the album-name field in new Trivia rounds. Shelves profile panels only appear for tracks and collections with eligible albums. Saved Shelves rounds containing an excluded album are hidden as whole rounds from reports, trends, rankings and Overall evidence; nothing is deleted, and including the album again restores that history.

Tournament history links to a dedicated bracket page. Mirrored halves feed a larger central final, with a smaller third-place match below. Track selection includes route and match details, and replay results advance every 1.6 seconds. Blind identity protection, reduced motion, skip and bounded preview playback remain in place.

## V5.5.3

Bracket replay audio uses the four semi-finalists, with sound enabled by default. Clip changes reuse the shared ready-only 1.5-second crossfade, and natural completion fades out before the podium. Sound off, skip, leave and reduced-motion behavior remain explicit.

Mouse and pen users can click and drag the bracket in both directions. A movement threshold preserves normal track selection; touch scrolling and keyboard/round controls remain available.

## V5.5.4

Standard Vote, Tournament and Elo Guesser cover artwork gains a soft mode-coloured rim. Confirmed playback brightens the rim, moves a glow around its edge and sends out a small fading wave. The other cover stays quiet; buffering, pause and stop remove the pulse. Reduced-motion users retain a stationary playback highlight. Playback and voting rules are unchanged.

## V5.5.5

Automatic preview loudness balancing is on by default, with an on/off checkbox beside the site volume slider. The shared player measures audible levels as a preview plays, gently boosts quieter clips and reduces louder clips within conservative limits. Site volume remains the overall level; existing fades and loops remain independent.

Learning uses the playing audio stream, so it adds no downloads or database storage. A small tab cache remembers levels by source revision. Direct external previews and browsers unable to use Web Audio keep normal playback. Very quiet recordings and different mixes may still sound different; this is practical balancing rather than a full loudness remaster.

## V5.5.6

Tournament replay holds each result for 3.5 seconds. The bracket fills the page between the navigation banner and footer, with no inset frame or stage selectors. Drag, touch scrolling and keyboard selection remain available.

Selecting a track drops its details directly below that match; Close or Escape dismisses the panel. Outer rounds use darker tournament pink, stepping into brighter shades and a stronger glow towards the central final. Existing results, Blind privacy and the four-track audio handoff are preserved.

## V5.5.7

Active tournament matches no longer show the out-of-place Explore bracket link during voting or answer reveals. Saved brackets remain accessible from Tournament Stats, and the completed tournament still shows its bracket replay before the podium.

## V5.5.8

Roll back automatic preview loudness balancing and its checkbox. Native recording levels, site volume and smooth crossfades remain.

Tournament replay completes each quarter in order, following its semi-finalist's song without restarting on each result. Semi-finals, third place and the final play their winners. Full previews loop naturally instead of jumping back every six seconds; song changes use the shared ready-only crossfade. Missing clips stay silent rather than substituting unrelated tracks.

## V5.5.9

Bracket workspaces have almost a full viewport of diagram height, with the banner/header outside it so the page can scroll them away. Vertical scrolling can continue from the map onto the page.

Impact now uses only songs that have played a match, and a lighter square-root median tested peer-size prior. This removes unplayed-1200 dilution and excessive compression without changing song Elo or saved results. Collections without tested tracks show no Impact. On the current backup, proper-album scores span approximately 33 points instead of 14; artist and tag spreads also widen.

## V5.5.10

Tournament competition credit favours library brackets (100%), then tags (50%). Artist-only and album-only evidence is limited to 2% and 0.5% of each track's completed broader entry credit; repeating local brackets shares that cap instead of inflating it. No broader evidence means no local contribution to competition. Weighted wins, points, podiums and entry evidence feed rankings, record leaders and Overall consistently.

Artist and album profiles show their own selective brackets with full raw match/point summaries, winners and replay links. Archives, saved results and Elo stay unchanged. Overall calibration updates automatically.

## V5.5.10.1

Remove repeated scope-credit policy notes from tournament stats, rankings and profiles. Artist/album-only tournaments have a separate profile box below the main tournament record, with completed-bracket, match, played-track and point totals plus individual bracket/replay links. Seed patterns now explains starting seeds, top/bottom halves and later-seed wins. Scoring is unchanged.

## V5.5.10.2

Artist/album tournaments now have zero competition and Overall influence. Library/tag reports exclude them; saved results and all bracket replays remain available.

A dedicated Artist & Album Tournament Stats page compares completed local results: track titles, win/title rates, repeated entries, podiums, points, artist/album breakdowns and head-to-head pairings, with collection filters and a paged archive. Unfinished Blind identities stay hidden. Profile cards become compact summaries linking to the filtered report and latest bracket.

## V5.5.10.3

Library and tag tournaments both contribute full competition credit to tournament stats and Overall; artist and album brackets remain excluded. Tag first-round Elo retains half influence. Existing results are recalculated without changing saved matches or Elo.

Tournament Stats includes a compact artist/album summary linked to its dedicated report, which uses shorter labels and track artwork.

## V5.5.10.4

Artist and album tournament stats use shared report rows with top and bottom comparisons and a lookup for individual track, artist and album results. Filters use styled native controls. Tournament and collection profiles show the leading track in a compact inset.

## V5.5.10.5

Local tournament reports reuse tournament selection controls, show recent activity, bracket distributions and repeated-entry/champion evidence. Lookups align titles, podiums, rates, wins, losses and points, with related tracks or opponent records. Scope filters apply throughout; no scoring or Elo changes.

## V5.5.10.5.1

Tournament report menus include entity artwork. Lookup separates songs, artists and albums with a compact type selector. Entity comparison borders, dividers and glows use matching semantic colours.

## V5.6.0

Reviewed adaptive mode selectors. Tournament seeding prioritises strength over past titles, with bounded opponent-adjusted local evidence. Voting softly favours fresh opponents using all tournament rounds, including artist/album results. Entry fairness and rating policies remain unchanged.

### V5.6.0 selector review

Tournament entry draws retain exposure fairness and bounded Vibe affinity. Seeding now follows Elo with only 2% pool-spread jitter; a former title alone no longer overrides strength. Seeds one/two occupy opposite halves and the top four separate quarters. Artist/album match outcomes add at most 10% of pool spread to seed strength, adjusted against current opponent Elo, shrunk by eight neutral observations per opponent and averaged equally across distinct opponents. This is private selection evidence, not a rating.

Standard and Blind voting softly reduce repeat-opponent weight using ordinary effective votes and all valid saved tournament matches, including local rounds. The multiplier bottoms out at 25%; exposure fairness, Elo proximity and exploration remain. Trivia, Guesser, Shelves and Vibe retain their existing mode-specific policies. Public Elo, Overall and saved history are unchanged. Difficult losses already cost less Elo than unexpected losses; selection does not fabricate rating corrections from a small sample.

## V5.6.1

Standard Vote family surfaces use light green, distinct from song green and the unchanged orange Non-blind / teal Blind subsets. Tournament first-round history combines pink origin edges with visibility-coloured edges and labels. Scoring and selection are unchanged.
