/* Single-register MMIO with no base-register writeback. Gunyah's MMIO
 * emulation relies on ESR_EL2.ISV, which pre/post-indexed accesses do not
 * provide. Volatile C alone lets the compiler select those instructions.
 * These are relaxed device accesses; callers supply hardware barriers.
 */
#ifndef XIGUA_MMIO_H
#define XIGUA_MMIO_H
#include <stdint.h>

static inline uint32_t
xigua_mmio_read32(uintptr_t address)
{
    uint32_t value;
    __asm__ volatile("ldr %w0, [%1]" : "=r"(value) : "r"(address) : "memory");
    return value;
}

static inline uint64_t
xigua_mmio_read64(uintptr_t address)
{
    uint64_t value;
    __asm__ volatile("ldr %0, [%1]" : "=r"(value) : "r"(address) : "memory");
    return value;
}

static inline void
xigua_mmio_write32(uintptr_t address, uint32_t value)
{
    __asm__ volatile("str %w0, [%1]" : : "r"(value), "r"(address) : "memory");
}
#endif
