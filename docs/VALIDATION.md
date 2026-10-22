# Validation

## Current evidence

The integrated Vibe Map v1.1 code passed **358 Python tests**, the complete
JavaScript suite and the Chromium integration run on feature commit
`962ef3a50cc79967da1ee6fab380c68c37dd0306`:
[successful workflow](https://github.com/The-Rafeicious/Song_ranker/actions/runs/39692077626).
That is recorded code-validation evidence, not a claim that documentation edits
change or retest gameplay. This documentation PR additionally checks local links,
anchors, file references, family coverage and a documentation-only diff.

The frozen `tests/fixtures/schema_v9.sql` and `schema_v12.sql` files are present.
Old “missing fixtures / full discovery blocked” statements are **expired**;
[fixture provenance](../tests/fixtures/README.md) explains the restored inputs.
Historical test totals referred to different releases/suites and are not current
counts. Long repeated validation transcripts and old package hash manifests have
been retired; see [retired references](RETIRED.md).

## Reproduce the automated checks

From the repository root, install runtime requirements and test-only Node tools:

```sh
python -m pip install -r requirements.txt
npm install --no-save --no-package-lock jsdom@26 playwright-core@1.58.2
python -m unittest discover -s tests -v
```

Run JavaScript suites with the served-Dev harness for its integration test:

```sh
for test in tests/test_*.js; do
  case "$test" in
    tests/test_dev_pages.js) python tools/validate_dev_pages.py ;;
    *) node "$test" ;;
  esac || exit 1
done
python tools/validate_vibe_page.py
```

The shell loop is for a POSIX shell; PowerShell users can run the individual
`node tests/test_NAME.js` suites and the Python harnesses. The browser harness
requires an installed Chromium/Chrome executable; GitHub Actions supplies the
Linux environment. CI runs on pull requests and pushes to `main` and
`New-modes-test`, and fails on errors rather than ignoring missing tests.
See [workflow](../.github/workflows/tests.yml) for the maintained commands.

## What these checks establish

| Area | Evidence |
| --- | --- |
| Storage and recovery | Frozen-schema migration, lossless export/rebuild, exact values/rowids/sequences, validation, rollback and backed-up restoration. |
| Preference and game facts | Retry/idempotency, stale offers, corrections/replay, weighted tournament Elo, frozen quiz answers and mode-specific scoring. |
| Catalogue/Apple/Dev | Signed offers, current-source storage, bulk review, tag limits, metadata fill, transaction boundaries and Dev authentication. Apple transport is mocked. |
| Sync and shutdown | Disposable checkouts/bare remotes, branch/baseline/deletion conflicts, no unsafe upload, launcher ordering and acknowledged stop. |
| Browser/served pages | Real templates/scripts/routes, Home/Global/rankings/profiles, Vibe placement/results/inspection, Dev save/map-clear/delete, desktop/phone geometry and screenshots. |
| Merge cleanup | Preview no-op, multi-mode clear, exact catalogue retention, restore backup, stale/invalid requests, transaction rollback, one-time marker and export retry. Disposable databases only. |

Browser screenshots and DOM/media mocks do not prove physical audio output or
every Windows/Python/browser combination. Live Apple responses and the user's
private-LAN installation still depend on the service/device. No user database,
remote catalogue or production result set is used as disposable test input.

## Historical selector benchmark

**Expired experiment, retained for context.** Eight seeds, 3,000 rounds each,
80 starting tracks, ten added at round 1,500. These figures are the former
`SELECTION_VALIDATION.json`, not a new simulation or a target for live Elo.

| Policy | Rounds | Mean exposure | Exposure CV | Least | Most | New-track mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V4.1.6 | 100 | 2.5 | 0.4416 | 0.5 | 6.0 | — |
| V5 | 100 | 2.5 | 0.434 | 0.12 | 6.25 | — |
| V4.1.6 | 1000 | 25.0 | 0.0613 | 22.25 | 30.62 | — |
| V5 | 1000 | 25.0 | 0.0545 | 22.38 | 29.62 | — |
| V4.1.6 | 1700 | 37.78 | 0.129 | 21.25 | 45.38 | 25.21 |
| V5 | 1700 | 37.78 | 0.1037 | 24.88 | 45.0 | 27.98 |
| V4.1.6 | 3000 | 66.67 | 0.023 | 63.88 | 71.88 | 66.67 |
| V5 | 3000 | 66.67 | 0.0209 | 64.12 | 71.88 | 66.94 |

Reproduce a new report with `python tools/validate_v5_selection.py --output NEW_REPORT.json`;
`--reference` accepts a saved old selector when available. Do not treat an old
benchmark as current coverage of the later Vibe bias.

## v5.1.2 coverage

Regression coverage adds real two-clone Git tests for a reviewed local save,
restart/code fast-forward, normal upload, stale local/remote data, receipt recovery
and backup failure. HTTP tests enforce browser-bound review and exact confirmation;
Dev DOM tests exercise the comparison and busy controls. Browser CI additionally
checks the served review at phone and desktop widths. Schema-20 tests verify
complete old backups, exact retention of all other tables, old SQL restore,
idempotence and refusal of dependent extensions.
