# V5.1.2.2

- Connecting bar: Not connecting / Some connection / Really connecting.
- Server-calculated, half-up whole points: clamp(6x + 8(x − mean), 0, 12).
- Flexible 0–24 round total; results show Points awarded.
- Schema 18 adds original percentage positions and versioned close validation.
- Existing receipts, pending legacy rounds, IDs and backups retain their facts.
- Stats sum actual points; Overall uses the same monotone support scale.
- Preview rotation and placement selection follow each other. Manual play starts
  the loop. Explicit stop and silent page entry remain supported.

Validation: GitHub Actions passed all 278 Python tests and five JavaScript
suites (567 explicit assertions), plus 194,481 scoring combinations. Coverage
includes server-owned scores, idempotency, zero/max rounds, legacy migration,
lossless export/rebuild, database constraints, linked playback and global totals.
Local execution was unavailable; verification used GitHub's Ubuntu runner.
