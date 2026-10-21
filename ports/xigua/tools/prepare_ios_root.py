#!/usr/bin/env python3
"""Extract the pinned Apple iPhone X restore and build a local HFS+ iOS root.

Only host files are modified. No device connection or partition write is used.
The archive is supplied separately so interrupted downloads remain resumable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import time
import zipfile
from paths import ROOT, DONOR

COMPONENTS = {'OS': '087-86698-044.dmg', 'Cryptex1,SystemOS': '087-86593-047.dmg',
              'Cryptex1,AppOS': '087-86715-047.dmg'}


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipsw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait-download', action='store_true')
    args = parser.parse_args()
    archive = args.ipsw.resolve()
    if args.wait_download:
        control = archive.with_name(archive.name + '.aria2')
        while control.exists():
            time.sleep(10)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        manifest = plistlib.loads(z.read('BuildManifest.plist'))
        if (manifest['ProductBuildVersion'] != '20H392' or
                'iPhone10,3' not in manifest['SupportedProductTypes']):
            raise SystemExit('Expected iPhone X 20H392 restore archive')
        identity = next(x for x in manifest['BuildIdentities'] if x['Info']['DeviceClass'] == 'd22ap')
        for component, expected in COMPONENTS.items():
            actual = identity['Manifest'][component]['Info']['Path']
            if actual != expected:
                raise SystemExit(f'{component}: unexpected image {actual}')
            print('Extracting and checking ZIP CRC:', actual, flush=True)
            z.extract(actual, output)
        (output / 'BuildManifest.plist').write_bytes(z.read('BuildManifest.plist'))
    tools = ROOT / 'build/host-tools'
    environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
    root = output / 'ios-root-12g.img'
    subprocess.run(['bash', str(DONOR / 'tools/mkiosroot.sh'),
                    *[str(output / x) for x in COMPONENTS.values()], str(root), '12G'],
                   env=environment, check=True)
    mount = output / 'mounted-root'
    mount.mkdir()
    subprocess.run(['sudo', '-n', 'mount', '-t', 'hfsplus', '-o', 'loop,force', str(root), str(mount)], check=True)
    try:
        subprocess.run(['sudo', '-n', 'python3', str(DONOR / 'tools/sweet-root-tweaks.py'), str(mount)], check=True)
        for name in ['sbin/launchd', 'usr/lib/dyld',
                     'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64']:
            path = mount / name
            if not path.is_file() or not path.stat().st_size:
                raise SystemExit(f'Missing essential userland file: {name}')
        subprocess.run(['df', '-h', str(mount)], check=True)
    finally:
        subprocess.run(['sudo', '-n', 'umount', str(mount)], check=True)
    fsck = shutil.which('fsck.hfsplus', path=environment['PATH'])
    if not fsck:
        raise SystemExit('fsck.hfsplus missing from host tool path')
    subprocess.run([fsck, '-f', '-n', str(root)], check=True)
    receipt = {'build': '20H392', 'product': 'iPhone10,3', 'ipsw_sha256': sha(archive),
               'root_sha256': sha(root), 'root_bytes': root.stat().st_size,
               'components': {k: {'file': v, 'sha256': sha(output / v)} for k, v in COMPONENTS.items()},
               'hardware_boot_verified': False}
    (output / 'root.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Local iOS root prepared:', root, flush=True)


if __name__ == '__main__':
    main()
