/* PJA110 physical keys: PMK8550 GEN3 PON and PM8550 GPIO6, SPMI v7 EE0.
 * Live DT and pinned OnePlus pm8941-pwrkey.c/spmi-pmic-arb.c define wiring.
 * Read-only EXT_READL via observer; never map/write PMIC write channels,
 * IRQ acknowledgements, reset control, pin configuration or calibration.
 */
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/errno.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <pexpert/pexpert.h>
#include <pexpert/arm64/XiguaMMIO.h>
#include "xigua_keys.h"
extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
extern kern_return_t thread_terminate(thread_t);
extern void sweet_hid_key(int, int);
extern int hz;
void xigua_keys_start(void);
static uintptr_t keys_base[3];
static int keys_wait_channel;
static uint32_t keys_rd(void *context, unsigned region, unsigned off) {
    (void)context;
    uint32_t value = xigua_mmio_read32(keys_base[region] + off);
    __asm__ volatile("dmb oshld" ::: "memory");
    return value;
}
static void keys_wr(void *context, unsigned region, unsigned off, uint32_t value) {
    (void)context;
    __asm__ volatile("dmb oshst" ::: "memory");
    xigua_mmio_write32(keys_base[region] + off, value);
    __asm__ volatile("dsb osh" ::: "memory");
}
static void keys_delay(void *context, unsigned us) { (void)context; delay(us); }
static void keys_pause(unsigned ms) {
    (void)tsleep(&keys_wait_channel, PZERO, "xiguakeys", MAX(1, (int)(ms * hz / 1000)));
}
static void keys_thread(void *argument, wait_result_t result) {
    (void)argument; (void)result;
    keys_pause(1000);
    keys_base[XIGUA_KEYS_CORE] = ml_io_map(0xc400000, 0x3000);
    keys_base[XIGUA_KEYS_CNFG] = ml_io_map(0xc42d000, 0x4000);
    keys_base[XIGUA_KEYS_OBSERVER] = ml_io_map(0xc440000, 0x80000);
    if (!keys_base[0] || !keys_base[1] || !keys_base[2]) {
        printf("XIGUA KEYS: MMIO mapping failed\n"); goto done;
    }
    struct xigua_keys_io io = {NULL, keys_rd, keys_wr, keys_delay};
    uint32_t version = keys_rd(NULL, XIGUA_KEYS_CORE, 0);
    unsigned count = keys_rd(NULL, XIGUA_KEYS_CORE, 4) & 0x7ff;
    printf("XIGUA KEYS: arb=%x APIDs=%u bus=0 EE=0\n", version, count);
    if (version < 0x70000000 || version >= 0x80000000 || !count || count > 1024) {
        printf("XIGUA KEYS: unsupported arbiter; no observer command sent\n"); goto done;
    }
    struct xigua_key_channel pon = {0}, gpio = {0};
    int perr = xigua_keys_find(&io, count, 0x013, &pon);
    int gerr = xigua_keys_find(&io, count, 0x18d, &gpio);
    uint8_t subtype = 0, mode = 0, enabled = 0, ps = 0, gs = 1;
    if (!perr) perr = xigua_keys_read_byte(&io, &pon, 0x1305, &subtype);
    if (!perr && subtype != 9) perr = ENODEV;
    printf("XIGUA KEYS: PON APID=%u subtype=%x error=%d\n", pon.apid, subtype, perr);
    subtype = 0;
    if (!gerr) gerr = xigua_keys_read_byte(&io, &gpio, 0x8d05, &subtype);
    if (!gerr) gerr = xigua_keys_read_byte(&io, &gpio, 0x8d40, &mode);
    if (!gerr) gerr = xigua_keys_read_byte(&io, &gpio, 0x8d46, &enabled);
    unsigned direction = subtype >= 0x10 && subtype <= 0x13 ? mode & 3 : (mode >> 4) & 7;
    if (!gerr && (!(enabled & 0x80) || (direction != 0 && direction != 2))) gerr = ENODEV;
    printf("XIGUA KEYS: GPIO1:8d APID=%u subtype=%x mode=%x enable=%x error=%d\n",
        gpio.apid, subtype, mode, enabled, gerr);
    if (perr && gerr) goto done;
    printf("XIGUA KEYS: polling physical Power/Volume; ignore held-at-boot keys until release\n");
    struct xigua_key_filter filter[3] = {{0}};
    unsigned errors = 0;
    for (;;) {
        int pe = perr ? perr : xigua_keys_read_byte(&io, &pon, 0x1310, &ps);
        int ge = gerr ? gerr : xigua_keys_read_byte(&io, &gpio, 0x8d10, &gs);
        /* Use actual linux,input-code, not the misleading vol_up DT label:
         * resin=115 (up); GPIO6=114 (down); power=116. */
        bool state[3] = {!!(ps & 0x80), !!(ps & 0x40), !(gs & 1)};
        bool valid[3] = {!pe, !pe, !ge};
        for (unsigned k = 0; k < 3; k++) if (xigua_key_update(&filter[k], valid[k], state[k])) {
            printf("XIGUA KEYS: key=%u down=%u PON=%x GPIO6=%x valid=%u\n",
                k, filter[k].down, ps, gs, valid[k]);
            sweet_hid_key((int)k, filter[k].down);
        }
        if ((pe && !perr) || (ge && !gerr)) {
            if (!(errors++ % 100)) printf("XIGUA KEYS: read error PON=%d GPIO6=%d\n", pe, ge);
        } else errors = 0;
        keys_pause(10);
    }
done:
    thread_terminate(current_thread());
}
void xigua_keys_start(void) {
    static uint32_t started;
    uint32_t enabled = 0;
    PE_parse_boot_argn("xiguakeys", &enabled, sizeof(enabled));
    if (!enabled || __atomic_exchange_n(&started, 1, __ATOMIC_ACQ_REL)) return;
    thread_t thread;
    if (kernel_thread_start(keys_thread, NULL, &thread) == KERN_SUCCESS) thread_deallocate(thread);
    else printf("XIGUA KEYS: cannot create thread\n");
}
#endif
