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

    a = []

    def flush_errors(msgs: List[str]) -> None:
        nonlocal a
        if msgs:
            a.append('==== Errors flushed ====')
            a += msgs
    plugin = ChainedPlugin(options, [LoggingPlugin(options, flush_errors), DefaultPlugin(options)])

    sources = [BuildSource('main', '__main__', '\n'.join(testcase.input))]
    try:
        build.build(sources=sources,
                    options=options,
                    alt_lib_path=test_temp_dir,
                    flush_errors=flush_errors,
                    plugin=plugin)
    except CompileError as e:
        a.append('==== Blocking error ====')
        a += e.messages[e.num_already_seen:]

    assert_string_arrays_equal(testcase.output, a,
                               'Invalid output ({}, line {})'.format(
                                   testcase.file, testcase.line))


# Use a typechecking plugin to allow test cases to emit messages
# during typechecking. This allows us to verify that error messages
# from one SCC are printed before later ones are typechecked.
class LoggingPlugin(Plugin):
    def __init__(self, options: Options, log: Callable[[List[str]], None]) -> None:
        super().__init__(options)
        self.log = log

    def get_function_hook(self, fullname: str) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == 'log.log_checking':
            return self.hook
        return None

    def hook(self, ctx: FunctionContext) -> Type:
        assert(isinstance(ctx.context, CallExpr) and len(ctx.context.args) > 0 and
               isinstance(ctx.context.args[0], StrExpr))
        self.log([ctx.context.args[0].value])
        return ctx.default_return_type
