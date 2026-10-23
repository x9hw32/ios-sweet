#!/usr/bin/env python3
"""Read the native XNU console ring from the allocated linux partition in recovery."""
import argparse
from pathlib import Path
import struct
from install_ios_root import command, TARGET, CAPACITY

RING_BYTES = 4 * 1024 * 1024
BLOCK = 4096


def decode(data):
    if len(data) != BLOCK + RING_BYTES:
        raise ValueError('Incomplete console log read')
    magic, version, size, total, sequence = struct.unpack_from('<8sIIQQ', data)
    if magic != b'SWEETLOG' or version != 1 or size != RING_BYTES:
        raise ValueError('No compatible native UFS log found')
    ring = data[BLOCK:]
    if total < size:
        text = ring[:total]
    else:
        cursor = total % size
        text = ring[cursor:] + ring[:cursor]
    return text, {'total_bytes': total, 'flush_sequence': sequence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (command('getprop ro.bootmode').strip() != b'recovery' or
            command('getprop ro.product.model').strip() != b'PJA110' or
            command('/sbin/busybox id -u').strip() != b'0'):
        raise SystemExit('Expected PJA110 recovery with root BusyBox')
    if (command('/sbin/busybox readlink -f ' + TARGET).strip() != b'/dev/block/sda17' or
            int(command('/sbin/busybox blockdev --getsize64 ' + TARGET)) != CAPACITY):
        raise SystemExit('Allocated linux partition mapping changed')
    if args.output.exists():
        raise SystemExit('Output already exists')
    blocks = 1 + RING_BYTES // BLOCK
    data = command(f'/sbin/busybox dd if={TARGET} bs={BLOCK} skip={CAPACITY // BLOCK - blocks} count={blocks}')
    args.output.mkdir(parents=True)
    (args.output / 'raw.bin').write_bytes(data)
    text, info = decode(data)
    (args.output / 'console.txt').write_bytes(text)
    import json
    (args.output / 'info.json').write_text(json.dumps(info, indent=2) + '\n')
    print(f'Native console: {len(text)} bytes, flush {info["flush_sequence"]}, {args.output / "console.txt"}')


if __name__ == '__main__':
    main()
