"""Test cases for IR generation."""

import os.path

from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypy.errors import CompileError

from mypyc.common import TOP_LEVEL_NAME
from mypyc.ops import format_func
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, build_ir_for_single_file,
    assert_test_output, remove_comment_lines
)
from mypyc.options import CompilerOptions

files = [
    'genops-basic.test',
    'genops-lists.test',
    'genops-dict.test',
    'genops-statements.test',
    'genops-nested.test',
    'genops-classes.test',
    'genops-optional.test',
    'genops-tuple.test',
    'genops-any.test',
    'genops-generics.test',
    'genops-try.test',
    'genops-set.test',
    'genops-strip-asserts.test',
]


class TestGenOps(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        # Kind of hacky. Not sure if we need more structure here.
        options = CompilerOptions(strip_asserts='StripAssert' in testcase.name)
        """Perform a runtime checking transformation test case."""
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)

            try:
                ir = build_ir_for_single_file(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if (fn.name == TOP_LEVEL_NAME
                            and not testcase.name.endswith('_toplevel')):
                        continue
                    actual.extend(format_func(fn))

            assert_test_output(testcase, actual, 'Invalid source code output',
                               expected_output)
