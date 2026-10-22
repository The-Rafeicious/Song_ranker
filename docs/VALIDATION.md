# Validation

Install runtime and pinned test dependencies from the repository root:

```sh
python -m pip install -r requirements.txt
npm ci
python tools/check.py all
```

The single entry point runs source/asset checks, verifies the generated function
index, runs Python regressions and JavaScript DOM suites, serves the real Dev
pages against disposable data, then runs Chromium integration/screenshots.
Individual groups are available:

| Command | Checks |
| --- | --- |
| `python tools/check.py structure` | Syntax, current imports, duplicate definitions, template references and one owner per asset |
| `python tools/check.py docs` | Every Python function/method/closure has a current source-linked index entry |
| `python tools/check.py docs --write` | Regenerate the index after a source change |
| `python tools/check.py python` | Database, modes, sources, metadata, tags, Dev, sync, recovery and shutdown regressions |
| `python tools/check.py javascript` | Script syntax, real-controller DOM/media mocks and served Dev HTTP/DOM checks |
| `python tools/check.py browser` | Actual Chromium gameplay/stats/profile/Dev checks at desktop/tablet/phone widths |

The browser group requires installed Chrome/Chromium. Set
`SONG_RANKER_TEST_CHROME` to an explicit executable when it is not on PATH.
Screenshots are written to `artifacts/vibe-map/` and uploaded by CI. Missing
runtime/browser dependencies fail clearly; they are not counted as passed tests.

The frozen schema fixtures remain necessary regression inputs. Their version
numbers describe migration formats, not obsolete tests. See
[fixture provenance](../tests/fixtures/README.md). The V5.3 route fixture captures
all pre-consolidation URL/method/endpoint contracts and guards route registration.

| Area | What the evidence establishes |
| --- | --- |
| Storage/recovery | Backed-up migrations, lossless typed values/rowids/sequences, rollback, restore and extension refusal |
| Modes/results | Preference idempotency/corrections, weighted first-round Elo, frozen quiz facts, grading and Vibe averages |
| Catalogue/Dev | Signed source offers, reviewed bulk/tag edits, eight-tag limits, metadata fill, transaction boundaries and authentication |
| Git/shutdown | Two disposable clones/bare remotes, baselines/deletions/splits, guarded uploads and acknowledged stops |
| Frontend | Real scripts/templates/routes, one asset load/order, shared profile contracts, request races and responsive geometry |
| Shared shell | Static reports initialise without catalogue hydration; persisted volume works without a slider; common text policies agree |

Live Apple transport is mocked in regression fixtures. Physical audio output and
the user's private-LAN/device installation still need device testing. No active
user database or backup is disposable test input.

For a new seeded selector report, run:

```sh
python tools/benchmark_selection.py --output NEW_REPORT.json
```

The benchmark uses the production standard-library selector. Old V4 shadow
scripts, frozen prototype comparisons and one-time Vibe release-cleanup commands
were retired in V5.3. Current migrations and reviewed Dev resets remain tested.

V5.3 validation results and review limits are recorded in
[the consolidation report](CONSOLIDATION.md) and its pull request.
