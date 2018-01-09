"""Tests for mypy incremental error output."""
from typing import List, Callable, Optional

import os

from mypy import defaults, build
from mypy.test.config import test_temp_dir
from mypy.myunit import AssertionFailure
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.build import BuildSource
from mypy.errors import CompileError
from mypy.options import Options
from mypy.nodes import CallExpr, StrExpr
from mypy.types import Type


class ErrorStreamSuite(DataSuite):
    files = ['errorstream.test']

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_error_stream(testcase)


def test_error_stream(testcase: DataDrivenTestCase) -> None:
    """Perform a single error streaming test case.

    The argument contains the description of the test case.
    """
    options = Options()
    options.show_traceback = True

    logged_messages = []  # type: List[str]

    def flush_errors(msgs: List[str], serious: bool) -> None:
        if msgs:
            logged_messages.append('==== Errors flushed ====')
            logged_messages.extend(msgs)

    sources = [BuildSource('main', '__main__', '\n'.join(testcase.input))]
    try:
        build.build(sources=sources,
                    options=options,
                    alt_lib_path=test_temp_dir,
                    flush_errors=flush_errors)
    except CompileError as e:
        assert e.messages == []

    assert_string_arrays_equal(testcase.output, logged_messages,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))
