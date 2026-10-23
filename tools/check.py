"""One entry point for source checks, the function index and regression suites.

Use `python tools/check.py all` before a PR and `python tools/check.py docs --write`
after moving/adding Python definitions. This module never imports the application
or opens a database when checking structure or generating documentation.
"""

import argparse
import ast
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OWNERS = {
    "songranker/apple_access.py": "Apple request gates, bounded lookup/preview caches and streaming diagnostics.",
    "songranker/catalog.py": "Shared catalogue projections, cross-mode results and Elo history queries.",
    "songranker/services.py": "Flask configuration, managed connections, song hydration and catalogue writes.",
    "songranker/pages.py": "Home, catalogue/search/rankings, shared collection profiles and Global Stats routes.",
    "songranker/overall.py": "Derived, calibrated Overall scores and their rankings/details APIs.",
    "songranker/impact.py": "Pure catalogue-relative Impact calculations; JavaScript parity lives in ui.js.",
    "songranker/modes/voting.py": "Standard/blind voting operations, history page and detailed Voting Stats.",
    "songranker/modes/tournament.py": "Bracket generation, tournament voting/results and detailed Tournament Stats.",
    "songranker/modes/trivia.py": "Timed field recognition, answer grading/corrections and detailed Trivia Stats.",
    "songranker/modes/guesser.py": "Elo Guesser rounds, frozen-answer results and detailed Guesser Stats.",
    "songranker/modes/shelves.py": "Album Shelves eligibility, ordering/grading and detailed Shelves Stats.",
    "songranker/modes/vibe_map.py": "Vibe round state, saving, similarity, stats, profile/library queries and APIs.",
    "songranker/modes/preferences.py": "Preference offers, idempotent writes, corrections/replay and rating projections.",
    "songranker/modes/selection.py": "Adaptive draw algorithms plus the shared SQL exposure/recency adapters.",
    "songranker/modes/challenges.py": "Browser-owned persisted challenge runs and public pure-rule exports.",
    "songranker/modes/challenge_rules.py": "Pure streak/difficulty rules, reusable without Flask or a database.",
    "songranker/modes/vibe_similarity.py": "Pure coordinate similarity and coverage-aware selector affinity.",
    "songranker/reports/global_stats_data.py": "Read-only cross-mode Global Stats from one SQLite snapshot.",
    "songranker/reports/stats_activity.py": "Shared dated activity, comparison charts and report attachments.",
    "songranker/reports/health.py": "Shared exposure/coverage health and diagnostics using production selectors.",
    "songranker/developer/dev.py": "Developer authentication, catalogue edits, records and controlled resets.",
    "songranker/developer/dev_catalog.py": "Reviewed Apple source changes, release inspection and Singles moves.",
    "songranker/developer/catalog_sources.py": "Source validation/tokens, placement plans and track-number constraints.",
    "songranker/developer/dev_tags.py": "Canonical tag proposals, reviews and atomic membership apply routes.",
    "songranker/developer/metadata.py": "Fill-only metadata planning/apply, scan lifecycle and HTTP reports.",
    "songranker/developer/dev_system.py": "Git/backups/recovery, inventory, database inspection and analysis routes.",
    "songranker/developer/dev_shutdown.py": "Fresh-PIN stop preparation/acknowledgement and in-flight request leases.",
    "songranker/developer/dev_vibe.py": "Authenticated stale-safe Vibe coordinate/count maintenance.",
    "songranker/developer/git_sync.py": "Hash-reviewed SQL-only uploads, safe startup fast-forwards and Git storage compaction.",
    "songranker/developer/db_tools.py": "Offline audit/export/rebuild/restore/compare CLI.",
    "songranker/hosting.py": "Drained single-process shutdown and the Waitress stop callback.",
    "songranker/lan_security.py": "Private-LAN addresses/hosts, session secret, origin and local-write policy.",
    "songranker/storage/database.py": "Backed-up transactional bootstrap and versioned migration.",
    "songranker/storage/database_io.py": "Lossless capture/export/rebuild, validation, restore and backup rotation.",
    "songranker/storage/database_schema.py": "Canonical schema.sql registry and transaction-safe DDL execution.",
    "songranker/storage/schema_compat.py": "Offline historical quiz/source/retirement adapters; no Flask imports.",
    "songranker/storage/preference_state.py": "Pure preference replay and lossless historical state transport.",
    "songranker/storage/source_storage.py": "Lossless current-source codec, schema-15 adapter and SQLite page policy.",
    "songranker/storage/vibe_state.py": "Fixed Vibe definitions, schema validation and schema-17/18/19 adapters.",
    "songranker/storage/tag_limits.py": "Eight-tag policy and the historical schema-16 membership adapter.",
    "songranker/storage/database_access.py": "Connection gate and exclusive, drained maintenance context.",
    "songranker/storage/competition.py": "Configured database paths and one-time V2-to-V3 catalogue-only bootstrap.",
    "songranker/storage/competition_reset.py": "Transactional per-mode/all result resets; caller owns backup/commit.",
    "songranker/storage/git_database.py": "Logical database hashes, numbered-device registry, baseline receipts and reviewed adoption.",
    "songranker/vibe_maps.py": "Shared map display definitions, compact saved profiles and pass counts.",
    "songranker/version.py": "One application version for display and every asset cache key.",
    "songranker/paths.py": "One resolved project root for data, templates, assets and documentation.",
    "tools/check.py": "Source/asset checks, generated function ownership and unified test commands.",
    "tools/browser_check.py": "Disposable served-page and Chromium integration fixtures.",
    "tools/benchmark_selection.py": "Offline seeded production-selector benchmark; no live database access.",
    "main.py": "Startup Git handoff, explicit route registration, database bootstrap and Waitress hosting.",
}
HELPERS = {
    "finite": "Convert a numeric value to a finite float; reject invalid/nonfinite input.",
    "percentage": "Return a one-decimal percentage, or unavailable when its denominator is zero.",
    "percent": "Return a one-decimal percentage, or unavailable when its denominator is zero.",
    "saved_date": "Parse a saved result date for report display and ordering.",
    "saved_time": "Resolve the saved tournament timestamp for report display.",
    "normalized": "Normalise identity text for deterministic matching within this feature.",
    "integer": "Validate/normalise the feature’s integer input before using it.",
    "signer": "Create the feature-specific serializer used for signed review receipts.",
    "signed": "Sign a browser-owned, purpose-specific review receipt.",
    "unpack": "Validate and decode the signed feature review/offer.",
    "setUp": "Create isolated disposable state and register cleanup for this test.",
    "tearDown": "Release disposable test resources.",
    "setUpClass": "Prepare shared isolated fixtures for this test class.",
    "__init__": "Initialise this object’s state and dependencies.",
    "connect": "Open the fixture database with the row/connection settings needed by this test.",
    "client": "Create the test HTTP client with the requested authentication state.",
    "check": "Assert the local validation condition and record its outcome.",
}


def sources():
    """Enumerate maintained Python files, excluding generated caches and dependencies."""
    return sorted(
        [
            ROOT / "main.py",
            *[
                p
                for folder in ("songranker", "tools", "tests")
                for p in (ROOT / folder).rglob("*.py")
            ],
        ]
    )


def definitions(tree, parents=()):
    """Yield every function/method, including nested closures, with a qualified name."""
    for node in ast.iter_child_nodes(tree):
        named = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        scope = (*parents, node.name) if named else parents
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield ".".join(scope), node
        yield from definitions(node, scope)


def routes(node):
    """Read literal Flask decorators without importing route modules."""
    result = []
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
            continue
        method = dec.func.attr
        if (
            method not in ("route", "get", "post", "delete", "patch", "put")
            or not dec.args
        ):
            continue
        path = dec.args[0]
        if not isinstance(path, ast.Constant) or not isinstance(path.value, str):
            continue
        verbs = [method.upper()] if method != "route" else ["GET"]
        for kw in dec.keywords:
            if kw.arg == "methods":
                verbs = ast.literal_eval(kw.value)
        result.append(", ".join(verbs) + " " + path.value)
    return result


def purpose(name, node):
    """Describe a definition from its contract, route, validation name and SQL access."""
    doc = ast.get_docstring(node)
    if doc:
        return " ".join(doc.split("\n\n")[0].split())
    if name.startswith("test_"):
        return "Verify " + name[5:].replace("_", " ") + "."
    if name in HELPERS:
        return HELPERS[name]
    verb, _, rest = name.strip("_").partition("_")
    labels = {
        "build": "Build",
        "render": "Render",
        "get": "Read",
        "fetch": "Read",
        "save": "Save",
        "write": "Write",
        "read": "Read",
        "ensure": "Ensure",
        "check": "Validate",
        "validate": "Validate",
        "parse": "Parse",
        "format": "Format",
        "create": "Create",
        "delete": "Delete",
        "reset": "Reset",
        "apply": "Apply",
        "prepare": "Prepare",
        "restore": "Restore",
        "record": "Record",
        "edit": "Edit",
        "upgrade": "Upgrade",
        "rebuild": "Rebuild",
        "start": "Start",
        "cancel": "Cancel",
        "load": "Load",
        "capture": "Capture",
        "compare": "Compare",
        "display": "Format",
        "seed": "Seed",
        "export": "Export",
        "publish": "Publish",
        "attach": "Attach",
        "require": "Require",
        "release": "Release",
        "api": "Serve",
        "dev": "Serve developer",
        "test": "Verify",
    }
    summary = (
        labels[verb] + " " + rest.replace("_", " ")
        if rest and verb in labels
        else name.replace("_", " ").capitalize()
    )
    route = routes(node)
    if route:
        return summary + "; " + ("; ".join(route)) + "."
    sql = [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    reads = set()
    writes = set()
    for value in sql:
        reads.update(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", value, re.I))
        writes.update(
            re.findall(
                r"\b(?:INSERT(?: OR \w+)? INTO|UPDATE|DELETE FROM)\s+([a-z_][a-z0-9_]*)",
                value,
                re.I,
            )
        )
    detail = []
    if reads:
        detail.append("reads " + ", ".join(sorted(reads)[:8]))
    if writes:
        detail.append("writes " + ", ".join(sorted(writes)[:8]))
    return summary + ("; " + "; ".join(detail) if detail else "") + "."


def markdown(value):
    """Escape content that is embedded in a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("`", "\\`")


def function_index():
    """Generate a deterministic, source-linked index of every Python definition."""
    out = [
        "# Python function index",
        "",
        "Generated by `python tools/check.py docs --write`. Do not edit generated rows.",
        "Each entry records the current owner, source location, signature and purpose. Nested helpers and test definitions are included.",
        "Non-obvious contracts should have a source docstring; the index otherwise summarises the name, route and SQL access.",
        "",
    ]
    count = 0
    for path in sources():
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text())
        items = list(definitions(tree))
        if not items:
            continue
        owner = OWNERS.get(
            relative,
            ast.get_docstring(tree)
            or "Regression fixtures and assertions for "
            + path.stem.removeprefix("test_").replace("_", " ")
            + ".",
        )
        out.extend(
            [
                "## " + relative,
                "",
                owner.split("\n\n")[0],
                "",
                "| Definition | Signature | Purpose |",
                "| --- | --- | --- |",
            ]
        )
        for name, node in items:
            signature = ast.unparse(node.args)
            out.append(
                f"| [{markdown(name)}](../{relative}#L{node.lineno}) | `{markdown(signature)}` | {markdown(purpose(node.name,node))} |"
            )
            count += 1
        out.append("")
    out.extend([f"Total: **{count} Python definitions**.", ""])
    return "\n".join(out)


def documentation(write=False):
    """Write the function index, or fail when source changes made it stale."""
    path = ROOT / "docs/FUNCTIONS.md"
    expected = function_index()
    if write:
        path.write_text(expected)
        print("Updated docs/FUNCTIONS.md")
        return
    if not path.exists() or path.read_text() != expected:
        raise RuntimeError(
            "Function index is stale. Run: python tools/check.py docs --write"
        )
    print("Function index matches every maintained Python definition.")


def structure():
    """Check imports, duplicate definitions, template references and asset ownership."""
    paths = sources()
    errors = []
    modules = {
        p.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".") for p in paths
    }
    modules.update(
        m.removesuffix(".__init__") for m in list(modules) if m.endswith(".__init__")
    )

    def scopes(node, path):
        """Report repeated definitions within each lexical Python scope."""
        names = (
            [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            if hasattr(node, "body") and isinstance(node.body, list)
            else []
        )
        errors.extend(
            f"{path}: duplicate definition {name}"
            for name, n in Counter(names).items()
            if n > 1
        )
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scopes(child, path)

    for path in paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        scopes(tree, path.relative_to(ROOT))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("songranker")
                and node.module not in modules
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: missing import {node.module}"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "render_template"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                if not (ROOT / "templates" / node.args[0].value).is_file():
                    errors.append(f"{path}: missing template {node.args[0].value}")
    from jinja2 import Environment, FileSystemLoader, meta

    env = Environment(loader=FileSystemLoader(ROOT / "templates"))
    for path in (ROOT / "templates").glob("*.html"):
        tree = env.parse(path.read_text())
        for name in meta.find_referenced_templates(tree):
            if name and not (ROOT / "templates" / name).is_file():
                errors.append(f"{path}: missing template {name}")
    assets = (ROOT / "templates/assets.html").read_text()
    for kind, extension in (("css", "css"), ("js", "js")):
        declared = set(re.findall(r"\b" + kind + r"\('([\w_]+)'\)", assets))
        actual = {p.stem for p in (ROOT / "static" / kind).glob("*." + extension)}
        errors.extend(
            f"{kind}: missing declared asset {name}" for name in declared - actual
        )
        errors.extend(
            f"{kind}: asset has no registry owner: {name}" for name in actual - declared
        )
    # CSS/scripts belong to the registry, not a second template load list.
    for path in (ROOT / "templates").glob("*.html"):
        if path.name == "assets.html":
            continue
        if re.search(r"<link[^>]+stylesheet|<script[^>]+\bsrc=", path.read_text()):
            errors.append(f"{path}: asset declaration outside registry")
    if errors:
        raise RuntimeError("\n".join(errors))
    print(
        f"Structure checked: {len(paths)} Python files; every template and asset owner resolves."
    )


def run(command):
    """Run one validation command from the repository root and propagate failures."""
    print("+ " + " ".join(map(str, command)), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def javascript():
    """Run script syntax, DOM interaction suites and the served Dev integration."""
    for path in sorted((ROOT / "static/js").glob("*.js")):
        run(["node", "--check", str(path.relative_to(ROOT))])
    for path in sorted((ROOT / "tests").glob("test_*.js")):
        if path.name != "test_dev_pages.js":
            run(["node", str(path.relative_to(ROOT))])
    run([sys.executable, "tools/browser_check.py", "--suite", "dev"])


def main(argv=None):
    """Select an independently runnable validation group or the complete PR gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "suite",
        choices=("all", "structure", "docs", "python", "javascript", "browser"),
        default="all",
        nargs="?",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the function index (docs only).",
    )
    args = parser.parse_args(argv)
    if args.write and args.suite != "docs":
        parser.error("--write is supported only for docs")
    try:
        if args.suite in ("all", "structure"):
            structure()
        if args.suite in ("all", "docs"):
            documentation(args.write)
        if args.suite in ("all", "python"):
            run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        if args.suite in ("all", "javascript"):
            javascript()
        if args.suite in ("all", "browser"):
            run([sys.executable, "tools/browser_check.py", "--suite", "vibe"])
    except (RuntimeError, SyntaxError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
