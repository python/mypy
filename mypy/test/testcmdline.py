"""Test cases for the command line.

To begin we test that "mypy <directory>[/]" always recurses down the
whole tree.
"""

import os
import re
import subprocess
import sys

from typing import Tuple, List, Dict, Set

from mypy.myunit import Suite, SkipTestCaseException, AssertionFailure
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import fix_cobertura_filename
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal, normalize_error_messages
from mypy.version import __version__, base_version

# Path to Python 3 interpreter
python3_path = sys.executable

# Files containing test case descriptions.
cmdline_files = [
    'cmdline.test',
    'reports.test',
]


class PythonEvaluationSuite(DataSuite):

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in cmdline_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation,
                                  base_path=test_temp_dir,
                                  optional_out=True,
                                  native_sep=True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_python_evaluation(testcase)


def test_python_evaluation(testcase: DataDrivenTestCase) -> None:
    assert testcase.old_cwd is not None, "test was not properly set up"
    # Write the program to a file.
    program = '_program.py'
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    args = parse_args(testcase.input[0])
    args.append('--show-traceback')
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
    if testcase.output_files:
        for path, expected_content in testcase.output_files:
            if not os.path.exists(path):
                raise AssertionFailure(
                    'Expected file {} was not produced by test case'.format(path))
            with open(path, 'r') as output_file:
                actual_output_content = output_file.read().splitlines()
            normalized_output = normalize_file_output(actual_output_content,
                                                      os.path.abspath(test_temp_dir))
            if testcase.native_sep and os.path.sep == '\\':
                normalized_output = [fix_cobertura_filename(line) for line in normalized_output]
            normalized_output = normalize_error_messages(normalized_output)
            assert_string_arrays_equal(expected_content.splitlines(), normalized_output,
                                       'Output file {} did not match its expected output'.format(
                                           path))
    else:
        out = normalize_error_messages(out)
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


def normalize_file_output(content: List[str], current_abs_path: str) -> List[str]:
    """Normalize file output for comparison."""
    timestamp_regex = re.compile('\d{10}')
    result = [x.replace(current_abs_path, '$PWD') for x in content]
    result = [re.sub(r'\b' + re.escape(__version__) + r'\b', '$VERSION', x) for x in result]
    result = [re.sub(r'\b' + re.escape(base_version) + r'\b', '$VERSION', x) for x in result]
    result = [timestamp_regex.sub('$TIMESTAMP', x) for x in result]
    return result
