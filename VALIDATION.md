# V3.2.1 validation

- 34 backend tests pass on temporary database copies. New checks prove each
  scoped reset preserves the library and other modes' records, backs up the
  exact pre-reset data, validates its confirmation phrase and requires Dev
  access. Trivia answer links reveal only checked fields, and single rounds
  keep album correctness/timing NULL and a two-field recognition denominator.
- 70 V3.2.1 interface assertions, 58 V3.2 mode assertions and 78 prior-design
  regression assertions pass against Flask with jsdom (206 assertions total).
  Coverage includes input ordering, blanks for singles, slower flips, linked
  answers, short feedback/resumption, layout structure, badge thresholds,
  direct navigation, scope-specific reset dialogs, the three-place podium,
  standard/tournament voting, bulk editing and existing collection features.
- Python compilation and JavaScript syntax checks pass. SQLite integrity is
  `ok`; foreign-key checks have no violations. The supplied database is unchanged.
- Audio playback is simulated in interface checks. Live preview availability
  and audible playback are not verified here. Rendered browser screenshot
  review remains unavailable in this environment.
- V3.2.1 requires no schema change beyond V3.2's schema 5. The ZIP contains only
  application files and documentation, with no database or backup replacement.
