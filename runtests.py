#!/usr/bin/env python3
from os import system
from sys import argv, exit, platform, executable, version_info

prog, *args = argv


# Use the Python provided to execute the script, or fall back to a sane default
if version_info >= (3, 4, 0):
        python_name = executable
else:
    if platform == 'win32':
        python_name = 'py -3'
    else:
        python_name = 'python3'

# Slow test suites
CMDLINE = 'PythonCmdline'
SAMPLES = 'SamplesSuite'
TYPESHED = 'TypeshedSuite'
PEP561 = 'TestPEP561'
EVALUATION = 'PythonEvaluation'

ALL_NON_FAST = [CMDLINE, SAMPLES, TYPESHED, PEP561, EVALUATION]

# We split the pytest run into three parts to improve test
# parallelization. Each run should have tests that each take a roughly similiar
# time to run.
cmds = {
    # Self type check
    'self': python_name + ' -m mypy --config-file mypy_self_check.ini -p mypy',
    # Lint
    'lint': 'flake8 -j0',
    # Fast test cases only (this is the bulk of the test suite)
    'pytest-fast': 'pytest -k "not (%s)"' % ' or '.join(ALL_NON_FAST),
    # Test cases that invoke mypy (with small inputs)
    'pytest-cmdline': 'pytest -k "%s"' % ' or '.join([CMDLINE, EVALUATION]),
    # Test cases that may take seconds to run each
    'pytest-slow': 'pytest -k "%s"' % ' or '.join([SAMPLES, TYPESHED, PEP561]),
}

# Stop run immediately if these commands fail
FAST_FAIL = ['self', 'lint']

assert all(cmd in cmds for cmd in FAST_FAIL)

if not set(args).issubset(cmds):
    print("usage:", prog, " ".join('[%s]' % k for k in cmds))
    exit(1)

if not args:
    args = list(cmds)

status = 0

for arg in args:
    cmd = cmds[arg]
    print('run %s: %s' % (arg, cmd))
    res = (system(cmd) & 0x7F00) >> 8
    if res:
        print('\nFAILED: %s' % arg)
        status = res
        if arg in FAST_FAIL:
            exit(status)

exit(status)
