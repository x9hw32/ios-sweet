"""Adapt the donor UTP/SCSI backend to an explicit SM8550 firmware handoff."""
from pathlib import Path


def apply(replace, create):
    ufs = 'bsd/dev/sweet_ufs.c'
    for name in ['xigua_ufs_verify.h', 'xigua_ufs_diag.h', 'xigua_ufs_handoff.h', 'xigua_ufs_ready.h']:
        create('bsd/dev/' + name, (Path(__file__).resolve().parent.parent / 'kernel' / name).read_text())
    replace(ufs, '#include <sys/param.h>', '''#include <sys/param.h>
#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include <pexpert/arm64/XiguaMMIO.h>
#endif''')
    replace(ufs, '} su;', '} su;\n#if defined(ARM64_BOARD_CONFIG_XIGUA)\nstatic uint32_t xigua_ufs_mode;\n#endif')
    replace(ufs, 'return *(volatile uint32_t *)(su.regs + off);', '''
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    return xigua_mmio_read32(su.regs + off);
#else
    return *(volatile uint32_t *)(su.regs + off);
#endif'''.lstrip())
    replace(ufs, '*(volatile uint32_t *)(su.regs + off) = v;', '''
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    xigua_mmio_write32(su.regs + off, v);
#else
    *(volatile uint32_t *)(su.regs + off) = v;
#endif'''.lstrip())
    for function in ['flush_dcache64', 'clean_dcache64']:
        replace(ufs, f'\t{function}((addr64_t)(su.dma_pa + off), len, TRUE);', f'''
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    /* Firmware flushed this allocation before handoff; XNU owns a single
     * Normal-NC mapping outside its managed RAM. No cached alias exists. */
    (void)off; (void)len;
    __builtin_arm_dsb(0xf);
#else
\t{function}((addr64_t)(su.dma_pa + off), len, TRUE);
#endif'''.lstrip())
    replace(ufs, 'static int\nufs_scsi(', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n#include "xigua_ufs_diag.h"\n#endif\n\nstatic int\nufs_scsi(')
    replace(ufs, '\tassert(len <= BOUNCE_SIZE);', '\tassert(len <= BOUNCE_SIZE);\n#if defined(ARM64_BOARD_CONFIG_XIGUA)\n    bzero(&xigua_ufs_last, sizeof(xigua_ufs_last));\n    xigua_ufs_last.op = cdb[0];\n    xigua_ufs_last.lun = su.lun;\n    xigua_ufs_last.ocs = 0xf;\n#endif')
    replace(ufs, '\tufs_wr(REG_IS, ufs_rd(REG_IS));         /* acknowledge completion status */', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    xigua_ufs_last.interrupt = ufs_rd(REG_IS);
#endif
\tufs_wr(REG_IS, ufs_rd(REG_IS));         /* acknowledge completion status */''')
    replace(ufs, '\tuint32_t ocs = utrd->dw2 & 0xff;', '''\tuint32_t ocs = utrd->dw2 & 0xff;
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    xigua_ufs_last.ocs = ocs;
    xigua_ufs_last.upiu = ucd->resp[0];
    xigua_ufs_last.response = ucd->resp[6];
    xigua_ufs_last.status = ucd->resp[7];
    unsigned sense_code = ucd->resp[34] & 0x7f;
    bool descriptor_sense = sense_code == 0x72 || sense_code == 0x73;
    xigua_ufs_last.key = ucd->resp[34 + (descriptor_sense ? 1 : 2)] & 15;
    xigua_ufs_last.asc = ucd->resp[34 + (descriptor_sense ? 2 : 12)];
    xigua_ufs_last.ascq = ucd->resp[34 + (descriptor_sense ? 3 : 13)];
#endif''')
    replace(ufs, '\terror = ufs_take_over_host();', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n    xigua_ufs_stage = "handoff";\n#endif\n\terror = ufs_take_over_host();')
    replace(ufs, 'static int\nufs_read_blocks(', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n#include "xigua_ufs_ready.h"\n#endif\n\nstatic int\nufs_read_blocks(')
    replace(ufs, '\t\tstatic const uint8_t tur[6] = { 0x00 };', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n        error = xigua_ufs_ready();\n#else\n\t\tstatic const uint8_t tur[6] = { 0x00 };')
    replace(ufs, '\t\tfor (int i = 0; i < 3 && (error = ufs_scsi(tur, sizeof(tur), 0, false)); i++) {\n\t\t}\n', '\t\tfor (int i = 0; i < 3 && (error = ufs_scsi(tur, sizeof(tur), 0, false)); i++) {\n\t\t}\n#endif\n')
    replace(ufs, '\t\terror = ufs_find_partition(want);', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n        xigua_ufs_stage = "gpt";\n#endif\n\t\terror = ufs_find_partition(want);')
    replace(ufs, 'static int\nufs_take_over_host(void)', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
#include "xigua_ufs_verify.h"
#include "xigua_ufs_handoff.h"
#endif

static int
ufs_take_over_host(void)''')
    replace(ufs, '\tuint32_t hce = ufs_rd(REG_HCE), hcs = ufs_rd(REG_HCS);', '''\tuint32_t hce = ufs_rd(REG_HCE), hcs = ufs_rd(REG_HCS);
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    printf("XIGUA UFS: HCE=%x HCS=%x CAP=%x VER=%x DMA=0x%llx\\n",
        hce, hcs, ufs_rd(REG_CAP), ufs_rd(0x08), su.dma_pa);
#endif''')
    replace(ufs, '\tufs_wr(REG_IE, 0);                      /* polled operation */', '#if defined(ARM64_BOARD_CONFIG_XIGUA)\n    return xigua_ufs_handoff_start();\n#else\n\tufs_wr(REG_IE, 0);                      /* polled operation */')
    replace(ufs, '\treturn 0;\n}\n\nstatic int\nsweet_ufs_open', '\treturn 0;\n#endif\n}\n\nstatic int\nsweet_ufs_open')
    replace(ufs, 'sweet_ufs_init(void)\n{\n', '''sweet_ufs_init(void)
{
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    PE_parse_boot_argn("xiguaufs", &xigua_ufs_mode, sizeof(xigua_ufs_mode));
    if (xigua_ufs_mode != 1 && xigua_ufs_mode != 2) return ENXIO;
#endif
''')
    replace(ufs, '\tchar want[64] = "userdata";', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    char want[64] = "linux";
#else
\tchar want[64] = "userdata";
#endif''')
    replace(ufs, '\tPE_parse_boot_argn("ufsroot", want, sizeof(want));', '''\tPE_parse_boot_argn("ufsroot", want, sizeof(want));
#if defined(ARM64_BOARD_CONFIG_XIGUA)
    if (strcmp(want, "linux") || reg[0] != 0x1d84000 || reg[1] != 0x3000) return EINVAL;
#endif''')
    start = '\tif (kmem_alloc_contig(kernel_map, &su.dma, DMA_SIZE, PAGE_MASK, 0, 0,'
    replace(ufs, start, '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    const void *dma_prop;
    unsigned int dma_size;
    uint64_t dma_region[2];
    if (SecureDTGetProperty(node, "dma-region", &dma_prop, &dma_size) != kSuccess ||
        dma_size != sizeof(dma_region)) return EINVAL;
    memcpy(dma_region, dma_prop, sizeof(dma_region));
    if (dma_region[0] != XIGUA_UFS_DMA_BASE || dma_region[1] != XIGUA_UFS_DMA_BYTES ||
        DMA_SIZE > dma_region[1]) return EINVAL;
    extern vm_offset_t ml_io_map_wcomb(vm_offset_t, vm_size_t);
    su.dma_pa = dma_region[0];
    su.dma = ml_io_map_wcomb(dma_region[0], dma_region[1]);
    if (!su.regs || !su.dma) return ENOMEM;
    bzero((void *)su.dma, DMA_SIZE);
#else
''' + start)
    replace(ufs, '\tsu.dma_pa = ptoa_64(pn);', '\tsu.dma_pa = ptoa_64(pn);\n#endif')
    replace(ufs, '\t\terror = ufs_find_partition(want);', '''\t\terror = ufs_find_partition(want);
#if defined(ARM64_BOARD_CONFIG_XIGUA)
        if (!error) error = xigua_ufs_verify(node, xigua_ufs_mode == 1);
#endif''')
    replace(ufs, '\tsu.writable = (rw != 0);', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    su.writable = (xigua_ufs_mode == 2 && rw != 0);
#else
\tsu.writable = (rw != 0);
#endif''')
    replace(ufs, '\tsweet_log_start();\n\tsweet_sample_start();', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    if (xigua_ufs_mode == 2) {
        sweet_log_start();
        sweet_sample_start();
    }
#else
\tsweet_log_start();
\tsweet_sample_start();
#endif''')
    replace(ufs, '\tsweet_keys_init();\n\tsweet_touch_init();\n\tsweet_usb_probe();', '''#if !defined(ARM64_BOARD_CONFIG_XIGUA)
\tsweet_keys_init();
\tsweet_touch_init();
\tsweet_usb_probe();
#endif''')
    replace(ufs, 'nent * esz > BOUNCE_SIZE', 'nent > BOUNCE_SIZE / esz')
    init = 'iokit/bsddev/IOKitBSDInit.cpp'
    replace(init, '\tif (strcmp(rdBootVar, "ufsroot0") == 0) {', '''#if defined(ARM64_BOARD_CONFIG_XIGUA)
    uint32_t ufs_probe = 0;
    PE_parse_boot_argn("xiguaufs", &ufs_probe, sizeof(ufs_probe));
    if (ufs_probe == 1) {
        extern int sweet_ufs_rootdev(dev_t *dev);
        dev_t probe_device;
        int probe_error = sweet_ufs_rootdev(&probe_device);
        extern void xigua_ufs_probe_fail(int error);
        if (probe_error) xigua_ufs_probe_fail(probe_error);
    }
#endif
\tif (strcmp(rdBootVar, "ufsroot0") == 0) {''')
