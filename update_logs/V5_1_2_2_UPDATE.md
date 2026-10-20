# V5.1.2.2

- Connecting bar: Not connecting / Some connection / Really connecting.
- Server-calculated, half-up whole points: clamp(6x + 8(x − mean), 0, 12).
- Flexible 0–24 round total; results show Points awarded.
- Schema 18 adds original percentage positions and versioned close validation.
- Existing receipts, pending legacy rounds, IDs and backups retain their facts.
- Stats sum actual points; Overall uses the same monotone support scale.
- Preview rotation and placement selection follow each other. Manual play starts
  the loop. Explicit stop and silent page entry remain supported.

Validation: local Python/Node execution was unavailable in this session.
Added regression coverage for the new formula, receipts and schema checks.
