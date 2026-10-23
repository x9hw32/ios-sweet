"""Validate recovery from actual 02/04/02 sense without enabling block writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class UFSReadyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_device_wlun_activation_readiness_and_failure_bounds(self):
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>
#define NSEC_PER_SEC 1000000000ULL
#define printf(...) ((void)0)
static struct {uint8_t lun;} su;
static struct {unsigned op,lun,ocs,upiu,response,status,key,asc,ascq;} xigua_ufs_last;
static const char *xigua_ufs_stage;
static unsigned scenario, tur_count, starts;
static uint64_t tick;
static uint64_t mach_absolute_time(void) {return ++tick;}
static void nanoseconds_to_absolutetime(uint64_t ns,uint64_t *out) {*out=ns/1000000;}
static void delay(unsigned us) {tick+=us/1000;}
static int sense(unsigned key,unsigned asc,unsigned ascq) {
    xigua_ufs_last.response=1; xigua_ufs_last.status=2;
    xigua_ufs_last.key=key; xigua_ufs_last.asc=asc; xigua_ufs_last.ascq=ascq;
    return EIO;
}
static int ufs_scsi(const uint8_t *cmd,unsigned n,uint32_t size,bool write) {
    assert(n==6 && !size && !write);
    memset(&xigua_ufs_last,0,sizeof(xigua_ufs_last));
    xigua_ufs_last.op=cmd[0];xigua_ufs_last.lun=su.lun;xigua_ufs_last.upiu=0x21;
    if(cmd[0]==0x1b) {
        const uint8_t active[]={0x1b,0,0,0,0x10,0};
        assert(su.lun==0xd0 && !memcmp(cmd,active,6));
        starts++;
        if(scenario==2 && starts==1) return sense(6,0x29,0);
        if(scenario==3) return sense(5,0x20,0);
        return 0;
    }
    assert(cmd[0]==0 && su.lun==0);
    tur_count++;
    if(scenario==0) return 0;
    if(scenario==4) {xigua_ufs_last.ocs=7;return EIO;}
    if(scenario==5) return sense(2,4,3);
    if(scenario==6) return sense(2,4,1);
    if(scenario==7) return sense(6,0x29,0);
    if(!starts) return sense(2,4,2); /* Phone probe2's exact response. */
    if(scenario==1 && tur_count<4) return sense(2,4,1);
    return 0;
}
#include "xigua_ufs_ready.h"
static void reset(unsigned s) {scenario=s;su.lun=0;tur_count=starts=0;tick=0;}
int main(void) {
    reset(0);assert(!xigua_ufs_ready());assert(tur_count==1 && !starts);
    reset(1);assert(!xigua_ufs_ready());assert(tur_count==4 && starts==1 && su.lun==0);
    reset(2);assert(!xigua_ufs_ready());assert(starts==2 && su.lun==0);
    reset(3);assert(xigua_ufs_ready()==EIO);assert(starts==1 && su.lun==0);
    assert(!strcmp(xigua_ufs_stage,"activate") && xigua_ufs_last.lun==0xd0);
    reset(4);assert(xigua_ufs_ready()==EIO);assert(tur_count==1 && !starts);
    reset(5);assert(xigua_ufs_ready()==EIO);assert(tur_count==1 && !starts);
    reset(6);assert(xigua_ufs_ready()==ETIMEDOUT);assert(tick<2200 && !starts);
    reset(7);assert(xigua_ufs_ready()==EIO);assert(tur_count==3 && !starts);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'ready.c'
            binary = Path(tmp) / 'ready'
            src.write_text(code)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(src), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
