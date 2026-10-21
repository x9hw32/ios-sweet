#!/usr/bin/env python3
"""Place an external root in file-backed QEMU virt RAM without keeping it in host RAM."""
import argparse
import errno
import fcntl
import os
from pathlib import Path
import struct


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--root-phys', type=lambda x: int(x, 0), required=True)
    p.add_argument('--bytes', type=lambda x: int(x, 0), default=18 * 1024**3)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    offset = a.root_phys - 0x40000000  # QEMU virt DRAM starts at 1 GiB.
    size = a.root.stat().st_size
    if offset < 0 or offset % 4096 or size % 4096 or offset + size > a.bytes:
        p.error('Root must fit in file-backed guest RAM with 4 KiB alignment')
    with a.root.open('rb') as source, a.output.open('xb') as destination:
        destination.truncate(a.bytes)
        try:
            fcntl.ioctl(destination.fileno(), 0x4020940d,
                        struct.pack('qQQQ', source.fileno(), 0, size, offset))  # FICLONERANGE
            print('Cloned root extents into sparse QEMU memory file')
        except OSError as error:
            if error.errno not in (errno.EOPNOTSUPP, errno.EINVAL, errno.ENOTTY, errno.EXDEV):
                raise
            destination.seek(offset)
            left = size
            while left:
                copied = os.copy_file_range(source.fileno(), destination.fileno(), min(left, 64 * 1024 * 1024))
                if not copied:
                    raise RuntimeError('Incomplete root copy')
                left -= copied
            print('Copied root into sparse QEMU memory file')
        os.fsync(destination.fileno())


if __name__ == '__main__':
    main()
