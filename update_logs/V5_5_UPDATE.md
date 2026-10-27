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
