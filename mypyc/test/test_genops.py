"""Test cases for IR generation."""

import os.path

from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypy.errors import CompileError

from mypyc.ops import format_func, is_empty_module_top_level
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, build_ir_for_single_file,
    assert_test_output, remove_comment_lines
)

files = [
    'genops-basic.test',
    'genops-lists.test',
    'genops-dict.test',
    'genops-statements.test',
    'genops-nested.test',
    'genops-generators.test',
    'genops-classes.test',
    'genops-optional.test',
    'genops-tuple.test',
    'genops-any.test',
    'genops-generics.test',
    'genops-try.test',
    'genops-set.test',
]


class TestGenOps(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a runtime checking transformation test case."""
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)

            try:
                ir = build_ir_for_single_file(testcase.input)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if is_empty_module_top_level(fn):
                        # Skip trivial module top levels that only return.
                        continue
                    actual.extend(format_func(fn))

            assert_test_output(testcase, actual, 'Invalid source code output',
                               expected_output)
