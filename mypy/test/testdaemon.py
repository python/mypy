"""End-to-end test cases for the daemon (dmypy).

These are special because they run multiple shell commands.
"""

import os
import subprocess

from typing import List, Tuple

from mypy.test.config import test_temp_dir, PREFIX
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal

# Files containing test cases descriptions.
daemon_files = [
    'daemon.test',
]

class DaemonSuite(DataSuite):
    files = daemon_files

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_daemon(testcase)


def test_daemon(testcase: DataDrivenTestCase) -> None:
    assert testcase.old_cwd is not None, "test was not properly set up"
    for i, cmd in enumerate(parse_script(testcase.input)):
        input = cmd[0]
        expected_lines = cmd[1:]
        assert input.startswith('$')
        input = input[1:].strip()
        if input.startswith('dmypy '):
            input = 'python3 -m mypy.' + input
        sts, output = run_cmd(input)
        output_lines = output.splitlines()
        if sts:
            output_lines.append('== Return code: %d' % sts)
        if expected_lines != output_lines: import pdb; pdb.set_trace()
        assert_string_arrays_equal(expected_lines,
                                   output_lines,
                                   "Command %d (%s) did not give expected output" %
                                   (i + 1, input))


def parse_script(input: str) -> List[str]:
    # Parse testcase.input into commands.
    # Each command starts with a line starting with '$'.
    # The first line (less '$') is sent to the shell.
    # The remaining lines are expected output.
    commands = []
    cmd = []
    for line in input:
        if line.startswith('$'):
            if cmd:
                assert cmd[0].startswith('$')
                commands.append(cmd)
                cmd = []
        cmd.append(line)
    if cmd:
        commands.append(cmd)
    return commands


def run_cmd(input: str) -> Tuple[int, str]:
    env = os.environ.copy()
    env['PYTHONPATH'] = PREFIX
    try:
        output = subprocess.check_output(input,
                                         shell=True,
                                         stderr=subprocess.STDOUT,
                                         universal_newlines=True,
                                         cwd=test_temp_dir,
                                         env=env)
        return 0, output
    except subprocess.CalledProcessError as err:
        output = err.output
        if err.stderr:
            output = err.stderr + output
        return err.returncode, output
