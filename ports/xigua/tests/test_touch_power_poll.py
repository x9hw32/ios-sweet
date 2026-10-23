"""Exercise guarded touch power votes and responses without an IRQ edge."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class TouchPowerPollTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_power_ownership_and_polled_responses(self):
        code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include "xigua_vdd.h"
#include "xigua_tcm_poll.h"
struct hardware {
    uint32_t r[0x10000/4];
    unsigned major, writes, ticks, trigger, suppress, stuck;
};
static uint32_t get(void *ctx, unsigned off) {
    struct hardware *h=ctx;
    assert(!(off&3) && off<sizeof(h->r));
    return h->r[off/4];
}
static void put(void *ctx, unsigned off, uint32_t value) {
    struct hardware *h=ctx;
    assert(!(off&3) && off<sizeof(h->r)); h->writes++;
    if (h->stuck) return;
    if (off==8) { h->r[1]&=~value; return; }
    h->r[off/4]=value;
    unsigned ctl=h->major==3?0x24:0x14, cmd=h->major==3?0x34:0x30;
    unsigned stride=h->major==3?24:20;
    if (off%0x2a0==ctl && (value&(1U<<24))) {
        unsigned b=off-ctl;
        assert(!h->trigger); h->trigger=b/0x2a0+1;
        assert(h->r[(b+ctl+8)/4]==7);
        const unsigned addr[]={0x40800,0x40808,0x40804}, data[]={1800,7,1};
        for (unsigned n=0;n<3;n++) {
            unsigned c=b+cmd+n*stride;
            assert(h->r[c/4]==0x10108 && h->r[(c+4)/4]==addr[n]);
            assert(h->r[(c+8)/4]==data[n]);
            h->r[(c+12)/4]=0;
        }
        h->r[(b+ctl+4)/4]=0;
    }
}
static void pause_us(void *ctx, unsigned us) {
    struct hardware *h=ctx; h->ticks+=us;
    if (h->trigger && !h->suppress && h->ticks>=3) {
        unsigned b=(h->trigger-1)*0x2a0, ctl=h->major==3?0x24:0x14;
        unsigned cmd=h->major==3?0x34:0x30, stride=h->major==3?24:20;
        h->r[(b+ctl+4)/4]=1; h->r[1]|=1U<<(h->trigger-1);
        for(unsigned n=0;n<3;n++) h->r[(b+cmd+n*stride+12)/4]=0x10100;
    }
}
static void init(struct hardware *h, unsigned major) {
    memset(h,0,sizeof(*h)); h->major=major;
    for(unsigned t=0;t<3;t++) h->r[(t*0x2a0+(major==3?0x28:0x18))/4]=1;
    h->r[0]=0xa5; h->r[1]=0x80; /* Unrelated IRQ must survive. */
}
static uint32_t db[XIGUA_VDD_DB_BYTES/4];
static uint32_t db_get(void *ctx, unsigned off) {
    (void)ctx; assert(!(off&3) && off<sizeof(db)); return db[off/4];
}
struct poll { unsigned reads, pauses, elapsed, scenario, identifies, mode; };
static int poll_read(void *ctx,unsigned *code,unsigned *length) {
    struct poll *p=ctx; p->reads++; *length=24;
    if(p->scenario==1) return EAGAIN;
    if(p->scenario==2) { *code=8; return 0; }
    if(p->scenario==3) return EIO;
    if(p->reads==1) return EAGAIN; /* No IRQ edge and idle bus. */
    if(p->reads==2) { *code=0; return 0; }
    *code=p->scenario==4?1:0x10;
    return 0;
}
static unsigned identify(void *ctx,unsigned length) {
    struct poll *p=ctx; assert(length==24); p->identifies++; return p->mode;
}
static void poll_pause(void *ctx) { struct poll *p=ctx; p->pauses++; p->elapsed++; }
static bool expired(void *ctx) { return ((struct poll *)ctx)->elapsed>=8; }
int main(void) {
    db[0]=1; db[1]=0xc0330db; db[2]=(16U<<16)|4; db[3]=(1U<<16)|64;
    unsigned e=144+16; db[e/4]=0x626f646c; db[e/4+1]=0x34;
    db[e/4+4]=0x40800; db[e/4+5]=4;
    assert(!xigua_vdd_check_db(db_get,0));
    db[e/4+4]++; assert(xigua_vdd_check_db(db_get,0)==EINVAL); db[e/4+4]--;
    db[140/4]=1; assert(xigua_vdd_check_db(db_get,0)==EINVAL); db[140/4]=0;
    db[3]=(2U<<16)|64; memcpy(db+e/4+6,db+e/4,24);
    assert(xigua_vdd_check_db(db_get,0)==ENODEV); db[3]=(1U<<16)|64;
    db[e/4+5]=0xffffffff; assert(xigua_vdd_check_db(db_get,0)==EINVAL);
    for(unsigned major=2;major<=3;major++) {
        struct hardware h; init(&h,major);
        struct xigua_rpmh_io io={&h,get,put,pause_us}; bool poison=false;
        unsigned ctl=major==3?0x24:0x14, enable=ctl+8, cmd=major==3?0x34:0x30;
        h.r[(enable)/4]=1; h.r[(cmd+4)/4]=0x50000; /* TCS0 owned by someone else. */
        uint32_t first[0x2a0/4]; memcpy(first,h.r,sizeof(first));
        assert(!xigua_vdd_vote(&io,major,4,&poison) && !poison && h.trigger==2);
        assert(h.r[0]==0xa5 && h.r[1]==0x80 && !h.r[(0x2a0+enable)/4]);
        assert(!memcmp(first+4,h.r+4,sizeof(first)-16));
        init(&h,major); h.r[enable/4]=1; h.r[(cmd+4)/4]=0x40808;
        assert(xigua_vdd_vote(&io,major,4,&poison)==EBUSY && !h.writes);
        init(&h,major);
        for(unsigned t=0;t<3;t++) h.r[(t*0x2a0+ctl+4)/4]=0;
        assert(xigua_vdd_vote(&io,major,4,&poison)==EBUSY && !h.writes);
        init(&h,major); h.suppress=1;
        assert(xigua_vdd_vote(&io,major,4,&poison)==ETIMEDOUT && poison);
        unsigned writes=h.writes;
        assert(xigua_vdd_vote(&io,major,4,&poison)==EIO && h.writes==writes);
        init(&h,major); poison=false; h.stuck=1;
        assert(xigua_vdd_vote(&io,major,4,&poison)==EIO && poison && !h.trigger);
        init(&h,major); poison=false;
        assert(xigua_vdd_vote(&io,4,4,&poison)==ENODEV && !h.writes);
    }
    for(unsigned scenario=0;scenario<=4;scenario++) {
        struct poll p={.scenario=scenario,.mode=1}; unsigned length=0;
        struct xigua_tcm_poll_ops ops={&p,poll_read,identify,poll_pause,expired};
        int error=xigua_tcm_poll_response(&ops,2,&length);
        assert(error==(scenario==1?ETIMEDOUT:scenario==2||scenario==3?EIO:0));
        if(!error) assert(length==24 && p.identifies==1 && p.reads==3);
        if(scenario==1) assert(p.reads==8);
    }
    struct poll p={.mode=0xb};
    struct xigua_tcm_poll_ops ops={&p,poll_read,identify,poll_pause,expired};
    assert(xigua_tcm_poll_response(&ops,0x14,0)==ETIMEDOUT);
    p=(struct poll){.mode=1}; assert(!xigua_tcm_poll_response(&ops,0x14,0));
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
