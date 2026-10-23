"""Exercise actual handoff against a controller with delayed RSR transitions."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class UFSQueueTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_delayed_stop_start_and_failed_takeover_never_issue_io(self):
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#define REG_IE 0x24
#define REG_IS 0x20
#define REG_UTRLBA 0x50
#define REG_UTRLBAU 0x54
#define REG_UTRLDBR 0x58
#define REG_UTRLRSR 0x60
#define DMA_UTRL 0
#define NSEC_PER_MSEC 1000000ULL
#define __builtin_arm_dsb(x) ((void)(x))
#define printf(...) ((void)0)
static struct {uint64_t dma_pa;} su;
static const char *xigua_ufs_stage;
static unsigned fault, phase, samples, base_writes, starts;
static uint32_t regs[32];
static uint64_t tick;
static uint64_t mach_absolute_time(void) {return ++tick;}
static void nanoseconds_to_absolutetime(uint64_t ns,uint64_t *out) {*out=ns/1000000;}
static void delay(unsigned us) {tick+=us;}
static uint32_t ufs_rd(unsigned reg) {
    if(reg==REG_UTRLRSR) {
        samples++;
        if(phase==1 && samples>=3 && fault!=1) regs[reg/4]=0;
        if(phase==2 && samples>=4 && fault!=3) regs[reg/4]=1;
    }
    if(reg==REG_UTRLDBR && fault==4) return 1;
    return regs[reg/4];
}
static void ufs_wr(unsigned reg,uint32_t value) {
    assert(reg!=REG_UTRLDBR); /* Must not issue a device command here. */
    if(reg==REG_UTRLRSR) {
        samples=0;
        if(!value) phase=1;
        else {
            assert(!regs[REG_UTRLRSR/4]);
            assert(regs[REG_UTRLBA/4]==(uint32_t)su.dma_pa);
            starts++;phase=2;
        }
        return;
    }
    if(reg==REG_UTRLBA || reg==REG_UTRLBAU) {
        assert(!regs[REG_UTRLRSR/4]); /* Async stop must finish first. */
        base_writes++;
        if(fault==2) return;
    }
    regs[reg/4]=value;
}
#include "xigua_ufs_handoff.h"
static void reset(unsigned f) {
    fault=f;phase=samples=base_writes=starts=0;tick=0;
    memset(regs,0,sizeof(regs));regs[REG_UTRLRSR/4]=1;
    su.dma_pa=0xc4000000;
}
int main(void) {
    reset(0);assert(!xigua_ufs_handoff_start());assert(base_writes==2 && starts==1);
    reset(1);assert(xigua_ufs_handoff_start()==EBUSY);assert(!base_writes && !starts);
    assert(!strcmp(xigua_ufs_stage,"handoff-stop"));
    reset(2);assert(xigua_ufs_handoff_start()==EIO);assert(base_writes==2 && !starts);
    assert(!strcmp(xigua_ufs_stage,"handoff-base"));
    reset(3);assert(xigua_ufs_handoff_start()==EIO);assert(base_writes==2 && starts==1);
    assert(!strcmp(xigua_ufs_stage,"handoff-run"));
    reset(4);assert(xigua_ufs_handoff_start()==EBUSY);assert(!base_writes && !starts);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'queue.c'
            out = Path(tmp) / 'queue'
            src.write_text(code)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(src), '-o', str(out)], check=True)
            subprocess.run([str(out)], check=True)
