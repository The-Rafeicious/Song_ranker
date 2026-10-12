# V3.3.3.2 — Shelves spacing and result styling

Apply over **V3.3.3.1**. Stop the app, copy the patch's `Song_ranker` contents over
your project, restart and hard-refresh the browser. The footer shows **3.3.3.2**.

- The Album Shelves play page has a **1480 px desktop maximum**, increased from
  1280 px. Existing padding, mobile stacking and compact preview controls remain.
- Submitted positions stay small and red beside the correct number, with the
  strike-through removed for readability. Saved-position labels remain available.
- Points, Next round and Track order use matching backgrounds, borders, corners,
  height and glow. Points and Track order use matching label/value typography.
  The centred layout and narrow-screen arrangement are retained.

This is a CSS patch plus version/documentation updates. JavaScript, scoring,
selection, audio, data and schema are unchanged. No migration is required, and
no database or backups are included.

Verification: shared CSS parsing and the existing **351 interface assertions**
passed using a copied database with controlled media/timers. Computed-style
inspection confirms the width, matching box frames and readable submitted numbers.
The original database hash is unchanged. Graphical rendering was unavailable;
pixel-level appearance has not been verified here.
