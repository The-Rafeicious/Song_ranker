# V5.1.2.2 validation

GitHub Actions, Ubuntu, Python 3.11 and Node 22.

- 278 Python tests passed on commit 9b5ba7cbb45315f9f57990a3095dcc935b426f53.
- All five JavaScript suites passed: 167 catalogue, 99 developer system,
  112 tag workbench, 134 judgement gameplay and 55 Spotlight core assertions.
- 194,481 five-percent-grid position combinations passed scoring bounds,
  equal-position ties, ordering, permutation and absolute-placement checks.
- Reference points: all 0/20/50/80/100% produce 0/1/3/5/6 each;
  [100,0,0,0] produces [12,0,0,0]; [80,60,40,20] produces [7,4,2,0].
- New database tests cover original positions, server-owned scores, replay and
  conflicting retry, exports/rebuilds, invalid SQL close attempts, zero/max rounds,
  schema-17 migration with legacy answered and open receipts, and backup creation.
- UI tests cover silent entry, manual-start looping, selection-to-audio and
  audio-to-selection changes, stop, finite results, retry and legacy drafts.
- Final follow-up adds a direct 13-point Global Stats feed assertion and fixes
  its previous hardcoded 12-point caption; CI reruns on every branch update.

No active database or user backup was modified by this work. Database changes
apply through the app's existing verified, backed-up migration on launch.
