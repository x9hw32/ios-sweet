#!/usr/bin/env python3
"""Build an ARM64 UEFI hardware probe with pinned EDK2 type definitions."""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
EDK2_SHA = 'f2b519f83762a492b5a13f5477b9d76edfec5130'


def main():
    headers = ROOT / '.cache/edk2'
    if not headers.exists():
        subprocess.run(['git', 'clone', '--no-checkout', '--filter=blob:none',
                        'https://github.com/tianocore/edk2.git', str(headers)], check=True)
        subprocess.run(['git', '-C', str(headers), 'sparse-checkout', 'set', 'MdePkg/Include'], check=True)
        subprocess.run(['git', '-C', str(headers), 'checkout', EDK2_SHA], check=True)
    sha = subprocess.check_output(['git', '-C', str(headers), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != EDK2_SHA:
        raise SystemExit('EDK2 headers do not match pinned revision')
    out = ROOT / 'out/efi'
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['clang', '--target=aarch64-pc-windows-msvc', '-ffreestanding',
                    '-fshort-wchar', '-fno-stack-protector', '-fno-builtin', '-O2',
                    '-Wall', '-Wextra', '-Werror', '-Wno-microsoft-enum-value',
                    '-I' + str(headers / 'MdePkg/Include/AArch64'),
                    '-I' + str(headers / 'MdePkg/Include'),
                    '-c', str(ROOT / 'efi/probe.c'), '-o', str(out / 'probe.obj')], check=True)
    subprocess.run(['lld-link', '/subsystem:efi_application', '/entry:efi_main',
                    '/nodefaultlib', '/machine:arm64', '/out:' + str(out / 'probe.efi'),
                    str(out / 'probe.obj')], check=True)
    image = out / 'probe.efi'
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    (out / 'SHA256SUMS').write_text(f'{digest}  probe.efi\n')
    print(f'{image}: {image.stat().st_size} bytes, SHA256 {digest}')


if __name__ == '__main__':
    main()
