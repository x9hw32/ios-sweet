#!/usr/bin/env python3
"""Build an embedded-payload native XIGUA shim and Android boot image v4."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from mkadt_xigua import make

from paths import ROOT, DONOR
sys.path.insert(0, str(DONOR / 'tools'))
import mkpayload


def run(argv, **kwargs):
    subprocess.run([str(x) for x in argv], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--kernel', type=Path)
    p.add_argument('--ramdisk', type=Path)
    p.add_argument('--stock-boot', type=Path)
    p.add_argument('--experimental-abl-framebuffer', action='store_true',
                   help='Allow a Mu GOP framebuffer to be tested under ABL; scanout is unverified')
    a = p.parse_args()
    if a.ramdisk and not a.kernel:
        p.error('--ramdisk requires --kernel')
    profile = json.loads(a.profile.read_text())
    fb = profile['framebuffer']
    if profile['kind'] != 'qemu' and not fb.get('abl_scanout_verified') and not a.experimental_abl_framebuffer:
        p.error('ABL scanout not verified; use --experimental-abl-framebuffer for a diagnostic experiment')
    if not (0 < fb['width'] <= fb['stride'] // 4 <= 8192 and fb['stride'] % 4 == 0 and
            0 < fb['height'] <= 8192 and fb['stride'] * fb['height'] <= fb['size']):
        p.error('Invalid framebuffer geometry')
    ram, size = profile['ram_base'], profile['ram_size']
    if ram < fb['base'] + fb['size'] and fb['base'] < ram + size:
        p.error('Framebuffer overlaps kernel RAM')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tree = out / 'xigua.adt'
    tree.write_bytes(make(profile))
    info = {'kind': 'diagnostic', 'profile': profile}
    payload = out / 'payload.bin'
    if a.kernel:
        command = ('debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress '
                   'rd=md0 sweetusb=0 sweettouch=0 sweetkeys=0 sweetlog=0 sweetbattery=0 '
                   'ufsrw=0 wdt=-1 wdt_test=no_user_checkin')
        blob, kernel_info = mkpayload.build(str(a.kernel), str(tree), command,
                                            str(a.ramdisk) if a.ramdisk else None)
        if kernel_info['cpusub'] != 0:
            p.error('Only plain arm64 kernels are supported')
        payload.write_bytes(blob)
        info.update(kind='xnu-ram-root', kernel=kernel_info,
                    kernel_sha256=hashlib.sha256(a.kernel.read_bytes()).hexdigest())
    else:
        payload.write_bytes(b'')
    constants = {'FB_BASE': fb['base'], 'FB_SIZE': fb['size'], 'FB_WIDTH': fb['width'],
                 'FB_HEIGHT': fb['height'], 'FB_STRIDE': fb['stride'],
                 'RAM_BASE': ram, 'RAM_SIZE': size, 'BOOT_MPIDR': profile['boot_mpidr'],
                 'TIMEBASE': profile['timebase']}
    (out / 'board.h').write_text(''.join(f'#define {k} {v:#x}ULL\n' for k, v in constants.items()))
    cc = 'aarch64-linux-gnu-gcc'
    flags = ['-Os', '-ffreestanding', '-nostdlib', '-fno-pic', '-fno-stack-protector',
             '-fno-asynchronous-unwind-tables', '-mgeneral-regs-only', '-mstrict-align',
             '-Wall', '-Wextra', '-Werror', '-I' + str(out),
             '-I' + str(DONOR / 'shim')]
    objects = []
    for name in ['start.S', 'main.c', 'payload.c']:
        obj = out / (Path(name).stem + '.o')
        run([cc, *flags, '-c', ROOT / 'shim' / name, '-o', obj], cwd=out)
        objects.append(obj)
    for obj in objects[1:]:
        relocations = subprocess.check_output(['aarch64-linux-gnu-readelf', '-r', str(obj)], text=True)
        if 'ABS64' in relocations:
            raise SystemExit(f'{obj}: absolute address relocation in position-independent shim')
    elf = out / 'shim.elf'
    run([cc, *flags, '-static', '-T', ROOT / 'shim/shim.ld', '-Wl,--build-id=none',
         '-Wl,--no-warn-rwx-segments', '-Wl,-N', *objects, '-o', elf])
    image = out / 'Image'
    run(['aarch64-linux-gnu-objcopy', '-O', 'binary', elf, image])
    symbols = subprocess.check_output(['aarch64-linux-gnu-nm', str(elf)], text=True)
    end = next(int(line.split()[0], 16) for line in symbols.splitlines() if line.split()[-1] == '_end')
    with image.open('r+b') as f:
        f.truncate(end)
    # Match the five-byte ramdisk of the user's working Mu v4 image.
    # The XNU/root payload is embedded in Image and never read from this field.
    empty = out / 'dummy-ramdisk'
    empty.write_bytes(b'dummy')
    boot = out / 'boot.img'
    run(['mkbootimg', '--header_version', '4', '--kernel', image, '--ramdisk', empty,
         '--cmdline', 'console=null', '-o', boot])
    if a.stock_boot:
        with a.stock_boot.open('rb') as f:
            stock = f.read(4096)
        if stock[:8] != b'ANDROID!' or struct.unpack_from('<I', stock, 40)[0] != 4:
            p.error('Expected stock Android boot image v4')
        with boot.open('r+b') as f:
            f.seek(16)
            f.write(stock[16:20])
    with boot.open('rb') as f:
        header = f.read(4096)
        actual_image = f.read(image.stat().st_size)
    if (header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4 or
            struct.unpack_from('<I', header, 8)[0] != image.stat().st_size or
            struct.unpack_from('<I', header, 12)[0] != 5 or
            actual_image != image.read_bytes() or boot.stat().st_size > 201326592):
        raise SystemExit('Boot image v4 verification failed')
    info.update(image_bytes=image.stat().st_size, boot_bytes=boot.stat().st_size,
                boot_sha256=hashlib.sha256(boot.read_bytes()).hexdigest(),
                hardware_boot_verified=False)
    (out / 'build.json').write_text(json.dumps(info, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(info['boot_sha256'] + '  boot.img\n')
    print(f'{boot}: {boot.stat().st_size} bytes; hardware boot unverified')


if __name__ == '__main__':
    main()
