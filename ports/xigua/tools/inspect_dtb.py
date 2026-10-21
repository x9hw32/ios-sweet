#!/usr/bin/env python3
"""Extract board facts from a live DTB; do not guess framebuffer or safe RAM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from fdt import parse


def summarize(data):
    nodes, reservations = parse(data)
    def region(base, size):
        return {'base': hex(base), 'size': hex(size), 'end': hex(base + size)}
    memory = []
    fixed = []
    dynamic = []
    devices = {}
    cpus = []
    for node in nodes.values():
        compat = node.strings('compatible')
        if node.strings('device_type') == ['memory']:
            memory.extend(region(*r) for r in node.ranges())
        if node.parent and node.parent.path == '/reserved-memory':
            if 'reg' in node.props:
                fixed.extend({'path': node.path, **region(*r)} for r in node.ranges())
            else:
                dynamic.append({'path': node.path, 'size': node.props.get('size', b'').hex(),
                                'alloc_ranges': node.props.get('alloc-ranges', b'').hex()})
        if node.parent and node.parent.path == '/cpus' and node.name.startswith('cpu@'):
            cpus.append({'path': node.path, 'mpidr': hex(node.ranges()[0][0]),
                         'enable_method': node.strings('enable-method')})
        kind = None
        if 'arm,gic-v3' in compat:
            kind = 'gic'
        elif 'qcom,ufshc' in compat:
            kind = 'ufs'
        elif 'arm,armv8-timer' in compat:
            kind = 'timer'
        elif 'synaptics,tcm-spi-hbp' in compat:
            kind = 'touch'
        if kind:
            value = {'path': node.path, 'compatible': compat,
                     'status': node.strings('status') if 'status' in node.props else ['okay']}
            if 'reg' in node.props:
                value['reg'] = [region(*r) for r in node.ranges()]
            if 'interrupts' in node.props:
                raw = node.props['interrupts']
                value['interrupt_cells'] = list(struct.unpack('>%dI' % (len(raw) // 4), raw))
            if kind == 'timer':
                cells = value['interrupt_cells']
                if len(cells) < 9 or cells[6] != 1 or cells[7] >= 16:
                    raise ValueError('Unsupported architected virtual timer encoding')
                value['virtual_timer_intid'] = 16 + cells[7]
            devices[kind] = value
    return {'dtb_sha256': hashlib.sha256(data).hexdigest(),
            'compatible': nodes['/'].strings('compatible'), 'memory': memory,
            'fixed_reserved': fixed, 'dynamic_reserved': dynamic,
            'header_reservations': [region(*r) for r in reservations],
            'cpus': cpus, 'devices': devices,
            'framebuffer_verified': False, 'kernel_ram_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = summarize(args.dtb.read_bytes())
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as out:
            out.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
