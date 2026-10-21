"""Allocated-partition writes must stop before streaming on a wrong device/state."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import install_ios_root


class RootWriteGuardTests(unittest.TestCase):
    def assert_stopped(self, replacements, message):
        def command(text, **kwargs):
            values = {'getprop ro.bootmode': b'recovery', 'getprop ro.product.model': b'PJA110',
                      '/sbin/busybox id -u': b'0',
                      '/sbin/busybox readlink -f /dev/block/by-name/linux': b'/dev/block/sda17',
                      '/sbin/busybox blockdev --getsize64 /dev/block/by-name/linux': b'77137424384'}
            values.update(replacements)
            if '/proc/mounts' in text:
                return replacements.get('mounts', b'')
            if text not in values:
                self.fail('Unexpected device operation before guard failure: ' + text)
            return values[text]
        with patch.object(sys, 'argv', ['install_ios_root.py', '/missing/root.img', '--output', '/missing/receipt']), \
                patch.object(install_ios_root, 'command', command), \
                patch.object(install_ios_root.subprocess, 'Popen') as stream:
            with self.assertRaisesRegex(SystemExit, message):
                install_ios_root.main()
            stream.assert_not_called()

    def test_android_stops_before_root_write(self):
        self.assert_stopped({'getprop ro.bootmode': b'normal'}, 'require recovery')

    def test_wrong_model_stops_before_root_write(self):
        self.assert_stopped({'getprop ro.product.model': b'Other device'}, 'Expected PJA110')

    def test_partition_remapping_stops_before_root_write(self):
        self.assert_stopped({'/sbin/busybox readlink -f /dev/block/by-name/linux': b'/dev/block/sda18'}, 'mapping changed')

    def test_mounted_alias_stops_before_root_write(self):
        self.assert_stopped({'mounts': b'/dev/block/sda17\n'}, 'linux is mounted')


if __name__ == '__main__':
    unittest.main()
