"""Test cases for the command line.

To begin we test that "mypy <directory>[/]" always recurses down the
whole tree.
"""

import os
import re
import subprocess
import sys

from typing import Tuple, List, Dict, Set

from mypy.myunit import Suite, SkipTestCaseException
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.helpers import assert_string_arrays_equal

# Path to Python 3 interpreter
python3_path = sys.executable

# Files containing test case descriptions.
cmdline_files = ['cmdline.test']


class PythonEvaluationSuite(Suite):

    def cases(self) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in cmdline_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation,
                                  base_path=test_temp_dir,
                                  optional_out=True,
                                  native_sep=True)
        return c


def test_python_evaluation(testcase: DataDrivenTestCase) -> None:
    # Write the program to a file.
    program = '_program.py'
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    args = parse_args(testcase.input[0])
    args.append('--tb')  # Show traceback on crash.
    # Type check the program.
    fixed = [python3_path,
             os.path.join(testcase.old_cwd, 'scripts', 'mypy')]
    process = subprocess.Popen(fixed + args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               cwd=test_temp_dir)
    outb = process.stdout.read()
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    # Remove temp file.
    os.remove(program_path)
    # Compare actual output to expected.
    assert_string_arrays_equal(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


def parse_args(line: str) -> List[str]:
    """Parse the first line of the program for the command line.

    This should have the form

      # cmd: mypy <options>

    For example:

      # cmd: mypy pkg/
    """
    m = re.match('# cmd: mypy (.*)$', line)
    if not m:
        return []  # No args; mypy will spit out an error.
    return m.group(1).split()
