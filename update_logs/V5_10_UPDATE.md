# V5.10.0.0

Tournament matches award bracket points in every round. The one-time startup
rebuild backs up the database, deletes tournament Elo events, then replays the
remaining votes and manual adjustments. Saved brackets and placements remain
available. Voting and Query no longer present a separate first-round Elo source.

## V5.10.1.0

- Play background previews from the banner. Choose related music by shared tags
  and Vibe Maps, or browse the top and bottom by track Elo or collection mean Elo.
- The player starts after your first preview, waits for selected previews to
  finish, and follows the site volume. Pause it from the banner at any time.
- The queue and clip position carry across pages in the same tab. Related mixes
  periodically favor a neighboring track by a different artist.

## V5.10.1

- The background player automatically rotates between album, artist, tag, and
  Vibe Map connections. Connection types that have gone unused gain weight
  when a suitable track is available.
- The banner popup shows the cover, track, artist, visible release, progress,
  and how the current clip connects to the previous one.

## V5.10.2

- Randomise tournament bracket positions and first-round sides after the
  exposure-weighted entry draw. A favourite can face another favourite early,
  and similarly rated tracks can meet at any stage. Strength seed numbers
  still describe the entrants in tournament reports.

## V5.10.2.1

- Restore seeded bracket placement. The top two start in opposite halves and
  the top four in separate quarters. Lower seeds vary within groups of four,
  and each first-round match still randomises its left and right sides.

## V5.10.3

- Voting unlocks after listening to both previews for 5 seconds in non-blind
  or 10 seconds in blind. Tournament rounds add 2 seconds per round, capped
  at 20 seconds. Each button fills as its preview plays.
- Listening excludes pauses, buffering, seeking, muted audio and hidden pages.
  Tracks without a preview wait for the other track's listening requirement.
