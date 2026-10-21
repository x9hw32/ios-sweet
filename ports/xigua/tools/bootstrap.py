#!/usr/bin/env python3
"""Fetch pinned donor sources for a standalone workspace (no device operations)."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
DONOR_SHA = '425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116'


def main():
    local = ROOT / 'upstream/ios-sweet'
    bundled = ROOT.parent.parent
    if (local / 'tools/mkpayload.py').is_file() or (bundled / 'tools/mkpayload.py').is_file():
        print('Donor helper sources already present')
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', str(local)], check=True)
    subprocess.run(['git', '-C', str(local), 'fetch', '--depth', '1',
                    'https://github.com/dipa-studio/ios-sweet.git', DONOR_SHA], check=True)
    subprocess.run(['git', '-C', str(local), 'checkout', '--detach', 'FETCH_HEAD'], check=True)


if __name__ == '__main__':
    main()
