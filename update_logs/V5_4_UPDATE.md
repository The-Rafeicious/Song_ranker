# V5.4 — adaptive Elo

V5.4.0 preserves the 32-point ordinary/global and 16-point scoped-tournament
Elo budgets while adapting the logistic scale to tested-song rating spread.

- Target scale is `clamp(8 × IQR, 200, 400)`, blended from 400 using mean
  completed appearances divided by that mean plus four. Fewer than four tested
  tracks use 400. Unplayed catalogue additions do not compress the scale.
- First startup archives the complete previous database before replaying effective
  match history, corrections, voids, tournament weights and manual overrides in
  saved order. All projections and the durable policy marker commit atomically.
- Future votes, corrections and startup replay use the same public and independent
  Non-blind/Blind calculations. Full-history peak Elo/rank are rebuilt; protected
  legacy anchors are retained. Equal opponents still exchange ±16 or ±8.
- Backup/replay failure leaves old ratings intact and stops startup. Concurrent
  starts serialize; later starts skip the completed activation. The startup log
  identifies the permanent rollback archive; recovery guidance describes how to
  restore it together with the old source.
- Schema remains 21. No catalogue, tag, other game result, selector or tournament
  eligibility change. Original vote facts and frozen Guesser answers are retained.
