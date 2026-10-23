#!/usr/bin/env python3
"""Reuse checked XNU 8796 IIG sources without changing the kernel's RPC ABI.

The interface generator from newer Xcodes targets a newer IORPC layout.
Only generated headers/implementations are reused; every object is rebuilt.
All DriverKit source inputs must match the previously successful build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(archive, output):
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:gz') as tar:
        files = {m.name: m for m in tar.getmembers() if m.isfile()}
        def read(name):
            return tar.extractfile(files[name]).read()
        inputs = {Path(name).name: digest(read(name)) for name in files
                  if name.startswith('xnu/iokit/DriverKit/') and
                  '/' not in name[len('xnu/iokit/DriverKit/'):] and
                  Path(name).suffix in ['.h', '.iig']}
        generated = {}
        for name in sorted(files):
            if not name.startswith('build/xnu.obj/') or not name.endswith('.iig.cpp'):
                continue
            cpp = Path(name)
            stem = cpp.name.removesuffix('.iig.cpp')
            header_name = str(cpp.with_name(stem + '.h'))
            if header_name not in files or stem + '.iig' not in inputs:
                continue
            pair = {stem + '.h': read(header_name), stem + '.iig.cpp': read(name)}
            for filename, data in pair.items():
                if filename in generated and generated[filename] != digest(data):
                    raise ValueError('Conflicting generated IIG variants: ' + filename)
                generated[filename] = digest(data)
                (output / filename).write_bytes(data)
        definitions = {name.removesuffix('.iig') for name in inputs if name.endswith('.iig')}
        if not definitions or any(stem + '.iig.cpp' not in generated or stem + '.h' not in generated
                                  for stem in definitions):
            raise ValueError('Previous build is missing generated IIG interfaces')
    (output / 'manifest.json').write_text(json.dumps({'version': 1, 'inputs': inputs,
                                                    'generated': generated}, indent=2) + '\n')
    print(f'Prepared {len(definitions)} checked legacy IIG interfaces')


def generate(cache, definition, header, implementation):
    manifest = json.loads((cache / 'manifest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unknown IIG cache format')
    source_dir = definition.resolve().parent
    for name, expected in manifest['inputs'].items():
        if digest((source_dir / name).read_bytes()) != expected:
            raise ValueError('IIG source changed; regenerate with a compatible generator: ' + name)
    stem = definition.stem
    if header.name != stem + '.h' or implementation.name != stem + '.iig.cpp':
        raise ValueError('Unexpected IIG output paths')
    for destination in [header, implementation]:
        data = (cache / destination.name).read_bytes()
        if digest(data) != manifest['generated'][destination.name]:
            raise ValueError('Generated IIG cache checksum mismatch')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'prepare':
        p = argparse.ArgumentParser()
        p.add_argument('mode'); p.add_argument('archive', type=Path); p.add_argument('output', type=Path)
        a = p.parse_args()
        prepare(a.archive, a.output)
    else:
        p = argparse.ArgumentParser()
        p.add_argument('--def', dest='definition', type=Path, required=True)
        p.add_argument('--header', type=Path, required=True)
        p.add_argument('--impl', type=Path, required=True)
        a, _ = p.parse_known_args()
        generate(Path(os.environ['IIG_LEGACY_CACHE']), a.definition, a.header, a.impl)


if __name__ == '__main__':
    main()
