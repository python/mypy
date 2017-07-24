"""Test runner for reference count opcode insertion transform test cases.

The transform inserts needed reference count increment/decrement
operations to IR.
"""

import os.path
from typing import List

from mypy.test.config import test_temp_dir
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.errors import CompileError
from mypy.test.helpers import assert_string_arrays_equal_wildcards

from mypyc.ops import format_func
from mypyc.refcount import insert_ref_count_opcodes
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    build_ir_for_single_file,
    use_custom_builtins,
)
from mypyc.test.config import test_data_prefix

files = [
    'refcount.test'
]


class TestRefCountTransform(DataSuite):
    def __init__(self, *, update_data: bool) -> None:
        pass

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a reference count opcode insertion transform test case."""

        with use_custom_builtins(os.path.join(test_data_prefix, ICODE_GEN_BUILTINS), testcase):
            try:
                ir = build_ir_for_single_file(testcase.input)
            except CompileError as e:
                actual = e.messages
            else:
                assert len(ir) == 1, "Only 1 function definition expected per test case"
                fn = ir[0]
                insert_ref_count_opcodes(fn)
                actual = format_func(fn)
                actual = actual[actual.index('L0:'):]

            expected_output = testcase.output
            assert_string_arrays_equal_wildcards(
                expected_output, actual,
                'Invalid source code output ({}, line {})'.format(testcase.file,
                                                                  testcase.line))
