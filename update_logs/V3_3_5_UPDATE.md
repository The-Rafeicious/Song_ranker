# V3.3.5 — Preview audio and patch-note organisation

This release family includes the V3.3.5.1 hotfix below. The original V3.3.5
sections describe that release; the later patch updates its cache lifetime.

## Preview playback

- Tournament podium snippets run for **six seconds** instead of four, before
  starting the next handoff. The outgoing song continues through the overlap.
- Audio handoffs use a **1.5-second crossfade**. The outgoing preview keeps its
  sound while the incoming preview loads. The fade starts only after native
  playback begins and the incoming element has enough data to continue playing.
- The shared handoff covers podiums, album/tag queues, Shelves playback and answer
  reveals, manual cover switching, trivia result/next-round transitions and
  repeated full-preview loops. The existing 10-second queue sample lengths and
  game scoring rules stay in place. New Standard/Tournament/Guesser rounds still
  start silently; their closing samples fade out.
- One next preview is buffered ahead in cycling players. Slow or failed incoming
  previews retain the outgoing sound; a stalled Shelves answer can be skipped
  without fading the previous snippet away prematurely. Fatal errors during a
  fade restore the healthy outgoing preview.
- Loading, buffering, error and cooldown notices remain. Outgoing readiness
  events cannot overwrite the notice for an incoming preview still loading.
- The volume control changes the whole mix without resetting fade levels. Pause,
  rapid/reverse skips, page navigation and preview limits cancel pending work
  and clean up retired audio. Fades use short timer ticks, so they do not depend
  on animation frames continuing in a background tab.

## Temporary last-ten preview cache

The existing app had Apple metadata lookup caching and a one-preview Shelves
buffer, but no shared last-ten audio cache. This release adds that cache to the
**local app's RAM**, shared across its pages within the same app process:

- Retains at most **ten complete Apple previews**, with least-recently-used
  eviction and **ten-minute expiry**; restarting the app clears it.
- Each cached response is limited to **4 MiB** (at most 40 MiB of stored audio).
  Larger previews still stream normally without being cached.
- Replays and valid byte ranges can use the complete cached response without
  contacting the preview CDN again. Partial, interrupted, abandoned or mismatched
  responses are not stored as full previews.
- Cache keys follow the current preview URL; editing that URL also changes the
  browser lookahead key, so stale buffered audio is bypassed.
- No audio files, new database columns or stored playback counters are written.
  Existing rate-limit/backoff checks remain for upstream requests. Other custom
  preview hosts continue to use direct playback and native buffering.

A slow or unavailable stream can still require a wait or report an error; the
cache and overlap reduce handoff gaps without suppressing those notices.

## Notes grouped by the third version number

Hotfix notes are consolidated into their three-part release file, with the full
patch number kept as a section heading. Future V3.3.5.x fixes go into this file.
The index lists release families instead of separate hotfix documents.

Existing notes were merged into V3.2.5, V3.2.7, V3.3.3 and V3.3.4. After applying
this patch, these redundant older files can be removed from `update_logs`:

- `README_V3_2_5_1.md`
- `V3_2_7_1_UPDATE.md`
- `V3_3_3_1_UPDATE.md`
- `V3_3_3_2_UPDATE.md`
- `V3_3_4_1_UPDATE.md`
- `V3_3_4_2_UPDATE.md`
- `V3_3_4_2_1_UPDATE.md`

Their contents and relevant links are preserved in the consolidated files.

## Validation

- 84 simulated shared-audio/controller assertions passed, including readiness,
  buffering, failed loads, fades, volume changes, rapid reverse selection,
  cleanup, podium timing, album/Shelves queues, loop rollover and Trivia handoffs.
- 14 cache/backend tests passed for full and partial responses, ranges, expiry,
  eviction, size bounds, interrupted downloads and edited URLs.
- The existing 46 calculator/lookup tests and 119 DOM/interface checks passed.
- Shared JavaScript syntax and Python compilation passed. The supplied database
  is unchanged, and the Overall calculator is unchanged from V3.3.4.2.1.

Media events and the CDN were mocked. Actual Apple audio, device output and
browser-specific acoustic behavior could not be listened to here; these checks
verify the state/timing logic rather than real sound quality.

## Apply this edited-file patch

Apply over **V3.3.4.2.1**. Stop the app, copy the ZIP's `Song_ranker` files over
the matching files in your existing project, restart, and hard-refresh. The
footer should show **V3.3.5**. Keep the rest of your project, database and backups.
The ZIP contains edited files and release notes only, not a full application.


## Patch V3.3.5.1 — Pair preloading and artist previews

- **Standard Vote, Blind Audition, Tournament and Elo Guesser** quietly preload
  both cover previews as soon as the pair appears. Apple previews are downloaded
  completely into the temporary RAM cache, then the cover audio is primed for
  playback. Custom preview hosts use native preloading. Nothing autoplays.
- Quiet Apple downloads are queued and spaced by at least 650 ms to respect the
  existing local request gate. Downloaded chunks are discarded by JavaScript,
  avoiding a second retained byte/blob cache. The existing 1.5-second handoff and
  buffering notices remain; a click before loading completes can still wait.
- **Standard/Blind Vote and Elo Guesser** release both cached previews and native
  buffers when moving to the next pair, after the result sample. Failed saves
  keep the current pair available. **Tournament** retains recent previews across
  rounds, subject to the existing ten-item / ten-minute / 4 MiB-per-item bounds.
- Cache entries now belong to the page that loaded them. Leaving releases its
  audio buffers, aborts queued/active warmup work and clears that page's RAM
  entries. Another tab's cache is unaffected. Browser Back restores controls
  with a fresh page token and preloads its visible pair again. Expiry remains a
  fallback if page-exit delivery is interrupted.
- Late downloads cannot refill a pair/page cache after cleanup. Scoped cache
  responses still support byte ranges and playback during upstream backoff.
- **Artist profiles** now have the same cover play/pause and previous/next
  controls as album/tag profiles. Their available songs play for ten seconds
  each in descending Elo rank, with the existing crossfade and one-ahead buffer.
  Missing-preview tracks are omitted; an empty queue disables the cover player.
  Artist artwork stays circular. Album queues retain track-number order.

### Apply this hotfix

Apply these edited files over **V3.3.5**, restart the app and hard-refresh. The
footer should show **V3.3.5.1**. No database migration is needed. This patch's
notes are kept here rather than in a separate four-part-version file.

### Validation

40 new pair/cache/artist assertions and the existing 84 audio assertions passed.
All 25 cache/backend tests and 119 DOM/interface checks passed, along with the
46 existing calculator/lookup tests, JavaScript syntax and Python compilation.
The original database and Overall calculator remain unchanged. Media/CDN events
were mocked; actual device audio and first-click network timing were not tested.
