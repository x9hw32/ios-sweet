#!/usr/bin/env python3
"""Read PJA110 boot/calibration partitions to the PC and verify their SHA-256."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

PARTITIONS = [
    name + slot
    for name in ('boot', 'init_boot', 'vendor_boot', 'dtbo', 'vbmeta',
                 'vbmeta_system', 'vbmeta_vendor', 'recovery')
    for slot in ('_a', '_b')
] + ['persist', 'modemst1', 'modemst2', 'fsg', 'fsc', 'esp']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serial')
    args = parser.parse_args()
    adb = ['adb'] + (['-s', args.serial] if args.serial else [])

    def command(remote):
        return adb + ['exec-out', 'su -c ' + shlex.quote(remote)]

    def read(remote):
        return subprocess.run(command(remote), check=True, capture_output=True,
                              timeout=120).stdout

    if read('id -u').strip() != b'0':
        raise RuntimeError('Root shell required')
    if read('getprop ro.product.model').strip() != b'PJA110':
        raise RuntimeError('Refusing backup: expected PJA110')
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest = {'model': 'PJA110', 'slot': read('getprop ro.boot.slot_suffix').decode().strip(),
                'partitions': {}}
    manifest_path = args.output / 'manifest.json'
    for name in PARTITIONS:
        device = '/dev/block/by-name/' + name
        size = int(read('blockdev --getsize64 ' + device))
        target = read('readlink -f ' + device).decode().strip()
        # These are boot/calibration partitions, never entire UFS LUNs/userdata.
        if not 0 < size <= 512 * 1024 * 1024:
            raise RuntimeError(f'{name}: unexpected size {size}')
        temporary = args.output / (name + '.img.partial')
        digest = hashlib.sha256()
        count = 0
        with temporary.open('xb') as out:
            os.chmod(temporary, 0o600)
            process = subprocess.Popen(command('cat ' + device), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            try:
                while chunk := process.stdout.read(1024 * 1024):
                    count += len(chunk)
                    if count > size:
                        raise RuntimeError(f'{name}: output exceeds partition size')
                    digest.update(chunk)
                    out.write(chunk)
                process.communicate(timeout=120)
                if process.returncode:
                    raise RuntimeError(f'{name}: adb read failed ({process.returncode})')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            out.flush()
            os.fsync(out.fileno())
        if count != size:
            raise RuntimeError(f'{name}: truncated backup ({count}/{size})')
        local_hash = digest.hexdigest()
        remote_hash = read('sha256sum ' + device).decode().split()[0]
        if local_hash != remote_hash:
            raise RuntimeError(f'{name}: checksum mismatch')
        temporary.rename(args.output / (name + '.img'))
        manifest['partitions'][name] = {
            'device': target, 'size': size, 'sha256': local_hash,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(f'{name}: {size} bytes, SHA-256 verified', flush=True)
    print(f'Backups complete: {args.output}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Backup stopped: {error}', file=sys.stderr)
        sys.exit(1)
