#!/usr/bin/env python3
"""Collect hardware metadata through adb; issue no block-device writes or reboot."""

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


REPORT = r'''
set -eu
echo '== Identity =='
for key in ro.product.model ro.product.device ro.product.board ro.board.platform ro.soc.model ro.build.version.release ro.build.version.security_patch ro.boot.slot_suffix; do
    printf '%s=' "$key"
    getprop "$key"
done
echo '== Kernel =='
uname -a
echo '== CPU (selected fields) =='
sed -n '/^processor/p; /^Features/p; /^CPU implementer/p; /^CPU architecture/p; /^CPU variant/p; /^CPU part/p; /^CPU revision/p; /^Hardware/p' /proc/cpuinfo
echo '== Memory =='
cat /proc/meminfo
echo '== Physical map =='
cat /proc/iomem
echo '== Partitions (kernel sizes in 512-byte sectors) =='
cat /proc/partitions
echo '== Partition labels, physical targets, start and size =='
for base in /dev/block/by-name /dev/block/bootdevice/by-name; do
    [ -d "$base" ] || continue
    for node in "$base"/*; do
        [ -b "$node" ] || continue
        target=$(readlink -f "$node")
        block=${target##*/}
        printf '%s -> %s' "${node##*/}" "$target"
        for field in start size queue/logical_block_size; do
            path=/sys/class/block/$block/$field
            if [ -r "$path" ]; then
                printf ' %s=%s' "$field" "$(cat "$path")"
            fi
        done
        printf '\n'
    done
    break
done
echo '== Framebuffer metadata, if exposed by Android =='
for fb in /sys/class/graphics/fb*; do
    [ -d "$fb" ] || continue
    printf '%s\n' "$fb"
    for field in name virtual_size stride bits_per_pixel modes; do
        [ ! -r "$fb/$field" ] || cat "$fb/$field"
    done
done
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', help='ADB target when several devices are attached')
    parser.add_argument('--output', type=Path, default=Path('diagnostics/ace2pro'))
    args = parser.parse_args()
    adb = ['adb'] + (['-s', args.serial] if args.serial else [])

    def run(command, *, script=None, timeout=30):
        return subprocess.run(
            adb + command, input=script, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
        )

    def require(result, operation):
        if result.returncode:
            # Do not echo adb diagnostics: those can contain device identifiers.
            raise RuntimeError(f'{operation} failed (exit {result.returncode}); check adb and root access')
        return result.stdout

    def root(command, **kwargs):
        # adb transmits a remote shell command; retain su's command as one word.
        return run(['exec-out', 'su -c ' + shlex.quote(command)], **kwargs)

    state = require(run(['get-state']), 'ADB connection').strip()
    if state != b'device':
        raise RuntimeError('Boot Android and authorize USB debugging first')
    uid = require(root('id -u'), 'Root check').strip()
    if uid != b'0':
        raise RuntimeError('Root shell unavailable; authorize the adb shell in your root manager')
    # Refuse overwrites so each directory remains a record of one collection.
    args.output.mkdir(parents=True, exist_ok=False)
    # exec-out does not reliably deliver EOF to a root sh reading stdin on all
    # adbd builds. Pass the fixed script as su's quoted command instead.
    report = require(root(REPORT, timeout=90), 'Metadata collection')
    (args.output / 'hardware.txt').write_bytes(report)

    # Prefer the original FDT handed to Linux. Never mix stderr into binary data.
    fdt = root('cat /sys/firmware/fdt')
    if fdt.returncode == 0 and fdt.stdout.startswith(b'\xd0\x0d\xfe\xed'):
        (args.output / 'live.dtb').write_bytes(fdt.stdout)
        print(f'Saved {args.output}/live.dtb')
    else:
        tree = root('tar -C /sys/firmware/devicetree/base -cf - .', timeout=90)
        if tree.returncode == 0 and len(tree.stdout) >= 512:
            (args.output / 'live-devicetree.tar').write_bytes(tree.stdout)
            print(f'Saved {args.output}/live-devicetree.tar (FDT file unavailable)')
        else:
            print('Device tree unavailable; hardware.txt saved, need stock DTB separately', file=sys.stderr)
    print(f'Saved {args.output}/hardware.txt; no partition writes or reboot requested')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Collection stopped: {error}', file=sys.stderr)
        sys.exit(1)
