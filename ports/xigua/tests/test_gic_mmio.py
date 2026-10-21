"""Check the MMIO instruction forms that the phone's firmware must emulate."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class GICMMIOTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('clang'), 'Clang required for ARM code generation')
    def test_optimized_device_accesses_never_update_the_address_register(self):
        source = r'''
#include "xigua_mmio.h"
uint64_t read_registers(uintptr_t base) {
    uint64_t value = xigua_mmio_read64(base + 8);
    for (unsigned i = 0; i < 8; i++)
        value += xigua_mmio_read32(base + 0x10400 + 4 * i);
    return value;
}
void init_registers(uintptr_t base, uint32_t value) {
    xigua_mmio_write32(base + 0x10080, ~0U);
    for (unsigned i = 0; i < 8; i++)
        xigua_mmio_write32(base + 0x10400 + 4 * i, value);
    xigua_mmio_write32(base + 0x10100, 0x8000002);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'mmio.c').write_text(source)
            for optimization in ['-O2', '-Os', '-O3']:
                output = subprocess.check_output([
                    'clang', '--target=arm64-apple-ios16.0', '-ffreestanding',
                    '-mgeneral-regs-only', '-mstrict-align', '-Wall', '-Wextra',
                    '-Werror', optimization, '-I' + str(ROOT / 'kernel'),
                    '-S', str(path / 'mmio.c'), '-o', '-'], text=True)
                instructions = re.findall(r'^\s*(ldr|str)\s+([^\n;]+)', output, re.M)
                self.assertTrue(instructions, output)
                self.assertTrue(any(op == 'ldr' and args.startswith('x')
                                    for op, args in instructions), output)
                self.assertTrue(any(op == 'str' for op, args in instructions), output)
                for op, args in instructions:
                    self.assertRegex(args.strip(), r'^[wx]\d+,\s*\[x\d+\]$',
                                     f'{optimization}: {op} {args}')
                self.assertNotRegex(output, r'^\s*(?:ldp|stp|ldur|stur)\s', output)


if __name__ == '__main__':
    unittest.main()
