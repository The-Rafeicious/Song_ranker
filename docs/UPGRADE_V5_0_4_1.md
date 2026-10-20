# V5.0.4.1 — profile page revamp

Stop the app, apply the changed files, restart and hard-refresh all open tabs.
The footer should show V5.0.4.1. No database migration or dependency change is
required; schema remains 15.

- Song/album hero artwork, player frame and play overlay share rounded corners.
  Artist artwork keeps the same circular clipping across every player layer.
- All four entity pages share compact Voting, Recognisability, Tournament,
  Elo Guesser and Album Shelves panels. Useful breakdowns are visible inside
  the panels. Explanations, per-bracket lists and listening diagnostics are
  removed from profiles; dedicated stats pages remain available.
- Overall alone keeps its Mode balance dropdown, without explanatory paragraphs.
- Tag albums initially show six; Show more adds six. Artist, album and tag
  song lists initially show thirty; Show more adds thirty. Buttons are centred
  below the list and disappear when all entries are visible.
- Expansion preserves active row previews; collection playback still uses the
  full preview queue. Album track-number sorting remains available.

Validation: 137 jsdom profile assertions pass using the real frontend scripts
with stubbed collection/Overall requests. JavaScript syntax and diff whitespace
checks pass. Browser painting, physical-device layout and real audio were not
verified in this environment. See [validation](VALIDATION.md).
