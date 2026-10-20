# V5.0.4.2 — eight tags per song

Stop the app, apply the changed files, restart and hard-refresh open tabs.
The footer should show V5.0.4.2. No dependency change is required.

## Existing songs and recovery

The normal backed-up migration upgrades schema 15 to **16**. Each song keeps
its earliest eight saved tag links, using the junction table’s stored rowid order.
Later links are removed. For an imported database without rowids, tag ID order
is the deterministic fallback. This is attachment order, not alphabetical name
order or relevance: historical links do not have attachment timestamps.

The pre-upgrade snapshot retains the full old memberships. Migration is atomic
and does not repeat on each launch. No tag definitions, ratings or game facts
are deleted. Restoring an older database through the normal restore workflow
also applies the current policy. Current schema-16 files with invalid over-limit
memberships fail validation rather than silently changing data.

The repository’s saved database snapshot contained no songs over eight during
this audit. A local installation can differ; its cleanup runs at startup.

## Selecting and saving

- Song details: a live count, disabled unchecked choices at capacity, and a
  validation message for more than eight distinct typed names. Uncheck a tag
  to free a slot. Duplicate names do not consume extra slots.
- Tag workbench: capacity is calculated from each selected song’s final set,
  not just the number of chosen tags. Add includes existing memberships; Replace
  counts the replacement set. Remove may target any number of tags.
- New typed names count alongside existing choices. Over-limit drafts disable
  Review; the server checks both review and save against current memberships.
- All writers, including bulk tools and imports, are guarded by database rules.
  Apple Music’s supplied genre counts toward eight along with optional tags.
  Overflow fails the transaction with a clear message, keeping saved data intact.

## Suggested tags

These are suggestions, not automatically created or assigned. They follow the
short, mostly hyphenated theme/style names in the repository’s existing tag list.

| Suggested tag | Use it for | Distinction from existing tags |
| --- | --- | --- |
| `moving-on` | Actively letting go while it may still hurt. | `better-off` describes feeling happier after the split. |
| `self-acceptance` | Making peace with yourself, flaws included. | A softer counterpart to `self-hate`, rather than the defiance of `strong`. |
| `growing-up` | Identity, independence and new responsibilities. | `changing` currently describes changes within a relationship. |
| `regret` | Wishing you had acted or spoken differently. | More specific than looking back in `retrospective`. |
| `escapism` | Imagining or seeking a way out of everyday life. | Separates escape and fantasy from `rebel` defiance. |
| `dreamy` | Floating vocals, hazy textures and spacious production. | Describes sound rather than `low-pop` intensity or `electronic` instrumentation. |
| `tension` | Sustained unease, anticipation or unresolved pressure. | `build-up` describes the rise into a powerful chorus. |
| `grief` | Processing bereavement or a lasting absence. | Covers loss beyond romantic `heart-ache` or general `sad`. |

Use these where they add meaning; a song does not need to fill all eight slots.
The existing `crush`/`flirt`/`falling-in-love` and `past-love`/`hung-up` groups
already cover their areas well, so extra near-duplicates are less useful.

## Validation

Seven new Python policy tests cover migration backup, exact retained links,
rollback, repeat startup, API limits, duplicate names, mixed bulk changes and
database guards. Focused existing catalogue/tag/Git checks and frontend DOM
checks are documented in [VALIDATION.md](VALIDATION.md). Browser painting and
real-device audio were not tested here.
