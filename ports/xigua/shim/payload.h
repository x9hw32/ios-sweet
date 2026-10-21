/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef XIGUA_PAYLOAD_H
#define XIGUA_PAYLOAD_H
#include <stdint.h>
#include <stddef.h>
#define XIGUA_PAGE 0x4000ull
#define XIGUA_COMMAND 608

struct segment { uint64_t va, memory_size, offset, file_size; };
struct payload {
    char magic[8];
    uint32_t version, count;
    uint64_t virt_base, entry_va, adt_offset, adt_size, kernel_end;
    uint64_t phys_base, memory_size;
    char command[XIGUA_COMMAND];
    struct segment segments[];
};
struct region { uint64_t base, size; };
struct placement { uint64_t adt, boot_args, top, entry; };
_Static_assert(offsetof(struct payload, segments) == 0x2a8, "payload ABI");

int payload_validate(const void *, uint64_t, struct region, const struct region *,
                     unsigned, struct placement *);
#endif
