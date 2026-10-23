/* Run under sweet_ufs_lock, before exposing the disk. Firmware may leave the
 * device stopped at ExitBootServices. UFS power conditions use START STOP UNIT
 * on DEVICE WLUN 0xd0 (not RPMB 0xc4), with ACTIVE=1 in CDB byte 4 bits 7:4.
 * No block writes, mode pages, format commands or link resets are issued.
 */
#ifndef XIGUA_UFS_READY_H
#define XIGUA_UFS_READY_H
static bool
xigua_ufs_check_condition(void)
{
    return xigua_ufs_last.ocs == 0 && xigua_ufs_last.upiu == 0x21 &&
        xigua_ufs_last.response <= 1 && xigua_ufs_last.status == 2;
}

static int
xigua_ufs_activate(void)
{
    static const uint8_t active[6] = {0x1b, 0, 0, 0, 0x10, 0};
    uint8_t saved_lun = su.lun;
    int error = EIO;
    xigua_ufs_stage = "activate";
    su.lun = 0xd0;
    for (unsigned attempt = 0; attempt < 3; attempt++) {
        error = ufs_scsi(active, sizeof(active), 0, false);
        if (!error || !xigua_ufs_check_condition() || xigua_ufs_last.key != 6) break;
        delay(10000);
    }
    su.lun = saved_lun;
    return error;
}

static int
xigua_ufs_ready(void)
{
    static const uint8_t tur[6] = {0};
    bool activated = false;
    unsigned attentions = 0;
    uint64_t deadline = 0;
    for (;;) {
        xigua_ufs_stage = activated ? "ready-wait" : "ready";
        int error = ufs_scsi(tur, sizeof(tur), 0, false);
        if (!error) return 0;
        if (!xigua_ufs_check_condition()) return error;
        if (xigua_ufs_last.key == 6) {
            if (++attentions >= 3) return error;
            delay(10000);
            continue;
        }
        if (xigua_ufs_last.key != 2 || xigua_ufs_last.asc != 4 ||
            (xigua_ufs_last.ascq != 1 && xigua_ufs_last.ascq != 2)) return error;
        if (!activated && xigua_ufs_last.ascq == 2) {
            printf("XIGUA UFS: NOT READY 04/02; activating DEVICE WLUN d0\n");
            error = xigua_ufs_activate();
            if (error) return error;
            activated = true;
        }
        if (!deadline) {
            nanoseconds_to_absolutetime(2 * NSEC_PER_SEC, &deadline);
            deadline += mach_absolute_time();
        }
        xigua_ufs_stage = "ready-wait";
        if (mach_absolute_time() >= deadline) return ETIMEDOUT;
        delay(100000);
    }
}
#endif
