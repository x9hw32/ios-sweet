/* GENI local IRQ enables also gate the polled command/FIFO status. Keep
 * external IRQ routing disabled; no GIC registration is required here.
 * Event definitions match the OnePlus qcom-geni-se initialization path.
 */
#ifndef XIGUA_GENI_SPI_H
#define XIGUA_GENI_SPI_H
#include <stdint.h>
#define XIGUA_GENI_LOCAL_EVENTS (0x7fU | (0x1ffU << 22))
static inline void
xigua_geni_spi_polling(void (*write_reg)(unsigned, uint32_t))
{
    write_reg(0xe18, 0); /* GSI */
    write_reg(0xe1c, 0); /* external IRQ routing */
    write_reg(0x258, 0); /* FIFO, not DMA */
    write_reg(0x644, 0); /* no secondary sequencer */
    write_reg(0x614, XIGUA_GENI_LOCAL_EVENTS);
}
#endif
