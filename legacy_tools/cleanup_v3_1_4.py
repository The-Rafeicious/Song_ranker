"""Run after merging the V3.1.4 patch to remove the obsolete tier template."""
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    if not (root / 'main.py').is_file() or not (root / 'services.py').is_file():
        raise SystemExit('Copy this script into your Song_ranker folder before running it.')
    obsolete = root / 'templates' / 'tier_list.html'
    if obsolete.is_file() or obsolete.is_symlink():
        obsolete.unlink()
        print('Removed templates/tier_list.html.')
    else:
        print('The tier-list template is already removed.')


if __name__ == '__main__':
    main()
