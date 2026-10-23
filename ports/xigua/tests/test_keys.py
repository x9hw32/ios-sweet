"""Check v7 observer addressing, restricted read commands and real key edges."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class KeysTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_v7_apid_read_allowlist_failures_and_debounce(self):
        code = r'''
#include <assert.h>
#include <errno.h>
#include <string.h>
#include "xigua_keys.h"
struct device { uint32_t map[1024], owner[1024]; unsigned writes, off, cmd, pauses, status; };
static uint32_t read_reg(void *ctx,unsigned region,unsigned off) {
    struct device *d=ctx; assert(!(off&3));
    if(region==XIGUA_KEYS_CORE) { assert(off>=0x2000 && off<0x3000); return d->map[(off-0x2000)/4]; }
    if(region==XIGUA_KEYS_CNFG) { assert(off<0x1000); return d->owner[off/4]; }
    assert(region==XIGUA_KEYS_OBSERVER && (off==d->off+8 || off==d->off+0x18));
    return off==d->off+8?d->status:0xa5;
}
static void write_reg(void *ctx,unsigned region,unsigned off,uint32_t value) {
    struct device *d=ctx; assert(region==XIGUA_KEYS_OBSERVER && !(off%0x20) && off<0x8000);
    assert((value>>27)==1 && !(value&15)); /* Read one byte, never a PMIC write. */
    d->off=off;d->cmd=value;d->writes++;
}
static void pause_us(void *ctx,unsigned us) { ((struct device *)ctx)->pauses+=us; }
int main(void) {
    struct device d={0}; struct xigua_keys_io io={&d,read_reg,write_reg,pause_us};
    d.map[2]=0x013<<8;d.owner[2]=2;
    d.map[7]=(0x013<<8)|(1U<<24);d.owner[7]=0;
    d.map[9]=0x013<<8;d.owner[9]=3;
    d.map[11]=0x18d<<8;d.owner[11]=0;
    struct xigua_key_channel pon={0},gpio={0};
    assert(!xigua_keys_find(&io,12,0x013,&pon) && pon.apid==7);
    assert(!xigua_keys_find(&io,12,0x18d,&gpio) && gpio.apid==11);
    assert(xigua_keys_find(&io,0,0x013,&pon)==EINVAL);
    assert(xigua_keys_find(&io,1025,0x013,&pon)==EINVAL);
    assert(xigua_keys_find(&io,12,0x008,&pon)==EINVAL); /* Donor PON must be refused. */
    assert(xigua_keys_find(&io,4,0x18d,&gpio)==ENODEV);
    d.status=1;uint8_t value=0;
    assert(!xigua_keys_read_byte(&io,&pon,0x1310,&value));
    assert(value==0xa5 && d.off==0x20*7 && d.cmd==((1U<<27)|(0x10<<4)));
    assert(!xigua_keys_read_byte(&io,&gpio,0x8d46,&value) && d.off==0x20*11);
    unsigned writes=d.writes;
    assert(xigua_keys_read_byte(&io,&pon,0x1340,&value)==EINVAL);
    assert(xigua_keys_read_byte(&io,&gpio,0x1310,&value)==EINVAL && d.writes==writes);
    for(unsigned failure=2;failure<=8;failure*=2) {
        d.status=1|failure;value=0x77;
        assert(xigua_keys_read_byte(&io,&pon,0x1310,&value)==EIO && value==0x77);
    }
    d.status=0;
    assert(xigua_keys_read_byte(&io,&pon,0x1310,&value)==ETIMEDOUT && pon.poisoned);
    writes=d.writes;d.status=1;
    assert(xigua_keys_read_byte(&io,&pon,0x1310,&value)==EIO && writes==d.writes);
    d.map[0]=UINT32_MAX;
    assert(xigua_keys_find(&io,12,0x013,&pon)==EIO);
    struct xigua_key_filter key={0};
    for(unsigned n=0;n<30;n++) assert(!xigua_key_update(&key,true,true)); /* Held at boot. */
    assert(!xigua_key_update(&key,true,false) && key.armed);
    assert(!xigua_key_update(&key,true,true));
    assert(!xigua_key_update(&key,true,false)); /* Bounce cancels press. */
    assert(!xigua_key_update(&key,true,true));
    assert(!xigua_key_update(&key,true,true));
    assert(xigua_key_update(&key,true,true) && key.down);
    for(unsigned n=0;n<100;n++) assert(!xigua_key_update(&key,true,true));
    assert(!xigua_key_update(&key,true,false));
    assert(!xigua_key_update(&key,true,false));
    assert(xigua_key_update(&key,true,false) && !key.down);
    assert(!xigua_key_update(&key,true,true));
    assert(!xigua_key_update(&key,true,true));
    assert(xigua_key_update(&key,true,true));
    assert(!xigua_key_update(&key,false,true));
    assert(!xigua_key_update(&key,false,true));
    assert(xigua_key_update(&key,false,true) && !key.down && !key.armed);
    assert(!xigua_key_update(&key,true,true)); /* No phantom re-press after failure. */
    assert(!xigua_key_update(&key,true,false) && key.armed);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'keys.c'
            binary = Path(tmp) / 'keys'
            source.write_text(code)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
