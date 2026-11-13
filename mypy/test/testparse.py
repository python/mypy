"""Tests for the mypy parser."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

import pytest
from pytest import skip

from mypy import build, defaults
from mypy.config_parser import parse_mypy_comments
from mypy.errors import CompileError, Errors
from mypy.modulefinder import BuildSource
from mypy.options import Options
from mypy.parse import parse
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.test.helpers import Suite, assert_string_arrays_equal, find_test_files, parse_options
from mypy.test.update_data import update_testcase_output
from mypy.util import get_mypy_comments


class ParserSuite(DataSuite):
    required_out_section = True
    base_path = "."
    files = find_test_files(pattern="parse*.test", exclude=["parse-errors.test"])

    if sys.version_info < (3, 12):
        files.remove("parse-python312.test")
    if sys.version_info < (3, 13):
        files.remove("parse-python313.test")
    if sys.version_info < (3, 14):
        files.remove("parse-python314.test")

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_parser(testcase)


def test_parser(testcase: DataDrivenTestCase) -> None:
    """Perform a single parser test case.

    The argument contains the description of the test case.
    """
    options = Options()
    options.hide_error_codes = True

    if testcase.file.endswith("python310.test"):
        options.python_version = (3, 10)
    elif testcase.file.endswith("python312.test"):
        options.python_version = (3, 12)
    elif testcase.file.endswith("python313.test"):
        options.python_version = (3, 13)
    elif testcase.file.endswith("python314.test"):
        options.python_version = (3, 14)

    source = "\n".join(testcase.input)

    # Apply mypy: comments to options.
    comments = get_mypy_comments(source)
    changes, _ = parse_mypy_comments(comments, options)
    options = options.apply_changes(changes)

    try:
        errors = Errors(options)
        n = parse(
            bytes(source, "ascii"),
            fnam="main",
            module="__main__",
            errors=errors,
            options=options,
            eager=True,
        )
        if errors.is_errors():
            errors.raise_error()
        a = n.str_with_options(options).split("\n")
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, a, f"Invalid parser output ({testcase.file}, line {testcase.line})"
    )


# The file name shown in test case output. This is displayed in error
# messages, and must match the file name in the test case descriptions.
INPUT_FILE_NAME = "file"


class ParseErrorSuite(DataSuite):
    required_out_section = True
    base_path = "."
    files = ["parse-errors.test"]

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_parse_error(testcase)


def test_parse_error(testcase: DataDrivenTestCase) -> None:
    try:
        options = parse_options("\n".join(testcase.input), testcase, 0)
        if options.python_version < defaults.PYTHON3_VERSION:
            options.python_version = defaults.PYTHON3_VERSION
        if options.python_version != sys.version_info[:2]:
            skip()
        if testcase.name.endswith("_old_parser"):
            # This test is only for the old parser.
            options.native_parser = False
        # Compile temporary file. The test file contains non-ASCII characters.
        errors = Errors(options)
        parse(
            bytes("\n".join(testcase.input), "utf-8"),
            INPUT_FILE_NAME,
            "__main__",
            errors=errors,
            options=options,
            eager=True,
        )
        if errors.is_errors():
            errors.raise_error()
        raise AssertionError("No errors reported")
    except CompileError as e:
        if e.module_with_blocker is not None:
            assert e.module_with_blocker == "__main__"

        # This may not work perfectly, since it was designed for testcheck.py, use with care.
        if testcase.output != e.messages and testcase.config.getoption("--update-data", False):
            update_testcase_output(testcase, e.messages, incremental_step=1)

        # Verify that there was a compile error and that the error messages
        # are equivalent.
        assert_string_arrays_equal(
            testcase.output,
            e.messages,
            f"Invalid compiler output ({testcase.file}, line {testcase.line})",
        )


class TransformSourceSuite(Suite):
    """Tests for options.transform_source (see #21222).

    transform_source is a Python callable, so it cannot be exercised via the
    data-driven test cases; these are plain unit tests instead.
    """

    def parse_with_transform(self, native_parser: bool) -> int:
        """Parse a trivial module with transform_source set.

        Return the number of top-level definitions in the resulting AST.
        """
        options = Options()
        options.native_parser = native_parser
        options.transform_source = lambda source: source + "reveal_type(1)\n"
        errors = Errors(options)
        tree = parse(
            "x = 1\n", fnam="main", module="__main__", errors=errors, options=options, eager=True
        )
        assert not errors.is_errors()
        return len(tree.defs)

    def test_transform_source_native_parser(self) -> None:
        pytest.importorskip("ast_serialize")
        assert Options().native_parser
        # The transform appends a statement, so we expect two top-level definitions.
        assert self.parse_with_transform(native_parser=True) == 2

    def test_transform_source_old_parser(self) -> None:
        # The transform appends a statement, so we expect two top-level definitions.
        assert self.parse_with_transform(native_parser=False) == 2

    def test_transform_source_parallel_build(self) -> None:
        """transform_source must be honored with parallel (native parser) checking.

        With more than one file the native parser parses in parallel threads, and
        the source must be read (and transformed) instead of letting the parser
        use the file on disk directly.
        """
        pytest.importorskip("ast_serialize")
        assert Options().native_parser
        tmpdir = tempfile.mkdtemp(prefix="mypy-test-transform-")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        for name in ("a.py", "b.py"):
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x: int = 1\n")
        options = Options()
        # The transform introduces a type error on line 3 of each file.
        options.transform_source = lambda source: source + "\nbad: str = 1\n"
        options.incremental = False
        options.cache_dir = os.devnull
        options.show_traceback = True
        sources = [
            BuildSource(os.path.join(tmpdir, name), name[:-3], None) for name in ("a.py", "b.py")
        ]
        try:
            result = build.build(sources=sources, options=options)
            messages = result.errors
        except CompileError as e:
            messages = e.messages
        assert len([m for m in messages if ":3: error" in m]) == 2
