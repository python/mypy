#!/usr/bin/env python3
import subprocess
from subprocess import Popen
from os import system
from sys import argv, exit, platform, executable, version_info


# Use the Python provided to execute the script, or fall back to a sane default
if version_info >= (3, 5, 0):
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
PEP561 = 'PEP561Suite'
EVALUATION = 'PythonEvaluation'
DAEMON = 'testdaemon'
STUBGEN_CMD = 'StubgenCmdLine'
STUBGEN_PY = 'StubgenPythonSuite'
MYPYC_RUN = 'TestRun'
MYPYC_RUN_MULTI = 'TestRunMultiFile'
MYPYC_EXTERNAL = 'TestExternal'
MYPYC_COMMAND_LINE = 'TestCommandLine'
ERROR_STREAM = 'ErrorStreamSuite'


ALL_NON_FAST = [
    CMDLINE,
    SAMPLES,
    TYPESHED,
    PEP561,
    EVALUATION,
    DAEMON,
    STUBGEN_CMD,
    STUBGEN_PY,
    MYPYC_RUN,
    MYPYC_RUN_MULTI,
    MYPYC_EXTERNAL,
    MYPYC_COMMAND_LINE,
    ERROR_STREAM,
]


# These must be enabled by explicitly including 'mypyc-extra' on the command line.
MYPYC_OPT_IN = [MYPYC_RUN, MYPYC_RUN_MULTI]

# We split the pytest run into three parts to improve test
# parallelization. Each run should have tests that each take a roughly similar
# time to run.
cmds = {
    # Self type check
    'self': python_name + ' -m mypy --config-file mypy_self_check.ini -p mypy',
    # Lint
    'lint': 'flake8 -j0',
    # Fast test cases only (this is the bulk of the test suite)
    'pytest-fast': 'pytest -q -k "not (%s)"' % ' or '.join(ALL_NON_FAST),
    # Test cases that invoke mypy (with small inputs)
    'pytest-cmdline': 'pytest -q -k "%s"' % ' or '.join([CMDLINE,
                                                         EVALUATION,
                                                         STUBGEN_CMD,
                                                         STUBGEN_PY]),
    # Test cases that may take seconds to run each
    'pytest-slow': 'pytest -q -k "%s"' % ' or '.join(
        [SAMPLES,
         TYPESHED,
         PEP561,
         DAEMON,
         MYPYC_EXTERNAL,
         MYPYC_COMMAND_LINE,
         ERROR_STREAM]),
    # Test cases to run in typeshed CI
    'typeshed-ci': 'pytest -q -k "%s"' % ' or '.join([CMDLINE, EVALUATION, SAMPLES, TYPESHED]),
    # Mypyc tests that aren't run by default, since they are slow and rarely
    # fail for commits that don't touch mypyc
    'mypyc-extra': 'pytest -q -k "%s"' % ' or '.join(MYPYC_OPT_IN),
}

# Stop run immediately if these commands fail
FAST_FAIL = ['self', 'lint']

DEFAULT_COMMANDS = [cmd for cmd in cmds if cmd not in ('mypyc-extra', 'typeshed-ci')]

assert all(cmd in cmds for cmd in FAST_FAIL)


def run_cmd(name: str) -> int:
    status = 0
    cmd = cmds[name]
    print('run %s: %s' % (name, cmd))
    res = (system(cmd) & 0x7F00) >> 8
    if res:
        print('\nFAILED: %s' % name)
        status = res
        if name in FAST_FAIL:
            exit(status)
    return status


def start_background_cmd(name: str) -> Popen:
    cmd = cmds[name]
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE)
    return proc


def wait_background_cmd(name: str, proc: Popen) -> int:
    output = proc.communicate()[0]
    status = proc.returncode
    print('run %s: %s' % (name, cmds[name]))
    if status:
        print(output.decode().rstrip())
        print('\nFAILED: %s' % name)
        if name in FAST_FAIL:
            exit(status)
    return status


def main() -> None:
    prog, *args = argv

    if not set(args).issubset(cmds):
        print("usage:", prog, " ".join('[%s]' % k for k in cmds))
        print()
        print('Run the given tests. If given no arguments, run everything except mypyc-extra.')
        exit(1)

    if not args:
        args = DEFAULT_COMMANDS[:]

    status = 0

    if 'self' in args and 'lint' in args:
        # Perform lint and self check in parallel as it's faster.
        proc = start_background_cmd('lint')
        cmd_status = run_cmd('self')
        if cmd_status:
            status = cmd_status
        cmd_status = wait_background_cmd('lint', proc)
        if cmd_status:
            status = cmd_status
        args = [arg for arg in args if arg not in ('self', 'lint')]

    for arg in args:
        cmd_status = run_cmd(arg)
        if cmd_status:
            status = cmd_status

    exit(status)


if __name__ == '__main__':
    main()
