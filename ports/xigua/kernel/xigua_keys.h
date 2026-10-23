/* PJA110 SPMI v7 observer reads only; no PMIC configuration writes. */
#ifndef XIGUA_KEYS_H
#define XIGUA_KEYS_H
#include <stdint.h>
#include <stdbool.h>
enum { XIGUA_KEYS_CORE, XIGUA_KEYS_CNFG, XIGUA_KEYS_OBSERVER };
struct xigua_keys_io {
    void *context;
    uint32_t (*read)(void *, unsigned, unsigned);
    void (*write)(void *, unsigned, unsigned, uint32_t);
    void (*pause)(void *, unsigned);
};
struct xigua_key_channel { uint16_t apid, ppid; bool poisoned; };

static int
xigua_keys_find(const struct xigua_keys_io *io, unsigned count, unsigned ppid,
    struct xigua_key_channel *channel)
{
    if (!count || count > 1024 || (ppid != 0x013 && ppid != 0x18d)) return EINVAL;
    int found = -1;
    for (unsigned i = 0; i < count; i++) {
        uint32_t map = io->read(io->context, XIGUA_KEYS_CORE, 0x2000 + 4 * i);
        if (map == UINT32_MAX) return EIO;
        if (!map || ((map >> 8) & 0xfff) != ppid) continue;
        uint32_t owner = io->read(io->context, XIGUA_KEYS_CNFG, 4 * i);
        if (owner == UINT32_MAX) return EIO;
        /* Match Linux's bus0/EE0 duplicate PPID selection. */
        if (found < 0 || !(owner & 7)) found = (int)i;
    }
    if (found < 0) return ENODEV;
    *channel = (struct xigua_key_channel){(uint16_t)found, (uint16_t)ppid, false};
    return 0;
}

static int
xigua_keys_read_byte(const struct xigua_keys_io *io, struct xigua_key_channel *ch,
    unsigned address, uint8_t *value)
{
    bool allowed = (ch->ppid == 0x013 && (address == 0x1305 || address == 0x1310)) ||
        (ch->ppid == 0x18d && (address == 0x8d05 || address == 0x8d10 ||
        address == 0x8d40 || address == 0x8d46));
    if (!allowed || ch->apid >= 1024) return EINVAL;
    if (ch->poisoned) return EIO;
    unsigned off = 0x20U * ch->apid; /* v7, observer EE0, no write channel. */
    io->write(io->context, XIGUA_KEYS_OBSERVER, off,
        (1U << 27) | ((address & 255U) << 4)); /* EXT_READL, exactly one byte */
    for (unsigned n = 0; n < 1000; n++) {
        uint32_t status = io->read(io->context, XIGUA_KEYS_OBSERVER, off + 8);
        if (status != UINT32_MAX && (status & 1)) {
            if (status & 14) return EIO;
            *value = (uint8_t)io->read(io->context, XIGUA_KEYS_OBSERVER, off + 0x18);
            return 0;
        }
        io->pause(io->context, 1);
    }
    ch->poisoned = true; /* Do not reuse an observer with unknown completion. */
    return ETIMEDOUT;
}

struct xigua_key_filter { bool armed, down, candidate; unsigned count, errors; };
/* Return 1 on an edge. Ignore held-at-boot keys and require three samples.
 * Failed reads cannot create a press; release a reported key after 3 failures. */
static bool
xigua_key_update(struct xigua_key_filter *key, bool valid, bool down)
{
    if (!valid) {
        key->count = 0;
        if (++key->errors >= 3 && key->down) {
            key->down = false; key->armed = false;
            return true;
        }
        return false;
    }
    key->errors = 0;
    if (!key->armed) {
        if (!down) key->armed = true;
        return false;
    }
    if (down == key->down) { key->count = 0; return false; }
    if (!key->count || down != key->candidate) { key->candidate = down; key->count = 1; }
    else key->count++;
    if (key->count < 3) return false;
    key->down = down; key->count = 0;
    return true;
}
#endif
