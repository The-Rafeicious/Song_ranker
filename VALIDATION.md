# V3.3 validation

- **87 backend tests passed**, including existing voting, trivia, tournament,
  catalogue, metadata and Dev tests plus 14 new-mode tests.
- **73 interface assertions passed** against a Flask app running on a copied
  database. Checks cover Guesser/voting tab switching, hidden/revealed ratings,
  independent writes, ten-track shelves, keyboard controls, preview cycling and
  pause, scoring, next round, new stats/rankings, profiles, home/global records,
  Dev search/reset controls and the footer.
- JavaScript syntax checks and parsing of both shared stylesheets passed.
- Schema-8 migration preserves existing domain records and makes a pre-upgrade
  backup. Repeating migration does not change the database again. Integrity and
  foreign-key checks passed on test databases.
- New modes reject forged/repeated answers and invalid track placements, use
  frozen answer facts, handle unequal shelf sizes and position gaps, exclude
  singles from shelving, and keep completed scoring after song deletion.
- Reset/delete tests verify authentication, backup creation and isolation from
  other modes and music records.
- The original supplied database was not migrated or edited while building this
  update. All tests use temporary/copied databases. No database, SQL snapshot or
  personal test results are included in the release ZIP.

Graphical browser rendering and real Apple playback were unavailable. Interface
checks use DOM rendering and mocked media events; they verify the logic and
structure, not actual sound output or pixel-level spacing. Existing Apple
throttling/preview error handling has its own regression coverage and is retained.
