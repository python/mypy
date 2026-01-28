"""Test cases for capsule dependency analysis."""

from __future__ import annotations

import os.path

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.analysis.capsule_deps import find_implicit_op_dependencies
from mypyc.common import TOP_LEVEL_NAME
from mypyc.options import CompilerOptions
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file,
    infer_ir_build_options_from_test_name,
    use_custom_builtins,
)
from mypyc.transform.lower import lower_ir

files = ["capsule-deps.test"]


class TestCapsuleDeps(MypycDataSuite):
    files = files
    base_path = test_temp_dir

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        options = infer_ir_build_options_from_test_name(testcase.name)
        if options is None:
            # Skipped test case
            return
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            try:
                ir = build_ir_for_single_file(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                all_deps: set[str] = set()
                for fn in ir:
                    if fn.name == TOP_LEVEL_NAME and not testcase.name.endswith("_toplevel"):
                        continue
                    compiler_options = CompilerOptions()
                    lower_ir(fn, compiler_options)
                    deps = find_implicit_op_dependencies(fn)
                    if deps:
                        for dep in deps:
                            all_deps.add(repr(dep))
                actual = sorted(all_deps) if all_deps else ["No deps"]

            assert_test_output(testcase, actual, "Invalid test output", testcase.output)
