"""Test cases for running mypy programs using a Python interpreter.

Each test case type checks a program then runs it using Python. The
output (stdout) of the program is compared to expected output. Type checking
uses full builtins and other stubs.

Note: Currently Python interpreter paths are hard coded.

Note: These test cases are *not* included in the main test suite, as including
      this suite would slow down the main suite too much.
"""

from contextlib import contextmanager
import errno
import os
import os.path
import re
import subprocess
import sys

import typing
from typing import Dict, List, Tuple

from mypy.myunit import Suite, SkipTestCaseException
from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import DataDrivenTestCase, parse_test_cases
from mypy.test.helpers import assert_string_arrays_equal
from mypy.util import try_find_python2_interpreter


# Files which contain test case descriptions.
python_eval_files = ['pythoneval.test',
                     'python2eval.test']

python_34_eval_files = ['pythoneval-asyncio.test',
                        'pythoneval-enum.test']

# Path to Python 3 interpreter
python3_path = sys.executable
program_re = re.compile(r'\b_program.py\b')


class PythonEvaluationSuite(Suite):
    def cases(self) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in python_eval_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation, test_temp_dir, True)
        if sys.version_info.major == 3 and sys.version_info.minor >= 4:
            for f in python_34_eval_files:
                c += parse_test_cases(os.path.join(test_data_prefix, f),
                    test_python_evaluation, test_temp_dir, True)
        return c


def test_python_evaluation(testcase: DataDrivenTestCase) -> None:
    """Runs Mypy in a subprocess.

    If this passes without errors, executes the script again with a given Python
    version.
    """
    mypy_cmdline = [
        python3_path,
        os.path.join(testcase.old_cwd, 'scripts', 'mypy'),
        '--show-traceback',
    ]
    py2 = testcase.name.lower().endswith('python2')
    if py2:
        mypy_cmdline.append('--py2')
        interpreter = try_find_python2_interpreter()
        if not interpreter:
            # Skip, can't find a Python 2 interpreter.
            raise SkipTestCaseException()
    else:
        interpreter = python3_path

    # Write the program to a file.
    program = '_' + testcase.name + '.py'
    mypy_cmdline.append(program)
    program_path = os.path.join(test_temp_dir, program)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    # Type check the program.
    # This uses the same PYTHONPATH as the current process.
    returncode, out = run(mypy_cmdline)
    if returncode == 0:
        # Set up module path for the execution.
        # This needs the typing module but *not* the mypy module.
        vers_dir = '2.7' if py2 else '3.2'
        typing_path = os.path.join(testcase.old_cwd, 'lib-typing', vers_dir)
        assert os.path.isdir(typing_path)
        env = os.environ.copy()
        env['PYTHONPATH'] = typing_path
        returncode, interp_out = run([interpreter, program], env=env)
        out += interp_out
    # Remove temp file.
    os.remove(program_path)
    assert_string_arrays_equal(adapt_output(testcase), out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


def split_lines(*streams: bytes) -> List[str]:
    """Returns a single list of string lines from the byte streams in args."""
    return [
        s.rstrip('\n\r')
        for stream in streams
        for s in str(stream, 'utf8').splitlines()
    ]


def adapt_output(testcase: DataDrivenTestCase) -> List[str]:
    """Translates the generic _program.py into the actual filename."""
    program = '_' + testcase.name + '.py'
    return [program_re.sub(program, line) for line in testcase.output]


def run(
    cmdline: List[str], *, env: Dict[str, str] = None, timeout: int = 30
) -> Tuple[int, List[str]]:
    """A poor man's subprocess.run() for 3.3 and 3.4 compatibility."""
    process = subprocess.Popen(
        cmdline,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=test_temp_dir,
    )
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        out = err = b''
        process.kill()
    return process.returncode, split_lines(out, err)
