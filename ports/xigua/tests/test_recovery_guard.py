"""ESP writes must never start from Android, even with working root."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import probe_device


class RecoveryGuardTests(unittest.TestCase):
    def test_android_cannot_reach_push_or_dd(self):
        seen = []
        def run(command, **kwargs):
            seen.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=b'normal\n', stderr=b'')
        with patch.object(sys, 'argv', ['probe_device.py', 'install']), patch.object(probe_device.subprocess, 'run', run):
            with self.assertRaisesRegex(SystemExit, 'require ADB in recovery'):
                probe_device.main()
        self.assertEqual(len(seen), 1)
        self.assertIn('getprop ro.bootmode', seen[0][-1])

    def test_different_model_in_recovery_cannot_reach_push_or_dd(self):
        seen = []
        def run(command, **kwargs):
            seen.append(command)
            value = b'recovery\n' if 'ro.bootmode' in command[-1] else b'Other device\n'
            return subprocess.CompletedProcess(command, 0, stdout=value, stderr=b'')
        with patch.object(sys, 'argv', ['probe_device.py', 'collect-restore']), patch.object(probe_device.subprocess, 'run', run):
            with self.assertRaisesRegex(SystemExit, 'Expected PJA110 recovery'):
                probe_device.main()
        self.assertEqual(len(seen), 2)


if __name__ == '__main__':
    unittest.main()
