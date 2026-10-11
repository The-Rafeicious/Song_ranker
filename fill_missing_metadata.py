"""Standalone fill-only helper. Dry run is the default; --apply writes with backup."""
import argparse
from datetime import datetime
from pathlib import Path
from metadata_fill import plan_metadata, apply_plan, text_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, help='Path to song_ranker_v2.db')
    parser.add_argument('--country', default='gb', help='Apple store code (default: gb)')
    parser.add_argument('--apply', action='store_true', help='Apply confidently matched missing values; backup first')
    parser.add_argument('--report', help='New text report path; existing files are never overwritten')
    args = parser.parse_args()
    path = Path(args.report) if args.report else Path('metadata_fill_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.txt')
    # Reserve the report before starting or applying anything.
    try:
        reserved = path.open('x', encoding='utf-8')
    except OSError as error:
        parser.error('Cannot create a new report: '+str(error))
    with reserved as report:
        plan = None
        try:
            plan = plan_metadata(args.database, args.country,
                                 progress=lambda n,total,title: print(f'{n}/{total}: {title}', flush=True))
            if args.apply:
                apply_plan(args.database, plan)
            report.write(text_report(plan))
        except KeyboardInterrupt:
            report.write('\nINTERRUPTED: no unfinished metadata plan was applied.\n')
            return 130
        except Exception as error:
            if plan:
                report.write(text_report(plan))
            report.write('\nERROR: '+str(error)+'\n')
            print('Stopped: '+str(error))
            return 1
    print('Report: '+str(path.resolve()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
