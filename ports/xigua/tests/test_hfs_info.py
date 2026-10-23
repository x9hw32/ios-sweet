import struct
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from hfs_volume_info import volume_info


class HFSInfoTests(unittest.TestCase):
    def header(self):
        data = bytearray(4096)
        struct.pack_into('>HHI', data, 1024, 0x4858, 5, 0x2000)
        struct.pack_into('>III', data, 1064, 4096, 3145728, 100000)
        return data

    def test_volume_capacity_is_distinct_from_partition_and_dirty_journal(self):
        r = volume_info(self.header(), 77137424384)
        self.assertEqual(r['volume_bytes'], 12884901888)
        self.assertEqual(r['free_bytes_in_header'], 409600000)
        self.assertTrue(r['journaled'])
        self.assertFalse(r['cleanly_unmounted'])
        self.assertGreater(r['partition_bytes'], r['volume_bytes'])

    def test_rejects_truncation_bad_signature_overflow_and_invalid_block_size(self):
        for offset, value in [(1024, 0), (1064, 3000), (1072, 3145729)]:
            data = self.header()
            struct.pack_into('>I', data, offset, value)
            with self.assertRaises(ValueError):volume_info(data, 77137424384)
        with self.assertRaises(ValueError):volume_info(self.header()[:2048], 77137424384)
        with self.assertRaises(ValueError):volume_info(self.header(), 1024)
