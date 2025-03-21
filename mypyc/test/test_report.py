"""Test cases for report generation."""

from __future__ import annotations

import os.path

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.common import TOP_LEVEL_NAME
from mypyc.ir.pprint import format_func
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file2,
    infer_ir_build_options_from_test_name,
    remove_comment_lines,
    use_custom_builtins,
)
from mypyc.report import generate_annotations

files = [
    "report-basic.test",
]


class TestReport(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a runtime checking transformation test case."""
        options = infer_ir_build_options_from_test_name(testcase.name)
        if options is None:
            # Skipped test case
            return
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)
            name = testcase.name
            try:
                ir, tree = build_ir_for_single_file2(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                annotations = generate_annotations("native.py", tree, ir)
                actual = []
                for line, str in annotations.annotations.items():
                    actual.append(f"{line}: {str}")

            assert_test_output(testcase, actual, "Invalid source code output", expected_output)
