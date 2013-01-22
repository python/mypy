"""Test cases for mypy-to-Python translation.

Each test case translates a fragment of mypy to Python and checks that
the generated Python code is as expected. The test cases use minimal builtins
stubs to speed up running.
"""

import os.path
import sys

import build
from myunit import Suite, run_test
from testconfig import test_data_prefix, test_temp_dir
from testdata import parse_test_cases
from testhelpers import assert_string_arrays_equal
from testoutput import fix_path, remove_prefix
from pythongen import PythonGenerator
from errors import CompileError


# Files which contain test case descriptions.
python_generation_files = ['pythongen.test']


class PythonGenerationSuite(Suite):
    def cases(self):
        c = []
        for f in python_generation_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_generation, test_temp_dir, True)
        return c


def test_python_generation(testcase):
    """Perform a mypy-to-Python source code transformation test case."""
    any a
    expected = testcase.output
    # By default, assume an identity translation. This is useful for
    # dynamically typed code.
    if expected == []:
        expected = testcase.input
    try:
        src = '\n'.join(testcase.input)
        # Parse and semantically analyze the source program.
        files, infos, types = build.build(src, 'main',
                                          target=build.SEMANTIC_ANALYSIS,
                                          test_builtins=True,
                                          alt_lib_path=test_temp_dir)
        a = []
        first = True
        # Produce an output containing the pretty-printed forms (with original
        # formatting) of all the relevant source files.
        for fnam in sorted(files.keys()):
            f = files[fnam]
            # Omit the builtins module and files marked for omission.
            if not f.path.endswith(os.sep +
                                   'builtins.py') and '-skip.' not in f.path:
                # Add file name + colon for files other than the first.
                if not first:
                    a.append('{}:'.format(
                        fix_path(remove_prefix(f.path, test_temp_dir))))

                ver = 3
                # Generate Python 2 instead of 3?
                if '-2' in testcase.name:
                    ver = 2
                v = PythonGenerator(ver)
                f.accept(v)
                s = v.output()
                if s != '':
                    a += s.split('\n')
            first = False
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        expected, a, 'Invalid source code output ({}, line {})'.format(
            testcase.file, testcase.line))


if __name__ == '__main__':
    run_test(PythonGenerationSuite(), sys.argv[1:])
