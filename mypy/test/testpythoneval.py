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

from mypy.myunit import Suite, run_test, SkipTestCaseException
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import parse_test_cases
from mypy.test.helpers import assert_string_arrays_equal


# Files which contain test case descriptions.
python_eval_files = ['pythoneval.test',
                    'python2eval.test']

python_34_eval_files = ['pythoneval-asyncio.test']

# Path to Python 3 interpreter
python3_path = 'python3'

default_python2_interpreter = 'python'


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
    # Write the program to a file.
    program = '_program.py'
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    # Set up module path.
    typing_path = os.path.join(os.getcwd(), 'lib-typing', '3.2')
    assert os.path.isdir(typing_path)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([typing_path, os.getcwd()])
    # Type check the program.
    process = subprocess.Popen([python3_path,
                                os.path.join(os.getcwd(), 'scripts', 'mypy')] + args + [program],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               cwd=test_temp_dir,
                               env=env)
    outb = process.stdout.read()
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    if not process.wait():
        if py2:
            typing_path = os.path.join(os.getcwd(), 'lib-typing', '2.7')
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


def try_find_python2_interpreter():
    try:
        process = subprocess.Popen([default_python2_interpreter, '-V'], stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if b'Python 2.7' in stderr:
            return default_python2_interpreter
        else:
            return None
    except OSError:
        return False


if __name__ == '__main__':
    run_test(PythonEvaluationSuite(), sys.argv[1:])
