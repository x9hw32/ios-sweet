#!/usr/bin/env python3
"""Build a single-CPU, RAM-root ADT from an explicit XIGUA/QEMU profile."""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys

from paths import ROOT, DONOR
sys.path.insert(0, str(DONOR / 'tools'))
import adt
import mkadt


def put(node, key, value):
    node.props = [(k, f, v) for k, f, v in node.props if k != key] + [(key, 0, value)]


def make(profile):
    ram, size = profile['ram_base'], profile['ram_size']
    panic = 1024 * 1024
    if ram % 0x2000000 or size % 0x4000 or size < 128 * 1024 * 1024:
        raise ValueError('RAM base must be 32 MiB aligned and size sufficient/16 KiB aligned')
    if profile['boot_mpidr'] != 0:
        raise ValueError('Initial XIGUA CPU driver currently requires MPIDR affinity 0')
    root = mkadt.build(qemu=True)
    chosen = next(n for n in root.children if n.name == 'chosen')
    for key, value in [('dram-base', ram), ('dram-size', size - panic)]:
        put(chosen, key, struct.pack('<Q', value))
    for key in ['firmware-version', 'system-firmware-version']:
        put(chosen, key, b'xigua-shim\0')
    put(root, 'compatible', b'D22AP\0iPhone10,3\0oneplus,xigua\0qcom,sm8550\0AppleARM\0')
    cpus = next(n for n in root.children if n.name == 'cpus')
    count = profile.get('cpu_count', 1)
    mpidrs = profile.get('cpu_mpidrs', [profile['boot_mpidr']])
    if (not isinstance(count, int) or not 1 <= count <= 8 or count > len(mpidrs) or
            len(mpidrs) != len(set(mpidrs)) or mpidrs[0] != profile['boot_mpidr'] or
            any(not isinstance(m, int) or m < 0 or m > 0x700 or m & 0xff for m in mpidrs)):
        raise ValueError('CPU count/MPIDRs must match the verified single-cluster PSCI topology')
    template = cpus.children[0]
    cpus.children = []
    for index, mpidr in enumerate(mpidrs[:count]):
        cpu = copy.deepcopy(template)
        for key, value in [('reg', mpidr), ('cpu-id', index), ('cluster-core-id', index),
                           ('l2-cache-id', index), ('AAPL,phandle', 0x1000 + index)]:
            put(cpu, key, struct.pack('<I', value))
        put(cpu, 'name', f'cpu{index}\0'.encode())
        put(cpu, 'state', b'running\0' if index == 0 else b'stopped\0')
        put(cpu, 'compatible', b'qcom,kryo\0ARM,v8\0')
        for key in ['timebase-frequency', 'peripheral-frequency', 'fixed-frequency']:
            put(cpu, key, struct.pack('<I', profile['timebase']))
        cpus.children.append(cpu)
    io = next(n for n in root.children if n.name == 'arm-io')
    gic = next(n for n in io.children if n.name == 'gic')
    put(gic, 'reg', struct.pack('<4Q', profile['gicd'] - mkadt.SOC_BASE,
                               profile['gicd_size'], profile['gicr'] - mkadt.SOC_BASE,
                               profile['gicr_size']))
    put(gic, 'virtual-timer-intid', struct.pack('<I', profile['virtual_timer_intid']))
    # GUI/display service is a later milestone; no UFS node or hardware driver startup.
    if not profile.get('gui'):
        io.children = [n for n in io.children if n.name != 'disp0']
    fb = profile['framebuffer']
    if profile.get('gui') and profile.get('display_mode') == 'native':
        display = next(n for n in io.children if n.name == 'disp0')
        put(display, 'canvas-width', struct.pack('<I', fb['width']))
        put(display, 'canvas-height', struct.pack('<I', fb['height']))
    console = next(n for n in root.children if n.name == 'sweet-fbcon')
    put(console, 'reg', struct.pack('<2Q', fb['base'], fb['size']))
    for key in ['width', 'height', 'stride']:
        put(console, key, struct.pack('<I', fb[key]))
    pram = next(n for n in root.children if n.name == 'pram')
    put(pram, 'reg', struct.pack('<2Q', ram + size - panic, panic))
    return adt.serialize(root)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    blob = make(json.loads(a.profile.read_text()))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(blob)
    print(f'{a.output}: {len(blob)} bytes')


if __name__ == '__main__':
    main()
