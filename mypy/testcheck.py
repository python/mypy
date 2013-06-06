"""Type checker test cases"""

import os.path

from mypy import build
from mypy.myunit import Suite, run_test
from mypy.testconfig import test_temp_dir, test_data_prefix
from mypy.testdata import parse_test_cases
from mypy.testhelpers import assert_string_arrays_equal
from mypy.errors import CompileError
from mypy.testsemanal import normalize_error_messages


# List of files that contain test case descriptions.
files = [
    'check-basic.test',
    'check-classes.test',
    'check-expressions.test',
    'check-statements.test',
    'check-generics.test',
    'check-tuples.test',
    'check-dynamic.test',
    'check-functions.test',
    'check-inference.test',
    'check-inference-context.test',
    'check-varargs.test',
    'check-kwargs.test',
    'check-overloading.test',
    #'check-interfaces.test',
    #'check-super.test',
    'check-modules.test',
    #'check-generic-subtyping.test',
    'check-unsupported.test',
]


class TypeCheckSuite(Suite):
    def cases(self):
        c = []
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  self.run_test, test_temp_dir, True)
        return c
    
    def run_test(self, testcase):
        a = []
        try:
            src = '\n'.join(testcase.input)
            build.build('main',
                        target=build.TYPE_CHECK,
                        program_text=src,
                        flags=[build.TEST_BUILTINS],
                        alt_lib_path=test_temp_dir)
        except CompileError as e:
            a = normalize_error_messages(e.messages)
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid type checker output ({}, line {})'.format(
                testcase.file, testcase.line))


if __name__ == '__main__':
    import sys
    run_test(TypeCheckSuite(), sys.argv[1:])
