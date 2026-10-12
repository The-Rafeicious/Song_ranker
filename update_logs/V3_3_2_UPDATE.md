# V3.3.2 — answer reveals and mode records

## Install

Apply over **V3.3.1**. Stop the app, extract this patch and copy its `Song_ranker`
contents into your existing project, preserving the relative paths. Restart with
`python main.py` and hard-refresh the browser. The footer should show **3.3.2**.
Keep your existing database and backups; neither is included in this patch.

## Elo Guesser

- Elo ratings reveal at the bottom of the covers after answering.
- A correct pick shows green feedback and +1. A wrong pick shows a red loss
  message, +0 and the streak reset, alongside the actual correct song.
- The higher-rated song plays a short snippet after either result.
- The next pair loads automatically after about 4.5 seconds. It starts silently;
  there is no normal next-round button. Retry appears only if loading fails.

## Album Shelves

- Two or three albums are chosen automatically; the count selector and manual
  new/next-round controls are removed.
- Submit sits immediately below the preview player. It becomes an animated score
  counter during the reveal. Round results stay together at the top in the
  Shelves colour, with percentage bars.
- Tracks flip one by one to reveal the correct album and original track number.
  Each gets a short snippet when available. The sequence follows the submitted
  shelf positions so mistakes can be compared directly.
- Green means the album and every applicable ordering comparison are correct.
  Wrong albums **or ordering errors** show red with explicit labels. Partial
  credit is preserved and counted; correct album membership alone cannot make
  an incorrectly ordered track look perfect.
- Each reveal uses a 0.42-second closing flip and a 1.6-second answer window,
  including a snippet of up to 1.2 seconds. After all ten reveals, correct shelves
  appear and the final score stays visible for about 3.2 seconds. The next round
  then loads automatically and silently.
- Reveal rows scroll into view, the score summary stays visible and the next
  round returns to the controls. Reduced-motion settings disable flip animations.

## Stats, rankings and Dev

- Guesser and Shelves stats have more space between summary sections, percentage
  bars and bold green song links. Shelves accuracy is separated from round totals.
- Shelves has an **Albums Played** section with artwork, rounds, tested tracks,
  correct placement percentages and bars. It reads saved album membership from
  completed rounds, so later catalogue moves do not rewrite participation.
- Songs, Artists and Albums buttons on all special-mode rankings use their own
  entity colour when selected or hovered.
- Guesser and Shelves Dev records use dedicated tables, wider search fields,
  readable wrapped track names and clearer action spacing. Existing searches,
  individual deletion and scoped resets remain available.

## Data and playback

Database schema stays **8**. No migration, new table or stored field is required.
Scoring, round selection and answer writes are unchanged. Each reveal uses the
single saved answer response; animations do not generate extra result records.
The stats API adds only a read-only participating-album query.

Answer audio uses the existing preview checks, volume and request limits. There
are no retry storms or increased limits. Missing previews, playback errors or
rate limiting do not stop the reveal or progression. New clips pause older clips;
leaving the page cancels audio and transition timers. Reopening resumes an
unanswered round as before.

## Verification

**88 backend tests** and **62 interface assertions** passed, alongside JavaScript
syntax and stylesheet parsing checks. Tests cover automatic progression,
navigation cancellation, snippets, single-write scoring, wrong-order colouring,
partial credit, stats bars, saved album participation and Dev records. The live
database remains untouched.

Actual Apple playback and graphical browser rendering were unavailable in this
environment. Media events and reveal timers were controlled for interface tests;
pixel-level layout and real sound output need a local browser check.
