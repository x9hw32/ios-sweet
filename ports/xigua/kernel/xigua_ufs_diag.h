/* Keep the failed stage and response in the final panic, even after the
 * framebuffer scrolls away the initial host/SCSI messages. No disk writes. */
#ifndef XIGUA_UFS_DIAG_H
#define XIGUA_UFS_DIAG_H
static const char *xigua_ufs_stage = "setup";
static struct {
    uint32_t op, lun, ocs, upiu, response, status, key, asc, ascq, interrupt;
} xigua_ufs_last;
void xigua_ufs_probe_fail(int error);
void
xigua_ufs_probe_fail(int error)
{
    if (su.regs) {
        printf("XIGUA UFS: failure host HCE=%x HCS=%x IS=%x list=%x:%08x RSR=%x DBR=%x\n",
            ufs_rd(REG_HCE), ufs_rd(REG_HCS), ufs_rd(REG_IS),
            ufs_rd(REG_UTRLBAU), ufs_rd(REG_UTRLBA), ufs_rd(REG_UTRLRSR), ufs_rd(REG_UTRLDBR));
    }
    panic("XIGUA UFS: %s err=%d op=%02x lun=%02x ocs=%x upiu=%02x rsp=%02x st=%02x sense=%02x/%02x/%02x IS=%x",
        xigua_ufs_stage, error, xigua_ufs_last.op, xigua_ufs_last.lun, xigua_ufs_last.ocs,
        xigua_ufs_last.upiu, xigua_ufs_last.response, xigua_ufs_last.status,
        xigua_ufs_last.key, xigua_ufs_last.asc, xigua_ufs_last.ascq, xigua_ufs_last.interrupt);
}
#endif
