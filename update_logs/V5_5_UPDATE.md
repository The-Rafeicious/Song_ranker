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
