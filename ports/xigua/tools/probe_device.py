#!/usr/bin/env python3
"""Temporarily boot an EFI probe from the backed-up ESP (raw, 4 KiB aligned I/O).

install: verifies unchanged ESP, prepares/rechecks a local FAT image, writes ESP.
collect-restore: reads ESP to PC, extracts reports, restores original ESP bytewise.
No boot partition writes or reboot are performed by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(1024 * 1024): h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['install', 'collect-restore', 'restore'])
    p.add_argument('--backup', type=Path, default=ROOT / 'backup/initial')
    p.add_argument('--output', type=Path, default=ROOT / 'diagnostics/uefi')
    p.add_argument('--prepared-image', type=Path, help='Install a FAT image from build_efi_boot.py')
    a = p.parse_args()
    if a.prepared_image and a.action != 'install':
        p.error('--prepared-image is only valid with install')

    def root(command, *, out=None):
        r = subprocess.run(['adb', 'exec-out', 'sh -c ' + shlex.quote(command)],
                           stdout=out if out else subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=180, check=True)
        return r.stdout

    if root('getprop ro.bootmode').strip() != b'recovery':
        raise SystemExit('ESP operations require ADB in recovery (user requirement)')
    if root('getprop ro.product.model').strip() != b'PJA110' or root('/sbin/busybox id -u').strip() != b'0':
        raise SystemExit('Expected PJA110 recovery with root and /sbin/busybox')
    manifest = json.loads((a.backup / 'manifest.json').read_text())
    for name in ['boot_a', 'boot_b', 'esp']:
        if sha(a.backup / (name + '.img')) != manifest['partitions'][name]['sha256']:
            raise SystemExit(f'{name}: local backup verification failed')
    device = '/dev/block/by-name/esp'
    expected_size = manifest['partitions']['esp']['size']
    if int(root('/sbin/busybox blockdev --getsize64 ' + device)) != expected_size:
        raise SystemExit('ESP size changed')
    actual = root('/sbin/busybox readlink -f ' + device).decode().strip()
    if actual != manifest['partitions']['esp']['device']:
        raise SystemExit('ESP device mapping changed; inspect partition table first')
    mounted = root('while read dev rest; do case "$dev" in /dev/block/*) /sbin/busybox readlink -f "$dev";; esac; done < /proc/mounts').decode().splitlines()
    if actual in mounted:
        raise SystemExit('ESP is mounted; stop before raw I/O')
    original = a.backup / 'esp.img'
    if a.action == 'install':
        current = root('/sbin/busybox sha256sum ' + device).decode().split()[0]
        if current != sha(original):
            raise SystemExit('ESP changed since backup; take a fresh backup first')
        if a.prepared_image:
            image = a.prepared_image
            build = json.loads((image.parent / 'build.json').read_text())
            if build['esp_sha256'] != sha(image) or build['esp_bytes'] != expected_size:
                raise SystemExit('Prepared ESP receipt mismatch')
            loader = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/BOOT/BOOTAA64.EFI'])
            if loader != (image.parent / 'BOOTAA64.EFI').read_bytes():
                raise SystemExit('Prepared loader file mismatch')
            native = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/XIGUA/Image'])
            if hashlib.sha256(native).hexdigest() != build['native_image_sha256']:
                raise SystemExit('Prepared native Image mismatch')
        else:
            image = ROOT / 'out/efi/esp-probe.img'
            shutil.copyfile(original, image)
            # mtools handles a 512-byte FAT BPB inside a 4-KiB-sector UFS partition.
            subprocess.run(['mcopy', '-o', '-i', str(image),
                            str(ROOT / 'out/efi/probe.efi'), '::/EFI/BOOT/BOOTAA64.EFI'], check=True)
            probe = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/BOOT/BOOTAA64.EFI'])
            if probe != (ROOT / 'out/efi/probe.efi').read_bytes():
                raise SystemExit('EFI readback from prepared image failed')
        receipt = {'original_sha256': sha(original), 'probe_image_sha256': sha(image),
                   'size': expected_size, 'target': device}
        (ROOT / 'out/efi/install.json').write_text(json.dumps(receipt, indent=2) + '\n')
    else:
        a.output.mkdir(parents=True, exist_ok=False)
        received = a.output / 'esp-after-probe.img'
        with received.open('xb') as out: root('/sbin/busybox cat ' + device, out=out)
        if received.stat().st_size != expected_size:
            raise SystemExit('Incomplete ESP read; original ESP not yet restored')
        remote_sha = root('/sbin/busybox sha256sum ' + device).decode().split()[0]
        if remote_sha != sha(received):
            raise SystemExit('ESP backup readback checksum mismatch')
        # Restore even when firmware produced no report; preserve received image.
        r = subprocess.run(['mcopy', '-n', '-i', str(received), '::/xigua-probe-*.txt',
                            str(a.output) + '/'], capture_output=True)
        reports = list(a.output.glob('xigua-probe-*.txt')) if r.returncode == 0 else []
        image = original
    if image.stat().st_size != expected_size or expected_size % 4096:
        raise SystemExit('Unexpected ESP image size/alignment')
    remote = '/tmp/xigua-esp-transfer.img'
    subprocess.run(['adb', 'push', str(image), remote], check=True)
    expected = sha(image)
    if root('/sbin/busybox sha256sum ' + remote).decode().split()[0] != expected:
        raise SystemExit('Uploaded image checksum mismatch')
    print(f'Writing {device}: {expected_size} bytes, SHA256 {expected}', flush=True)
    # Exact allowlisted device and fixed 4-KiB alignment; all other partitions stay read-only.
    result = root('set -eu; /sbin/busybox dd if=' + remote + ' of=' + device +
                  ' bs=4096 conv=fsync; /sbin/busybox sync; /sbin/busybox sha256sum ' + device)
    if expected.encode() not in result.split():
        raise SystemExit('ESP write verification failed; original backup is available')
    print('ESP write and readback verified', flush=True)
    if a.action in ['collect-restore', 'restore']:
        if not reports and a.action == 'collect-restore':
            raise SystemExit('Original ESP restored, but no EFI probe report found; inspect esp-after-probe.img')
        print('Original ESP restored; reports: ' + (', '.join(str(p) for p in reports) or 'none expected'))


if __name__ == '__main__':
    main()
