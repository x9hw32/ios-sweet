import sys
import struct
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from make_profile import parse_probe, large_ram_range, make_profile
from fdt import parse, Node
from mkadt_xigua import make, adt, mkadt


class ProfileTests(unittest.TestCase):
    def test_firmware_stride_survives_fdt_profile_and_apple_tree(self):
        # SM8550 declares 256 KiB spacing independently of TYPER.VLPIS.
        root = Node('', '/', props={'#address-cells': struct.pack('>I', 2),
                                    '#size-cells': struct.pack('>I', 2)})
        memory = Node('memory', '/memory', root, props={
            'device_type': b'memory\0', 'reg': struct.pack('>QQ', 0x100000000, 0x20000000)})
        gic = Node('gic', '/gic', root, props={
            'compatible': b'arm,gic-v3\0',
            'reg': struct.pack('>4Q', 0x17100000, 0x10000, 0x17180000, 0x200000),
            'redistributor-stride': struct.pack('>Q', 0x40000)})
        timer = Node('timer', '/timer', root, props={
            'compatible': b'arm,armv8-timer\0',
            'interrupts': struct.pack('>9I', 1, 13, 4, 1, 14, 4, 1, 11, 4)})
        cpus = Node('cpus', '/cpus', root, props={
            '#address-cells': struct.pack('>I', 1), '#size-cells': bytes(4)})
        nodes = {n.path: n for n in [root, memory, gic, timer, cpus]}
        for i in range(8):
            cpu = Node(f'cpu@{i:x}00', f'/cpus/cpu@{i:x}00', cpus, props={
                'reg': struct.pack('>I', i << 8), 'enable-method': b'psci\0'})
            nodes[cpu.path] = cpu
        probe = ('XIGUA-PROBE version=2\nmemory_map_status=0x0\ntgran16=0x1\n'
                 'cntfrq_el0=0x124f800\nmpidr_el1=0x81000000\ngop_status=0x0\ngop_pixel_format=0x1\n'
                 'gop_base=0xb8000000\ngop_width=0x4d8\ngop_height=0xad4\n'
                 'gop_pixels_per_scanline=0x4d8\ngop_size=0xd1cc00\n'
                 'memory 0x7 0x100000000 0x20000 0xf\n')
        with patch('inspect_dtb.parse', return_value=(nodes, [])):
            profile = make_profile(b'synthetic SM8550 DT', probe)
        self.assertEqual(profile['gicr_stride'], 0x40000)
        profile['cpu_count'] = 6
        with patch.object(mkadt, 'd22ap_product', return_value=None):
            tree, _ = adt.parse(make(profile))
        io = next(n for n in tree.children if n.name == 'arm-io')
        apple_gic = next(n for n in io.children if n.name == 'gic')
        self.assertEqual(apple_gic.prop('redistributor-stride'), struct.pack('<Q', 0x40000))

    def test_v2_probe_can_supply_memory_map(self):
        values, _ = parse_probe('XIGUA-PROBE version=2\nmemory_map_status=0x0\ntgran16=0x1\ncntfrq_el0=0x124f800\n')
        self.assertEqual(values['tgran16'], 1)

    def test_large_ram_can_span_adjacent_dt_banks(self):
        values = dict(large_ram_base=0x8c0000000, large_ram_size=0x340000000,
                      large_ram_allocate_status=0, large_ram_sample_pages_passed=1)
        memory = [(7, 0x8c0000000, 0x340000000, 0xf)]
        banks = [(0x8c0000000, 0xa00000000), (0xa00000000, 0xc00000000)]
        self.assertEqual(large_ram_range(values, memory, banks, []), (0x8c0000000, 0x340000000))

    def test_large_ram_rejects_holes_and_reservations(self):
        values = dict(large_ram_base=0x8c0000000, large_ram_size=0x340000000,
                      large_ram_allocate_status=0, large_ram_sample_pages_passed=1)
        memory = [(7, 0x8c0000000, 0x340000000, 0xf)]
        banks = [(0x8c0000000, 0x9ffffc000), (0xa00000000, 0xc00000000)]
        with self.assertRaises(ValueError):
            large_ram_range(values, memory, banks, [])
        with self.assertRaises(ValueError):
            large_ram_range(values, memory, [(0x8c0000000, 0xc00000000)], [(0xb00000000, 0xb00004000)])

    def test_large_ram_requires_successful_allocation_probe(self):
        with self.assertRaises(ValueError):
            large_ram_range(dict(large_ram_base=0x8c0000000, large_ram_size=0x340000000),
                            [(7, 0x8c0000000, 0x340000000, 0xf)], [(0x8c0000000, 0xc00000000)], [])

    def test_probe_reports_without_sixteen_k_support_are_rejected(self):
        for granule in [0, 15]:
            with self.assertRaises(ValueError):
                parse_probe(f'XIGUA-PROBE version=1\nmemory_map_status=0x0\ntgran16=0x{granule:x}\ncntfrq_el0=0x124f800\n')

    def test_bad_memory_map_does_not_qualify_a_ram_region(self):
        with self.assertRaises(ValueError):
            parse_probe('XIGUA-PROBE version=1\nmemory_map_status=0x800000000000000e\ntgran16=0x1\ncntfrq_el0=0x124f800\n')

    def test_memory_map_pages_are_always_four_k_even_for_sixteen_k_xnu(self):
        values, memory = parse_probe('XIGUA-PROBE version=1\nmemory_map_status=0x0\ntgran16=0x1\ncntfrq_el0=0x124f800\nmemory 0x7 0x880000000 0x20000 0x8\n')
        self.assertEqual(memory[0][2], 512 * 1024 * 1024)

    def test_malformed_fdt_header_is_rejected(self):
        with self.assertRaises(ValueError):
            parse(bytes(40))


if __name__ == '__main__':
    unittest.main()
