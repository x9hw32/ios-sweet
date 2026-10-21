#!/usr/bin/env python3
"""Package a read-only UEFI stager plus an existing native Image into a FAT image."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zlib
from paths import ROOT


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', type=Path, required=True, help='Directory produced by build_boot.py')
    p.add_argument('--esp-template', type=Path, required=True)
    p.add_argument('--root-image', type=Path)
    p.add_argument('--root-base', type=lambda x: int(x, 0))
    p.add_argument('--root-partition', choices=['linux', 'installer'], default='linux')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    info = json.loads((a.native / 'build.json').read_text())
    profile = info['profile']
    native = (a.native / 'Image').read_bytes()
    if len(native) != info['image_bytes'] or len(native) > 192 * 1024 * 1024:
        p.error('Native Image size differs from its build receipt')
    root_bytes = a.root_image.stat().st_size if a.root_image else 0
    root_base = a.root_base or 0
    ram, size = profile['ram_base'], profile['ram_size']
    if ram % 4096 or size % 4096:
        p.error('EFI reservation must be 4 KiB aligned')
    if root_bytes and (not root_base or root_base % 16384 or root_bytes % 16384 or
                       root_base < ram or root_base - ram + root_bytes > size - 1024 * 1024):
        p.error('External root must fit inside reserved RAM and be 16 KiB aligned')
    if root_bytes and info.get('external_ramdisk') != {'base': root_base, 'size': root_bytes}:
        p.error('Native receipt must describe this exact external RAM disk')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    chunk = 4 * 1024 * 1024
    crcs = []
    if a.root_image:
        with a.root_image.open('rb') as f:
            while data := f.read(chunk):
                crcs.append(zlib.crc32(data))
    sizes = {'linux': 77137424384, 'installer': 6899630080}
    if root_bytes > sizes[a.root_partition]:
        p.error('Root image exceeds the allocated partition')
    constants = {'IMAGE_BYTES': len(native), 'IMAGE_CRC': zlib.crc32(native),
                 'RAM_BASE': ram, 'RAM_BYTES': size, 'ROOT_BASE': root_base,
                 'ROOT_BYTES': root_bytes, 'ROOT_BLOCK_SIZE': 4096, 'ROOT_CHUNK': chunk,
                 'ROOT_PARTITION_BYTES': sizes[a.root_partition]}
    header = ''.join(f'#define {k} {v:#x}ULL\n' for k, v in constants.items())
    header += f'#define ROOT_NAME L"{a.root_partition}"\n'
    header += 'static const UINT32 root_crc[] = {' + ','.join(hex(x) for x in crcs or [0]) + '};\n'
    (out / 'loader-config.h').write_text(header)
    headers = ROOT / '.cache/edk2/MdePkg/Include'
    flags = ['clang', '--target=aarch64-pc-windows-msvc', '-ffreestanding', '-fshort-wchar',
             '-fno-stack-protector', '-fno-builtin', '-O2', '-Wall', '-Wextra', '-Werror',
             '-Wno-microsoft-enum-value', '-mgeneral-regs-only',
             '-I' + str(headers / 'AArch64'), '-I' + str(headers), '-I' + str(out)]
    for name in ['loader.c', 'enter.S']:
        run(*flags, '-c', ROOT / 'efi' / name, '-o', out / (Path(name).stem + '.obj'))
    binary = out / 'BOOTAA64.EFI'
    run('lld-link', '/subsystem:efi_application', '/entry:efi_main', '/nodefaultlib',
        '/machine:arm64', '/out:' + str(binary), out / 'loader.obj', out / 'enter.obj')
    esp = out / 'esp.img'
    shutil.copyfile(a.esp_template, esp)
    run('mmd', '-i', esp, '::/EFI/XIGUA')
    run('mcopy', '-o', '-i', esp, binary, '::/EFI/BOOT/BOOTAA64.EFI')
    run('mcopy', '-o', '-i', esp, a.native / 'Image', '::/EFI/XIGUA/Image')
    for source, target in [(binary, '::/EFI/BOOT/BOOTAA64.EFI'), (a.native / 'Image', '::/EFI/XIGUA/Image')]:
        actual = subprocess.check_output(['mtype', '-i', str(esp), target])
        if source.read_bytes() != actual:
            raise SystemExit('ESP file readback mismatch')
    receipt = {'profile': profile, 'native_image_sha256': hashlib.sha256(native).hexdigest(),
               'esp_sha256': hashlib.file_digest(esp.open('rb'), 'sha256').hexdigest(),
               'esp_bytes': esp.stat().st_size, 'external_ramdisk': info.get('external_ramdisk'),
               'root_partition': a.root_partition if root_bytes else None,
               'hardware_boot_verified': False}
    (out / 'build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{esp}: {esp.stat().st_size} bytes; EFI transition requires validation')


if __name__ == '__main__':
    main()
