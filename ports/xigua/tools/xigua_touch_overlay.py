"""Wire the opt-in S3910 driver into XNU and preserve physical touch geometry."""
from pathlib import Path


def apply(replace, create):
    root = Path(__file__).resolve().parent.parent
    for name in ['xigua_tcm.h', 'xigua_geni_spi.h', 'xigua_touch.c']:
        create('bsd/dev/' + name, (root / 'kernel' / name).read_text())
    replace('bsd/conf/files', 'bsd/dev/sweet_touch.c\t\t\tstandard\n',
            'bsd/dev/sweet_touch.c\t\t\tstandard\nbsd/dev/xigua_touch.c\t\t\tstandard\n')
    replace('iokit/bsddev/IOKitBSDInit.cpp', '    uint32_t ufs_probe = 0;',
            '    extern void xigua_touch_start(void);\n    xigua_touch_start();\n    uint32_t ufs_probe = 0;')
    hid = 'iokit/Kernel/arm/hid/SweetHID.cpp'
    replace(hid, '\tint fLogicalW, fLogicalH, fOffX, fOffY;',
            '\tint fLogicalW, fLogicalH, fOffX, fOffY, fPanelW, fPanelH;')
    replace(hid, '''\tfLogicalW = native ? 1080 : 1125;
\tfLogicalH = native ? 2400 : 2436;
\tfOffX = (fLogicalW - 1080) / 2;
\tfOffY = (fLogicalH - 2400) / 2;''', '''\tfPanelW = 1080;
\tfPanelH = 2400;
#if defined(ARM64_BOARD_CONFIG_XIGUA)
\tPE_Video video;
\tbzero(&video, sizeof(video));
\tPE_current_console(&video);
\tif (video.v_width > 0 && video.v_width <= 8192 &&
\t    video.v_height > 0 && video.v_height <= 8192) {
\t\tfPanelW = (int)video.v_width;
\t\tfPanelH = (int)video.v_height;
\t} else {
\t\tfPanelW = 1240;
\t\tfPanelH = 2772;
\t}
\tint fit = 0;
\tPE_parse_boot_argn("sweetfb_fit", &fit, sizeof(fit));
\tif (fit) native = 1; /* Full-panel scaling maps physical edges to UI edges. */
#endif
\tfLogicalW = native ? fPanelW : 1125;
\tfLogicalH = native ? fPanelH : 2436;
\tfOffX = (fLogicalW - fPanelW) / 2;
\tfOffY = (fLogicalH - fPanelH) / 2;''')
    replace(hid, '\tx = x < 0 ? 0 : (x > 1079 ? 1079 : x);',
            '\tx = x < 0 ? 0 : (x >= fPanelW ? fPanelW - 1 : x);')
    replace(hid, '\ty = y < 0 ? 0 : (y > 2399 ? 2399 : y);',
            '\ty = y < 0 ? 0 : (y >= fPanelH ? fPanelH - 1 : y);')
    replace(hid, 'x > 1079 - SWEET_TOUCH_EDGE_PX', 'x >= fPanelW - SWEET_TOUCH_EDGE_PX')
    replace(hid, 'y > 2399 - SWEET_TOUCH_EDGE_PX', 'y >= fPanelH - SWEET_TOUCH_EDGE_PX')
