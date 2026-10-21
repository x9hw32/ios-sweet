/* SPDX-License-Identifier: BSD-2-Clause
 * Validate every payload range before the first memory copy.
 */
#include "payload.h"

static int inside(uint64_t base, uint64_t size, uint64_t outer, uint64_t length)
{
    return base >= outer && size <= length && base - outer <= length - size;
}

static int overlaps(uint64_t a, uint64_t n, uint64_t b, uint64_t m)
{
    if (!n || !m) return 0;
    return a <= b ? b - a < n : a - b < m;
}

int payload_validate(const void *blob, uint64_t length, struct region ram,
                     const struct region *reserved, unsigned reserved_count,
                     struct placement *out)
{
    const struct payload *p = blob;
    const char expected[8] = {'S','W','E','E','T','X','N','U'};
    if (length < sizeof(*p) || ((uintptr_t)blob & 15) ||
        !ram.size || ram.base > UINT64_MAX - ram.size) return -1;
    for (unsigned i = 0; i < 8; i++) if (p->magic[i] != expected[i]) return -2;
    if (p->version != 1 || !p->count || p->count > 32 ||
        p->count > (length - sizeof(*p)) / sizeof(struct segment)) return -3;
    if (p->phys_base != ram.base || p->memory_size != ram.size ||
        (ram.base & (XIGUA_PAGE - 1)) || (ram.size & (XIGUA_PAGE - 1))) return -4;
    for (unsigned i = 0; i < reserved_count; i++)
        if (overlaps(ram.base, ram.size, reserved[i].base, reserved[i].size)) return -5;
    uint64_t header = sizeof(*p) + p->count * sizeof(struct segment);
    if (!p->adt_size || p->adt_size > 1024 * 1024 || p->adt_offset < header ||
        !inside(p->adt_offset, p->adt_size, 0, length) || (p->adt_offset & 15)) return -6;
    int terminated = 0, entry = 0;
    for (unsigned i = 0; i < XIGUA_COMMAND; i++) if (!p->command[i]) terminated = 1;
    if (!terminated || (p->entry_va & 3) || p->kernel_end < p->virt_base ||
        p->kernel_end - p->virt_base >= ram.size || (p->kernel_end & (XIGUA_PAGE - 1))) return -7;
    uint64_t last = 0;
    for (unsigned i = 0; i < p->count; i++) {
        const struct segment *s = &p->segments[i];
        if (!s->memory_size || s->va < p->virt_base || s->file_size > s->memory_size ||
            s->offset < header || !inside(s->offset, s->file_size, 0, length) ||
            (s->va & (XIGUA_PAGE - 1)) ||
            !inside(s->va - p->virt_base, s->memory_size, 0, ram.size)) return -8;
        uint64_t end = s->va - p->virt_base + s->memory_size;
        if (end > last) last = end;
        if (inside(p->entry_va, 4, s->va, s->file_size)) entry = 1;
        for (unsigned j = 0; j < i; j++)
            if (overlaps(s->va, s->memory_size, p->segments[j].va,
                         p->segments[j].memory_size)) return -9;
    }
    if (!entry || last > p->kernel_end - p->virt_base) return -10;
    uint64_t adt_offset = p->kernel_end - p->virt_base;
    if (!inside(adt_offset, p->adt_size + 2 * XIGUA_PAGE, 0, ram.size)) return -11;
    out->adt = ram.base + adt_offset;
    out->boot_args = (out->adt + p->adt_size + XIGUA_PAGE - 1) & ~(XIGUA_PAGE - 1);
    out->top = out->boot_args + XIGUA_PAGE;
    out->entry = ram.base + (p->entry_va - p->virt_base);
    return 0;
}
