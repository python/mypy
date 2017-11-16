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
import re
import subprocess
import sys

import pytest  # type: ignore  # no pytest in typeshed
from typing import Dict, List, Tuple, Optional

from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import DataDrivenTestCase, parse_test_cases, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.util import try_find_python2_interpreter
from mypy import api

# Files which contain test case descriptions.
python_eval_files = ['pythoneval.test',
                     'python2eval.test']

python_34_eval_files = ['pythoneval-asyncio.test']

# Path to Python 3 interpreter
python3_path = sys.executable
program_re = re.compile(r'\b_program.py\b')


class PythonEvaluationSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in python_eval_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_evaluation, test_temp_dir, True)
        if sys.version_info.major == 3 and sys.version_info.minor >= 4:
            for f in python_34_eval_files:
                c += parse_test_cases(os.path.join(test_data_prefix, f),
                    test_python_evaluation, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_python_evaluation(testcase)


def test_python_evaluation(testcase: DataDrivenTestCase) -> None:
    """Runs Mypy in a subprocess.

    If this passes without errors, executes the script again with a given Python
    version.
    """
    assert testcase.old_cwd is not None, "test was not properly set up"
    mypy_cmdline = ['--show-traceback']
    py2 = testcase.name.lower().endswith('python2')
    if py2:
        mypy_cmdline.append('--py2')
        interpreter = try_find_python2_interpreter()
        if interpreter is None:
            # Skip, can't find a Python 2 interpreter.
            pytest.skip()
            # placate the type checker
            return
    else:
        interpreter = python3_path

    # Write the program to a file.
    program = '_' + testcase.name + '.py'
    program_path = os.path.join(test_temp_dir, program)
    mypy_cmdline.append(program_path)
    with open(program_path, 'w') as file:
        for s in testcase.input:
            file.write('{}\n'.format(s))
    output = []
    # Type check the program.
    out, err, returncode = api.run(mypy_cmdline)
    # split lines, remove newlines, and remove directory of test case
    for line in (out + err).splitlines():
        if line.startswith(test_temp_dir + os.sep):
            output.append(line[len(test_temp_dir + os.sep):].rstrip("\r\n"))
        else:
            output.append(line.rstrip("\r\n"))
    if returncode == 0:
        # Execute the program.
        returncode, interp_out = run([interpreter, program])
        output.extend(interp_out)
    # Remove temp file.
    os.remove(program_path)
    assert_string_arrays_equal(adapt_output(testcase), output,
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
    cmdline: List[str], *, env: Optional[Dict[str, str]] = None, timeout: int = 300
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
