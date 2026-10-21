"""Exercise memory-corruption rejection before the firmware's first payload copy."""
import ctypes
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class Region(ctypes.Structure):
    _fields_ = [('base', ctypes.c_uint64), ('size', ctypes.c_uint64)]


class Placement(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ('adt', 'boot_args', 'top', 'entry')]


class PayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        library = str(Path(cls.tmp.name) / 'payload.so')
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(ROOT / 'shim/payload.c'), '-o', library], check=True)
        cls.validate = ctypes.CDLL(library).payload_validate
        cls.validate.argtypes = [ctypes.c_void_p, ctypes.c_uint64, Region,
                                 ctypes.POINTER(Region), ctypes.c_uint,
                                 ctypes.POINTER(Placement)]
        cls.validate.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def payload(self, memory_size=0x4000):
        b = bytearray(0x400)
        base = 0xfffffe0006000000
        struct.pack_into('<8sII', b, 0, b'SWEETXNU', 1, 1)
        end = (0x1000000 + memory_size + 0x3fff) & ~0x3fff
        struct.pack_into('<7Q', b, 0x10, base, base + 0x1000000,
                         0x300, 32, base + end, 0xb0000000, 0x3ff00000)
        struct.pack_into('<4Q', b, 0x2a8, base + 0x1000000, memory_size, 0x2d0, 16)
        return b

    def check_payload(self, data, reserved=()):
        b = ctypes.create_string_buffer(bytes(data))
        out = Placement()
        blocks = (Region * len(reserved))(*(Region(*r) for r in reserved))
        code = self.validate(b, len(data), Region(0xb0000000, 0x3ff00000), blocks,
                             len(reserved), ctypes.byref(out))
        return code, out

    def test_valid_payload_and_placement(self):
        code, out = self.check_payload(self.payload())
        self.assertEqual(code, 0)
        self.assertEqual(out.entry, 0xb1000000)
        self.assertEqual(out.boot_args % 0x4000, 0)
        self.assertLess(out.adt, out.boot_args)

    def test_real_macho_linkedit_can_have_unaligned_memory_size(self):
        self.assertEqual(self.check_payload(self.payload(0x3b4b30))[0], 0)

    def test_truncated_segment_data(self):
        b = self.payload()
        struct.pack_into('<Q', b, 0x2a8 + 16, len(b) - 8)
        self.assertEqual(self.check_payload(b)[0], -8)

    def test_segment_cannot_escape_ram(self):
        b = self.payload()
        struct.pack_into('<Q', b, 0x2a8 + 8, 0x40000000)
        self.assertEqual(self.check_payload(b)[0], -8)

    def test_entry_cannot_point_into_bss(self):
        b = self.payload()
        struct.pack_into('<Q', b, 0x18, 0xfffffe0007000100)
        self.assertEqual(self.check_payload(b)[0], -10)

    def test_no_kernel_memory_overlaps_loader_or_fdt(self):
        self.assertEqual(self.check_payload(self.payload(), [(0xb1000000, 4096)])[0], -5)

    def test_reject_short_header(self):
        self.assertEqual(self.check_payload(bytes(64))[0], -1)

    def test_adt_cannot_reference_outside_payload(self):
        b = self.payload()
        struct.pack_into('<Q', b, 0x20, 0xfffffffffffffff0)
        self.assertEqual(self.check_payload(b)[0], -6)


if __name__ == '__main__':
    unittest.main()
