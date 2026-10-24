#!/usr/bin/env python3
"""Set an explicit mobile home for chronod in the host COW launchd job only."""
import copy

ENV = {'HOME': '/var/mobile', 'CFFIXED_USER_HOME': '/var/mobile',
       'TMPDIR': '/private/var/tmp/com.apple.chrono',
       'OS_ACTIVITY_DT_MODE': 'YES', 'CFLOG_FORCE_STDERR': 'YES'}
PROGRAM = '/System/Library/PrivateFrameworks/ChronoCore.framework/Support/chronod'


def patch_jobs(data):
    result = copy.deepcopy(data)
    jobs = result['LaunchDaemons']
    found = [job for job in jobs.values() if job.get('Label') == 'com.apple.chronod']
    if len(found) != 1:
        raise ValueError('Expected exactly one chronod job')
    job = found[0]
    if job.get('UserName') != 'mobile' or job.get('ProgramArguments') != [PROGRAM]:
        raise ValueError('Unsupported chronod identity/program')
    job.setdefault('EnvironmentVariables', {}).update(ENV)
    return result
