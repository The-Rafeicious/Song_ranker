"""One-time test-map replacement; schema 19 reruns never erase new placements."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from songranker.storage.database import initialize_database
from songranker.storage.database_io import readonly, validate


def reset_test_vibes(filename):
    path=Path(filename).resolve(strict=True)
    with readonly(path) as conn:
        validate(conn)
        version=conn.execute('PRAGMA user_version').fetchone()[0]
    if version==19:
        return dict(reset=False,database=str(path),schema=19,message='Already updated; new Vibe Map results kept.')
    if version not in (17,18):
        raise ValueError('Choose the Vibe Map test database (schema 17 or 18), not a production/legacy database.')
    directory=path.parent/'database_backups'
    before=set(directory.glob('pre_upgrade_*.db'))
    initialize_database(path)  # Backed-up, validated, transactional schema 19 reset.
    backups=set(directory.glob('pre_upgrade_*.db'))-before
    return dict(reset=True,database=str(path),schema=19,backups=[str(p) for p in sorted(backups)],
                message='Old Vibe Map results cleared. Catalogue and other game results kept.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,help='Explicit path to the CLOSED app’s test SQLite database.')
    args=parser.parse_args()
    print(json.dumps(reset_test_vibes(args.database),indent=2))


if __name__=='__main__':main()
