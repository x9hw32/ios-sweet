#!/usr/bin/env python3
"""Build the XIGUA PID 1 used before loading Apple userland."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
from paths import ROOT, DONOR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/xigua-init')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    obj = args.output / 'init.o'
    subprocess.run(['clang', '-target', 'arm64-apple-ios16.0', '-c',
                    str(ROOT / 'tools/xigua-init.S'), '-o', str(obj)], check=True)
    spec = importlib.util.spec_from_file_location('mkinit', DONOR / 'tools/mkinit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.IDENT = b'org.xigua.init\0'
    binary = module.build(obj.read_bytes())
    (args.output / 'init').write_bytes(binary)
    print(f'{args.output / "init"}: {len(binary)} bytes')


if __name__ == '__main__':
    main()
