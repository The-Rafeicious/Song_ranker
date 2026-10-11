# V3.2.5.1 validation

- 53 backend tests pass, including nine new checks for rolling-window admission,
  spacing/range reservations, Retry-After parsing, cache reuse, busy requests,
  HTTP 429 cooldowns, HTML/transport errors, streamed bytes/range headers,
  connection closure, refusal/missing/invalid audio and forbidden redirects.
- 235 interface assertions pass: 27 focused hotfix checks, 58 existing mode
  checks, 63 V3.2.4 checks, 66 V3.2.5 styling checks and 21 tests loading actual
  HTTP-served script assets. Hotfix cases cover loading/playing feedback,
  diagnostics without blind-answer leakage, cooldowns, stopped album/podium
  queues, Dev search errors/deduplication and trivia timing after media readiness.
- Backend Apple responses are mocked; UI media/layout are simulated with jsdom.
  The user's actual Apple restriction and real-device streaming/appearance were
  not reproduced or verified. A successful test is not a promise of unblocking.
- Syntax, SQLite integrity/foreign keys, unchanged supplied database checksum
  and ZIP integrity pass. Tests use copies; the patch contains no database,
  stored request logs or cached audio. Existing schema 6 is unchanged.
- Apple's current primary documentation was checked for the free Search API's
  approximate 20-calls-per-minute guidance and metadata caching recommendation:
  https://performance-partners.apple.com/search-api
