"""Read HFS+/HFSX allocation counts from a saved first 4 KiB; never replay a journal."""
import struct


def volume_info(data, partition_bytes):
    if len(data) != 4096:
        raise ValueError('Expected the first 4 KiB of the partition')
    signature, version, attributes = struct.unpack_from('>HHI', data, 1024)
    if (signature, version) not in [(0x482b, 4), (0x4858, 5)]:
        raise ValueError('No supported HFS+ or HFSX volume header')
    block, total, free = struct.unpack_from('>III', data, 1024 + 40)
    if (block < 512 or block > 1024 * 1024 or block & (block - 1) or
            not total or free > total or block * total > partition_bytes):
        raise ValueError('Invalid HFS allocation geometry')
    return {'filesystem': 'HFSX' if signature == 0x4858 else 'HFS+',
            'allocation_block_bytes': block, 'volume_bytes': block * total,
            'free_bytes_in_header': block * free, 'partition_bytes': partition_bytes,
            'journaled': bool(attributes & 0x2000),
            'cleanly_unmounted': bool(attributes & 0x100),
            'source': 'on-disk header snapshot; journal not replayed'}
