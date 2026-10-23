/* TouchCom command polling must clock the bus even when ATTN stays high.
 * OnePlus's polling path calls read_message periodically, not only on IRQ.
 */
#ifndef XIGUA_TCM_POLL_H
#define XIGUA_TCM_POLL_H
#include <stdbool.h>
struct xigua_tcm_poll_ops {
    void *context;
    int (*read)(void *, unsigned *, unsigned *);
    unsigned (*identify)(void *, unsigned);
    void (*pause)(void *);
    bool (*expired)(void *);
};
static int
xigua_tcm_poll_response(const struct xigua_tcm_poll_ops *ops, unsigned command, unsigned *reply_size)
{
    while (!ops->expired(ops->context)) {
        ops->pause(ops->context);
        unsigned code = 0, length = 0;
        int error = ops->read(ops->context, &code, &length);
        if (error == EAGAIN) continue;
        if (error) return error;
        if (code == 0x10) {
            unsigned mode = ops->identify(ops->context, length);
            if (command == 2 || (command == 0x14 && mode == 1)) {
                if (reply_size) *reply_size = length;
                return 0;
            }
        }
        if (code == 1) {
            if (command == 2) (void)ops->identify(ops->context, length);
            if (reply_size) *reply_size = length;
            return 0;
        }
        if (code >= 8 && code < 0x10) return EIO;
    }
    return ETIMEDOUT;
}
#endif
