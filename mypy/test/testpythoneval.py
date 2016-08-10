"""Test cases for running mypy programs using a Python interpreter.

Each test case type checks a program then runs it using Python. The
output (stdout) of the program is compared to expected output. Type checking
uses full builtins and other stubs.

Note: Currently Python interpreter paths are hard coded.

Note: These test cases are *not* included in the main test suite, as including
      this suite would slow down the main suite too much.
"""

import os
import os.path
import subprocess
import sys

import typing

from mypy.myunit import Suite, SkipTestCaseException
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import parse_test_cases
from mypy.test.helpers import assert_string_arrays_equal
from mypy.util import try_find_python2_interpreter


# Files which contain test case descriptions.
python_eval_files = ['pythoneval.test',
                     'python2eval.test']

python_34_eval_files = ['pythoneval-asyncio.test',
                        'pythoneval-enum.test']

# Path to Python 3 interpreter
python3_path = sys.executable


class PythonEvaluationSuite(Suite):
    def cases(self):
        c = []
        for f in python_eval_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation, test_temp_dir, True)
        if sys.version_info.major == 3 and sys.version_info.minor >= 4:
            for f in python_34_eval_files:
                c += parse_test_cases(os.path.join(test_data_prefix, f),
                    test_python_evaluation, test_temp_dir, True)
        return c


def test_python_evaluation(testcase):
    python2_interpreter = try_find_python2_interpreter()
    # Use Python 2 interpreter if running a Python 2 test case.
    if testcase.name.lower().endswith('python2'):
        if not python2_interpreter:
            # Skip, can't find a Python 2 interpreter.
            raise SkipTestCaseException()
        interpreter = python2_interpreter
        args = ['--py2']
        py2 = True
    else:
        interpreter = python3_path
        args = []
        py2 = False
    args.append('--tb')  # Show traceback on crash.
    # Write the program to a file.
    program = '_program.py'
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    # Type check the program.
    # This uses the same PYTHONPATH as the current process.
    process = subprocess.Popen([python3_path,
                                os.path.join(testcase.old_cwd, 'scripts', 'mypy')]
                            + args + [program],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               cwd=test_temp_dir)
    outb = process.stdout.read()
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    if not process.wait():
        # Set up module path for the execution.
        # This needs the typing module but *not* the mypy module.
        vers_dir = '2.7' if py2 else '3.2'
        typing_path = os.path.join(testcase.old_cwd, 'lib-typing', vers_dir)
        assert os.path.isdir(typing_path)
        env = os.environ.copy()
        env['PYTHONPATH'] = typing_path
        process = subprocess.Popen([interpreter, program],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   cwd=test_temp_dir,
                                   env=env)
        outb = process.stdout.read()
        # Split output into lines.
        out += [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    # Remove temp file.
    os.remove(program_path)
    assert_string_arrays_equal(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))
