/* XIGUA's allocated linux partition; included after the generic read helper.
 * Probe mode reads three independently checksummed 4 MiB regions. Root mode
 * permits a filesystem changed by previous iOS boots, so checks its header.
 */
#ifndef XIGUA_UFS_VERIFY_H
#define XIGUA_UFS_VERIFY_H
#define XIGUA_UFS_PARTITION_BYTES 77137424384ULL
#define XIGUA_UFS_ROOT_BYTES 0x300000000ULL
#define XIGUA_UFS_DMA_BASE 0xc4000000ULL
#define XIGUA_UFS_DMA_BYTES 0x200000ULL

static uint32_t
xigua_ufs_crc32(uint32_t crc, const uint8_t *data, uint32_t size)
{
    for (uint32_t i = 0; i < size; i++) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; bit++)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return crc;
}

static int
xigua_ufs_verify(DTEntry node, bool full_probe)
{
    if (su.nblocks != XIGUA_UFS_PARTITION_BYTES / UFS_BLOCK || !su.first_block) {
        printf("XIGUA UFS: linux partition geometry mismatch\n");
        return ENXIO;
    }
#ifdef XIGUA_UFS_DIAG_H
    xigua_ufs_stage = "root-header";
#endif
    int error = ufs_read_blocks(su.first_block, 1);
    if (error) return error;
    const uint8_t *header = (const uint8_t *)(su.dma + DMA_BOUNCE + 1024);
    if (memcmp(header, "HX\0\5", 4)) {
        printf("XIGUA UFS: linux does not contain the prepared HFSX root\n");
        return EINVAL;
    }
    if (!full_probe) return 0;

    const void *offset_prop, *crc_prop;
    unsigned int offset_size, crc_size;
    if (SecureDTGetProperty(node, "probe-offsets", &offset_prop, &offset_size) != kSuccess ||
        SecureDTGetProperty(node, "probe-crcs", &crc_prop, &crc_size) != kSuccess ||
        offset_size != 3 * sizeof(uint64_t) || crc_size != 3 * sizeof(uint32_t)) {
        return EINVAL;
    }
#ifdef XIGUA_UFS_DIAG_H
    xigua_ufs_stage = "root-crc";
#endif
    for (unsigned sample = 0; sample < 3; sample++) {
        uint64_t offset;
        uint32_t expected;
        memcpy(&offset, (const uint8_t *)offset_prop + sample * 8, 8);
        memcpy(&expected, (const uint8_t *)crc_prop + sample * 4, 4);
        if (offset % UFS_BLOCK || offset > XIGUA_UFS_ROOT_BYTES - 0x400000) return EINVAL;
        uint32_t crc = ~0U;
        for (uint32_t done = 0; done < 0x400000; done += BOUNCE_SIZE) {
            error = ufs_read_blocks(su.first_block + (offset + done) / UFS_BLOCK,
                BOUNCE_SIZE / UFS_BLOCK);
            if (error) return error;
            crc = xigua_ufs_crc32(crc, (const uint8_t *)(su.dma + DMA_BOUNCE), BOUNCE_SIZE);
        }
        crc = ~crc;
        printf("XIGUA UFS: sample %u offset=0x%llx CRC=%08x expected=%08x\n",
            sample, offset, crc, expected);
        if (crc != expected) return EIO;
    }
    printf("XIGUA UFS: READ CHECK PASS, 3 x 4 MiB match; disk writes disabled\n");
    return 0;
}
#endif
