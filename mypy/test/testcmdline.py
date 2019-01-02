"""Test cases for the command line.

To begin we test that "mypy <directory>[/]" always recurses down the
whole tree.
"""

import os
import re
import subprocess
import sys

from typing import List

from mypy.test.config import test_temp_dir, PREFIX
from mypy.test.data import fix_cobertura_filename
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal, normalize_error_messages
import mypy.version

# Path to Python 3 interpreter
python3_path = sys.executable

# Files containing test case descriptions.
cmdline_files = [
    'cmdline.test',
    'reports.test',
]


class PythonCmdlineSuite(DataSuite):
    files = cmdline_files
    native_sep = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        for step in [1] + sorted(testcase.output2):
            test_python_cmdline(testcase, step)


def test_python_cmdline(testcase: DataDrivenTestCase, step: int) -> None:
    assert testcase.old_cwd is not None, "test was not properly set up"
    # Write the program to a file.
    program = '_program.py'
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w', encoding='utf8') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    args = parse_args(testcase.input[0])
    args.append('--show-traceback')
    args.append('--no-site-packages')
    # Type check the program.
    fixed = [python3_path, '-m', 'mypy']
    env = os.environ.copy()
    env['PYTHONPATH'] = PREFIX
    process = subprocess.Popen(fixed + args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               cwd=test_temp_dir,
                               env=env)
    outb, errb = process.communicate()
    result = process.returncode
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    err = [s.rstrip('\n\r') for s in str(errb, 'utf8').splitlines()]

    if "PYCHARM_HOSTED" in os.environ:
        for pos, line in enumerate(err):
            if line.startswith('pydev debugger: '):
                # Delete the attaching debugger message itself, plus the extra newline added.
                del err[pos:pos + 2]
                break

    # Remove temp file.
    os.remove(program_path)
    # Compare actual output to expected.
    if testcase.output_files:
        # Ignore stdout, but we insist on empty stderr and zero status.
        if err or result:
            raise AssertionError(
                'Expected zero status and empty stderr%s, got %d and\n%s' %
                (' on step %d' % step if testcase.output2 else '',
                 result, '\n'.join(err + out)))
        for path, expected_content in testcase.output_files:
            if not os.path.exists(path):
                raise AssertionError(
                    'Expected file {} was not produced by test case{}'.format(
                        path, ' on step %d' % step if testcase.output2 else ''))
            with open(path, 'r', encoding='utf8') as output_file:
                actual_output_content = output_file.read().splitlines()
            normalized_output = normalize_file_output(actual_output_content,
                                                      os.path.abspath(test_temp_dir))
            # We always normalize things like timestamp, but only handle operating-system
            # specific things if requested.
            if testcase.normalize_output:
                if testcase.suite.native_sep and os.path.sep == '\\':
                    normalized_output = [fix_cobertura_filename(line)
                                         for line in normalized_output]
                normalized_output = normalize_error_messages(normalized_output)
            assert_string_arrays_equal(expected_content.splitlines(), normalized_output,
                                       'Output file {} did not match its expected output{}'.format(
                                           path, ' on step %d' % step if testcase.output2 else ''))
    else:
        if testcase.normalize_output:
            out = normalize_error_messages(err + out)
        obvious_result = 1 if out else 0
        if obvious_result != result:
            out.append('== Return code: {}'.format(result))
        expected_out = testcase.output if step == 1 else testcase.output2[step]
        assert_string_arrays_equal(expected_out, out,
                                   'Invalid output ({}, line {}){}'.format(
                                       testcase.file, testcase.line,
                                       ' on step %d' % step if testcase.output2 else ''))


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
    timestamp_regex = re.compile(r'\d{10}')
    result = [x.replace(current_abs_path, '$PWD') for x in content]
    version = mypy.version.__version__
    result = [re.sub(r'\b' + re.escape(version) + r'\b', '$VERSION', x) for x in result]
    # We generate a new mypy.version when building mypy wheels that
    # lacks base_version, so handle that case.
    base_version = getattr(mypy.version, 'base_version', version)
    result = [re.sub(r'\b' + re.escape(base_version) + r'\b', '$VERSION', x) for x in result]
    result = [timestamp_regex.sub('$TIMESTAMP', x) for x in result]
    return result
