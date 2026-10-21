# CI maintenance — 21 October 2026

Shared maintenance changes for `main` and `New-modes-test`; no app or schema
version bump, runtime feature changes or user database changes.

- Restore the original schema-9 and schema-12 SQL fixtures from Git history.
  These are frozen DDL-only inputs, not current-schema substitutes. Historical
  database and catalogue migration tests can now run rather than fail to load.
- Give temporary Git test repositories their own discovery ceiling, preventing
  an unconfigured fixture directory from discovering the enclosing checkout.
  GitHub Actions checks out a detached commit; that enclosing repository was
  causing the fixture to report detached instead of not_repo. Production Git
  repository discovery remains unchanged.
- Update the launcher test mock for the V5.0.5 reconciliation phase. Verify
  source check → bootstrap → database reconciliation → server startup, while
  WSGI imports still bootstrap without running Git or starting the server.
- Run the served developer-page JavaScript test through its existing Python
  harness, which creates a disposable database and local fixture server first.
  Continue running the other JavaScript suites directly through Node.
- Run the workflow on pushes to `main` and `New-modes-test`, in addition to pull
  requests, replacing an obsolete feature-branch-only push trigger.

The workflow still fails on test errors; no test is skipped or failure ignored.
The developer-page harness mocks Apple transport and does not open an active
database. See `tests/fixtures/README.md` for restored fixture provenance.

Validation on the current branch versions: all 263 Python tests passed for main;
all 297 passed for New-modes-test after Vibe-Map-v1.0.2. Both also passed every
JavaScript suite, including 39 served developer-page checks. No test exclusions
were used. The shared maintenance files are identical on both branches.
