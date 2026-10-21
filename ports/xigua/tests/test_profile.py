import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from make_profile import parse_probe, large_ram_range
from fdt import parse


class ProfileTests(unittest.TestCase):
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
