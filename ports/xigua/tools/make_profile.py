#!/usr/bin/env python3
"""Combine live DT and a UEFI probe report; keep firmware-dependent facts explicit."""
import argparse
import json
from pathlib import Path
from inspect_dtb import summarize


def parse_probe(text):
    lines = text.splitlines()
    if not lines or lines[0] not in ('XIGUA-PROBE version=1', 'XIGUA-PROBE version=2'):
        raise ValueError('Not an XIGUA probe v1/v2 report')
    values = {}
    memory = []
    for line in text.splitlines():
        if line.startswith('memory '):
            kind, base, pages, attr = (int(x, 16) for x in line.split()[1:])
            if base + pages * 4096 > 1 << 64:
                raise ValueError('UEFI memory range overflow')
            memory.append((kind, base, pages * 4096, attr))
        elif '=' in line:
            key, value = line.split('=', 1)
            if value.startswith('0x'):
                values[key] = int(value, 16)
    if values.get('memory_map_status') != 0 or values.get('tgran16') not in (1, 2):
        raise ValueError('No valid UEFI memory map or 16 KiB translation granule')
    if not values.get('cntfrq_el0'):
        raise ValueError('Invalid architected timer frequency')
    return values, memory


def large_ram_range(values, memory, banks, fixed):
    def covered(base, end, ranges):
        cursor = base
        for lo, hi in sorted(ranges):
            if lo > cursor:
                break
            if hi > cursor:
                cursor = hi
            if cursor >= end:
                return True
        return False
    base, size = values.get('large_ram_base', 0), values.get('large_ram_size', 0)
    end = base + size
    if (values.get('large_ram_allocate_status') != 0 or
            values.get('large_ram_sample_pages_passed') != 1 or
            base < 1 << 32 or base % 0x2000000 or size < 1 << 30 or
            size % 0x4000 or end > 1 << 36 or
            not covered(base, end, banks) or
            not covered(base, end, [(lo, lo+n) for kind, lo, n, attr in memory
                                    if kind == 7 and not attr & (1 << 63)]) or
            any(base < hi and lo < end for lo, hi in fixed)):
        raise ValueError('Large RAM range must be reserved/tested by UEFI and covered by DT/free memory')
    return base, size


def make_profile(dtb, report, large_ram=False):
    board = summarize(dtb)
    values, memory = parse_probe(report)
    if values.get('gop_status') != 0 or values.get('gop_pixel_format') not in (0, 1):
        raise ValueError('A directly addressable RGB/BGR 32-bit GOP framebuffer is required')
    base, width, height, pitch, size = (values['gop_' + key] for key in
                                      ['base', 'width', 'height', 'pixels_per_scanline', 'size'])
    if not (0 < width <= pitch <= 8192 and 0 < height <= 8192 and
            pitch * height * 4 <= size <= 256 * 1024 * 1024 and base % 4 == 0):
        raise ValueError('Invalid GOP geometry')
    fixed = [(int(r['base'], 16), int(r['end'], 16)) for r in
             board['fixed_reserved'] + board['header_reservations'] if int(r['size'], 16)]
    fixed.append((base, base + size))
    candidates = []
    for bank in board['memory']:
        bank_base, bank_end = int(bank['base'], 16), int(bank['end'], 16)
        for kind, lo, length, attr in memory:
            if kind != 7 or attr & (1 << 63):
                continue
            lo, hi = max(bank_base, lo, 0x100000000), min(bank_end, lo + length, 1 << 36)
            lo = (lo + 0x1ffffff) & ~0x1ffffff
            length = 512 * 1024 * 1024
            if hi - lo >= length and not any(lo < b and a < lo + length for a, b in fixed):
                candidates.append((lo, length))
    if not candidates:
        raise ValueError('No 512 MiB high-RAM candidate shared by DT and UEFI free memory')
    ram, length = min(candidates)
    if large_ram:
        ram, length = large_ram_range(values, memory,
            [(int(b['base'], 16), int(b['end'], 16)) for b in board['memory']], fixed)
    gic = board['devices']['gic']['reg']
    return {'model': 'PJA110', 'kind': 'phone', 'dtb_sha256': board['dtb_sha256'],
            'boot_mpidr': values['mpidr_el1'] & 0xffffff, 'timebase': values['cntfrq_el0'],
            'virtual_timer_intid': board['devices']['timer']['virtual_timer_intid'],
            'gicd': int(gic[0]['base'], 16), 'gicd_size': int(gic[0]['size'], 16),
            'gicr': int(gic[1]['base'], 16), 'gicr_size': int(gic[1]['size'], 16),
            'ram_base': ram, 'ram_size': length,
            'ram_status': ('UEFI reserved range; three pages sampled; large XNU mapping unverified'
                           if large_ram else 'candidate: live DT intersected with UEFI conventional memory'),
            'framebuffer': {'base': base, 'size': size, 'width': width, 'height': height,
                            'stride': pitch * 4, 'rgb': values['gop_pixel_format'] == 0,
                            'source': 'Mu UEFI GOP', 'abl_scanout_verified': False},
            'hardware_xnu_boot_verified': False}


def qemu_profile():
    return {'model': 'QEMU', 'kind': 'qemu', 'boot_mpidr': 0,
            'timebase': 62500000, 'virtual_timer_intid': 27,
            'gicd': 0x08000000, 'gicd_size': 0x10000,
            'gicr': 0x080a0000, 'gicr_size': 0xf60000,
            'ram_base': 0xb0000000, 'ram_size': 0x40000000,
            'framebuffer': {'base': 0x9c000000, 'size': 0x1000000, 'width': 1080,
                            'height': 2400, 'stride': 4320, 'rgb': False,
                            'source': 'QEMU RAM', 'abl_scanout_verified': True},
            'hardware_xnu_boot_verified': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dtb', type=Path)
    p.add_argument('--probe', type=Path)
    p.add_argument('--qemu', action='store_true')
    p.add_argument('--large-ram', action='store_true', help='Use the range explicitly allocated by EFI probe v2')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.qemu:
        profile = qemu_profile()
    else:
        if not a.dtb or not a.probe:
            p.error('--dtb and --probe required for a phone profile')
        profile = make_profile(a.dtb.read_bytes(), a.probe.read_text(), a.large_ram)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as out:
        json.dump(profile, out, indent=2)
        out.write('\n')
    print(a.output)


if __name__ == '__main__':
    main()
