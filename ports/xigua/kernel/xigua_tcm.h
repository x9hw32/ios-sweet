/* Minimal TouchCom v1 coordinate format, configured explicitly by our driver.
 * No vendor host-processing algorithm is needed in the controller's LBP mode.
 */
#ifndef XIGUA_TCM_H
#define XIGUA_TCM_H
#include <stdint.h>
#include <stddef.h>

static const uint8_t xigua_tcm_report_config[] = {
    0x18, 8,                 /* active object count */
    0x01,                    /* foreach active object */
    0x06, 4, 0x07, 4,        /* object index, classification */
    0x08, 16, 0x09, 16,      /* x, y */
    0x0a, 8,                 /* pressure */
    0x04, 0x03, 0x00         /* byte padding, end loop, end report */
};

/* First chunk carries the total command payload size. Continuations contain
 * only command 0x01 plus subsequent bytes; each bus write fits the FW limit.
 * This helper never dereferences data for a zero-length command. */
static inline unsigned
xigua_tcm_write_chunk(unsigned command, const uint8_t *data, unsigned size,
    unsigned offset, unsigned maximum, uint8_t *packet, unsigned *next)
{
    unsigned prefix = offset ? 1 : 3;
    if (offset > size || size > 65535 || maximum <= prefix) return 0;
    unsigned count = size - offset;
    if (count > maximum - prefix) count = maximum - prefix;
    packet[0] = offset ? 1 : (uint8_t)command;
    if (!offset) { packet[1] = (uint8_t)size; packet[2] = (uint8_t)(size >> 8); }
    for (unsigned i = 0; i < count; i++) packet[prefix + i] = data[offset + i];
    *next = offset + count;
    return prefix + count;
}

struct xigua_contact { uint16_t x, y; };

static inline unsigned xigua_le16(const uint8_t *p) { return p[0] | ((unsigned)p[1] << 8); }

static inline int
xigua_tcm_contacts(const uint8_t *data, size_t size, unsigned max_x, unsigned max_y,
    unsigned width, unsigned height, struct xigua_contact contacts[10], uint16_t *active)
{
    if (!size || data[0] > 10 || size < 1 + 6U * data[0] ||
        !max_x || !max_y || !width || !height || width > 65535 || height > 65535) return -1;
    uint16_t seen = 0, mask = 0;
    for (unsigned n = 0; n < data[0]; n++) {
        const uint8_t *p = data + 1 + n * 6;
        unsigned id = p[0] & 15, type = p[0] >> 4;
        if (id >= 10 || (seen & (1U << id))) return -1;
        seen |= 1U << id;
        if (type != 1 && type != 2 && type != 3) continue; /* no palms/hover */
        unsigned x = xigua_le16(p + 1), y = xigua_le16(p + 3);
        if (x > max_x) x = max_x;
        if (y > max_y) y = max_y;
        contacts[id].x = (uint16_t)((uint64_t)x * (width - 1) / max_x);
        contacts[id].y = (uint16_t)((uint64_t)y * (height - 1) / max_y);
        mask |= 1U << id;
    }
    *active = mask;
    return 0;
}
#endif
