"""Runner for IR optimization tests."""

from __future__ import annotations

import os.path

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.common import TOP_LEVEL_NAME
from mypyc.ir.pprint import format_func
from mypyc.options import CompilerOptions
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file,
    remove_comment_lines,
    use_custom_builtins,
)
from mypyc.transform.copy_propagation import do_copy_propagation
from mypyc.transform.flag_elimination import do_flag_elimination
from mypyc.transform.uninit import insert_uninit_checks


class TestCopyPropagation(MypycDataSuite):
    files = ["opt-copy-propagation.test"]
    base_path = test_temp_dir

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)
            try:
                ir = build_ir_for_single_file(testcase.input)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if fn.name == TOP_LEVEL_NAME and not testcase.name.endswith("_toplevel"):
                        continue
                    insert_uninit_checks(fn)
                    do_copy_propagation(fn, CompilerOptions())
                    actual.extend(format_func(fn))

            assert_test_output(testcase, actual, "Invalid source code output", expected_output)


class TestFlagElimination(MypycDataSuite):
    files = ["opt-flag-elimination.test"]
    base_path = test_temp_dir

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)
            try:
                ir = build_ir_for_single_file(testcase.input)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if fn.name == TOP_LEVEL_NAME and not testcase.name.endswith("_toplevel"):
                        continue
                    insert_uninit_checks(fn)
                    do_flag_elimination(fn, CompilerOptions())
                    actual.extend(format_func(fn))

            assert_test_output(testcase, actual, "Invalid source code output", expected_output)
