"""Virtual repair writes must leave their source untouched; journal replay is checked."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from recovery_hfs_cow import Cow
from replay_hfs_journal import checksum, plan
from apply_hfs_cow import runs_for


class RecoveryCowTests(unittest.TestCase):
    def test_apply_groups_cover_every_sector_once_and_commit_header_last(self):
        rows = [{'physical': n} for n in [100, 2, 98, 1, 99]]
        order, runs = runs_for(rows, 98)
        self.assertEqual(order, [1, 2, 99, 100, 98])
        self.assertEqual(runs, [(1, 2, 0), (99, 2, 2), (98, 1, 4)])
        for block, count, index in runs:
            self.assertEqual(order[index:index+count], list(range(block, block+count)))
        for bad in [[{'physical': 1}, {'physical': 1}], [{'physical': -1}], [{'physical': True}]]:
            with self.assertRaises(ValueError):
                runs_for(bad, 98)

    def test_partial_writes_read_overlay_and_revert_without_source_changes(self):
        source = bytes((i * 17) & 255 for i in range(16384))
        with tempfile.TemporaryDirectory() as tmp:
            cow = Cow(lambda off, n: source[off:off+n], len(source), Path(tmp))
            cow.write(4094, b'abcdef')
            self.assertEqual(cow.read(4090, 16), source[4090:4094] + b'abcdef' + source[4100:4106])
            self.assertEqual(cow.read(8192, 4096), source[8192:12288])
            rows = cow.save()
            self.assertEqual([r['physical'] for r in rows], [0, 1])
            self.assertEqual((Path(tmp)/'sectors/0.original.bin').read_bytes(), source[:4096])
            cow.write(4094, source[4094:4100])
            self.assertFalse(cow.save())
            self.assertEqual(cow.read(0, len(source)), source)
            with self.assertRaises(ValueError):
                cow.write(len(source)-1, b'xx')
            self.assertFalse(cow.changed)

    def journal(self, wrap=False):
        raw = bytearray(4096)
        start, end = (3584, 1024) if wrap else (512, 1536)
        struct.pack_into('<IIQQQIIII', raw, 0, 0x4a4e4c78, 0x12345678,
                         start, end, len(raw), 512, 0, 512, 8)
        struct.pack_into('<I', raw, 36, checksum(raw[:44]))
        block = bytearray(512)
        struct.pack_into('<HHIII', block, 0, 31, 2, 1024, 0, 3)
        struct.pack_into('<qII', block, 16, 0, 0, 8)
        struct.pack_into('<qII', block, 32, 20, 512, checksum(b'B'*512))
        struct.pack_into('<I', block, 8, checksum(block[:32]))
        raw[start:start+512] = block
        payload = 512 if wrap else 1024
        raw[payload:payload+512] = b'B'*512
        return raw, start, payload

    def test_checked_replay_and_empty_header_with_ring_wrap(self):
        for wrap in [False, True]:
            raw, start, payload = self.journal(wrap)
            writes, header, report = plan(raw, 32768)
            self.assertEqual(writes, [(10240, b'B'*512)])
            self.assertEqual(report['headers'], 1)
            raw[:512] = header
            self.assertEqual(plan(raw, 32768)[0], [])

    def test_bad_header_payload_and_range_refuse(self):
        for wrap in [False, True]:
            raw, start, payload = self.journal(wrap)
            for off in [36, start+8, payload+12]:
                bad = bytearray(raw)
                bad[off] ^= 1
                with self.subTest(wrap=wrap, offset=off), self.assertRaises(ValueError):
                    plan(bad, 32768)
            bad = bytearray(raw)
            struct.pack_into('<q', bad, start+32, 1000000000)
            with self.assertRaises(ValueError):
                plan(bad, 32768)
