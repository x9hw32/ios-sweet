"""Check configured TouchCom wire packets against known contacts and FW limits."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class TouchComTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_contact_lifecycle_bounds_and_chunk_reassembly(self):
        code = r'''
#include <assert.h>
#include <string.h>
#include "xigua_tcm.h"
int main(void) {
    struct xigua_contact points[10] = {{0}};
    uint16_t mask = 0xffff;
    /* Finger 0 at the top left, glove 9 at the bottom right, palm 4 ignored. */
    const uint8_t packet[] = {3, 0x10,0,0,0,0,20,
        0x29,0x80,0x4d,0x40,0xad,100, 0x64,0,0,0,0,0};
    assert(!xigua_tcm_contacts(packet,sizeof(packet),19840,44352,1240,2772,points,&mask));
    assert(mask == 0x201 && points[0].x == 0 && points[0].y == 0);
    assert(points[9].x == 1239 && points[9].y == 2771);
    const uint8_t middle[] = {1,0x13,0xc0,0x26,0xa0,0x56,50};
    assert(!xigua_tcm_contacts(middle,sizeof(middle),19840,44352,1240,2772,points,&mask));
    assert(mask == 8 && points[3].x == 619 && points[3].y == 1385);
    const uint8_t empty[] = {0};
    assert(!xigua_tcm_contacts(empty,1,19840,44352,1240,2772,points,&mask));
    assert(!mask); /* Driver releases every previous contact. */
    uint8_t bad[sizeof(packet)]; memcpy(bad,packet,sizeof(bad));
    bad[7]=0x20; /* Duplicate index 0. */
    assert(xigua_tcm_contacts(bad,sizeof(bad),19840,44352,1240,2772,points,&mask));
    bad[7]=0x2a; /* Index 10 exceeds the HID slots. */
    assert(xigua_tcm_contacts(bad,sizeof(bad),19840,44352,1240,2772,points,&mask));
    for (unsigned n=0;n<sizeof(packet);n++)
        assert(xigua_tcm_contacts(packet,n,19840,44352,1240,2772,points,&mask));
    assert(xigua_tcm_contacts(packet,sizeof(packet),0,44352,1240,2772,points,&mask));
    const uint8_t overflow[] = {1,0x10,255,255,255,255,1};
    assert(!xigua_tcm_contacts(overflow,sizeof(overflow),19840,44352,1240,2772,points,&mask));
    assert(points[0].x==1239 && points[0].y==2771);
    /* Independent receiver reconstructs a 512-byte SET_REPORT_CONFIG command
     * with firmware buffer sizes crossing both first/continued boundaries. */
    uint8_t payload[512], bus[1027], received[512];
    for (unsigned i=0;i<512;i++) payload[i]=(uint8_t)(i*37);
    for (unsigned limit=4;limit<520;limit++) {
        unsigned offset=0, count=0, expected_size=0;
        do {
            unsigned start=offset;
            unsigned n=xigua_tcm_write_chunk(0x26,payload,512,offset,limit,bus,&offset);
            assert(n && n<=limit && offset>start);
            unsigned prefix= count ? 1 : 3;
            if (!count) { assert(bus[0]==0x26); expected_size=bus[1]+256U*bus[2]; }
            else assert(bus[0]==1);
            memcpy(received+count,bus+prefix,n-prefix); count+=n-prefix;
        } while(offset<512);
        assert(expected_size==512 && count==512 && !memcmp(payload,received,512));
    }
    unsigned next=123;
    assert(xigua_tcm_write_chunk(0x20,0,0,0,64,bus,&next)==3 && next==0);
    assert(bus[0]==0x20 && !bus[1] && !bus[2]);
    assert(!xigua_tcm_write_chunk(0x26,payload,512,0,3,bus,&next));
    assert(!xigua_tcm_write_chunk(0x26,payload,512,513,64,bus,&next));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'touch.c'
            binary = Path(tmp) / 'touch'
            source.write_text(code)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
