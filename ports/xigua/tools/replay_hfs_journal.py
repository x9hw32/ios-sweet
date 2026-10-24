#!/usr/bin/env python3
"""Strict replay of the committed HFS journal range on a HOST COW device only.

Layout/checksum rules: XNU bsd/sweet_hfs/core/hfs_journal.{c,h}.
All headers/payloads/ranges are checked before any virtual writes; no recovery
or phone commands exist here. The target must be our active /dev/nbd3 COW.
"""
import argparse
import json
from pathlib import Path
import struct
import os
from prepare_activation_patch import ROOT_BYTES


def checksum(data):
    value = 0
    for byte in data:
        value = ((value << 8) ^ (value + byte)) & 0xffffffff
    return (~value) & 0xffffffff


def plan(journal, volume_bytes=ROOT_BYTES):
    if len(journal) < 48:
        raise ValueError('Truncated journal')
    endian = '<' if struct.unpack_from('<I', journal)[0] == 0x4a4e4c78 else '>'
    magic, marker, start, end, size, blsize, crc, hsize, sequence = struct.unpack_from(endian + 'IIQQQIIII', journal)
    if (magic != 0x4a4e4c78 or marker != 0x12345678 or size != len(journal) or
            hsize not in (512, 4096) or blsize < 32 or blsize > min(size - hsize, 1024 * 1024) or
            not hsize <= start <= size or not hsize <= end <= size):
        raise ValueError('Unsupported journal geometry')
    header = bytearray(journal[:hsize])
    struct.pack_into(endian + 'I', header, 36, 0)
    if checksum(header[:44]) != crc:
        raise ValueError('Journal header checksum mismatch')
    start = hsize if start == size else start
    end = hsize if end == size else end
    pending = end - start if end >= start else size - start + end - hsize

    def ring(offset, length):
        offset = hsize + (offset - hsize) % (size - hsize)
        if not 0 <= length <= size - hsize:
            raise ValueError('Invalid ring read')
        first = min(length, size - offset)
        return journal[offset:offset + first] + journal[hsize:hsize + length - first]

    writes, consumed, position, previous, headers = [], 0, start, None, 0
    while consumed < pending:
        raw = ring(position, blsize)
        maximum, count, used, stored, flags = struct.unpack_from(endian + 'HHIII', raw)
        check = bytearray(raw[:32])
        struct.pack_into(endian + 'I', check, 8, 0)
        if checksum(check) != stored:
            raise ValueError('Transaction header checksum mismatch')
        if (not flags & 1 or flags & ~3 or not 1 <= count <= maximum <= (blsize - 16) // 16 or
                used < blsize or used > pending - consumed):
            raise ValueError('Unsupported transaction bounds/flags')
        seq = struct.unpack_from(endian + 'I', raw, 28)[0]
        if previous is not None and seq not in (previous, (previous + 1) & 0xffffffff):
            raise ValueError('Journal sequence discontinuity')
        previous = seq
        data_offset = position + blsize
        total = blsize
        for n in range(1, count):
            number, length, stored = struct.unpack_from(endian + 'qII', raw, 16 + n * 16)
            if not length or length % 512 or length > used - total:
                raise ValueError('Invalid journal block size')
            payload = ring(data_offset, length)
            if stored and checksum(payload) != stored:
                raise ValueError('Journal data checksum mismatch')
            if number != -1:
                if number < 0 or number * hsize + length > volume_bytes:
                    raise ValueError('Journal target outside volume')
                writes.append((number * hsize, payload))
            total += length
            data_offset += length
        if total != used:
            raise ValueError('Transaction byte count mismatch')
        consumed += used
        position = hsize + (position + used - hsize) % (size - hsize)
        headers += 1
    if position != end:
        raise ValueError('Replay did not end at committed boundary')
    struct.pack_into(endian + 'QQ', header, 8, end, end)
    struct.pack_into(endian + 'I', header, 36, 0)
    struct.pack_into(endian + 'I', header, 36, checksum(header[:44]))
    return writes, bytes(header), {'headers': headers, 'entries': len(writes),
                                  'journal_bytes': pending, 'start': start, 'end': end}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cow', type=Path, required=True)
    args = p.parse_args()
    session = json.loads((args.cow / 'session.json').read_text())
    if (session.get('device') != '/dev/nbd3' or session.get('phone_writes') is not False or
            int(Path('/sys/block/nbd3/pid').read_text()) != session['kernel_pid']):
        raise SystemExit('Expected our active host COW device')
    with open('/dev/nbd3', 'r+b', buffering=0) as f:
        f.seek(1024)
        vh = f.read(512)
        jib = struct.unpack_from('>I', vh, 12)[0]
        block = struct.unpack_from('>I', vh, 40)[0]
        if vh[:2] not in (b'HX', b'H+') or block != 4096:
            raise SystemExit('Unsupported volume')
        f.seek(jib * block)
        info = f.read(512)
        flags = struct.unpack_from('>I', info)[0]
        offset, size = struct.unpack_from('>QQ', info, 36)
        if flags != 1 or size > 64 * 1024 * 1024 or offset + size > ROOT_BYTES:
            raise SystemExit('Unsupported internal journal')
        f.seek(offset)
        journal = f.read(size)
        writes, header, report = plan(journal)
        if any(a < offset + size and a + len(b) > offset for a, b in writes):
            raise SystemExit('Journal targets its own storage')
        for a, b in writes:
            f.seek(a)
            f.write(b)
        os.fsync(f.fileno())
        f.seek(offset)
        f.write(header)
        os.fsync(f.fileno())
    report['host_cow_only'] = True
    (args.cow / 'journal-replay.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Journal validated/replayed on host COW only:', report)


if __name__ == '__main__':
    main()
