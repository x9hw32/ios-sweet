"""Check CPU device-tree topology and actual blitter output without a VM."""
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from make_profile import qemu_profile
from mkadt_xigua import make, adt, mkadt


class DisplaySMPTests(unittest.TestCase):
    def profile(self):
        p = qemu_profile()
        p.update(cpu_mpidrs=[i << 8 for i in range(8)], cpu_count=8, gui=True)
        return p

    def tree(self, p):
        with patch.object(mkadt, 'd22ap_product', return_value=None):
            return adt.parse(make(p))[0]

    def test_eight_cpus_keep_real_affinities_and_unique_handles(self):
        root = self.tree(self.profile())
        cpus = next(n for n in root.children if n.name == 'cpus')
        self.assertEqual(len(cpus.children), 8)
        props = [dict((k, v) for k, f, v in n.props) for n in cpus.children]
        self.assertEqual([int.from_bytes(p['reg'], 'little') for p in props],
                         [i << 8 for i in range(8)])
        self.assertEqual(len(set(p['AAPL,phandle'] for p in props)), 8)
        self.assertEqual([p['state'] for p in props], [b'running\0'] + [b'stopped\0'] * 7)

    def test_cpu_selection_rejects_unknown_or_duplicated_targets(self):
        for change in [dict(cpu_count=0), dict(cpu_count=9), dict(cpu_mpidrs=[0]),
                       dict(cpu_mpidrs=[0] * 8), dict(cpu_mpidrs=[0, 1])]:
            p = self.profile(); p.update(change)
            with self.assertRaises(ValueError):
                self.tree(p)

    def test_gic_stride_rejects_partial_or_out_of_range_redistributors(self):
        for stride in [1, 0x10000, 0x21000, 0x100000000]:
            p = self.profile(); p['gicr_stride'] = stride
            with self.assertRaises(ValueError):
                self.tree(p)
        p = self.profile(); p.update(gicr_stride=0x40000, gicr_size=0x1d0000)
        with self.assertRaises(ValueError):
            self.tree(p)
        p = self.profile(); p['kind'] = 'phone'
        with self.assertRaises(ValueError):
            self.tree(p)

    def test_fit_retains_known_canvas_native_updates_both_dimensions(self):
        for mode, expected in [('fit', (1125, 2436)), ('native', (1080, 2400))]:
            p = self.profile(); p['display_mode'] = mode
            io = next(n for n in self.tree(p).children if n.name == 'arm-io')
            display = next(n for n in io.children if n.name == 'disp0')
            props = dict((k, v) for k, f, v in display.props)
            self.assertEqual(tuple(int.from_bytes(props[k], 'little') for k in
                                   ['canvas-width', 'canvas-height']), expected)

    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler required for pixel-output check')
    def test_scaling_dirty_tiles_padding_and_wake_redraw(self):
        source = r'''
#include <cassert>
#include <cstring>
#include <vector>
#include "xigua_blit.h"
int main() {
    for (unsigned w : {71u, 130u}) {
        const unsigned cw=5,ch=3,h=7,stride=w*4+4;
        std::vector<uint32_t> src(cw*ch), prev(w*h), xm(w), ym(h);
        std::vector<uint8_t> bytes(16+stride*h+16,0xcd);
        uint8_t *panel=bytes.data()+16;
        for(unsigned i=0;i<src.size();i++) src[i]=0x80000000+i;
        for(unsigned x=0;x<w;x++) xm[x]=(uint64_t)x*cw/w;
        for(unsigned y=0;y<h;y++) ym[y]=(uint64_t)y*ch/h;
        auto flush = [&](int force) {
            return xigua_blit_flush(src.data(),cw,xm.data(),ym.data(),prev.data(),
                                    panel,w,h,stride,force,memcpy);
        };
        auto check = [&]() {
            for(unsigned y=0;y<h;y++) {
                for(unsigned x=0;x<w;x++) {
                    uint32_t actual;
                    memcpy(&actual,panel+y*stride+x*4,4);
                    assert(actual==src[((uint64_t)y*ch/h)*cw+(uint64_t)x*cw/w]);
                }
                for(unsigned b=w*4;b<stride;b++) assert(panel[y*stride+b]==0xcd);
            }
            for(unsigned b=0;b<16;b++) {
                assert(bytes[b]==0xcd); assert(bytes[16+stride*h+b]==0xcd);
            }
        };
        assert(flush(1)==w*h*4); check();
        assert(flush(0)==0); check();
        src[0]^=0x1234;
        auto changed=flush(0); assert(changed>0 && changed<w*h*4); check();
        for(unsigned y=0;y<h;y++) memset(panel+y*stride,0,w*4);
        assert(flush(1)==w*h*4); check();
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'pixels.cpp').write_text(source)
            subprocess.run(['c++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'kernel'), str(path / 'pixels.cpp'),
                            '-o', str(path / 'pixels')], check=True, capture_output=True)
            subprocess.run([str(path / 'pixels')], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
