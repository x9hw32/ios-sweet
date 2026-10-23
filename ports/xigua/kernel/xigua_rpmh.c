/* PJA110 S3910 1.8V VDD only. No SPMI, other rails or sleep/wake TCS writes. */
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/errno.h>
#include <kern/clock.h>
#include <pexpert/pexpert.h>
#include <pexpert/arm64/XiguaMMIO.h>
#include "xigua_vdd.h"
extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
extern vm_offset_t ml_io_map_wcomb(vm_offset_t, vm_size_t);
int xigua_touch_vdd_on(void);
static uintptr_t vdd_rsc, vdd_db;
static bool vdd_poisoned;
static uint32_t vdd_read(void *ctx, unsigned off) {
    uint32_t v = xigua_mmio_read32((uintptr_t)ctx + off);
    __asm__ volatile("dmb oshld" ::: "memory");
    return v;
}
static void vdd_write(void *ctx, unsigned off, uint32_t value) {
    __asm__ volatile("dmb oshst" ::: "memory");
    xigua_mmio_write32((uintptr_t)ctx + off, value);
    __asm__ volatile("dsb osh" ::: "memory");
}
static void vdd_pause(void *ctx, unsigned us) { (void)ctx; delay(us); }
int xigua_touch_vdd_on(void) {
    if (!vdd_rsc) vdd_rsc = ml_io_map(0x17a20000, 0x10000);
    if (!vdd_db) vdd_db = ml_io_map_wcomb(0x81c60000, XIGUA_VDD_DB_BYTES);
    if (!vdd_rsc || !vdd_db) return ENOMEM;
    uint32_t id = vdd_read((void *)vdd_rsc, 0), cfg = vdd_read((void *)vdd_rsc, 0xc);
    unsigned major = (id >> 16) & 255, count = (cfg >> 12) & 63, ncpt = cfg >> 27;
    printf("XIGUA TOUCH VDD: RSC2 id=%x cfg=%x major=%u TCS=%u ncpt=%u\n", id, cfg, major, count, ncpt);
    if (count < 8 || count > 16 || ncpt < 3 || ncpt > 16 || (major != 2 && major != 3)) return ENODEV;
    int error = xigua_vdd_check_db(vdd_read, (void *)vdd_db);
    if (error) { printf("XIGUA TOUCH VDD: cmd-db ldob4 mapping refused: %d\n", error); return error; }
    struct xigua_rpmh_io io = {(void *)(vdd_rsc + 0xd00), vdd_read, vdd_write, vdd_pause};
    error = xigua_vdd_vote(&io, major, ncpt, &vdd_poisoned);
    printf("XIGUA TOUCH VDD: ldob4 addr=40800 ACTIVE 1800mV HPM enable vote result=%d\n", error);
    return error;
}
#endif
