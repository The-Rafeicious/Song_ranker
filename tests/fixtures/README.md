# Historical schema fixtures

These files contain frozen schema definitions only, with no user database rows.
Migration tests intentionally load older layouts, so do not regenerate them
from the current `data/schema.sql` or change their version to match the app.

- `schema_v9.sql`: pre-preference-replay layout.
- `schema_v12.sql`: layout before source identity and exact-date additions.
- `schema_v17.sql` (mode test branch): frozen definitions before Vibe Map sample
  counters and resumable rounds. Tests seed its four fixed map definitions before
  adding songs, matching the schema-17 application bootstrap.

The schema-9 and schema-12 files were restored byte-for-byte from repository commit
`f9aa00e213e0cd7d9cd5c57b34854ed3c7bdb3e9`, after their deletion in the
`b81e589a64730e0ed44657da28e4b70f6bbf6897` revert. Additional frozen versions
may be present on feature branches for their own migration tests.
