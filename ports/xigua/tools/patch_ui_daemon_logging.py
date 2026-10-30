#!/usr/bin/env python3
"""Route only the two observed failing UI dependencies to the native console."""
import copy

PROGRAMS = {
    'com.apple.chronod': '/System/Library/PrivateFrameworks/ChronoCore.framework/Support/chronod',
    'com.apple.mobileactivationd': '/usr/libexec/mobileactivationd',
}


def patch_jobs(data):
    result = copy.deepcopy(data)
    for label, program in PROGRAMS.items():
        jobs = [job for job in result['LaunchDaemons'].values() if job.get('Label') == label]
        if len(jobs) != 1:
            raise ValueError('Expected exactly one ' + label)
        job = jobs[0]
        if job.get('UserName') != 'mobile' or job.get('ProgramArguments') != [program]:
            raise ValueError('Unsupported identity/program for ' + label)
        job['StandardErrorPath'] = '/dev/console'
        job['StandardOutPath'] = '/dev/console'
        job.setdefault('EnvironmentVariables', {}).update({
            'OS_ACTIVITY_DT_MODE': 'YES', 'CFLOG_FORCE_STDERR': 'YES',
        })
    return result
