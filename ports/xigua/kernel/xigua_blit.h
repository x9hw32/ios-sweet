/* Nearest-neighbour panel scaling with a cached copy of the last scanout.
 * No display MMIO reads: unchanged tiles never touch the physical panel.
 * Caller validates dimensions and supplies maps/buffers and memcpy.
 */
#ifndef XIGUA_BLIT_H
#define XIGUA_BLIT_H
#include <stdint.h>
#include <stddef.h>

typedef void *(*xigua_copy_bytes)(void *, const void *, size_t);

static inline uint64_t
xigua_blit_flush(const uint32_t *canvas, uint32_t canvas_width,
    const uint32_t *xmap, const uint32_t *ymap, uint32_t *previous,
    uint8_t *panel, uint32_t width, uint32_t height, uint32_t stride,
    int force, xigua_copy_bytes copy)
{
    uint64_t written = 0;
    for (uint32_t y = 0; y < height; y++) {
        const uint32_t *src = canvas + (uint64_t)ymap[y] * canvas_width;
        uint32_t *last = previous + (uint64_t)y * width;
        uint8_t *dst = panel + (uint64_t)y * stride;
        for (uint32_t x = 0; x < width; x += 64) {
            uint32_t tile[64];
            uint32_t count = width - x < 64 ? width - x : 64;
            int changed = force;
            for (uint32_t i = 0; i < count; i++) {
                tile[i] = src[xmap[x + i]];
                changed |= tile[i] != last[x + i];
            }
            if (changed) {
                copy(dst + (uint64_t)x * 4, tile, count * 4);
                copy(last + x, tile, count * 4);
                written += count * 4;
            }
        }
    }
    return written;
}
#endif
