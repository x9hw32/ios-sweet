#!/usr/bin/env python3
"""Capture the full XNU console ring and framebuffer from a running native QEMU boot."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
from test_native_qemu import qemu


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    info = json.loads((a.native / 'build.json').read_text())
    virt = int(info['kernel']['virt_base'], 16)
    phys = info['profile']['ram_base']
    names = {}
    for line in subprocess.check_output(['llvm-nm', '--defined-only', str(a.kernel)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in ['_sweet_log_ring', '_sweet_log_total']:
            names[fields[2]] = phys + int(fields[0], 16) - virt
    if len(names) != 2:
        raise SystemExit('Kernel console-ring symbols missing')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sock = str((a.run / 'qmp.sock').resolve())
    qemu.qmp(sock, 'stop')
    try:
        for key, length, filename in [('_sweet_log_ring', 4 * 1024 * 1024, 'ring.bin'),
                                      ('_sweet_log_total', 8, 'total.bin')]:
            qemu.qmp(sock, pmemsave=(names[key], length, str(out / filename)))
        qemu.qmp(sock, pmemsave=(qemu.FB_BASE, qemu.FB_STRIDE * qemu.FB_H, str(out / 'fb.raw')))
    finally:
        qemu.qmp(sock, 'cont')
    ring = (out / 'ring.bin').read_bytes()
    total, = struct.unpack('<Q', (out / 'total.bin').read_bytes())
    if total < len(ring):
        data = ring[:total]
    else:
        offset = total % len(ring)
        data = ring[offset:] + ring[:offset]
    (out / 'console.txt').write_text(data.decode('utf-8', errors='replace'))
    qemu.write_png(str(out / 'fb.png'), (out / 'fb.raw').read_bytes())
    print(f'Captured {len(data)} console bytes and framebuffer to {out}')


if __name__ == '__main__':
    main()
