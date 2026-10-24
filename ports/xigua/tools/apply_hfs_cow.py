#!/usr/bin/env python3
"""Apply a checked host COW repair to allocated PJA110 linux through BusyBox dd.

Every original sector is saved and checked before any writes; all results are
read back. Journal header is written last. An I/O failure rolls back the known
preflight bytes. Restore refuses sectors changed by subsequent native boots.
"""
import argparse
import json
from pathlib import Path
import subprocess
from install_ios_root import command
from prepare_activation_patch import ROOT_BYTES, SECTOR, volume_identity, sha

TARGET = '/dev/block/by-name/linux'
REMOTE = '/tmp/xigua-hfs-repair'


def runs_for(rows, last):
    numbers = [s['physical'] for s in rows]
    if (len(set(numbers)) != len(numbers) or any(type(n) is not int or not 0 <= n < ROOT_BYTES // SECTOR for n in numbers)):
        raise ValueError('Invalid sector targets')
    order = sorted(n for n in numbers if n != last) + ([last] if last in numbers else [])
    runs, index = [], 0
    for n in order:
        if runs and runs[-1][0] + runs[-1][1] == n and n != last:
            a, count, off = runs[-1]
            runs[-1] = (a, count + 1, off)
        else:
            runs.append((n, 1, index))
        index += 1
    return order, runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    root = args.prepared
    r = json.loads((root / 'receipt.json').read_text())
    checked = json.loads((root / 'validated.json').read_text())
    purpose = checked.get('purpose', 'migration-file')
    known_repair = ((purpose == 'migration-file' and checked.get('ark_bytes') == 459) or
                    (purpose == 'chronod-home' and checked.get('chronod_home') == '/var/mobile' and
                     checked.get('job_only_environment_change') is True))
    if (r.get('target') != TARGET or r.get('phone_writes') is not False or
            r.get('source_bytes') != ROOT_BYTES or r.get('sector_bytes') != SECTOR or
            not 1 <= len(r.get('sectors', [])) <= 8192 or
            checked.get('fsck_ok') is not True or checked.get('journal_empty') is not True or
            not known_repair or checked.get('stock_springboard_cache') is not True):
        raise SystemExit('A checked supported HFS repair plan is required')
    if (command('getprop ro.product.model').strip() != b'PJA110' or
            command('getprop ro.bootmode').strip() != b'recovery' or
            command('/sbin/busybox id -u').strip() != b'0' or
            command('/sbin/busybox readlink -f ' + TARGET).strip() != b'/dev/block/sda17' or
            command('/sbin/busybox blockdev --getsize64 ' + TARGET).strip() != b'77137424384'):
        raise SystemExit('Expected allocated PJA110 root in recovery')
    mounts = command('while read dev rest; do case "$dev" in /dev/block/*) /sbin/busybox readlink -f "$dev";; esac; done < /proc/mounts').splitlines()
    if b'/dev/block/sda17' in mounts:
        raise SystemExit('Root must be unmounted before raw I/O')
    header = command(f'/sbin/busybox dd if={TARGET} bs=4096 count=1 2>/dev/null')
    if volume_identity(header) != r['volume_identity']:
        raise SystemExit('Root volume identity changed')
    order, runs = runs_for(r['sectors'], checked['journal_header_sector'])
    by_number = {s['physical']: s for s in r['sectors']}
    old, new = bytearray(), bytearray()
    for n in order:
        a = (root / f'sectors/{n}.original.bin').read_bytes()
        b = (root / f'sectors/{n}.patched.bin').read_bytes()
        if (len(a) != SECTOR or len(b) != SECTOR or sha(a) != by_number[n]['original_sha256'] or
                sha(b) != by_number[n]['patched_sha256']):
            raise SystemExit('Prepared sector checksum mismatch')
        old.extend(a)
        new.extend(b)
    command('/sbin/busybox mkdir -p ' + REMOTE)
    runfile = root / 'apply-runs.txt'
    runfile.write_text(''.join(f'{a} {n} {off}\n' for a, n, off in runs))
    subprocess.run(['adb', 'push', str(runfile), REMOTE + '/runs.txt'], check=True)
    read = f'while read block count skip; do /sbin/busybox dd if={TARGET} bs=4096 skip="$block" count="$count" 2>/dev/null; done < {REMOTE}/runs.txt'
    actual = command(read)
    wanted = bytes(old if args.restore else new)
    if actual == wanted:
        print('Repair sectors already in requested state; no writes')
        return
    if len(actual) != len(old):
        raise SystemExit('Incomplete preflight read')
    for off in range(0, len(actual), SECTOR):
        if actual[off:off+SECTOR] not in (old[off:off+SECTOR], new[off:off+SECTOR]):
            raise SystemExit('Filesystem changed since preparation; no writes made')
    for label, data in [('wanted', wanted), ('before', actual)]:
        path = root / (label + '.bin')
        path.write_bytes(data)
        subprocess.run(['adb', 'push', str(path), REMOTE + '/' + label + '.bin'], check=True)
        if command(f'/sbin/busybox sha256sum {REMOTE}/{label}.bin').decode().split()[0] != sha(data):
            raise SystemExit('Uploaded payload hash mismatch')

    def write(label):
        command(f'set -eu; while read block count skip; do /sbin/busybox dd if={REMOTE}/{label}.bin of={TARGET} bs=4096 skip="$skip" seek="$block" count="$count" conv=fsync 2>/dev/null; done < {REMOTE}/runs.txt; /sbin/busybox sync')

    try:
        write('wanted')
        if command(read) != wanted:
            raise ValueError('Repair readback differs')
    except Exception:
        write('before')
        if command(read) != actual:
            raise RuntimeError('Rollback verification failed; remain in recovery')
        raise
    (root / ('restored.json' if args.restore else 'installed.json')).write_text(json.dumps({
        'operation': 'restore' if args.restore else 'install', 'verified': True,
        'sectors': len(order), 'bytes': len(wanted), 'runs': len(runs),
        'preflight_sha256': sha(actual), 'readback_sha256': sha(wanted),
        'journal_header_written_last': True}, indent=2) + '\n')
    print('HFS repair ' + ('restored' if args.restore else 'installed') + '; all changed sectors verified')


if __name__ == '__main__':
    main()
