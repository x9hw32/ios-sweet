#!/usr/bin/env python3
"""Summarize a saved XNU boot console and keep each process's ASLR context."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
SAMPLE = re.compile(r'^SMP --- sample (\d+)')
PROCESS = re.compile(r'^SMP (\S+)\[(\d+)\] slide (0x[0-9a-fA-F]+) mh (0x[0-9a-fA-F]+)')
THREAD = re.compile(r'^SMP (\S+) t(\d+) pc (0x[0-9a-fA-F]+) lr (0x[0-9a-fA-F]+) sp (0x[0-9a-fA-F]+) bt(.*)')
CRASH = re.compile(r'^CRASH (\S+)\[\d+\] sig (\d+)')
SPACE = re.compile(r'ENOSPC|No space left|(?:errno|error|err)\s*[:=]?\s*28\b', re.I)
TIMEOUT = re.compile(r'timed?\s*out|timeout|waiting for|waited for', re.I)


def records(text):
    # Console writers can concatenate truncated sampler records. Preserve their
    # physical line number while keeping later threads out of the first stack.
    for number, raw in enumerate(text.splitlines(), 1):
        for part in re.split(r'(?=SMP \S+ t\d+ pc )', raw):
            if part.strip(): yield number, part


def parse(text):
    crashes = Counter()
    samples, space, waits, storage, boot = [], [], [], [], []
    current = None
    orphans = 0
    for number, raw in records(text):
        line = ANSI.sub('', raw).strip()
        hit = CRASH.match(line)
        if hit:
            crashes[hit[1] + ' sig ' + hit[2]] += 1
        item = {'line': number, 'text': line}
        if SPACE.search(line): space.append(item)
        if TIMEOUT.search(line): waits.append(item)
        if re.search(r'(?:XIGUA|SWEET) (?:UFS|LOG):.*(?:fail|error|timed|stopping)', line, re.I):
            storage.append(item)
        if ('BSD root:' in line or 'hfs: mounted' in line or 'load_init_program:' in line or
                re.search(r'(?:XIGUA|SWEET) CPU:.*(?:all|started|ready|failed)', line)):
            boot.append(item)
        hit = SAMPLE.match(line)
        if hit:
            current = {'index': int(hit[1]), 'line': number, 'processes': {}}
            samples.append(current)
            continue
        hit = PROCESS.match(line)
        if hit:
            if current is None:
                current = {'index': None, 'line': number, 'processes': {}}
                samples.append(current)
            current['processes'][hit[1]] = {
                'pid': int(hit[2]), 'slide': int(hit[3], 16), 'mh': int(hit[4], 16), 'threads': []}
            continue
        hit = THREAD.match(line)
        if hit:
            if current is None or hit[1] not in current['processes']:
                orphans += 1
                continue
            process = current['processes'][hit[1]]
            addresses = [int(hit[3], 16), int(hit[4], 16)]
            addresses += [int(a, 16) for a in re.findall(r'0x[0-9a-fA-F]+', hit[6])]
            frames = []
            for address in addresses:
                unslid = address - process['slide']
                if 0x180000000 <= unslid < 0x300000000:
                    frames.append({'address': hex(address), 'kind': 'shared-cache', 'unslid': hex(unslid)})
                elif process['mh'] <= address < process['mh'] + 0x10000000 and process['mh']:
                    frames.append({'address': hex(address), 'kind': 'main-binary',
                                   'mach_o_address': hex(address - process['mh'] + 0x100000000)})
                else:
                    frames.append({'address': hex(address), 'kind': 'unknown'})
            process['threads'].append({'index': int(hit[2]), 'sp': hit[5], 'frames': frames})
    return {'crashes': dict(crashes.most_common()), 'no_space_lines': space,
            'wait_lines': waits, 'storage_errors': storage, 'boot_lines': boot,
            'samples': samples, 'orphan_thread_lines': orphans}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('console', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = parse(args.console.read_text(errors='replace'))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = [f"Samples: {len(report['samples'])}; orphan thread lines: {report['orphan_thread_lines']}",
             f"No-space messages: {len(report['no_space_lines'])}; storage errors: {len(report['storage_errors'])}"]
    lines += [f'Crash headers: {name}: {count}' for name, count in report['crashes'].items()]
    for kind in ['boot_lines', 'storage_errors', 'no_space_lines', 'wait_lines']:
        lines += [f'{kind} L{i["line"]}: {i["text"]}' for i in report[kind][-30:]]
    for sample in report['samples']:
        for name, process in sample['processes'].items():
            for thread in process['threads']:
                if thread['index'] != 0: continue
                frames = ', '.join(f.get('unslid', f.get('mach_o_address', f['address'])) for f in thread['frames'][:8])
                lines.append(f'Sample {sample["index"]} {name}[{process["pid"]}] main: {frames}')
    (args.output / 'summary.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:45]))
    print(args.output / 'report.json')


if __name__ == '__main__':
    main()
