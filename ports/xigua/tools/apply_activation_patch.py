#!/usr/bin/env python3
"""Install/restore a verified two-sector local port patch through recovery BusyBox.

Requires a prepared receipt and original sectors from prepare_activation_patch.
All sectors are read/verified before writes. Failed writes trigger immediate
rollback to the bytes read at preflight. No mounts or filesystem metadata writes.
"""
import argparse
import json
from pathlib import Path
import subprocess
from install_ios_root import command
from prepare_activation_patch import SECTOR, ROOT_BYTES, METHOD_SHA256, sha, volume_identity

TARGET = '/dev/block/by-name/linux'


def read_sector(number):
    result = command(f'/sbin/busybox dd if={TARGET} bs=4096 skip={number} count=1')
    if len(result) != SECTOR:
        raise ValueError('Short device read')
    return result


def write_sector(number, data, label):
    remote = '/tmp/xigua-local-state-' + label + '.bin'
    local = Path('build') / ('xigua-local-state-' + label + '.bin')
    local.write_bytes(data)
    subprocess.run(['adb', 'push', str(local), remote], check=True)
    if command('/sbin/busybox sha256sum ' + remote).decode().split()[0] != sha(data):
        raise ValueError('Uploaded sector checksum mismatch')
    command(f'/sbin/busybox dd if={remote} of={TARGET} bs=4096 seek={number} count=1 conv=fsync; /sbin/busybox sync')
    if read_sector(number) != data:
        raise ValueError('Sector write readback mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    r = json.loads((args.prepared / 'receipt.json').read_text())
    if (r.get('kind') != 'xigua-ios-20H392-local-lockdown-state' or
            r.get('target') != TARGET or r.get('sector_bytes') != SECTOR or
            r.get('root_bytes') != ROOT_BYTES or r.get('method_sha256') != METHOD_SHA256 or
            len(r.get('sectors', [])) != 2):
        raise SystemExit('Unsupported patch receipt')
    if (command('getprop ro.product.model').strip() != b'PJA110' or
            command('getprop ro.bootmode').strip() != b'recovery' or
            command('/sbin/busybox id -u').strip() != b'0'):
        raise SystemExit('Expected PJA110 recovery with root BusyBox')
    if (command('/sbin/busybox readlink -f ' + TARGET).strip() != b'/dev/block/sda17' or
            int(command('/sbin/busybox blockdev --getsize64 ' + TARGET)) != 77137424384):
        raise SystemExit('Allocated linux partition changed')
    mounts = command('while read dev rest; do case "$dev" in /dev/block/*) /sbin/busybox readlink -f "$dev";; esac; done < /proc/mounts').splitlines()
    if b'/dev/block/sda17' in mounts:
        raise SystemExit('linux partition is mounted; refusing raw writes')
    if volume_identity(read_sector(0)) != r['volume_identity']:
        raise SystemExit('Root volume identity changed')
    plan, numbers = [], set()
    for i, item in enumerate(r['sectors']):
        number = item['physical']
        if type(number) is not int or not 0 < number < ROOT_BYTES // SECTOR or number in numbers:
            raise SystemExit('Invalid physical sector plan')
        numbers.add(number)
        old = (args.prepared / f'{i}.original.bin').read_bytes()
        new = (args.prepared / f'{i}.patched.bin').read_bytes()
        if (len(old) != SECTOR or len(new) != SECTOR or sha(old) != item['original_sha256'] or
                sha(new) != item['patched_sha256']):
            raise SystemExit('Prepared sector receipt mismatch')
        actual = read_sector(number)
        if actual not in (old, new):
            raise SystemExit('Target sector has unexpected bytes; no writes made')
        plan.append((number, actual, old if args.restore else new))
    changed = []
    try:
        for i, (number, before, wanted) in enumerate(plan):
            if before != wanted:
                changed.append((number, before))
                write_sector(number, wanted, str(i))
    except Exception:
        for i, (number, before) in enumerate(reversed(changed)):
            write_sector(number, before, 'rollback-' + str(i))
        raise
    result = {'operation': 'restore' if args.restore else 'install', 'verified': True,
              'written_bytes': SECTOR * len(changed), 'sectors': [p[0] for p in plan]}
    (args.prepared / ('restored.json' if args.restore else 'installed.json')).write_text(json.dumps(result, indent=2) + '\n')
    print('Port patch ' + ('restored' if args.restore else 'installed') + '; full sector readbacks verified')


if __name__ == '__main__':
    main()
