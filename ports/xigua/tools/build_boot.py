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
    p.add_argument('--external-ramdisk-base', type=lambda x: int(x, 0))
    p.add_argument('--external-ramdisk-size', type=lambda x: int(x, 0))
    p.add_argument('--ios-userland', action='store_true', help='Enable the iOS display service and launchd boot arguments')
    p.add_argument('--touch', action='store_true', help='Enable experimental XIGUA Synaptics SPI touch input')
    storage = p.add_mutually_exclusive_group()
    storage.add_argument('--ufs-probe', action='store_true', help='Read-only UFS CRC probe before a small RAM-root init')
    storage.add_argument('--ufs-root', action='store_true', help='Use the allocated linux UFS partition as the iOS root')
    p.add_argument('--ufs-crc-cache', type=Path, help='Verified CRC table for the prepared 12 GiB root')
    p.add_argument('--cpus', type=int, choices=range(1, 9), default=1,
                   help='Number of verified CPU nodes to enable (default 1)')
    p.add_argument('--fb-hz', type=int, choices=range(1, 61), default=30,
                   help='Maximum framebuffer presentation rate for iOS (default 30)')
    p.add_argument('--display-mode', choices=['iphone-x', 'native', 'fit'], default='iphone-x')
    p.add_argument('--stock-boot', type=Path)
    p.add_argument('--experimental-abl-framebuffer', action='store_true',
                   help='Allow a Mu GOP framebuffer to be tested under ABL; scanout is unverified')
    a = p.parse_args()
    if a.ramdisk and not a.kernel:
        p.error('--ramdisk requires --kernel')
    if (a.ufs_probe or a.ufs_root) and (not a.kernel or a.external_ramdisk_base or a.external_ramdisk_size):
        p.error('UFS modes require a kernel and no external RAM root')
    if a.ufs_probe and (not a.ramdisk or not a.ufs_crc_cache or a.ios_userland):
        p.error('UFS probe requires a small diagnostic RAM disk and CRC cache, without iOS userland')
    if a.ufs_root and (a.ramdisk or not a.ios_userland):
        p.error('UFS root requires iOS userland without a RAM disk')
    if a.touch and (not a.ios_userland or a.display_mode != 'fit'):
        p.error('--touch requires iOS userland and full-panel fit mode')
    external = a.external_ramdisk_base is not None or a.external_ramdisk_size is not None
    if external and (not a.kernel or a.ramdisk or not a.external_ramdisk_base or not a.external_ramdisk_size):
        p.error('External RAM disk requires a kernel and both base/size, without --ramdisk')
    profile = json.loads(a.profile.read_text())
    profile['cpu_count'] = a.cpus
    profile['display_mode'] = a.display_mode
    if a.ufs_probe or a.ufs_root:
        if profile['kind'] != 'phone':
            p.error('UFS firmware handoff is specific to the verified PJA110 phone')
        indices, crcs = [0, 1536, 3071], []
        if a.ufs_crc_cache:
            cache = json.loads(a.ufs_crc_cache.read_text())
            if (cache['root_bytes'] != 0x300000000 or cache['chunk_bytes'] != 0x400000 or
                    cache['root_sha256'] != '7ed76a14da8d9bf21ceb2d3f62c2524492e0ec30a3405128ca0c7879322fd7df' or
                    len(cache['crcs']) != 3072 or any(type(c) is not int or not 0 <= c <= 0xffffffff for c in cache['crcs'])):
                p.error('UFS probe cache must identify the verified root already installed in linux')
            crcs = [cache['crcs'][i] for i in indices]
        profile['ufs'] = {'reg': [0x1d84000, 0x3000], 'dma_region': [0xc4000000, 0x200000],
                          'mode': 1 if a.ufs_probe else 2,
                          'probe_offsets': [i * 0x400000 for i in indices] if crcs else [], 'probe_crcs': crcs}
    if a.ios_userland:
        profile['gui'] = True
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
        root_device = 'ufsroot0' if a.ufs_root else 'md0'
        command = (f'debug=0xc serial=3 cpus={a.cpus} keepsyms=1 -enable_kprintf_spam -noprogress '
                   f'rd={root_device} sweetusb=0 sweettouch=0 sweetkeys=0 sweetlog={int(a.ufs_root)} sweetbattery=0 '
                   f'ufsrw={int(a.ufs_root)} wdt=-1 wdt_test=no_user_checkin')
        if a.ufs_probe or a.ufs_root:
            command += f' xiguaufs={1 if a.ufs_probe else 2} ufsroot=linux ufscache=0 ufswait=1 ufslogsecs=5'
        if a.touch:
            if profile['kind'] != 'phone':
                p.error('XIGUA touch requires the verified phone profile')
            command += ' xiguatouch=1'
        if a.ios_userland:
            command += ' unentitled_ios_sim_launch=1 ignition_level=1 rootrw=1 launchd_unsecure_cache=1 sweetfb_noconsole=1'
            command += f' sweetfb_hz={a.fb_hz}'
            if a.display_mode == 'native':
                command += ' sweetfb_native=1'
            elif a.display_mode == 'fit':
                command += ' sweetfb_fit=1'
        blob, kernel_info = mkpayload.build(str(a.kernel), str(tree), command,
                                            str(a.ramdisk) if a.ramdisk else None)
        if kernel_info['cpusub'] != 0:
            p.error('Only plain arm64 kernels are supported')
        if external:
            base, length = a.external_ramdisk_base, a.external_ramdisk_size
            virt_base = int(kernel_info['virt_base'], 16)
            kernel_end = int(kernel_info['kernel_end'], 16) - virt_base + ram
            if (base % 0x4000 or length % 0x4000 or base < kernel_end or
                    base < ram or base - ram + length > size - 768 * 1024 * 1024):
                p.error('External root must follow the kernel inside RAM, leaving at least 768 MiB free')
            adt_offset, adt_size = struct.unpack_from('<2Q', blob, 0x20)
            updated = mkpayload.add_ramdisk_to_adt(blob[adt_offset:adt_offset + adt_size], base, length)
            mutable = bytearray(blob[:adt_offset])
            mutable += updated
            mutable += b'\0' * (-len(mutable) & 15)
            struct.pack_into('<Q', mutable, 0x28, len(updated))
            struct.pack_into('<Q', mutable, 0x30, virt_base + base - ram + length)
            blob = bytes(mutable)
            info['external_ramdisk'] = {'base': base, 'size': length}
            kernel_info['kernel_end'] = hex(virt_base + base - ram + length)
            kernel_info['ramdisk'] = [hex(base), hex(length)]
        payload.write_bytes(blob)
        info.update(kind='xnu-ufs-root' if a.ufs_root else 'xnu-ram-root', kernel=kernel_info,
                    kernel_sha256=hashlib.sha256(a.kernel.read_bytes()).hexdigest())
    else:
        payload.write_bytes(b'')
    constants = {'FB_BASE': fb['base'], 'FB_SIZE': fb['size'], 'FB_WIDTH': fb['width'],
                 'FB_HEIGHT': fb['height'], 'FB_STRIDE': fb['stride'],
                 'RAM_BASE': ram, 'RAM_SIZE': size, 'BOOT_MPIDR': profile['boot_mpidr'],
                 'TIMEBASE': profile['timebase'], 'DIAGNOSTIC': 0 if a.kernel else 1,
                 'REBOOT_SECONDS': 20 if a.kernel else 45}
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
