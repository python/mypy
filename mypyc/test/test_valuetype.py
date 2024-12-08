"""Test runner for value type test cases."""

from __future__ import annotations

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.test.testutil import (
    MypycDataSuite,
    build_ir_for_single_file,
    infer_ir_build_options_from_test_name,
)

files = ["valuetype-errors.test"]


class TestValueTypeCompileErrors(MypycDataSuite):
    """Negative cases which emit error on compile."""

    files = files
    base_path = test_temp_dir

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a runtime checking transformation test case."""
        options = infer_ir_build_options_from_test_name(testcase.name)
        if options is None:
            # Skipped test case
            return

        assert options.experimental_value_types
        try:
            build_ir_for_single_file(testcase.input, options)
        except CompileError as e:
            actual = "\n".join(e.messages).strip()
            expected = "\n".join(testcase.output).strip()
            assert actual == expected
        else:
            assert False, "Expected CompileError"
