import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from patch_chronod_home import patch_jobs, ENV, PROGRAM


class ChronodHomeTests(unittest.TestCase):
    def fixture(self):
        return {'LaunchDaemons': {'chrono': {'Label': 'com.apple.chronod',
                'UserName': 'mobile', 'ProgramArguments': [PROGRAM],
                'EnvironmentVariables': {'MallocStackLoggingDirectory': '/private/var/tmp/com.apple.chrono'},
                'MachServices': {'com.apple.chronoservices': True}},
                'other': {'Label': 'other', 'UserName': 'root'}}, 'other-root-key': [1, 2]}

    def test_only_expected_job_environment_changes(self):
        source = self.fixture()
        before = copy.deepcopy(source)
        result = patch_jobs(source)
        self.assertEqual(source, before)
        self.assertEqual(result['LaunchDaemons']['other'], before['LaunchDaemons']['other'])
        self.assertEqual(result['other-root-key'], before['other-root-key'])
        job = result['LaunchDaemons']['chrono']
        original = before['LaunchDaemons']['chrono']
        self.assertEqual({k: v for k, v in job.items() if k != 'EnvironmentVariables'},
                         {k: v for k, v in original.items() if k != 'EnvironmentVariables'})
        self.assertEqual(job['EnvironmentVariables'], original['EnvironmentVariables'] | ENV)
        self.assertEqual(patch_jobs(result), result)

    def test_unknown_or_duplicate_job_refuses(self):
        for field, value in [('UserName', 'root'), ('ProgramArguments', ['/bin/other']),
                             ('Label', 'com.apple.other')]:
            data = self.fixture()
            data['LaunchDaemons']['chrono'][field] = value
            with self.assertRaises(ValueError):
                patch_jobs(data)
        data = self.fixture()
        data['LaunchDaemons']['duplicate'] = copy.deepcopy(data['LaunchDaemons']['chrono'])
        with self.assertRaises(ValueError):
            patch_jobs(data)
