/* XIGUA / SM8550 / Synaptics S3910: polled GENI SPI -> native HID contacts.
 * Board wiring and register layouts are from the verified live DT and the
 * OnePlus Linux sources. Controller firmware must already be loaded by the
 * platform; this driver never flashes touch firmware or writes PMIC registers.
 */
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/errno.h>
#include <kern/thread.h>
#include <kern/clock.h>
#include <mach/mach_time.h>
#include <pexpert/pexpert.h>
#include <pexpert/arm64/XiguaMMIO.h>
#include "xigua_tcm.h"
#include "xigua_geni_spi.h"
#include "xigua_tcm_poll.h"

extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
extern kern_return_t thread_terminate(thread_t);
extern void sweet_hid_touch(int, int, int, int);
extern int hz;
extern int xigua_touch_vdd_on(void);
void xigua_touch_start(void);
static uintptr_t tp_se, tp_gpio, tp_gcc;
static unsigned tp_depth, tp_max_x, tp_max_y, tp_max_write = 64, tp_fw_mode;
static uint16_t tp_active;
static struct xigua_contact tp_contacts[10];
static uint8_t tp_packet[1024], tp_transfer[1027];
static int tp_sleep_channel;
static const char *tp_stage = "mapping";
static int tp_fault_logged;
static uint8_t tp_last_header[4];
static unsigned tp_header_count;

static uint32_t tp_read(unsigned reg) { return xigua_mmio_read32(tp_se + reg); }
static void tp_write(unsigned reg, uint32_t v) { xigua_mmio_write32(tp_se + reg, v); }
static void tp_pause(unsigned ms) {
    (void)tsleep(&tp_sleep_channel, PZERO, "xiguatp", MAX(1, (int)(ms * hz / 1000)));
}
static uint64_t tp_deadline(unsigned ms) {
    uint64_t t; nanoseconds_to_absolutetime((uint64_t)ms * 1000000, &t);
    return mach_absolute_time() + t;
}
static void tp_gpio_output(unsigned pin, unsigned value) {
    uintptr_t address = tp_gpio + pin * 0x1000;
    xigua_mmio_write32(address + 4, value ? 2 : 0);
    uint32_t cfg = xigua_mmio_read32(address);
    xigua_mmio_write32(address, (cfg & ~0x3ffU) | (3U << 6) | (1U << 9));
}
static int tp_attention(void) { return !(xigua_mmio_read32(tp_gpio + 25 * 0x1000 + 4) & 1); }

static int tp_fault(const char *phase, int error, unsigned opcode, unsigned sent, unsigned received) {
    if (!tp_fault_logged++ && tp_se) {
        printf("XIGUA TOUCH: failure step=%s phase=%s err=%d op=%x sent=%u rx=%u\n",
            tp_stage, phase, error, opcode, sent, received);
        printf("XIGUA TOUCH: CMD=%x IRQ=%x ACTIVE=%x TX=%x RX=%x EN=%x\n",
            tp_read(0x600), tp_read(0x610), tp_read(0x40), tp_read(0x800), tp_read(0x804), tp_read(0x614));
        printf("XIGUA TOUCH: MCLK=%x SEL=%x IOS=%x TOP=%x GPIO25=%x\n",
            tp_read(0x48), tp_read(0x7c), tp_read(0x908), tp_read(0xe1c),
            xigua_mmio_read32(tp_gpio + 25 * 0x1000 + 4));
        printf("XIGUA TOUCH: HDR=%02x/%02x/%02x/%02x GPIO10=%x/%x GPIO24=%x/%x IRQCFG=%x\n",
            tp_last_header[0], tp_last_header[1], tp_last_header[2], tp_last_header[3],
            xigua_mmio_read32(tp_gpio + 10 * 0x1000), xigua_mmio_read32(tp_gpio + 10 * 0x1000 + 4),
            xigua_mmio_read32(tp_gpio + 24 * 0x1000), xigua_mmio_read32(tp_gpio + 24 * 0x1000 + 4),
            xigua_mmio_read32(tp_gpio + 25 * 0x1000));
    }
    return error;
}

static int tp_command(unsigned opcode, unsigned parameters) {
    tp_write(0x618, ~0U);
    tp_write(0x600, (opcode << 27) | parameters);
    uint64_t deadline = tp_deadline(100);
    for (;;) {
        uint32_t status = tp_read(0x610);
        if (status & 0xe) return tp_fault("command", EIO, opcode, 0, 0);
        if (status & 1) { tp_write(0x618, status); return 0; }
        if (mach_absolute_time() > deadline) {
            tp_fault("command", ETIMEDOUT, opcode, 0, 0);
            tp_write(0x604, 2); return ETIMEDOUT;
        }
        delay(1);
    }
}

static int tp_spi(const uint8_t *tx, uint8_t *rx, unsigned size) {
    if (!size || size > sizeof(tp_transfer)) return EINVAL;
    int error = tp_command(8, 0); /* manual CS assert */
    if (error) return error;
    tp_write(0x26c, size);
    tp_write(0x270, rx ? size : 0);
    tp_write(0x618, ~0U);
    tp_write(0x600, ((rx ? 3U : 1U) << 27) | 4U); /* full duplex / TX, keep CS */
    unsigned sent = 0, received = 0;
    uint64_t deadline = tp_deadline(100);
    for (;;) {
        unsigned used = tp_read(0x800) & 0xffffff;
        if (used > tp_depth) { error = EIO; break; }
        for (unsigned slots = tp_depth - used; slots && sent < size; slots--) {
            uint32_t word = ~0U;
            for (unsigned byte = 0; byte < 4 && sent < size; byte++, sent++) {
                unsigned value = tx ? tx[sent] : 0xff;
                word = (word & ~(0xffU << (byte * 8))) | (value << (byte * 8));
            }
            tp_write(0x700, word);
        }
        unsigned words = tp_read(0x804) & 0xffffff;
        if (words > tp_depth) { error = EIO; break; }
        while (words--) {
            uint32_t word = tp_read(0x780);
            for (unsigned byte = 0; byte < 4 && received < size; byte++, received++)
                if (rx) rx[received] = (uint8_t)(word >> (byte * 8));
        }
        uint32_t status = tp_read(0x610);
        if (status & (0xeU | (3U << 24) | (3U << 28))) { error = EIO; break; }
        if ((status & 1) && sent == size && (!rx || received == size)) break;
        if (mach_absolute_time() > deadline) { error = ETIMEDOUT; break; }
        delay(1);
    }
    if (error) {
        tp_fault("fifo", error, rx ? 3 : 1, sent, received);
        tp_write(0x604, 2);
    }
    tp_write(0x618, ~0U);
    int cs_error = tp_command(9, 0);
    return error ? error : cs_error;
}

static int tp_message(unsigned *code, unsigned *length) {
    uint8_t header[4];
    int error = tp_spi(NULL, header, sizeof(header));
    if (error) return error;
    memcpy(tp_last_header, header, sizeof(header));
    if (tp_header_count++ < 4) printf("XIGUA TOUCH: bus read=%02x/%02x/%02x/%02x ATTN=%u\n",
        header[0], header[1], header[2], header[3], tp_attention());
    if (header[0] != 0xa5) {
        if ((!header[0] && !header[1] && !header[2] && !header[3]) ||
            (header[0] == 255 && header[1] == 255 && header[2] == 255 && header[3] == 255)) return EAGAIN;
        return EIO;
    }
    *code = header[1]; *length = xigua_le16(header + 2);
    if (*length > sizeof(tp_packet)) return EMSGSIZE;
    if (!*length) return 0;
    /* Continued reads carry their own marker/status, then payload and padding. */
    error = tp_spi(NULL, tp_transfer, *length + 3);
    if (error) return error;
    if (tp_transfer[0] != 0xa5 || tp_transfer[1] != 3 || tp_transfer[*length + 2] != 0x5a) return EIO;
    memcpy(tp_packet, tp_transfer + 2, *length);
    return 0;
}

static void tp_identify(unsigned length) {
    if (length < 24) return;
    tp_fw_mode = tp_packet[1];
    unsigned maximum = xigua_le16(tp_packet + 22);
    if (maximum >= 4) tp_max_write = MIN(maximum, sizeof(tp_transfer));
    printf("XIGUA TOUCH: TCM version=%u mode=%u max-write=%u\n",
        tp_packet[0], tp_fw_mode, tp_max_write);
}

static int tp_poll_read(void *context, unsigned *code, unsigned *length) {
    (void)context;
    int error = tp_message(code, length);
    if (!error && *code >= 8 && *code < 0x10) printf("XIGUA TOUCH: command status=%x\n", *code);
    return error;
}
static unsigned tp_poll_identify(void *context, unsigned length) {
    (void)context; tp_identify(length); return tp_fw_mode;
}
static void tp_poll_pause(void *context) { (void)context; tp_pause(5); }
static bool tp_poll_expired(void *context) { return mach_absolute_time() >= *(const uint64_t *)context; }

static int tp_request(unsigned command, const uint8_t *data, unsigned size, unsigned *reply_size) {
    if (size > sizeof(tp_transfer) - 3) return EMSGSIZE;
    unsigned offset = 0, packet_size;
    int error;
    do {
        packet_size = xigua_tcm_write_chunk(command, data, size, offset,
            tp_max_write, tp_transfer, &offset);
        if (!packet_size) return EINVAL;
        error = tp_spi(tp_transfer, NULL, packet_size);
        if (error) return error;
        if (offset < size) delay(200);
    } while (offset < size);
    uint64_t deadline = tp_deadline(1000);
    const struct xigua_tcm_poll_ops ops = {
        &deadline, tp_poll_read, tp_poll_identify, tp_poll_pause, tp_poll_expired
    };
    error = xigua_tcm_poll_response(&ops, command, reply_size);
    return error ? tp_fault("tcm-response", error, command, size, 0) : 0;
}

static int tp_setup(void) {
    tp_gcc = ml_io_map(0x100000, 0x60000);
    tp_gpio = ml_io_map(0xf100000, 0x100000);
    tp_se = ml_io_map(0xa90000, 0x4000);
    if (!tp_gcc || !tp_gpio || !tp_se) return ENOMEM;
    /* Only the selected serial engine and wrapper AHB votes, preserve others. */
    tp_stage = "clock-votes";
    uintptr_t vote = tp_gcc + 0x52008;
    xigua_mmio_write32(vote, xigua_mmio_read32(vote) | (1U << 26) | (3U << 20));
    uint64_t deadline = tp_deadline(100);
    while ((xigua_mmio_read32(tp_gcc + 0x184e4) & (1U << 31)) && mach_absolute_time() < deadline) delay(1);
    if (xigua_mmio_read32(tp_gcc + 0x184e4) & (1U << 31)) return ETIMEDOUT;
    tp_stage = "spi-firmware";
    unsigned firmware = tp_read(0x68);
    printf("XIGUA TOUCH: SPI firmware=%x status=%x\n", firmware, tp_read(0x40));
    if (((firmware >> 8) & 0xff) != 1 || (tp_read(0x40) & 1)) return ENXIO;
    tp_depth = (tp_read(0xe24) >> 16) & 0xff;
    if (tp_depth < 4 || tp_depth > 256 || ((tp_read(0xe24) >> 24) & 0x3f) != 32) return ENXIO;
    tp_stage = "pinmux";
    for (unsigned pin = 44; pin <= 47; pin++) {
        uintptr_t address = tp_gpio + pin * 0x1000;
        uint32_t cfg = xigua_mmio_read32(address);
        xigua_mmio_write32(address, (cfg & ~0x1ffU) | (1U << 2) | (2U << 6));
    }
    uintptr_t irq_cfg = tp_gpio + 25 * 0x1000;
    xigua_mmio_write32(irq_cfg, (xigua_mmio_read32(irq_cfg) & ~0x3ffU) | (3U << 6) | 3U);
    xigua_mmio_write32(irq_cfg + 8, xigua_mmio_read32(irq_cfg + 8) & ~1U);
    tp_stage = "fifo-setup";
    xigua_geni_spi_polling(tp_write);
    tp_write(0x28, tp_read(0x28) | 0x7f); tp_write(0xe30, tp_read(0xe30) | 0xf);
    tp_write(0x24, 0x7f); tp_write(0x20, 1);
    tp_write(0x48, (64U << 4) | 1U); /* conservative divider, existing parent */
    tp_write(0x224, 0); tp_write(0x22c, 0); tp_write(0x230, 0);
    tp_write(0x24c, 0); tp_write(0x250, 0); tp_write(0x25c, tp_read(0x25c) & ~1U);
    tp_write(0x268, 4); tp_write(0x254, 0); /* 8-bit SPI, four bytes/FIFO word */
    uint32_t packing[4];
    for (unsigned i = 0; i < 4; i++) packing[i] = ((7 + i * 8) << 5) | 0x10 | (7 << 1) | (i == 3);
    tp_write(0x260, packing[0] | (packing[1] << 10)); tp_write(0x264, packing[2] | (packing[3] << 10));
    tp_write(0x284, packing[0] | (packing[1] << 10)); tp_write(0x288, packing[2] | (packing[3] << 10));
    tp_write(0x80c, 0); tp_write(0x810, 1); tp_write(0x814, tp_depth - 2);
    tp_write(0x618, ~0U); tp_write(0x648, ~0U);
    tp_stage = "power-reset";
    tp_gpio_output(10, 1);
    tp_stage = "vdd-1v8";
    int error = xigua_touch_vdd_on();
    if (error) return error;
    tp_pause(200);
    tp_gpio_output(24, 0); tp_pause(10); tp_gpio_output(24, 1); tp_pause(80);
    tp_stage = "reset-identify";
    /* Like Linux detect_device, read SPI directly; ATTN is not a prerequisite. */
    for (unsigned retry = 0; retry < 5 && !tp_fw_mode; retry++) {
        unsigned code, length;
        error = tp_message(&code, &length);
        if (error && error != EAGAIN) return error;
        if (!error && code == 0x10) tp_identify(length);
        if (!tp_fw_mode) tp_pause(20);
    }
    unsigned length = 0;
    if (!tp_fw_mode) {
        tp_stage = "identify-command";
        error = tp_request(2, NULL, 0, &length);
        if (error) return error;
        if (!tp_fw_mode) return EIO;
    }
    if (tp_fw_mode && tp_fw_mode != 1) {
        tp_stage = "run-application";
        error = tp_request(0x14, NULL, 0, NULL); /* run installed application */
        if (error) return error;
        tp_pause(200);
    }
    for (unsigned retry = 0; ; retry++) {
        tp_stage = "application-info";
        error = tp_request(0x20, NULL, 0, &length); /* application information */
        if (error) return error;
        if (length < 38) return EIO;
        if (!xigua_le16(tp_packet + 2)) break;
        if (retry == 10) return EIO;
        tp_pause(200);
    }
    tp_max_x = xigua_le16(tp_packet + 32); tp_max_y = xigua_le16(tp_packet + 34);
    unsigned config_size = xigua_le16(tp_packet + 12);
    if (!tp_max_x || !tp_max_y || config_size < sizeof(xigua_tcm_report_config) || config_size > 512) return EINVAL;
    printf("XIGUA TOUCH: S3910 app raw=%ux%u objects=%u config=%u\n",
        tp_max_x, tp_max_y, xigua_le16(tp_packet + 36), config_size);
    const uint8_t hbp = 0x23, lbp[] = {0x11, 2, 0};
    tp_stage = "disable-hbp";
    error = tp_request(0x06, &hbp, 1, NULL); /* disable HBP raw frames */
    if (error) return error;
    tp_stage = "lbp-mode";
    error = tp_request(0x24, lbp, sizeof(lbp), NULL);
    if (error) return error;
    uint8_t config[512]; bzero(config, config_size);
    memcpy(config, xigua_tcm_report_config, sizeof(xigua_tcm_report_config));
    tp_stage = "report-config";
    error = tp_request(0x26, config, config_size, NULL);
    if (error) return error;
    const uint8_t touch = 0x11;
    tp_stage = "enable-coordinate-reports";
    return tp_request(0x05, &touch, 1, NULL);
}

static void tp_release(void) {
    for (int i = 0; i < 10; i++) if (tp_active & (1U << i))
        sweet_hid_touch(i, 0, tp_contacts[i].x, tp_contacts[i].y);
    tp_active = 0;
}

static void tp_thread(void *arg, wait_result_t result) {
    (void)arg; (void)result;
    tp_pause(1000);
    int error = tp_setup();
    if (error) { printf("XIGUA TOUCH: initialization stopped: %d\n", error); goto done; }
    printf("XIGUA TOUCH: coordinate reports enabled, GPIO25 polling\n");
    unsigned errors = 0, reports = 0;
    for (;;) {
        if (!tp_attention()) { tp_pause(5); continue; }
        unsigned code, length;
        error = tp_message(&code, &length);
        uint16_t active = 0;
        if (!error && code == 0x11) {
            struct xigua_contact contacts[10] = {{0}};
            error = xigua_tcm_contacts(tp_packet, length, tp_max_x, tp_max_y,
                1240, 2772, contacts, &active) ? EINVAL : 0;
            if (!error) {
                uint16_t previous_active = tp_active;
                for (int i = 0; i < 10; i++) {
                    if (active & (1U << i)) sweet_hid_touch(i, 1, contacts[i].x, contacts[i].y);
                    else if (tp_active & (1U << i)) sweet_hid_touch(i, 0, tp_contacts[i].x, tp_contacts[i].y);
                }
                tp_active = active; memcpy(tp_contacts, contacts, sizeof(contacts));
                if (reports++ < 8 || active != previous_active) {
                    unsigned first = 0;
                    while (first < 9 && !(active & (1U << first))) first++;
                    printf("XIGUA TOUCH: report %u contacts=%x point=%u,%u\n",
                        reports, active, contacts[first].x, contacts[first].y);
                }
            }
        }
        if (error) {
            if (++errors == 1) printf("XIGUA TOUCH: read error %d\n", error);
            tp_release();
            if (errors >= 8) break;
            tp_pause(20);
        } else errors = 0;
        tp_pause(5);
    }
done:
    tp_release();
    thread_terminate(current_thread());
}

void xigua_touch_start(void) {
    static uint32_t started;
    uint32_t on = 0;
    PE_parse_boot_argn("xiguatouch", &on, sizeof(on));
    if (!on || __atomic_exchange_n(&started, 1, __ATOMIC_ACQ_REL)) return;
    thread_t thread;
    if (kernel_thread_start(tp_thread, NULL, &thread) == KERN_SUCCESS) thread_deallocate(thread);
    else printf("XIGUA TOUCH: cannot start polling thread\n");
}
#endif
