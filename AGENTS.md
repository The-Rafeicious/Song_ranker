# Song Ranker work

Read docs/PAGE_STYLE.md before layout changes. It is the current styling contract;
older release notes are history. Preserve semantic colours, responsive geometry,
short useful labels and all active databases/backups. Test data is disposable.

Backend code lives in songranker/; each mode owns its operations and detailed
statistics. Shared catalogue queries live in catalog.py. Keep pure storage/replay
helpers independent of Flask. Consolidate related work in these feature owners;
do not add version-named scripts, stylesheets or tiny files for one-off patches.

All frontend assets are declared once in templates/assets.html. Shared helpers
belong in ui.js, playback/volume in preview.js, and shared layouts in the CSS
owners listed in docs/PAGE_STYLE.md. site_baseline.css loads last.

Use docs/FILES.md and docs/FUNCTIONS.md to locate code. Describe non-obvious function
contracts in source docstrings. After moving/adding Python definitions run
python tools/check.py docs --write. Before a PR run
python tools/check.py all. Documentation lives in docs/; release notes live in
update_logs/. Preserve current routes unless a requested behavior change requires
an explicitly documented API change.
