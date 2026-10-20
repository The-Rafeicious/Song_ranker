# V5.1.2.1 validation

All five JavaScript suites passed: **124 gameplay, 49 Spotlight-core, 167
catalogue, 99 system and 112 tag-workbench assertions** (551 explicit assertions),
plus 625 allocation property cases. **272 Python tests passed.** Packaging checks are recorded in the release
manifest.

## Spotlight interaction

Deterministic DOM checks verify footer order, Next round wording, selectors
below metadata, thumbnail markers, overlap expansion coordinates and hidden
points before confirmation. Placement pulses, a resettable 1.5-second idle
selection delay, manual cancellation, revisiting a placed song and drag/release
behavior are covered. The allocation’s existing 625 distance/tie/order/translation
cases continue to pass.

Confirmed receipts reveal the same integer shares, rearrange covers by point
order and start the highest-scoring preview. Timed tests verify one finite pass,
current-song highlighting, stopping at the last snippet, a single next-round
schedule and manual Next cancellation. Result playback does not resample or
resubmit listening. Browser permission blocks retain the visible result for
manual Play/Next. Retry, legacy manual receipts, drafts, Vibe controls and
cross-tab Standard/Quick settings continue to pass.

A real Waitress/DOM run loaded the full shared/page script stack, exercised
placement, footer preview control and score-first results, saved real fixture
receipts and opened dedicated stats. No JavaScript errors were captured. Safe
restart retained those answers at one path; explicit refresh cleared only the
safe database at that same path. The source fixture remained byte-for-byte exact.

## Release and compatibility

The preceding release is relabelled V5.1.2. The old guide path remains a pointer;
V5.1.2.1 applies directly over the last Spotlight download, including its former
V5.1.1.3 label. Current documentation, style reference, technical/database guides
and release log are updated. Historical measurements below retain their counts.

Patch contents are checked against the last download so only changed/added files
ship. An overlay onto that installation must match the complete project hashes.
Schema, backend mode rules, adaptive selection/Overall and safe-mode sources
are checked unchanged. Syntax, CSS/templates, documentation links and archive
checks are run during packaging. No active database, secrets or generated test
answers are included. CSS/DOM checks do not establish rendered browser/device
paint or physical audio output.

---

# V5.1.2 validation

**272 Python tests passed. All five JavaScript suites passed:** 92 gameplay,
40 Spotlight-core, 167 developer catalogue, 99 system and 112 tag-workbench
assertions (510 explicit assertions), plus 625 allocation property cases.

## Relative placement and receipts

The allocation grid checks total 12, whole nonnegative shares, monotonic order,
exact tied shares, reversal/card-order independence and translation invariance.
Examples include 3/3/3/3 for equal placements, 12/0/0/0 for a lone high extreme,
0/4/4/4 for three equal high songs and near-equal points for tight clusters.
Invalid/partial/sparse positions cannot produce a split.

Real DOM checks cover card selection without autoplay, a centre click with no
slider-value change, all-four placement before saving, live cover points,
collision lanes, keyboard controls, preserved album links, removed manual/Skip
controls, exact integer API payloads, single rapid save, audio-node continuity,
listening samples, draft resumption and frozen retry. Old unconfirmed manual
receipts retain their original payload. Vibe controls and unjudged Skip pass.

## Rotating previews

Deterministic media-clock checks cover Standard 20 seconds, Quick 10 seconds,
wraparound, manual jumps, pace changes after partial listening, buffering pauses,
one current player, retained playback after save, cancellation, stale work,
all-four failures and browser playback blocks. Tests also load the real
RoundFlow settings module and exercise Standard/Quick/cross-tab duration changes.
DOM checks redirect an active loop by cover click and stop on a hidden page.

A real Waitress server/DOM harness loaded all shared and page scripts. It
verified the simplified Spotlight heading, selected all four positions, checked
sum 12 and ordered shares, started/redirected/stopped the loop, saved the answer
and rendered populated dedicated stats. Vibe also saved and rendered correctly.
There were no JavaScript errors. Safe restart kept both results at one path;
explicit refresh cleared only safe results at that same path. The source fixture
remained byte-for-byte unchanged.

## Compatibility and packaging

Schema 17, backend answer validation/rules, support formula, adaptive selectors,
Overall calibration 7 and persistent safe mode are unchanged. Their source
hashes are checked against V5.1.1.2. Python/template/JavaScript/CSS syntax,
documentation links, patch paths/checksums and an overlay onto V5.1.1.2 are
checked before delivery. The ZIP contains changed/added files only, with no
live databases, generated answers, backups, secrets or safe runs.

CSS/DOM checks do not verify rendered browser/device paint or physical audio.
Historical V5.1.1.2 validation follows unchanged.

---

# V5.1.1.2 validation

**271 Python tests and 456 JavaScript assertions passed.** The four DOM suites
contain 78 gameplay, 167 developer catalogue, 99 system and 112 tag-workbench
assertions. Retired-mode tests are replaced by migration and persistent-safe
regressions; historical counts are retained under `update_logs/validation/`.

## Storage and isolation

- Schema-16 fixtures migrate to schema 17 with only retired-mode choices,
  rounds/items, listening and exposure entries removed. Other stored values,
  row IDs, extension notes and sequence high-water marks reconcile exactly.
- The original database is retained in a verified pre-upgrade backup. A second
  launch adds no repeat migration backup. JSON rebuild and versionless SQL
  restore apply the same retirement. Foreign-key checks pass.
- Safe launches reuse one path and preserve test edits through repeated restarts.
  The newest marked legacy run is adopted and only same-source marked old runs
  are pruned. Unmarked folders are preserved and refused as overwrite targets.
- Explicit refresh loads the latest main snapshot at that same safe path.
  A failed source copy retains the previous safe database and releases the lock.
- WAL snapshots, missing/corrupt sources, source-byte equality, hardlink aliases,
  write/attach guards, launcher locks and disabled Git are covered. The backend
  smoke tool writes a disposable child copy.

## Pages and running app

A real Waitress server and DOM harness verified seven Home cards, the current
emojis, both subjective games and both dedicated stats pages with all shared
scripts loaded. Centre-overlay play/pause toggled once per click, album links
rendered and each game saved a real fixture decision. No JavaScript errors were
captured. After stopping/restarting, both results remained in the same safe
database. An explicit refresh cleared them at the same path; one safe-run folder
remained throughout. The source fixture stayed byte-for-byte unchanged.

Removed HTML/API routes return 404 and current navigation/configuration expose
only the two remaining subjective modes. Vibe advertises red `#FF3B3B`.
All 27 stylesheets and all Jinja templates parse. Stats dropdown rules provide
full-width block links, nowrap labels, no height limit and no inner overflow
scrolling. JavaScript/Python syntax, documentation links, archive contents and
release hashes are checked at packaging.

CSS/DOM checks are not rendered-browser or physical-device paint checks. No live
Apple requests, physical audio output or Windows runtime were verified here.
All tests use disposable data; the package contains no active database, sample
answers, backups, secrets or safe runs. Remaining adaptive selection/quality
formulas are retained; Overall stays calibration 7.

[Previous validation](../update_logs/validation/V5_1_1_1_VALIDATION.md) ·
[Earlier history](VALIDATION_HISTORY.md) · [Upgrade](UPGRADE_V5_1_1_2.md)
