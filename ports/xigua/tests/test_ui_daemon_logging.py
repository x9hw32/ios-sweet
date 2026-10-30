import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from patch_ui_daemon_logging import patch_jobs, PROGRAMS


class UIDaemonLoggingTests(unittest.TestCase):
    def fixture(self):
        return {'LaunchDaemons': {
            **{label: {'Label': label, 'UserName': 'mobile', 'ProgramArguments': [program],
                       'MachServices': {label: True}, 'EnvironmentVariables': {'HOME': '/var/mobile'}}
               for label, program in PROGRAMS.items()},
            'other': {'Label': 'other', 'RunAtLoad': True}}, 'root-key': [1, 2]}

    def test_changes_only_targeted_logging_preserving_source_and_home(self):
        source = self.fixture()
        before = copy.deepcopy(source)
        result = patch_jobs(source)
        self.assertEqual(source, before)
        self.assertEqual(patch_jobs(result), result)
        expected = copy.deepcopy(before)
        for label in PROGRAMS:
            expected['LaunchDaemons'][label].update(
                StandardErrorPath='/dev/console', StandardOutPath='/dev/console')
            expected['LaunchDaemons'][label]['EnvironmentVariables'].update(
                OS_ACTIVITY_DT_MODE='YES', CFLOG_FORCE_STDERR='YES')
        self.assertEqual(result, expected)

    def test_missing_duplicate_or_wrong_program_refuses(self):
        for label in PROGRAMS:
            for mutation in ['missing', 'duplicate', 'program', 'user']:
                data = self.fixture()
                if mutation == 'missing': del data['LaunchDaemons'][label]
                elif mutation == 'duplicate': data['LaunchDaemons']['duplicate'] = copy.deepcopy(data['LaunchDaemons'][label])
                elif mutation == 'program': data['LaunchDaemons'][label]['ProgramArguments'] = ['/bin/other']
                else: data['LaunchDaemons'][label]['UserName'] = 'root'
                with self.assertRaises(ValueError): patch_jobs(data)
