/* Fixed PJA110 touch VDD: cmd-db ldob4, 1800mV. No other resource can be voted.
 * Register layouts follow OnePlus rpmh-rsc.c v2.7/v3.0; only ACTIVE TCS0..2
 * from the live DT may be borrowed, and only when completely empty and idle.
 */
#ifndef XIGUA_VDD_H
#define XIGUA_VDD_H
#include <stdint.h>
#include <stdbool.h>
struct xigua_rpmh_io {
    void *context;
    uint32_t (*read)(void *, unsigned);
    void (*write)(void *, unsigned, uint32_t);
    void (*pause)(void *, unsigned);
};
#define XIGUA_LDOB4_ADDR 0x40800U
#define XIGUA_VDD_DB_BYTES 0x20000U

static int
xigua_vdd_check_db(uint32_t (*read)(void *, unsigned), void *context)
{
    if (read(context, 0) != 1 || read(context, 4) != 0xc0330db || (read(context, 140) & 1)) return EINVAL;
    unsigned matches = 0;
    for (unsigned i = 0; i < 8; i++) {
        unsigned h = 8 + i * 16;
        uint32_t a = read(context, h), b = read(context, h + 4);
        unsigned type = a & 0xffff, count = b >> 16;
        if (!type) break;
        if (type != 4) continue;
        unsigned entries = 144 + (a >> 16), aux = 144 + (b & 0xffff);
        if ((entries & 3) || entries > XIGUA_VDD_DB_BYTES ||
            count > (XIGUA_VDD_DB_BYTES - entries) / 24 || aux > XIGUA_VDD_DB_BYTES) return EINVAL;
        for (unsigned n = 0; n < count; n++) {
            unsigned e = entries + n * 24;
            if (read(context, e) != 0x626f646c || read(context, e + 4) != 0x34) continue; /* ldob4 */
            uint32_t aux_entry = read(context, e + 20);
            unsigned size = aux_entry & 0xffff, offset = aux_entry >> 16;
            if (read(context, e + 16) != XIGUA_LDOB4_ADDR ||
                offset > XIGUA_VDD_DB_BYTES - aux || size > XIGUA_VDD_DB_BYTES - aux - offset) return EINVAL;
            matches++;
        }
    }
    return matches == 1 ? 0 : ENODEV;
}

static bool
xigua_vdd_sync(const struct xigua_rpmh_io *io, unsigned off, uint32_t value)
{
    io->write(io->context, off, value);
    for (unsigned n = 0; n < 1000; n++) {
        if (io->read(io->context, off) == value) return true;
        io->pause(io->context, 1);
    }
    return false;
}

static bool
xigua_vdd_free(const struct xigua_rpmh_io *io, unsigned t, unsigned major)
{
    unsigned b = t * 0x2a0, reg = major >= 3 ? 0x20 : 0x10;
    uint32_t idle = io->read(io->context, b + reg + 8);
    return idle && idle != ~0U && !io->read(io->context, b + reg) &&
        !io->read(io->context, b + reg + 4) && !io->read(io->context, b + reg + 12) &&
        !(io->read(io->context, 4) & (1U << t));
}

static int
xigua_vdd_vote(const struct xigua_rpmh_io *io, unsigned major, unsigned ncpt, bool *poisoned)
{
    if (*poisoned) return EIO;
    if ((major != 2 && major != 3) || ncpt < 3 || ncpt > 16) return ENODEV;
    unsigned wait = major == 3 ? 0x20 : 0x10, control = wait + 4, status = wait + 8, enable = wait + 12;
    unsigned cmd = major == 3 ? 0x34 : 0x30, stride = major == 3 ? 24 : 20;
    int slot = -1;
    for (unsigned t = 0; t < 3; t++) {
        unsigned b = t * 0x2a0;
        uint32_t mask = io->read(io->context, b + enable);
        if (mask & ~((1U << ncpt) - 1)) return EIO;
        for (unsigned n = 0; n < ncpt; n++)
            if ((mask & (1U << n)) &&
                (io->read(io->context, b + cmd + n * stride + 4) & ~15U) == XIGUA_LDOB4_ADDR) return EBUSY;
        if (slot < 0 && xigua_vdd_free(io, t, major)) slot = (int)t;
    }
    if (slot < 0) return EBUSY;
    unsigned b = (unsigned)slot * 0x2a0, bit = 1U << slot;
    uint32_t irq = io->read(io->context, 0);
    if (irq == ~0U || !xigua_vdd_free(io, (unsigned)slot, major)) return EBUSY;
    if (!xigua_vdd_sync(io, 0, irq & ~bit)) { *poisoned = true; return EIO; }
    if (!xigua_vdd_free(io, (unsigned)slot, major)) {
        if (!xigua_vdd_sync(io, 0, (io->read(io->context, 0) & ~bit) | (irq & bit))) *poisoned = true;
        return EBUSY;
    }
    *poisoned = true; /* No retry or reuse after uncertain payload/trigger. */
    const uint32_t offsets[3] = {0, 8, 4}, data[3] = {1800, 7, 1};
    for (unsigned n = 0; n < 3; n++) {
        unsigned c = b + cmd + n * stride;
        if (!xigua_vdd_sync(io, c, 0x10108) ||
            !xigua_vdd_sync(io, c + 4, XIGUA_LDOB4_ADDR + offsets[n]) ||
            !xigua_vdd_sync(io, c + 8, data[n])) return EIO;
    }
    if (!xigua_vdd_sync(io, b + wait, 7) || !xigua_vdd_sync(io, b + enable, 7) ||
        !xigua_vdd_sync(io, b + control, 0) || !xigua_vdd_sync(io, b + control, 1U << 16)) return EIO;
    io->write(io->context, b + control, (1U << 16) | (1U << 24));
    bool done = false, progress = false;
    for (unsigned us = 0; us < 100000; us++) {
        uint32_t pending = io->read(io->context, 4), idle = io->read(io->context, b + status);
        bool complete = true;
        for (unsigned n = 0; n < 3; n++) {
            uint32_t s = io->read(io->context, b + cmd + n * stride + 12);
            complete &= s != ~0U && (s & 0x10100) == 0x10100;
        }
        progress |= idle == 0 || !complete;
        if (idle && idle != ~0U && pending != ~0U && ((pending & bit) || progress) && complete) { done = true; break; }
        io->pause(io->context, 1);
    }
    if (!done) return ETIMEDOUT;
    if (!xigua_vdd_sync(io, b + control, 1U << 16) || !xigua_vdd_sync(io, b + control, 0) ||
        !xigua_vdd_sync(io, b + enable, 0) || !xigua_vdd_sync(io, b + wait, 0)) return EIO;
    io->write(io->context, 8, bit); /* W1C only this slot. */
    if ((io->read(io->context, 4) & bit) ||
        !xigua_vdd_sync(io, 0, (io->read(io->context, 0) & ~bit) | (irq & bit))) return EIO;
    *poisoned = false;
    return 0;
}
#endif
