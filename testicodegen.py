"""Test cases for icode generation."""

import os.path
import re
import sys

import build
import icode
from myunit import Suite, run_test
from testhelpers import assert_string_arrays_equal_wildcards
from testdata import parse_test_cases
from testconfig import test_data_prefix, test_temp_dir
from testoutput import remove_prefix
from testtransform import builtins_wrapper, remove_comment_lines
from transform import DyncheckTransformVisitor
from errors import CompileError


# The builtins stub used during icode generation test cases.
ICODE_GEN_BUILTINS = 'fixtures/icodegen.py'


class IcodeGenerationSuite(Suite):
    test_case_files = ['icode-basic.test',
                       'icode-classes.test']
    
    def cases(self):
        c = []
        for f in self.test_case_files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                builtins_wrapper(test_transform,
                                 os.path.join(test_data_prefix,
                                              ICODE_GEN_BUILTINS)),
                test_temp_dir, True)
        return c


def test_transform(testcase):
    """Perform a runtime checking transformation test case."""
    expected = remove_comment_lines(testcase.output)

    func_names = get_func_names(expected)

    try:
        # Construct input as a single single.
        src = '\n'.join(testcase.input)
        # Parse and type check the input program.
        result = build.build(src, program_path='main',
                             target=build.ICODE,
                             alt_lib_path=test_temp_dir)
        a = []
        for fn in func_names:
            a.append('def {}:'.format(fn))
            try:
                funccode = result.icode[fn]
            except KeyError:
                raise RuntimeError('no icode for %s (%s)' % (
                    fn, list(result.icode.keys())))
            code = icode.render(funccode)
            a.extend(code)
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal_wildcards(
        expected, a,
        'Invalid source code output ({}, line {})'.format(testcase.file,
                                                          testcase.line))


def get_func_names(expected):
    res = []
    for s in expected:
        m = re.match(r'def ([_a-zA-Z0-9.*$]+):', s)
        if m:
            res.append(m.group(1))
    if not res:
        raise RuntimeError('No function name in test case output')
    return res


if __name__ == '__main__':
    run_test(IcodeGenerationSuite(), sys.argv[1:])
