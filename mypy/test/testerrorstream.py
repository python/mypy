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
from mypy.plugin import Plugin, ChainedPlugin, DefaultPlugin, FunctionContext
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
    real_messages = []  # type: List[str]

    def flush_errors(msgs: List[str], serious: bool, is_real: bool = True) -> None:
        if msgs:
            logged_messages.append('==== Errors flushed ====')
            logged_messages.extend(msgs)
        if is_real:
            real_messages.extend(msgs)

    plugin = ChainedPlugin(options, [LoggingPlugin(options, flush_errors), DefaultPlugin(options)])

    sources = [BuildSource('main', '__main__', '\n'.join(testcase.input))]
    try:
        res = build.build(sources=sources,
                          options=options,
                          alt_lib_path=test_temp_dir,
                          flush_errors=flush_errors,
                          plugin=plugin)
        reported_messages = res.errors
    except CompileError as e:
        reported_messages = e.messages

    assert_string_arrays_equal(testcase.output, logged_messages,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))
    assert_string_arrays_equal(reported_messages, real_messages,
                               'Streamed/reported mismatch ({}, line {})'.format(
                                   testcase.file, testcase.line))


# Use a typechecking plugin to allow test cases to emit messages
# during typechecking. This allows us to verify that error messages
# from one SCC are printed before later ones are typechecked.
class LoggingPlugin(Plugin):
    def __init__(self, options: Options, log: Callable[[List[str], bool, bool], None]) -> None:
        super().__init__(options)
        self.log = log

    def get_function_hook(self, fullname: str) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == 'log.log_checking':
            return self.hook
        return None

    def hook(self, ctx: FunctionContext) -> Type:
        assert(isinstance(ctx.context, CallExpr) and len(ctx.context.args) > 0 and
               isinstance(ctx.context.args[0], StrExpr))
        self.log([ctx.context.args[0].value], False, False)
        return ctx.default_return_type
