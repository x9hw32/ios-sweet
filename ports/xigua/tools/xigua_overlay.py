#!/usr/bin/env python3
"""Generate a checked XIGUA patch on an XNU tree with all donor patches applied."""
import argparse
import difflib
from pathlib import Path
import re


def overlay(source):
    originals = {}
    modified = {}

    def read(name):
        if name not in originals:
            path = source / name
            originals[name] = path.read_text(errors='surrogateescape') if path.exists() else ''
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
           '# XIGUA: SM8550 PSCI SMP RAM-root. Reuses donor generic ARM support.\n' +
           (source / 'config/MASTER.arm64.sweet').read_text())
    create('pexpert/pexpert/arm64/XIGUA.h', '''/* XIGUA (OnePlus Ace 2 Pro / SM8550): generic ARM support, no Apple SoC registers. */
#ifndef _PEXPERT_ARM64_XIGUA_H
#define _PEXPERT_ARM64_XIGUA_H
#include <pexpert/arm64/SWEET.h>
#define XIGUA 1
#undef SWEET_VTIMER_INTID
#define SWEET_VTIMER_INTID 27
#undef SWEET_SMP_MAX_CPUS
#define SWEET_SMP_MAX_CPUS 8
#endif
''')
    replace('pexpert/pexpert/arm64/Makefile', '\tSWEET.h\n',
            '\tSWEET.h \\\n\tXIGUA.h \\\n\tboard_name.h\n')
    create('pexpert/pexpert/arm64/board_name.h', '''/* Runtime diagnostics use the selected board's name. */
#ifndef _PEXPERT_ARM64_BOARD_NAME_H
#define _PEXPERT_ARM64_BOARD_NAME_H
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#define ARM_BOARD_NAME "XIGUA"
#else
#define ARM_BOARD_NAME "SWEET"
#endif
#endif
''')
    replace('pexpert/pexpert/arm64/board_config.h', '#include <pexpert/arm64/SWEET.h>',
            '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n#include <pexpert/arm64/XIGUA.h>\n#else\n#include <pexpert/arm64/SWEET.h>\n#endif')

    # GICv4 redistributors with VLPI frames occupy 256 KiB, not 128 KiB.
    # Match each secondary by its MPIDR without probing the intervening frame.
    gic = 'pexpert/arm/pe_fiq.c'
    replace(gic, 'for (vm_offset_t offset = 0; offset < gicr_size; offset += GICR_PE_SIZE) {',
            'for (vm_offset_t offset = 0; offset + GICR_TYPER + 8 <= gicr_size;) {')
    replace(gic, '''\t\tif (gicr_typer & GICR_TYPER_LAST) {
\t\t\tbreak;
\t\t}
''', '''\t\tif (gicr_typer & GICR_TYPER_LAST) {
\t\t\tbreak;
\t\t}
#if defined(ARM64_BOARD_CONFIG_XIGUA)
\t\toffset += (gicr_typer & 2ULL) ? 0x40000 : GICR_PE_SIZE;
#else
\t\toffset += GICR_PE_SIZE;
#endif
''')
    replace('iokit/Kernel/arm/SweetCPU.cpp',
            '\tcpuName = OSSymbol::withCStringNoCopy("Kryo 470");',
            '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tcpuName = OSSymbol::withCStringNoCopy("Snapdragon 8 Gen 2");
#else
\tcpuName = OSSymbol::withCStringNoCopy("Kryo 470");
#endif''')

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

    # The larger XIGUA panel can center the iPhone X canvas without cropping.
    # Keep iOS's known 1125x2436 layout rather than an unknown 1240x2772 class.
    replace('iokit/Kernel/arm/SweetFramebuffer.cpp',
            '\tif (!native && fWidth <= SWEET_FB_LOGICAL_W && fHeight <= SWEET_FB_LOGICAL_H) {',
            '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tif (!native) {
#else
\tif (!native && fWidth <= SWEET_FB_LOGICAL_W && fHeight <= SWEET_FB_LOGICAL_H) {
#endif''')

    # Keep UIKit's known iPhone screen class, compose into cacheable RAM and
    # scale to the complete panel. Only changed 64-pixel tiles reach scanout.
    fb = 'iokit/Kernel/arm/SweetFramebuffer.cpp'
    create('iokit/Kernel/arm/XiguaBlit.h',
           (Path(__file__).resolve().parent.parent / 'kernel/xigua_blit.h').read_text())
    replace(fb, '#include <sys/proc.h>\n', '''#include <sys/proc.h>
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include "XiguaBlit.h"
#endif
''')
    replace(fb, '\tbool          fPowerOff;', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tuint32_t *fCanvas, *fPrevious, *fXMap, *fYMap;
\tbool fFit, fForce;
#endif
\tbool          fPowerOff;''')
    replace(fb, '\tuint32_t hz = 10;', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tuint32_t hz = 30;
#else
\tuint32_t hz = 10;
#endif''')
    replace(fb, '\tregisterService();\n', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tfFit = false;
\tfForce = true;
\tint fit = 0;
\tPE_parse_boot_argn("sweetfb_fit", &fit, sizeof(fit));
\tif (fit && fLogicalW && fLogicalH && fWidth <= 8192 && fHeight <= 8192) {
\t\tsize_t canvasBytes = (size_t)fLogicalW * fLogicalH * 4;
\t\tsize_t previousBytes = (size_t)fWidth * fHeight * 4;
\t\tfCanvas = (uint32_t *)IOMallocZeroData(canvasBytes);
\t\tfPrevious = (uint32_t *)IOMallocZeroData(previousBytes);
\t\tfXMap = (uint32_t *)IOMallocData(fWidth * 4);
\t\tfYMap = (uint32_t *)IOMallocData(fHeight * 4);
\t\tif (fCanvas && fPrevious && fXMap && fYMap) {
\t\t\tfor (uint32_t x = 0; x < fWidth; x++)
\t\t\t\tfXMap[x] = (uint64_t)x * fLogicalW / fWidth;
\t\t\tfor (uint32_t y = 0; y < fHeight; y++)
\t\t\t\tfYMap[y] = (uint64_t)y * fLogicalH / fHeight;
\t\t\tfFit = true;
\t\t\tfOffX = fOffY = 0;
\t\t\tIOLog("XIGUA FB: full-panel fit enabled, cached composition and changed tiles\\n");
\t\t} else {
\t\t\tif (fCanvas) IOFreeData(fCanvas, canvasBytes);
\t\t\tif (fPrevious) IOFreeData(fPrevious, previousBytes);
\t\t\tif (fXMap) IOFreeData(fXMap, fWidth * 4);
\t\t\tif (fYMap) IOFreeData(fYMap, fHeight * 4);
\t\t\tfCanvas = fPrevious = fXMap = fYMap = NULL;
\t\t\tIOLog("XIGUA FB: fit allocation failed; centered display fallback\\n");
\t\t}
\t}
#endif
\tregisterService();
''')
    replace(fb, '\tuint32_t mask = get32(rec, 0x104);', '''\tuint32_t mask = get32(rec, 0x104);
\tuintptr_t target = fPixels;
\tuint32_t targetWidth = fWidth, targetHeight = fHeight, targetStride = fRowBytes;
#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tif (fFit) {
\t\ttarget = (uintptr_t)fCanvas;
\t\ttargetWidth = fLogicalW;
\t\ttargetHeight = fLogicalH;
\t\ttargetStride = fLogicalW * 4;
\t}
#endif''')
    replace(fb, 'w > (int32_t)fWidth - dx', 'w > (int32_t)targetWidth - dx')
    replace(fb, 'w = (int32_t)fWidth - dx', 'w = (int32_t)targetWidth - dx')
    replace(fb, 'h > (int32_t)fHeight - dy', 'h > (int32_t)targetHeight - dy')
    replace(fb, 'h = (int32_t)fHeight - dy', 'h = (int32_t)targetHeight - dy')
    replace(fb, 'fPixels + (uint64_t)(dy + y) * fRowBytes + (uint64_t)dx * 4',
            'target + (uint64_t)(dy + y) * targetStride + (uint64_t)dx * 4')
    replace(fb, '\t\ts->release();\n\t}\n}', '''\t\ts->release();
\t}
#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tif (fFit) {
\t\tbool force = __atomic_exchange_n(&fForce, false, __ATOMIC_ACQ_REL);
\t\t(void)xigua_blit_flush(fCanvas, fLogicalW, fXMap, fYMap, fPrevious,
\t\t    (uint8_t *)fPixels, fWidth, fHeight, fRowBytes, force, memcpy);
\t}
#endif
}''')
    replace(fb, '\t\t\t\tfFB->fFadeStep = 0;', '''\t\t\t\tfFB->fFadeStep = 0;
#if defined(ARM64_BOARD_CONFIG_XIGUA)
\t\t\t\tif (!off) __atomic_store_n(&fFB->fForce, true, __ATOMIC_RELEASE);
#endif''')

    # memdev stores its length as a 32-bit count of 4 KiB pages. Promote before
    # shifting: a 12 GiB root otherwise wraps to zero in strategy and ioctls.
    memdev = 'bsd/dev/memdev.c'
    expression = 'mdev[devid].mdSize << 12'
    replace(memdev, expression, '(uint64_t)mdev[devid].mdSize << 12',
            count=read(memdev).count(expression))
    replace(memdev,
            'count = imin(uio_resid(uio), ((uint64_t)mdev[devid].mdSize << 12) - uio->uio_offset);',
            'count = (int)MIN((uint64_t)INT_MAX, MIN((uint64_t)uio_resid(uio), ((uint64_t)mdev[devid].mdSize << 12) - uio->uio_offset));')

    # Change printed prefixes only. Driver symbols, boot arguments, protocol
    # names and stored log formats retain their existing interfaces.
    prefix = re.compile(r'"SWEET(?=[ :])')
    for directory in ['bsd', 'osfmk', 'pexpert', 'iokit', 'libkern']:
        for path in sorted((source / directory).rglob('*')):
            if path.suffix not in ['.c', '.cpp']:
                continue
            name = str(path.relative_to(source))
            text = modified.get(name)
            if text is None:
                raw = path.read_bytes()
                if b'"SWEET ' not in raw and b'"SWEET:' not in raw:
                    continue
                text = raw.decode('utf-8', errors='surrogateescape')
            if not prefix.search(text):
                continue
            read(name)
            updated = prefix.sub('ARM_BOARD_NAME "', text)
            first_include = re.search(r'^#include\b', updated, re.MULTILINE)
            if not first_include:
                raise ValueError(f'{name}: no include location for board name')
            pos = first_include.start()
            modified[name] = updated[:pos] + '#include <pexpert/arm64/board_name.h>\n' + updated[pos:]

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
    a.output.write_text(patch, errors='surrogateescape')
    print(f'{a.output}: {len(patch)} bytes')


if __name__ == '__main__':
    main()
