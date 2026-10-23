/* Switch only the legacy request list. Keep PHY, link, clocks and LUN state
 * initialized by firmware. RSR state changes may be asynchronous. */
#ifndef XIGUA_UFS_HANDOFF_H
#define XIGUA_UFS_HANDOFF_H
static int
xigua_ufs_handoff_start(void)
{
    ufs_wr(REG_IE, 0);
    ufs_wr(REG_IS, ufs_rd(REG_IS));
    xigua_ufs_stage = "handoff-stop";
    ufs_wr(REG_UTRLRSR, 0);
    __builtin_arm_dsb(0xf);
    uint64_t deadline;
    nanoseconds_to_absolutetime(100 * NSEC_PER_MSEC, &deadline);
    deadline += mach_absolute_time();
    while (ufs_rd(REG_UTRLRSR) & 1) {
        if (mach_absolute_time() > deadline) return EBUSY;
        delay(1);
    }
    if (ufs_rd(REG_UTRLDBR)) return EBUSY;

    xigua_ufs_stage = "handoff-base";
    uint64_t list = su.dma_pa + DMA_UTRL;
    ufs_wr(REG_UTRLBA, (uint32_t)list);
    ufs_wr(REG_UTRLBAU, (uint32_t)(list >> 32));
    __builtin_arm_dsb(0xf);
    if (ufs_rd(REG_UTRLBA) != (uint32_t)list || ufs_rd(REG_UTRLBAU) != (uint32_t)(list >> 32)) return EIO;

    xigua_ufs_stage = "handoff-run";
    ufs_wr(REG_UTRLRSR, 1);
    __builtin_arm_dsb(0xf);
    nanoseconds_to_absolutetime(100 * NSEC_PER_MSEC, &deadline);
    deadline += mach_absolute_time();
    while (!(ufs_rd(REG_UTRLRSR) & 1)) {
        if (mach_absolute_time() > deadline) return EIO;
        delay(1);
    }
    if (ufs_rd(REG_UTRLBA) != (uint32_t)list || ufs_rd(REG_UTRLBAU) != (uint32_t)(list >> 32)) return EIO;
    printf("XIGUA UFS: request list takeover confirmed\n");
    return 0;
}
#endif
