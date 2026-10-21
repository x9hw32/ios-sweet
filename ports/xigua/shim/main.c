/* SPDX-License-Identifier: BSD-2-Clause
 * No UFS, touch, power-controller or USB MMIO is accessed by this loader.
 */
#include <stdint.h>
#include "payload.h"
#include "board.h"
#include "font.h"

extern char _head[], _end[], _payload_start[], _payload_end[];
static unsigned row;
static volatile unsigned printing, framebuffer_failed;
#define REGISTER(name) ({ uint64_t r; __asm__ volatile("mrs %0, " #name : "=r"(r)); r; })

static void print(const char *s)
{
    if (framebuffer_failed) return;
    printing = 1;
    unsigned col = 0;
    if (row >= FB_HEIGHT / 32) row = 0;
    volatile uint32_t *fb = (void *)(uintptr_t)FB_BASE;
    for (unsigned y = 0; y < 32; y++)
        for (unsigned x = 0; x < FB_WIDTH; x++) fb[(row * 32 + y) * (FB_STRIDE / 4) + x] = 0;
    while (*s && col < FB_WIDTH / 16) {
        unsigned c = (unsigned char)*s++;
        if (c < 32 || c > 126) c = '?';
        const unsigned char *glyph = font8x16[c - 32];
        for (unsigned y = 0; y < 16; y++)
            for (unsigned x = 0; x < 8; x++)
                if (glyph[y] & (0x80 >> x))
                    for (unsigned sy = 0; sy < 2; sy++)
                        for (unsigned sx = 0; sx < 2; sx++)
                            fb[(row * 32 + y * 2 + sy) * (FB_STRIDE / 4) + col * 16 + x * 2 + sx] = 0xffffffff;
        col++;
    }
    row++;
    __asm__ volatile("dsb sy" ::: "memory");
    printing = 0;
}

static void value(const char *name, uint64_t v)
{
    char s[96];
    unsigned i = 0;
    while (*name && i < 60) s[i++] = *name++;
    s[i++] = '=';
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned n = (v >> shift) & 15;
        s[i++] = n < 10 ? '0' + n : 'a' + n - 10;
    }
    s[i] = 0;
    print(s);
}

static void reboot(void)
{
    print("Cold reboot to normal boot in 20 seconds");
    uint64_t frequency = REGISTER(CNTFRQ_EL0), start = REGISTER(CNTPCT_EL0);
    while (REGISTER(CNTPCT_EL0) - start < frequency * 20) __asm__ volatile("yield");
    register uint64_t x0 __asm__("x0") = 0x84000009;
    __asm__ volatile("smc #0" : "+r"(x0) : : "x1", "x2", "x3", "x4", "x5", "x6", "x7",
                     "x8", "x9", "x10", "x11", "x12", "x13", "x14", "x15", "x16", "x17", "cc", "memory");
    for (;;) __asm__ volatile("wfe");
}

void shim_exception(uint64_t vector)
{
    // A framebuffer access fault must still reach PSCI reset without drawing
    // recursively into the same inaccessible framebuffer.
    if (printing) framebuffer_failed = 1;
    print("XIGUA shim exception");
    value("vector", vector);
    value("ESR", REGISTER(ESR_EL1));
    value("ELR", REGISTER(ELR_EL1));
    value("FAR", REGISTER(FAR_EL1));
    reboot();
}

struct video { uint64_t base, display, stride, width, height, depth; };
struct boot_args {
    uint16_t revision, version;
    uint64_t virt_base, phys_base, memory_size, top;
    struct video video;
    uint32_t machine;
    uint64_t adt;
    uint32_t adt_size;
    char command[XIGUA_COMMAND];
    uint64_t flags, actual_memory;
};
_Static_assert(offsetof(struct boot_args, command) == 108, "XNU boot_args command ABI");
_Static_assert(sizeof(struct boot_args) == 736, "XNU boot_args size ABI");

static void copy(uint64_t destination, const void *source, uint64_t size)
{
    volatile uint8_t *d = (void *)(uintptr_t)destination;
    const volatile uint8_t *s = source;
    // With MMU off, unaligned multi-byte accesses can fault. Use words only
    // when both addresses are aligned, and handle every tail byte exactly.
    while (size && ((uintptr_t)d & 7)) {
        *d++ = s ? *s++ : 0;
        size--;
    }
    if (!s || !((uintptr_t)s & 7)) {
        while (size >= 8) {
            *(volatile uint64_t *)d = s ? *(const volatile uint64_t *)s : 0;
            d += 8;
            if (s) s += 8;
            size -= 8;
        }
    }
    while (size--) *d++ = s ? *s++ : 0;
}

void shim_main(uint64_t fdt)
{
    print("XIGUA native shim: experimental ABL framebuffer");
    value("Image", (uintptr_t)_head);
    value("FDT", fdt);
    value("MPIDR", REGISTER(MPIDR_EL1));
    value("MMFR0", REGISTER(ID_AA64MMFR0_EL1));
    value("CNTFRQ", REGISTER(CNTFRQ_EL0));
    uint64_t granule = (REGISTER(ID_AA64MMFR0_EL1) >> 20) & 15;
    if ((granule != 1 && granule != 2) ||
        (REGISTER(MPIDR_EL1) & 0xffffff) != BOOT_MPIDR ||
        REGISTER(CNTFRQ_EL0) != TIMEBASE) {
        print("CPU features/topology differ from profile; stopping");
        reboot();
    }
    uint64_t fdt_size = 0;
    if (fdt && !(fdt & 3)) {
        volatile uint32_t *header = (void *)(uintptr_t)fdt;
        if (__builtin_bswap32(header[0]) == 0xd00dfeed)
            fdt_size = __builtin_bswap32(header[1]);
    }
    if (!fdt_size || fdt_size > 16 * 1024 * 1024) {
        print("Missing/invalid ABL FDT; stopping");
        reboot();
    }
    struct region reserved[] = {
        {(uintptr_t)_head, (uintptr_t)_end - (uintptr_t)_head},
        {fdt, fdt_size}, {FB_BASE, FB_SIZE},
    };
    struct placement place;
    const struct payload *p = (void *)_payload_start;
    int error = payload_validate(p, _payload_end - _payload_start,
                                (struct region){RAM_BASE, RAM_SIZE - 1024 * 1024},
                                reserved, sizeof(reserved) / sizeof(reserved[0]), &place);
    if (error) {
        value("payload validation error", (uint64_t)(int64_t)error);
        reboot();
    }
    for (unsigned i = 0; i < p->count; i++) {
        const struct segment *s = &p->segments[i];
        uint64_t dst = p->phys_base + (s->va - p->virt_base);
        copy(dst, _payload_start + s->offset, s->file_size);
        copy(dst + s->file_size, NULL, s->memory_size - s->file_size);
    }
    copy(place.adt, _payload_start + p->adt_offset, p->adt_size);
    copy(place.boot_args, NULL, XIGUA_PAGE);
    struct boot_args *args = (void *)(uintptr_t)place.boot_args;
    args->revision = args->version = 2;
    args->virt_base = p->virt_base;
    args->phys_base = p->phys_base;
    args->memory_size = args->actual_memory = p->memory_size;
    args->top = place.top;
    args->video = (struct video){FB_BASE, 1, FB_STRIDE, FB_WIDTH, FB_HEIGHT, 32};
    args->adt = p->virt_base + (place.adt - p->phys_base);
    args->adt_size = p->adt_size;
    copy((uintptr_t)args->command, p->command, XIGUA_COMMAND);
    value("XNU entry PA", place.entry);
    value("XNU boot_args PA", place.boot_args);
    print("Entering XNU");
    __asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
    ((void (*)(uint64_t))(uintptr_t)place.entry)(place.boot_args);
    print("XNU unexpectedly returned");
    reboot();
}
