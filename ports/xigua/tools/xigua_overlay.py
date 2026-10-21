#!/usr/bin/env python3
"""Generate a checked XIGUA patch on an XNU tree with all donor patches applied."""
import argparse
import difflib
from pathlib import Path


def overlay(source):
    originals = {}
    modified = {}

    def read(name):
        if name not in originals:
            path = source / name
            originals[name] = path.read_text() if path.exists() else ''
            modified[name] = originals[name]
        return modified[name]

    def replace(name, old, new, count=1):
        text = read(name)
        if text.count(old) != count:
            raise ValueError(f'{name}: expected {count} occurrences of {old!r}')
        modified[name] = text.replace(old, new)

    def create(name, text):
        if read(name):
            raise ValueError(f'{name}: already exists')
        modified[name] = text

    inc = 'makedefs/MakeInc.def'
    replace(inc, 'T8103 VMAPPLE SWEET\n', 'T8103 VMAPPLE SWEET XIGUA\n')
    line = next(x for x in read(inc).splitlines(True) if x.startswith('MACHINE_FLAGS_ARM64_SWEET ='))
    replace(inc, line, line + 'MACHINE_FLAGS_ARM64_XIGUA = -DARM64_BOARD_CONFIG_SWEET -DARM64_BOARD_CONFIG_XIGUA -march=armv8.2-a+crypto\n')
    replace(inc, 'ifneq ($(CURRENT_MACHINE_CONFIG),SWEET)',
            'ifeq ($(filter SWEET XIGUA,$(CURRENT_MACHINE_CONFIG)),)')
    for template in ['bsd/conf/Makefile.template', 'libkern/conf/Makefile.template']:
        replace(template, 'ifeq ($(CURRENT_MACHINE_CONFIG),SWEET)',
                'ifneq ($(filter SWEET XIGUA,$(CURRENT_MACHINE_CONFIG)),)')
    create('config/MASTER.arm64.xigua',
           '# XIGUA: SM8550 single-CPU RAM-root bring-up. Reuses donor generic ARM support.\n' +
           (source / 'config/MASTER.arm64.sweet').read_text())
    create('pexpert/pexpert/arm64/XIGUA.h', '''/* XIGUA (OnePlus Ace 2 Pro / SM8550): generic ARM support, no Apple SoC registers. */
#ifndef _PEXPERT_ARM64_XIGUA_H
#define _PEXPERT_ARM64_XIGUA_H
#include <pexpert/arm64/SWEET.h>
#define XIGUA 1
#undef SWEET_VTIMER_INTID
#define SWEET_VTIMER_INTID 27
#undef SWEET_SMP_MAX_CPUS
#define SWEET_SMP_MAX_CPUS 1
#endif
''')
    replace('pexpert/pexpert/arm64/Makefile', '\tSWEET.h\n', '\tSWEET.h \\\n+\tXIGUA.h\n'.replace('+\t', '\t'))
    replace('pexpert/pexpert/arm64/board_config.h', '#include <pexpert/arm64/SWEET.h>',
            '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n#include <pexpert/arm64/XIGUA.h>\n#else\n#include <pexpert/arm64/SWEET.h>\n#endif')

    # The donor's two pre-ADT drawing blocks must never access its framebuffer.
    for comment in ['\t/* Stage 0: white 64x32 band, no stack or page tables needed. */',
                    '\t/*\n\t * Splash framebuffer: one 32MB Normal-NC block']:
        replace('osfmk/arm64/start.s', '#if defined(SWEET)\n' + comment,
                '#if defined(SWEET) && !defined(ARM64_BOARD_CONFIG_XIGUA)\n' + comment)
    # Keep exported hooks for callers, but suppress all hardcoded early drawing.
    replace('osfmk/arm64/sweet_early.c', '#if defined(SWEET)\n', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
void sweet_early_mark(unsigned int s, const char *l) { (void)s; (void)l; }
void sweet_early_putc(char c) { (void)c; }
void sweet_early_panic(const char *f, va_list *a) { (void)f; (void)a; }
void sweet_early_relocate(uint64_t b) { (void)b; }
void sweet_early_disable(void) {}
#elif defined(SWEET)
''')
    # arm_vm_init also makes a fixed alias of the donor's framebuffer (0012).
    vm = 'osfmk/arm64/arm_vm_init.c'
    replace(vm, '#if defined(SWEET)\n',
            '#if defined(SWEET) && !defined(ARM64_BOARD_CONFIG_XIGUA)\n', count=3)

    # Independent of boot args: no UFS takeover, persistent disk log, or drivers
    # initialized by sweet_ufs_init can run until the SM8550 port is audited.
    replace('bsd/dev/sweet_ufs.c', 'sweet_ufs_init(void)\n{\n', '''sweet_ufs_init(void)
{
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    printf("XIGUA: UFS/input/USB/disk-log disabled; RAM-root only\\n");
    return ENXIO;
#endif
''')
    replace('iokit/Kernel/arm/SweetBattery.cpp',
            '\tfReal = real == 1 && sweet_spmi_init() == 0;', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    fReal = false; /* SM7150 PMIC addresses do not apply to SM8550. */
#else
\tfReal = real == 1 && sweet_spmi_init() == 0;
#endif''')
    table = 'iokit/KernelConfigTables.cpp'
    for old, new in [('xiaomi,sweet', 'oneplus,xigua'), ('qcom,kryo470', 'qcom,kryo')]:
        line = next(x for x in read(table).splitlines(True) if "'IONameMatch'" in x and old in x)
        replace(table, line, '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n' + line.replace(old, new) +
                '#else\n' + line + '#endif\n')

    patch = ''
    for name in sorted(modified):
        if originals[name] == modified[name]:
            continue
        patch += ''.join(difflib.unified_diff(
            originals[name].splitlines(True), modified[name].splitlines(True),
            fromfile='a/' + name if originals[name] else '/dev/null', tofile='b/' + name))
    return patch


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    patch = overlay(a.source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(patch)
    print(f'{a.output}: {len(patch)} bytes')


if __name__ == '__main__':
    main()
