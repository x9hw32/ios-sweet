"""Use real sampler/crash wire formats, including partial ring snapshots."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from analyze_boot_log import parse


class BootLogTests(unittest.TestCase):
    def test_samples_keep_process_slides_separate_and_survive_pid_relaunch(self):
        text = '''SMP backboardd t0 pc 0x180004000 lr 0x180004004 sp 0x2000 bt
SMP --- sample 0
SMP SpringBoard[41] slide 0x4000 mh 0x100020000
SMP SpringBoard t0 pc 0x180004000 lr 0x100020100 sp 0x2000 bt 0x180004008
SMP backboardd[30] slide 0x8000 mh 0x100040000
SMP backboardd t0 pc 0x180008000 lr 0x100040200 sp 0x3000 bt
SMP --- sample 1
SMP SpringBoard[77] slide 0xc000 mh 0x100080000
SMP SpringBoard t0 pc 0x18000c000 lr 0x100080300 sp 0x4000 bt
'''
        r = parse(text)
        self.assertEqual(r['orphan_thread_lines'], 1)
        a, b = r['samples']
        for s, name in [(a, 'SpringBoard'), (a, 'backboardd'), (b, 'SpringBoard')]:
            self.assertEqual(s['processes'][name]['threads'][0]['frames'][0]['unslid'], '0x180000000')
        self.assertEqual(a['processes']['SpringBoard']['threads'][0]['frames'][1]['mach_o_address'], '0x100000100')
        self.assertEqual(b['processes']['SpringBoard']['pid'], 77)

    def test_concatenated_console_records_do_not_merge_thread_stacks(self):
        r = parse('SMP --- sample 0\nSMP backboardd[56] slide 0x4000 mh 0x100000000\n'
                  'SMP backboardd t9 pc 0x180004000 lr 0x180004004 sp 0x2000 bt 0x180004008'
                  'SMP backboardd t10 pc 0x180004010 lr 0x180004014 sp 0x3000 bt 0x180004018\n')
        threads = r['samples'][0]['processes']['backboardd']['threads']
        self.assertEqual([t['index'] for t in threads], [9, 10])
        self.assertEqual(len(threads[0]['frames']), 3)
        self.assertEqual(threads[1]['frames'][0]['unslid'], '0x180000010')

    def test_error_counts_are_evidence_and_no_panic_is_not_treated_as_success(self):
        r = parse('''CRASH mediaserverd[10] sig 11 code 0
CRASH mediaserverd pc 0x180001000
CRASH mediaserverd[15] sig 11 code 0
backboardd: No space left on device
cfprefsd: error=28
XIGUA LOG: write failed (5), stopping
IOKit wait timed out
''')
        self.assertEqual(r['crashes'], {'mediaserverd sig 11': 2})
        self.assertEqual(len(r['no_space_lines']), 2)
        self.assertEqual(len(r['storage_errors']), 1)
        self.assertEqual(r['samples'], [])
