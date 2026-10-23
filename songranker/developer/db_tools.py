"""Offline maintenance: audit, lossless export, rebuild, restore and compare.

Every output is a NEW file. The CLI never wipes or replaces the active database.
Run `python -m songranker.developer.db_tools --help`; no Flask/developer credentials are needed.
"""

import argparse
from pathlib import Path
import json
import sqlite3
import tempfile
from songranker.storage.database_io import DatabaseValidationError, audit, capture, json_bytes, digest, prepare_candidate, publish, read_export, rebuild, reconcile, snapshot, write_export


def parser():
    """Define the offline audit, export, rebuild, restore and compare commands with
    explicit input/output paths.
    """
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    from songranker.storage.competition import configured_paths
    default_db = str(configured_paths(Path(__file__).resolve().parents[2])[0])
    audit_parser = commands.add_parser('audit', help='Read-only integrity, counts, hashes and conflict report')
    audit_parser.add_argument('--db', default=default_db)
    export_parser = commands.add_parser('export', help='Consistent, checksummed JSON containing every stored value')
    export_parser.add_argument('--db', default=default_db)
    export_parser.add_argument('--output', required=True)
    build = commands.add_parser('rebuild', help='Canonical, compact database in a new file; IDs/data are preserved')
    sources = build.add_mutually_exclusive_group(required=True)
    sources.add_argument('--from-db')
    sources.add_argument('--from-export')
    build.add_argument('--output', required=True)
    restore = commands.add_parser('restore', help='Validate/migrate a SQLite backup into a new recovery file')
    restore.add_argument('--backup', required=True)
    restore.add_argument('--output', required=True)
    compare = commands.add_parser('compare', help='Reconcile all stored values, view results and ID high-water marks')
    compare.add_argument('--before', required=True)
    compare.add_argument('--after', required=True)
    for command in (audit_parser, export_parser, build, restore, compare):
        command.add_argument('--report', help='Also save the JSON report to a new file')
    return result


def run(args):
    """Dispatch one offline recovery command and return its validated JSON report."""
    if args.command == 'audit':
        return audit(args.db)
    if args.command == 'export':
        path = write_export(args.db, args.output)
        exported = read_export(path)
        return {'status': 'exported', 'output': str(path), 'integrity': 'ok',
                'foreign_key_errors': 0, 'schema_version': exported['user_version'],
                'state_sha256': digest(exported),
                'counts': {name: len(data['rows']) for name, data in exported['tables'].items()},
                'view_hashes': exported['view_hashes']}
    if args.command == 'compare':
        with snapshot(args.before) as before, snapshot(args.after) as after:
            reconcile(capture(before), capture(after))
        return {'status': 'identical stored values and view results', **audit(args.after)}
    output = Path(args.output).resolve()
    if output.exists():
        raise DatabaseValidationError('Output already exists; choose a new filename.')
    if args.command == 'restore':
        with tempfile.TemporaryDirectory(dir=output.parent, prefix='.restore_') as folder:
            candidate = prepare_candidate(args.backup, Path(folder) / 'candidate.db')
            publish(candidate, output)
    elif args.from_export:
        rebuild(read_export(args.from_export), output)
    else:
        with tempfile.TemporaryDirectory(dir=output.parent, prefix='.source_') as folder:
            candidate = prepare_candidate(args.from_db, Path(folder) / 'candidate.db')
            with snapshot(candidate) as source:
                rebuild(capture(source), output)
    return {'status': 'verified', 'output': str(output), **audit(output)}


def main(argv=None):
    """Run the recovery CLI, optionally save a new report file and return a
    structured success/error exit code.
    """
    args = parser().parse_args(argv)
    try:
        if args.report and Path(args.report).exists():
            raise DatabaseValidationError('Report already exists; choose a new filename.')
        report = run(args)
        if args.report:
            with Path(args.report).open('xb') as file:
                file.write(json_bytes(report) + b'\n')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (DatabaseValidationError, OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'error', 'message': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
