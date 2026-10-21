#!/usr/bin/env python3
"""Boot the native Linux Image entry in QEMU and save/decode its framebuffer."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from paths import ROOT, DONOR
spec = importlib.util.spec_from_file_location('qemu_sweet', DONOR / 'tools/qemu-sweet.py')
qemu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qemu)


def shim_text(raw):
    header = (DONOR / 'shim/font.h').read_text()
    font = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', header))
    if len(font) != 95 * 16:
        raise ValueError('Unexpected shim font format')
    patterns = {font[i:i+16]: chr(32 + i // 16) for i in range(0, len(font), 16)}
    lines = []
    for row in range(qemu.FB_H // 32):
        chars = []
        for col in range(qemu.FB_W // 16):
            glyph = bytearray(16)
            for y in range(16):
                for x in range(8):
                    off = (row * 32 + y * 2) * qemu.FB_STRIDE + (col * 16 + x * 2) * 4
                    if raw[off:off+4] == b'\xff' * 4:
                        glyph[y] |= 0x80 >> x
            chars.append(patterns.get(bytes(glyph), '?'))
        lines.append(''.join(chars).rstrip())
    return '\n'.join(lines).strip() + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--secs', type=int, default=5)
    p.add_argument('--kernel', type=Path)
    p.add_argument('--payload', type=Path)
    p.add_argument('--efi-esp', type=Path, help='Boot this FAT image through EDK2 instead of -kernel')
    p.add_argument('--root-disk', type=Path, help='Additional GPT disk with 4 KiB logical sectors')
    p.add_argument('--memory', default='4G', help='QEMU guest RAM (default 4G)')
    p.add_argument('--memory-file', type=Path, help='Existing file backing guest RAM, with external root preloaded')
    p.add_argument('--ios-userland', action='store_true', help='Capture real iOS boot for manual inspection; do not require the static-init marker')
    a = p.parse_args()
    if a.kernel and not a.payload:
        p.error('--kernel requires --payload for font lookup')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mon = out / 'qmp.sock'
    cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a76',
           '-smp', '1', '-m', a.memory, '-display', 'none', '-monitor', 'none',
           '-serial', 'file:' + str(out / 'serial.txt'),
           '-qmp', 'unix:' + str(mon) + ',server,nowait', '-no-reboot',
           '-d', 'guest_errors', '-D', str(out / 'qemu.log')]
    if a.efi_esp:
        cmd += ['-bios', '/usr/share/edk2-ovmf/aarch64/QEMU_EFI.fd',
                '-drive', f'if=none,id=esp,format=raw,file={a.efi_esp.resolve()},snapshot=on',
                '-device', 'virtio-blk-pci,drive=esp']
    else:
        cmd += ['-kernel', str(a.image.resolve())]
    if a.root_disk:
        cmd += ['-drive', f'if=none,id=root,format=raw,file={a.root_disk.resolve()},snapshot=on',
                '-device', 'virtio-blk-pci,drive=root,logical_block_size=4096,physical_block_size=4096']
    if a.memory_file:
        cmd[2] += ',memory-backend=guestmem'
        cmd += ['-object', f'memory-backend-file,id=guestmem,size={a.memory},mem-path={a.memory_file.resolve()},share=on,prealloc=off']
    with (out / 'stderr.txt').open('wb') as error:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=error)
        try:
            start = time.monotonic()
            while process.poll() is None and time.monotonic() - start < a.secs:
                time.sleep(0.2)
            if process.poll() is not None:
                raise RuntimeError('QEMU exited before framebuffer snapshot; inspect stderr.txt')
            _, regs = qemu.qmp(str(mon), 'stop', 'info registers',
                               pmemsave=(qemu.FB_BASE, qemu.FB_STRIDE * qemu.FB_H, str(out / 'fb.raw')))
            (out / 'regs.txt').write_text(regs)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    raw = (out / 'fb.raw').read_bytes()
    qemu.write_png(str(out / 'fb.png'), raw)
    if a.kernel:
        payload = a.payload.read_bytes()
        symbols = subprocess.check_output(['llvm-nm', '--defined-only', str(a.kernel)], text=True)
        address = next(int(line.split()[0], 16) for line in symbols.splitlines()
                       if line.split()[-1] == '_iso_font')
        font = qemu.payload_data(payload, address, 4096)
        text, unknown = qemu.decode_screen(raw, font)
        result = qemu.screen_result(text, unknown)
        result['pid1_observed'] = 'init running as PID 1' in text
        if a.ios_userland:
            result['expected_userland'] = 'ios'
            result['gui_requires_visual_inspection'] = True
    else:
        text = shim_text(raw)
        result = {'native_diagnostic_observed': 'XIGUA native shim' in text,
                  'empty_payload_rejected': 'ffffffffffffffff' in text}
    (out / 'fb.txt').write_text(text)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(text[:1400])
    print(json.dumps(result))
    if a.kernel:
        if a.ios_userland:
            return 1 if result['status'] == 'panic' else 0
        return 0 if result['pid1_observed'] and result['status'] != 'panic' else 1
    return 0 if result['native_diagnostic_observed'] and result['empty_payload_rejected'] else 1


if __name__ == '__main__':
    sys.exit(main())
