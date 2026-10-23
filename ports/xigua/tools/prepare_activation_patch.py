#!/usr/bin/env python3
"""Prepare a reversible two-sector fix for the verified iOS 20H392 port only.

SpringBoard's SBLockdownManager waits for the unsupported activation daemon.
The approach follows oosexgang's inject_sb.c (a79ff077): set the port's local
lockdown state to 2. No Apple account, SEP, device activation record or remote
service is involved. This implementation verifies our exact arm64 method and
updates its existing ad-hoc CodeDirectory hash. Only host files are written.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct

METHOD_OFFSET = 0x2C41A78
METHOD_SIZE = 352
METHOD_SHA256 = 'aa0562b1d3fbabcc43e0183dadd575047d3e5ad529d402456bfd3d7bbf3c204e'
SECTOR = 4096
ROOT_BYTES = 12884901888
# mov w8,#2; str w8,[x0,#8]; strb wzr,[x0,#12]; ret
REPLACEMENT = struct.pack('<4I', 0x52800048, 0xB9000808, 0x3900301F, 0xD65F03C0)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def volume_identity(header):
    if len(header) != SECTOR or header[1024:1026] not in (b'H+', b'HX'):
        raise ValueError('Expected HFS+/HFSX volume header')
    return sha(header[1024:1028] + header[1040:1044] + header[1064:1072] + header[1128:1136])


def patch_cache(data, method_offset=METHOD_OFFSET, method_size=METHOD_SIZE,
                method_sha256=METHOD_SHA256):
    if (len(data) < 0x68 or not data.startswith(b'dyld_v1') or
            method_offset < 0 or method_size < len(REPLACEMENT) or
            method_offset + method_size > len(data) or
            sha(data[method_offset:method_offset + method_size]) != method_sha256):
        raise ValueError('Unsupported cache or method fingerprint; no patch prepared')
    sigoff, sigsize = struct.unpack_from('<QQ', data, 0x28)
    if sigoff > len(data) or sigsize > len(data) - sigoff or sigsize < 20:
        raise ValueError('Invalid cache signature bounds')
    magic, length, count = struct.unpack_from('>III', data, sigoff)
    if magic != 0xFADE0CC0 or length > sigsize or count > (length - 12) // 8:
        raise ValueError('Invalid signature index')
    result = bytearray(data)
    result[method_offset:method_offset + len(REPLACEMENT)] = REPLACEMENT
    directories = []
    for i in range(count):
        slot, rel = struct.unpack_from('>II', data, sigoff + 12 + 8 * i)
        if rel > length - 8:
            raise ValueError('Invalid signature blob offset')
        off = sigoff + rel
        kind, size = struct.unpack_from('>II', data, off)
        if size < 8 or size > length - rel:
            raise ValueError('Invalid signature blob size')
        if kind != 0xFADE0C02:
            continue
        if size < 44:
            raise ValueError('Truncated CodeDirectory')
        fields = struct.unpack_from('>9I4B', data, off)
        _, _, version, flags, hashes, identifier, special, pages, limit, hashsize, hashtype, platform, shift = fields
        if not flags & 2 or hashtype != 2 or hashsize != 32 or shift not in (12, 14):
            raise ValueError('Only existing ad-hoc SHA256 cache signatures are supported')
        pagebytes = 1 << shift
        if (limit > sigoff or method_offset + method_size > limit or
                pages != (limit + pagebytes - 1) // pagebytes or hashes < 44 or
                hashes > size or pages > (size - hashes) // 32):
            raise ValueError('Unsupported CodeDirectory page geometry')
        first = method_offset // pagebytes
        last = (method_offset + len(REPLACEMENT) - 1) // pagebytes
        for page in range(first, last + 1):
            start, end = page * pagebytes, min((page + 1) * pagebytes, limit)
            h = off + hashes + page * 32
            if data[h:h + 32] != hashlib.sha256(data[start:end]).digest():
                raise ValueError('Original code page hash mismatch')
            result[h:h + 32] = hashlib.sha256(result[start:end]).digest()
        directories.append({'slot': slot, 'page_bytes': pagebytes, 'first_page': first,
                            'last_page': last})
    if not directories:
        raise ValueError('No supported CodeDirectory')
    sectors = [n for n in range((len(data) + SECTOR - 1) // SECTOR)
               if data[n * SECTOR:(n + 1) * SECTOR] != result[n * SECTOR:(n + 1) * SECTOR]]
    if len(sectors) != 2:
        raise ValueError('Expected exactly one code sector and one signature sector')
    return bytes(result), sectors, directories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-file', type=Path, required=True,
                        help='Cache .21 in the read-only mounted current root snapshot')
    parser.add_argument('--root-image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.root_image.stat().st_size != ROOT_BYTES:
        parser.error('Fresh output directory and current 12 GiB snapshot required')
    snapshot = json.loads((args.root_image.parent / 'receipt.json').read_text())
    if snapshot.get('source_sha_verified') is not True:
        parser.error('Snapshot must have a verified phone-source SHA256')
    data = args.cache_file.read_bytes()
    patched, sectors, directories = patch_cache(data)
    plan = []
    with args.cache_file.open('rb') as cache, args.root_image.open('rb') as root:
        identity = volume_identity(root.read(SECTOR))
        if os.fstatvfs(cache.fileno()).f_bsize != SECTOR:
            raise SystemExit('Expected HFS allocation blocks of 4096 bytes')
        for sector in sectors:
            index = bytearray(struct.pack('I', sector))
            fcntl.ioctl(cache.fileno(), 1, index, True)  # FIBMAP, read-only, needs CAP_SYS_RAWIO
            physical = struct.unpack('I', index)[0]
            if not 0 < physical < ROOT_BYTES // SECTOR:
                raise SystemExit('Invalid file-to-volume mapping')
            old = data[sector * SECTOR:(sector + 1) * SECTOR]
            new = patched[sector * SECTOR:(sector + 1) * SECTOR]
            root.seek(physical * SECTOR)
            if len(old) != SECTOR or len(new) != SECTOR or root.read(SECTOR) != old:
                raise SystemExit('Raw snapshot sector differs from mounted file; refusing patch')
            plan.append((physical, sector, old, new))
    if len({p[0] for p in plan}) != len(plan):
        raise SystemExit('Duplicate physical mapping')
    args.output.mkdir(parents=True)
    receipt = {'kind': 'xigua-ios-20H392-local-lockdown-state',
               'target': '/dev/block/by-name/linux', 'partition_bytes': 77137424384,
               'root_bytes': ROOT_BYTES, 'sector_bytes': SECTOR,
               'snapshot_sha256': snapshot['sha256'], 'original_cache_sha256': sha(data),
               'volume_identity': identity,
               'patched_cache_sha256': sha(patched), 'method_sha256': METHOD_SHA256,
               'method_vmaddr': '0x1c5991a78', 'method_file_offset': METHOD_OFFSET,
               'code_directories': directories, 'sectors': []}
    for i, (physical, logical, old, new) in enumerate(plan):
        (args.output / f'{i}.original.bin').write_bytes(old)
        (args.output / f'{i}.patched.bin').write_bytes(new)
        receipt['sectors'].append({'physical': physical, 'file_sector': logical,
                                   'original_sha256': sha(old), 'patched_sha256': sha(new)})
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Prepared 2 sectors (8192 bytes); phone unchanged')


if __name__ == '__main__':
    main()
