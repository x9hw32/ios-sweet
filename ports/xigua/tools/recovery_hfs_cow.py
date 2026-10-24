#!/usr/bin/env python3
"""Expose the recovery iOS root as an NBD copy-on-write device on the PC.

The phone is READ ONLY: every remote operation is BusyBox dd if=linux.
All virtual writes go to host files. This permits checking and repairing a
small file without downloading or rewriting the whole 12 GiB root.
"""
import argparse
from collections import OrderedDict
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time
from prepare_activation_patch import SECTOR, ROOT_BYTES, volume_identity, sha

CHUNK = 1024 * 1024
TARGET = '/dev/block/by-name/linux'


class Cow:
    def __init__(self, reader, size, directory):
        self.reader, self.size, self.directory = reader, size, directory
        self.original, self.changed = {}, {}

    def read(self, offset, length):
        if offset < 0 or length < 0 or offset + length > self.size:
            raise ValueError('NBD range outside root')
        out = bytearray()
        while length:
            block, start = divmod(offset, SECTOR)
            n = min(length, SECTOR - start)
            data = self.changed.get(block)
            if data is None:
                data = self.reader(block * SECTOR, SECTOR)
            if len(data) != SECTOR:
                raise ValueError('Short source sector')
            out.extend(data[start:start + n])
            length -= n
            offset += n
        return bytes(out)

    def write(self, offset, data):
        if offset < 0 or offset + len(data) > self.size:
            raise ValueError('NBD write outside root')
        while data:
            block, start = divmod(offset, SECTOR)
            n = min(len(data), SECTOR - start)
            if block not in self.original:
                self.original[block] = self.reader(block * SECTOR, SECTOR)
                if len(self.original[block]) != SECTOR:
                    raise ValueError('Short original sector')
            before = self.original[block]
            current = bytearray(self.changed.get(block, before))
            current[start:start + n] = data[:n]
            current = bytes(current)
            if current == before:
                self.changed.pop(block, None)
            else:
                self.changed[block] = current
            data = data[n:]
            offset += n

    def save(self):
        changes = self.directory / 'sectors'
        changes.mkdir(exist_ok=True)
        rows = []
        for block in sorted(self.changed):
            old, new = self.original[block], self.changed[block]
            (changes / f'{block}.original.bin').write_bytes(old)
            (changes / f'{block}.patched.bin').write_bytes(new)
            rows.append({'physical': block, 'original_sha256': sha(old), 'patched_sha256': sha(new)})
        return rows


def recv_exact(sock, n):
    result = bytearray()
    while len(result) < n:
        data = sock.recv(n - len(result))
        if not data:
            raise EOFError('NBD disconnected')
        result.extend(data)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='/dev/nbd3', choices=['/dev/nbd3'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disconnect', action='store_true')
    args = parser.parse_args()
    sysdir = Path('/sys/block') / Path(args.device).name
    if args.disconnect:
        info = json.loads((args.output / 'session.json').read_text())
        if int((sysdir / 'pid').read_text()) != info['kernel_pid']:
            raise SystemExit('NBD ownership changed')
        with open(args.device, 'r+b', buffering=0) as f:
            fcntl.ioctl(f, 0xAB08)  # NBD_DISCONNECT, our virtual device only
        return
    if args.output.exists() or (sysdir / 'pid').exists() or (sysdir / 'size').read_text().strip() != '0':
        raise SystemExit('Fresh output and unused nbd3 required')

    def remote(cmd):
        return subprocess.check_output(['adb', 'exec-out', cmd], timeout=90)

    if (remote('getprop ro.product.model').strip() != b'PJA110' or
            remote('getprop ro.bootmode').strip() != b'recovery' or
            remote('/sbin/busybox id -u').strip() != b'0' or
            remote('/sbin/busybox readlink -f ' + TARGET).strip() != b'/dev/block/sda17' or
            remote('/sbin/busybox blockdev --getsize64 ' + TARGET).strip() != b'77137424384'):
        raise SystemExit('Expected allocated PJA110 root in recovery')
    args.output.mkdir(parents=True)
    base = args.output / 'base'
    base.mkdir()
    memory = OrderedDict()

    def read_source(offset, size):
        result = bytearray()
        while size:
            number, inner = divmod(offset, CHUNK)
            path = base / f'{number}.bin'
            chunk = memory.get(number)
            if chunk is None:
                if path.exists():
                    chunk = path.read_bytes()
                else:
                    chunk = remote(f'/sbin/busybox dd if={TARGET} bs={CHUNK} skip={number} count=1 2>/dev/null')
                    if len(chunk) != CHUNK:
                        raise ValueError('Short recovery source read')
                    path.write_bytes(chunk)
                memory[number] = chunk
                if len(memory) > 32:
                    memory.popitem(last=False)
            memory.move_to_end(number)
            n = min(size, CHUNK - inner)
            result.extend(chunk[inner:inner + n])
            offset += n
            size -= n
        return bytes(result)

    identity = volume_identity(read_source(0, SECTOR))
    cow = Cow(read_source, ROOT_BYTES, args.output)
    client, server = socket.socketpair()
    dev = open(args.device, 'r+b', buffering=0)
    fcntl.ioctl(dev, 0xAB00, client.fileno())  # NBD_SET_SOCK
    fcntl.ioctl(dev, 0xAB01, SECTOR)
    fcntl.ioctl(dev, 0xAB07, ROOT_BYTES // SECTOR)
    fcntl.ioctl(dev, 0xAB09, 120)
    fcntl.ioctl(dev, 0xAB0A, 1 | 4 | 8)  # HAS_FLAGS, SEND_FLUSH, SEND_FUA

    def kernel():
        try:
            fcntl.ioctl(dev, 0xAB03)
        except OSError as exc:
            print("NBD kernel stop:", repr(exc), flush=True)

    thread = threading.Thread(target=kernel, daemon=True)
    thread.start()
    for _ in range(100):
        if (sysdir / 'pid').exists():
            break
        time.sleep(.02)
    session = {'device': args.device, 'kernel_pid': int((sysdir / 'pid').read_text()),
               'target': TARGET, 'source_bytes': ROOT_BYTES, 'volume_identity': identity,
               'phone_writes': False}
    (args.output / 'session.json').write_text(json.dumps(session, indent=2) + '\n')
    print('NBD ready. Phone READ ONLY; virtual writes stay in host COW.', flush=True)
    try:
        while True:
            magic, flags, handle, offset, length = struct.unpack('>II8sQI', recv_exact(server, 28))
            if magic != 0x25609513 or length > 16 * CHUNK:
                raise ValueError('Unsupported NBD request')
            kind = flags & 0xffff
            payload = recv_exact(server, length) if kind == 1 else b''
            if kind == 2:
                break
            error, reply = 0, b''
            try:
                if kind == 0:
                    reply = cow.read(offset, length)
                elif kind == 1:
                    cow.write(offset, payload)
                elif kind == 3:
                    cow.save()
                else:
                    error = errno.EOPNOTSUPP
            except Exception as exc:
                print('Virtual I/O error:', type(exc).__name__, str(exc), flush=True)
                error = errno.EIO
            server.sendall(struct.pack('>II8s', 0x67446698, error, handle) + (reply if not error else b''))
    except EOFError:
        pass
    finally:
        rows = cow.save()
        session.update(sector_bytes=SECTOR, sectors=rows, changed_bytes=len(rows) * SECTOR,
                       original_sha256=sha(b''.join(cow.original[b] for b in sorted(cow.changed))),
                       patched_sha256=sha(b''.join(cow.changed[b] for b in sorted(cow.changed))))
        (args.output / 'receipt.json').write_text(json.dumps(session, indent=2) + '\n')
        server.close()
        client.close()
        thread.join(5)
        fcntl.ioctl(dev, 0xAB04)
        dev.close()
        print('COW saved:', len(rows), 'sectors. Phone unchanged.', flush=True)


if __name__ == '__main__':
    main()
