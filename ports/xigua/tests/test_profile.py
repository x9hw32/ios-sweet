import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from make_profile import parse_probe
from fdt import parse


class ProfileTests(unittest.TestCase):
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
