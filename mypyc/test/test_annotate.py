"""Test cases for annotating source code to highlight inefficiencies."""

from __future__ import annotations

import os.path

from mypy.errors import CompileError
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.annotate import generate_annotations
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file2,
    infer_ir_build_options_from_test_name,
    remove_comment_lines,
    use_custom_builtins,
)

files = ["annotate-basic.test"]


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

            # Parse "# A: <message>" comments.
            for i, line in enumerate(testcase.input):
                if "# A:" in line:
                    msg = line.rpartition("# A:")[2].strip()
                    expected_output.append(f"{i + 1}: {msg}")

            try:
                ir, tree = build_ir_for_single_file2(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                annotations = generate_annotations("native.py", tree, ir)
                actual = []
                for line_num, line_anns in annotations.annotations.items():
                    s = " ".join(line_anns)
                    actual.append(f"{line_num}: {s}")

            assert_test_output(testcase, actual, "Invalid source code output", expected_output)
