"""Tests for the native mypy parser."""

from __future__ import annotations

import contextlib
import gc
import os
import tempfile
import unittest
from collections.abc import Iterator
from typing import Any

from mypy import defaults, nodes
from mypy.cache import END_TAG, LIST_GEN, LITERAL_INT, LITERAL_STR, LOCATION
from mypy.config_parser import parse_mypy_comments
from mypy.errors import CompileError
from mypy.nativeparse import native_parse, parse_to_binary_ast
from mypy.nodes import ExpressionStmt, MemberExpr, MypyFile
from mypy.options import Options
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.util import get_mypy_comments

gc.set_threshold(200 * 1000, 30, 30)


class NativeParserSuite(DataSuite):
    required_out_section = True
    base_path = "."
    files = ["native-parser.test"]

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_parser(testcase)


def test_parser(testcase: DataDrivenTestCase) -> None:
    """Perform a single native parser test case.

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
    else:
        options.python_version = defaults.PYTHON3_VERSION

    source = "\n".join(testcase.input)

    # Apply mypy: comments to options.
    comments = get_mypy_comments(source)
    changes, _ = parse_mypy_comments(comments, options)
    options = options.apply_changes(changes)

    # Check if we should skip function bodies (when ignoring errors)
    skip_function_bodies = "# mypy: ignore-errors=True" in source

    try:
        with temp_source(source) as fnam:
            try:
                node, errors, type_ignores = native_parse(fnam, options, skip_function_bodies)
            except ValueError as e:
                print(f"Parse failed: {e}")
                assert False
            node.path = "main"
            a = node.str_with_options(options).split("\n")
            a = [format_error(err) for err in errors] + a
            a = [format_ignore(ignore) for ignore in type_ignores] + a
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, a, f"Invalid parser output ({testcase.file}, line {testcase.line})"
    )


def format_error(err: dict[str, Any]) -> str:
    return f"{err['line']}:{err['column']}: error: {err['message']}"


def format_ignore(ignore: tuple[int, list[str]]) -> str:
    line, codes = ignore
    if not codes:
        return f"ignore: {line}"
    else:
        return f"ignore: {line} [{', '.join(codes)}]"


class TestNativeParse(unittest.TestCase):
    def test_trivial_binary_data(self) -> None:
        def int_enc(n: int) -> int:
            return (n + 10) << 1

        def locs(start_line: int, start_column: int, end_line: int, end_column: int) -> list[int]:
            return [
                LOCATION,
                int_enc(start_line),
                int_enc(start_column),
                int_enc(end_line - start_line),
                int_enc(end_column - start_column),
            ]

        with temp_source("print('hello')") as fnam:
            b, _, _, _ = parse_to_binary_ast(fnam)
            assert list(b) == (
                [LITERAL_INT, 22, nodes.EXPR_STMT, nodes.CALL_EXPR]
                + [nodes.NAME_EXPR, LITERAL_STR]
                + [int_enc(5)]
                + list(b"print")
                + locs(1, 1, 1, 6)
                + [END_TAG, LIST_GEN, 22, nodes.STR_EXPR]
                + [LITERAL_STR, int_enc(5)]
                + list(b"hello")
                + locs(1, 7, 1, 14)
                + [END_TAG]
                + locs(1, 1, 1, 15)
                + [END_TAG, END_TAG]
            )

    def test_deserialize_hello(self) -> None:
        with temp_source("print('hello')") as fnam:
            node = native_parse(fnam, Options())
            assert isinstance(node, MypyFile)

    def test_deserialize_member_expr(self) -> None:
        with temp_source("foo_bar.xyz2") as fnam:
            node, _, _ = native_parse(fnam, Options())
            assert isinstance(node, MypyFile)
            assert isinstance(node.defs[0], ExpressionStmt)
            assert isinstance(node.defs[0].expr, MemberExpr)

    def test_deserialize_bench(self) -> None:
        with temp_source("print('hello')\n" * 4000) as fnam:
            import time

            options = Options()
            for i in range(10):
                native_parse(fnam, options)
            t0 = time.time()
            for i in range(25):
                node, _, _ = native_parse(fnam, options)
            assert isinstance(node, MypyFile)
            print(len(node.defs))
            print((time.time() - t0) * 1000)
            assert False, 1 / ((time.time() - t0) / 100000)

    def test_parse_bench(self) -> None:
        with temp_source("print('hello')\n" * 4000) as fnam:
            import time

            from mypy.errors import Errors
            from mypy.options import Options
            from mypy.parse import parse

            o = Options()

            for i in range(10):
                with open(fnam, "rb") as f:
                    data = f.read()
                node = parse(data, fnam, "__main__", Errors(o), o)

            t0 = time.time()
            for i in range(25):
                with open(fnam, "rb") as f:
                    data = f.read()
                node = parse(data, fnam, "__main__", Errors(o), o)
            assert isinstance(node, MypyFile)
            assert False, 1 / ((time.time() - t0) / 100000)


@contextlib.contextmanager
def temp_source(text: str) -> Iterator[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, "t.py")
        with open(temp_path, "w") as f:
            f.write(text)
        yield temp_path
