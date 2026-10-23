"""Check the narrow cache edit and ad-hoc code-page hash repair on synthetic data."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_activation_patch import patch_cache, REPLACEMENT, SECTOR, volume_identity


class ActivationPatchTests(unittest.TestCase):
    def fixture(self):
        page = 16384
        data = bytearray(5 * page)
        data[:16] = b'dyld_v1  arm64\x00\x00'
        struct.pack_into('<QQ', data, 0x28, 4 * page, page)
        self.method_offset, self.method_size = 5000, 352
        data[5000:5352] = bytes(range(256)) + bytes(range(96))
        self.fingerprint = hashlib.sha256(data[5000:5352]).hexdigest()
        base = 4 * page
        cdlen = 44 + 4 * 32
        struct.pack_into('>III', data, base, 0xFADE0CC0, 20 + cdlen, 1)
        struct.pack_into('>II', data, base + 12, 0, 20)
        struct.pack_into('>9I4BI', data, base + 20, 0xFADE0C02, cdlen, 0x20001, 2,
                         44, 0, 0, 4, base, 32, 2, 0, 14, 0)
        for n in range(4):
            data[base + 64 + n * 32:base + 96 + n * 32] = hashlib.sha256(data[n * page:(n + 1) * page]).digest()
        return data

    def patch(self, data):
        return patch_cache(data, self.method_offset, self.method_size, self.fingerprint)

    def test_exact_change_and_valid_code_hash(self):
        data = self.fixture()
        result, sectors, directories = self.patch(data)
        self.assertEqual(sectors, [5000 // SECTOR, 65536 // SECTOR])
        self.assertEqual(result[5000:5016], REPLACEMENT)
        self.assertEqual(result[5016:5352], data[5016:5352])
        self.assertEqual(result[65600:65632], hashlib.sha256(result[:16384]).digest())
        self.assertEqual(result[65632:], data[65632:])
        self.assertEqual(directories[0]['page_bytes'], 16384)

    def test_wrong_method_or_signature_refuses(self):
        original = self.fixture()
        for offset, flip in [(5001, 1), (65600, 1), (65536, 1),
                             (65536 + 20 + 15, 2), (65536 + 20 + 37, 1)]:
            data = bytearray(original)
            data[offset] ^= flip
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.patch(data)
        with self.assertRaises(ValueError):
            self.patch(original[:65540])

    def test_volume_identity_ignores_free_count_but_tracks_volume(self):
        header = bytearray(SECTOR)
        header[1024:1026] = b'HX'
        identity = volume_identity(header)
        header[1072:1076] = b'free'
        self.assertEqual(identity, volume_identity(header))
        header[1128] = 1
        self.assertNotEqual(identity, volume_identity(header))
