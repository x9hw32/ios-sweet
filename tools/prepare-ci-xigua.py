#!/usr/bin/env python3
"""Adapt the pinned darwin-xnu-build script without tolerating skipped patches."""
from pathlib import Path
import sys


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected exactly one build-script anchor')
    path.write_text(text.replace(old, new))


def main():
    root = Path(sys.argv[1])
    for path in sorted((root / 'patches').glob('*-stage-*.sh')):
        replace_once(path, '[[ "${MACHINE_CONFIG:-}" == SWEET ]] || exit 0',
                     '[[ "${MACHINE_CONFIG:-}" == SWEET || "${MACHINE_CONFIG:-}" == XIGUA ]] || exit 0')
    build = root / 'build.sh'
    replace_once(build, 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"',
                 'ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"')
    text = build.read_text()
    start = text.index('        for PATCH in "${PATCH_DIR}"/*.patch; do')
    end = text.index('\n        done', start) + len('\n        done')
    text = text[:start] + '''        for PATCH in "${PATCH_DIR}"/*.patch; do
            if git apply --check "$PATCH"; then
                running "Applying patch: ${PATCH}"
                git apply "$PATCH" || exit 1
            elif [[ "$(basename "$PATCH")" =~ ^[0-9]{4}- ]]; then
                error "Required port patch did not apply: ${PATCH}"
                exit 1
            else
                warning "Toolchain compatibility patch already upstream or superseded: ${PATCH}"
            fi
        done''' + text[end:]
    build.write_text(text)


if __name__ == '__main__':
    main()
