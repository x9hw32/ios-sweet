"""Validate the real CRC probe against independent data and DT bounds."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from make_profile import qemu_profile
from mkadt_xigua import make, adt, mkadt


class UFSHandoffTests(unittest.TestCase):
    def profile(self):
        p = qemu_profile()
        p['kind'] = 'phone'
        p['ufs'] = dict(reg=[0x1d84000, 0x3000], dma_region=[0xc4000000, 0x200000],
                        mode=1, probe_offsets=[0, 0x180000000, 0x2ffc00000], probe_crcs=[1, 2, 3])
        return p

    def test_ufs_node_carries_firmware_dma_and_probe_identity(self):
        with patch.object(mkadt, 'd22ap_product', return_value=None):
            tree, _ = adt.parse(make(self.profile()))
        node = next(n for n in tree.children if n.name == 'sweet-ufs')
        self.assertEqual(struct.unpack('<2Q', node.prop('dma-region')), (0xc4000000, 0x200000))
        self.assertEqual(struct.unpack('<3Q', node.prop('probe-offsets')), (0, 0x180000000, 0x2ffc00000))

    def test_unknown_hardware_and_out_of_root_samples_are_rejected(self):
        for field, value in [('dma_region', [0xb8000000, 0x200000]),
                             ('reg', [0x1d84000, 0x9000]),
                             ('probe_offsets', [0, 0x180000000, 0x300000000])]:
            p = self.profile(); p['ufs'][field] = value
            with patch.object(mkadt, 'd22ap_product', return_value=None):
                with self.assertRaises(ValueError):
                    make(p)

    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_real_probe_matches_zlib_and_rejects_corruption_and_bad_geometry(self):
        offsets = [0, 0x180000000, 0x2ffc00000]
        expected = []
        for offset in offsets:
            data = bytearray()
            for i in range(4):
                data += bytes([(offset // 0x100000 + i) % 251]) * 0x100000
            if offset == 0:
                data[1024:1028] = b'HX\0\5'
            expected.append(zlib.crc32(data))
        source = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define printf(...) ((void)0)
#define UFS_BLOCK 4096u
#define BOUNCE_SIZE 0x100000u
#define DMA_BOUNCE 0x4000u
#define kSuccess 1
typedef void *DTEntry;
static struct { uint64_t nblocks, first_block; uintptr_t dma; } su;
static uint64_t offsets[3] = {0, 0x180000000ULL, 0x2ffc00000ULL};
static uint32_t crcs[3] = {CRCS};
static unsigned reads;
static bool bad_header;
static int SecureDTGetProperty(DTEntry node, const char *name, const void **value, unsigned *size) {
    (void)node;
    if (!strcmp(name,"probe-offsets")) { *value=offsets; *size=sizeof(offsets); }
    else if (!strcmp(name,"probe-crcs")) { *value=crcs; *size=sizeof(crcs); }
    else return 0;
    return kSuccess;
}
static int ufs_read_blocks(uint64_t lba, uint32_t count) {
    assert(lba >= su.first_block && count && count <= BOUNCE_SIZE/UFS_BLOCK);
    uint64_t offset=(lba-su.first_block)*UFS_BLOCK;
    assert(offset <= 0x300000000ULL-count*UFS_BLOCK);
    uint8_t *b=(void *)(su.dma+DMA_BOUNCE);
    memset(b,(offset/0x100000)%251,count*UFS_BLOCK);
    if (!offset) memcpy(b+1024,bad_header ? "BAD!" : "HX\0\5",4);
    reads++;
    return 0;
}
#include "xigua_ufs_verify.h"
int main(void) {
    su.nblocks=XIGUA_UFS_PARTITION_BYTES/UFS_BLOCK; su.first_block=0x10000;
    su.dma=(uintptr_t)calloc(1,DMA_BOUNCE+BOUNCE_SIZE); assert(su.dma);
    assert(xigua_ufs_verify(0,true)==0); assert(reads==13);
    crcs[1]^=1; reads=0;
    assert(xigua_ufs_verify(0,true)==EIO); assert(reads==9);
    crcs[1]^=1; su.nblocks--; reads=0;
    assert(xigua_ufs_verify(0,true)==ENXIO); assert(!reads); su.nblocks++;
    offsets[2]=0x300000000ULL;
    assert(xigua_ufs_verify(0,true)==EINVAL); offsets[2]=0x2ffc00000ULL;
    bad_header=true; assert(xigua_ufs_verify(0,true)==EINVAL);
    bad_header=false; crcs[0]^=1; reads=0;
    assert(xigua_ufs_verify(0,false)==0); assert(reads==1);
    free((void *)su.dma);
}
'''.replace('CRCS', ','.join(str(v) + 'U' for v in expected))
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory); (p / 'probe.c').write_text(source)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(p / 'probe.c'), '-o', str(p / 'probe')],
                           check=True, capture_output=True)
            subprocess.run([str(p / 'probe')], check=True, capture_output=True)
