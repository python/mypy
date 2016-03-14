"""Type checker test cases"""

import os.path
import re
import sys

from typing import Tuple, List

from mypy import build
import mypy.myunit  # for mutable globals (ick!)
from mypy.build import BuildSource
from mypy.myunit import Suite
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases
from mypy.test.helpers import (
    assert_string_arrays_equal, testcase_pyversion, update_testcase_output
)
from mypy.test.testsemanal import normalize_error_messages
from mypy.errors import CompileError


# List of files that contain test case descriptions.
files = [
    'check-basic.test',
    'check-classes.test',
    'check-expressions.test',
    'check-statements.test',
    'check-generics.test',
    'check-tuples.test',
    'check-dynamic-typing.test',
    'check-weak-typing.test',
    'check-functions.test',
    'check-inference.test',
    'check-inference-context.test',
    'check-varargs.test',
    'check-kwargs.test',
    'check-overloading.test',
    'check-type-checks.test',
    'check-abstract.test',
    'check-multiple-inheritance.test',
    'check-super.test',
    'check-modules.test',
    'check-generic-subtyping.test',
    'check-typevar-values.test',
    'check-python2.test',
    'check-unsupported.test',
    'check-unreachable-code.test',
    'check-unions.test',
    'check-isinstance.test',
    'check-lists.test',
    'check-namedtuple.test',
    'check-type-aliases.test',
    'check-ignore.test',
    'check-type-promotion.test',
    'check-semanal-error.test',
    'check-flags.test',
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
        pyversion = testcase_pyversion(testcase.file, testcase.name)
        program_text = '\n'.join(testcase.input)
        module_name, program_name, program_text = self.parse_options(program_text)
        flags = self.parse_flags(program_text)
        source = BuildSource(program_name, module_name, program_text)
        try:
            build.build(target=build.TYPE_CHECK,
                        sources=[source],
                        pyversion=pyversion,
                        flags=flags + [build.TEST_BUILTINS],
                        alt_lib_path=test_temp_dir)
        except CompileError as e:
            a = normalize_error_messages(e.messages)

        if testcase.output != a and mypy.myunit.UPDATE_TESTCASES:
            update_testcase_output(testcase, a, mypy.myunit.APPEND_TESTCASES)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid type checker output ({}, line {})'.format(
                testcase.file, testcase.line))

    def parse_options(self, program_text: str) -> Tuple[str, str, str]:
        """Return type check options for a test case.

        The default ('__main__') module name can be overriden by
        using a comment like this in the test case input:

          # cmd: mypy -m foo.bar

        Return tuple (main module name, main file name, main program text).
        """
        m = re.search('# cmd: mypy -m ([a-zA-Z0-9_.]+) *$', program_text, flags=re.MULTILINE)
        if m:
            # The test case wants to use a non-default main
            # module. Look up the module and give it as the thing to
            # analyze.
            module_name = m.group(1)
            path = build.find_module(module_name, [test_temp_dir])
            with open(path) as f:
                program_text = f.read()
            return m.group(1), path, program_text
        else:
            return '__main__', 'main', program_text

    def parse_flags(self, program_text: str) -> List[str]:
        m = re.search('# flags: (.*)$', program_text, flags=re.MULTILINE)
        if m:
            return m.group(1).split()
        else:
            return []
