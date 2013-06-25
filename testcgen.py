"""Test cases for compiling mypy programs to C and running them.

The compilation to C uses the full C builtins (lib/builtins.py).
    
Note: These test cases are not included in the main test suite yet.
"""

import os.path
import re
import subprocess
import sys

from mypy import build
from mypy import errors
from mypy.myunit import Suite, run_test
from mypy.testconfig import test_data_prefix, test_temp_dir
from mypy.testdata import parse_test_cases
from mypy.testhelpers import assert_string_arrays_equal
from mypy.testhelpers import assert_string_arrays_equal_wildcards


class CGenCompileSuite(Suite):
    """Test cases that compile to C and perform checks on the C code."""

    files = ['cgen-codeoutput.test']

    def cases(self):
        c = []
        for f in self.files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_cgen_compile, test_temp_dir, True)
        return c


def test_cgen_compile(testcase):
    # Build the program.
    text = '\n'.join(testcase.input)
    try:
        build.build('_program.py',
                    target=build.C,
                    program_text=text, 
                    alt_lib_path='lib',
                    flags=[build.COMPILE_ONLY, build.TEST_BUILTINS])
        outfile = '_program.c'
        f = open(outfile)
        out = [s.rstrip('\n\r') for s in f.readlines()]
        f.close()
        os.remove(outfile)
    except errors.CompileError as e:
        out = e.messages
    # Verify output.
    assert_string_arrays_equal_wildcards(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


class CGenRunSuite(Suite):
    """Test cases that compile a program to C and run it.

    The output (stdout) of the program is compared to expected output.
    """

    # Test case descriptions
    files = ['cgen-basic.test',
             'cgen-intops.test',
             'cgen-classes.test']

    def cases(self):
        c = []
        for f in self.files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_cgen, test_temp_dir, True)
        return c


def test_cgen(testcase):
    # Build the program.
    text = '\n'.join(testcase.input)
    program = '_program.py'
    try:
        build.build(program,
                    target=build.C,
                    program_text=text,
                    flags=[build.TEST_BUILTINS],
                    alt_lib_path='lib')
        # Run the program.
        outfile = './_program'
        outb = subprocess.check_output([outfile], stderr=subprocess.STDOUT)
        # Split output into lines.
        out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
        # Remove temp file.
        os.remove(outfile)
    except errors.CompileError as e:
        out = e.messages
    # Include line-end comments in the expected output.
    # Note: # characters in string literals can confuse this.
    for s in testcase.input:
        m = re.search(' #(?! type:)(.*)', s)
        if m:
            testcase.output.append(m.group(1).strip())
    # Verify output.
    assert_string_arrays_equal(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


class CGenSuite(Suite):
    def __init__(self):
        self.test_compile = CGenCompileSuite()
        self.test_run = CGenRunSuite()
        super().__init__()


if __name__ == '__main__':
    run_test(CGenSuite(), sys.argv[1:])
