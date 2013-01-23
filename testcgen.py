"""Test cases for running mypy programs by compiling to C.

Each test cases translates a mypy program to C and then compiles and runs it.
The output (stdout) of the program is compared to expected output. The
translation uses the C builtins (lib/builtins.py).

Note: These test cases are not included in the main test suite yet.
"""

import os.path
import re
import subprocess
import sys

import build
import errors
from myunit import Suite, run_test
from testconfig import test_data_prefix, test_temp_dir
from testdata import parse_test_cases
from testhelpers import assert_string_arrays_equal


# Files which contain test case descriptions.
cgen_files = ['cgen-basic.test',
              'cgen-intops.test']


class CGenSuite(Suite):
    def cases(self):
        c = []
        for f in cgen_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_cgen, test_temp_dir, True)
        return c


def test_cgen(testcase):
    # Build the program.
    text = '\n'.join(testcase.input)
    program = '_program.py'
    build.build(text, program, target=build.C, alt_lib_path='lib')
    # Run the program.
    outfile = './a.out'
    outb = subprocess.check_output([outfile], stderr=subprocess.STDOUT)
    # Split output into lines.
    out = [s.rstrip('\n\r') for s in str(outb, 'utf8').splitlines()]
    # Remove temp file.
    os.remove(outfile)
    # Include line-end comments in the expected output.
    # Note: # characters in string literals can confuse this.
    for s in testcase.input:
        m = re.search(' #(.*)', s)
        if m:
            testcase.output.append(m.group(1).strip())
    # Verify output.
    assert_string_arrays_equal(testcase.output, out,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


if __name__ == '__main__':
    run_test(CGenSuite(), sys.argv[1:])
