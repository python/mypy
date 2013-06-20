"""Test cases for running mypy programs using a Python interpreter.

Each test case type checks a program then runs it using Python. The
output (stdout) of the program is compared to expected output. Type checking
uses full builtins and other stubs.

Note: Currently Python interpreter and mypy implementation paths are hard coded
      (see python_path and mypy_path below).

Note: These test cases are *not* included in the main test suite, as running
      this suite is slow and it would slow down the main suite too much. The
      slowness is due to translating the mypy implementation in each test case.
"""

import os.path
import subprocess
import sys

from mypy.myunit import Suite, run_test
from mypy.testconfig import test_data_prefix, test_temp_dir
from mypy.testdata import parse_test_cases
from mypy.testhelpers import assert_string_arrays_equal


# Files which contain test case descriptions.
python_eval_files = ['pythoneval.test']

# Path to Python 3 interpreter
python_path = 'python3'
# Path to mypy implementation translated to Python.
mypy_path = '~/mypy-py/driver.py'


class PythonEvaluationSuite(Suite):
    def cases(self):
        c = []
        for f in python_eval_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation, test_temp_dir, True)
        return c


def test_python_evaluation(testcase):
    # Write the program to a file.
    program = '_program.py'
    outfile = '_program.out'
    f = open(program, 'w')
    for s in testcase.input:
        f.write('{}\n'.format(s))
    f.close()
    # Run the program.
    outb = subprocess.check_output([python_path,
                                    os.path.expanduser(mypy_path),
                                    'driver.py',
                                    program])
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    # Remove temp file.
    os.remove(program)
    assert_string_arrays_equal(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


if __name__ == '__main__':
    run_test(PythonEvaluationSuite(), sys.argv[1:])
