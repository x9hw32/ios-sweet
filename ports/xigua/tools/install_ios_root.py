#!/usr/bin/env python3
"""Write a verified HFS+ root to the user's allocated linux partition in recovery.

Requires the prepare_ios_root.py receipt, intact boot/ESP backups, the known
PJA110 partition mapping, root recovery and BusyBox. No boot/ESP writes occur.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time
from paths import ROOT

TARGET = '/dev/block/by-name/linux'
CAPACITY = 77137424384
BLOCK = 4 * 1024 * 1024


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def command(text, *, output=None):
    # Shell protocol v2 keeps remote stderr separate from binary stdout.
    # exec-out merges dd's statistics into raw partition backup bytes.
    return subprocess.run(['adb', 'shell', '-T', 'sh -c ' + shlex.quote(text)],
                          stdout=output or subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=600, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='ios-root-12g.img produced by prepare_ios_root.py')
    parser.add_argument('--output', type=Path, required=True, help='New directory for metadata backup and receipt')
    args = parser.parse_args()
    if command('getprop ro.bootmode').strip() != b'recovery':
        raise SystemExit('Root writes require recovery')
    if (command('getprop ro.product.model').strip() != b'PJA110' or
            command('/sbin/busybox id -u').strip() != b'0'):
        raise SystemExit('Expected PJA110 root recovery with BusyBox')
    if command('/sbin/busybox readlink -f ' + TARGET).strip() != b'/dev/block/sda17':
        raise SystemExit('linux device mapping changed')
    if int(command('/sbin/busybox blockdev --getsize64 ' + TARGET)) != CAPACITY:
        raise SystemExit('linux partition size changed')
    mounted = command('while read dev rest; do case "$dev" in /dev/block/*) /sbin/busybox readlink -f "$dev";; esac; done < /proc/mounts')
    if b'/dev/block/sda17' in mounted.splitlines():
        raise SystemExit('linux is mounted; raw writes stopped')
    help_text = subprocess.run(['adb', 'exec-out', '/sbin/busybox dd --help'], capture_output=True, check=False)
    if b'fullblock' not in help_text.stdout + help_text.stderr:
        raise SystemExit('Recovery BusyBox dd must support iflag=fullblock for streaming')
    manifest = json.loads((ROOT / 'backup/initial/manifest.json').read_text())
    for name in ['boot_a', 'boot_b', 'esp']:
        if sha(ROOT / f'backup/initial/{name}.img') != manifest['partitions'][name]['sha256']:
            raise SystemExit(f'{name}: local backup verification failed')
    receipt = json.loads((args.root.parent / 'root.json').read_text())
    size = args.root.stat().st_size
    if (receipt['build'] != '20H392' or receipt['root_bytes'] != size or
            size <= 0 or size > CAPACITY or size % BLOCK or sha(args.root) != receipt['root_sha256']):
        raise SystemExit('Root image size/hash/build validation failed')
    with args.root.open('rb') as f:
        f.seek(1024)
        if f.read(4) != b'HX\x00\x05':
            raise SystemExit('Expected case-sensitive HFS+ volume version 5')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # Preserve filesystem-identification metadata; this is not a data backup.
    for name, skip in [('first-mib', 0), ('last-mib', CAPACITY // 4096 - 256)]:
        with (output / (name + '.bin')).open('xb') as f:
            command(f'/sbin/busybox dd if={TARGET} bs=4096 skip={skip} count=256', output=f)
        if (output / (name + '.bin')).stat().st_size != 1024 * 1024:
            raise SystemExit('Incomplete partition metadata read; no writes performed')
    (output / 'pending.json').write_text(json.dumps({'target': TARGET, 'bytes': size,
        'sha256': receipt['root_sha256'], 'partition_bytes': CAPACITY}, indent=2) + '\n')
    print(f'Writing HFS+ root to allocated linux: {size} bytes', flush=True)
    remote = f'set -eu; /sbin/busybox dd of={TARGET} bs={BLOCK} iflag=fullblock conv=fsync; /sbin/busybox sync'
    with args.root.open('rb') as source:
        process = subprocess.Popen(['adb', 'shell', '-T', remote], stdin=source,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        last = -1
        while process.poll() is None:
            percent = min(100, source.tell() * 100 // size)
            if percent // 5 != last:
                print(f'Transferred {percent}%', flush=True); last = percent // 5
            time.sleep(2)
        stdout, stderr = process.communicate()
        (output / 'transfer.log').write_bytes(stdout + stderr)
        if process.returncode:
            raise SystemExit('Root transfer failed; inspect transfer.log')
    actual = command(f'/sbin/busybox dd if={TARGET} bs={BLOCK} count={size // BLOCK} | /sbin/busybox sha256sum').decode().split()[0]
    if actual != receipt['root_sha256']:
        raise SystemExit('Root partition readback hash mismatch')
    (output / 'verified.json').write_text(json.dumps({'target': TARGET, 'bytes': size,
        'sha256': actual, 'readback_verified': True}, indent=2) + '\n')
    print('Root write and complete readback SHA-256 verified', flush=True)


if __name__ == '__main__':
    main()
