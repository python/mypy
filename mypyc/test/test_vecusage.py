"""Test cases for analysing if vec capsule is needed."""

from __future__ import annotations

import os.path

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.analysis.vecusage import needs_vec_capsule
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file2,
    infer_ir_build_options_from_test_name,
    use_custom_builtins,
)

files = ["vecusage.test"]


class TestVecUsage(MypycDataSuite):
    files = files
    base_path = test_temp_dir

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        options = infer_ir_build_options_from_test_name(testcase.name)
        if options is None:
            # Skipped test case
            return
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            try:
                ir, _, _, _ = build_ir_for_single_file2(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                actual = [str(needs_vec_capsule(ir))]

            assert_test_output(testcase, actual, "Invalid test output", testcase.output)
