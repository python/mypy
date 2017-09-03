"""Test cases for compiling from mypy to C extension modules."""

import os.path
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal_wildcards
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc.test.config import test_data_prefix
from mypyc.test.testutil import ICODE_GEN_BUILTINS, use_custom_builtins


files = ['module-output.test']


class TestCompiler(DataSuite):
    """Test cases that compile to C and perform checks on the C code."""

    def __init__(self, *, update_data: bool) -> None:
        pass

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        with use_custom_builtins(os.path.join(test_data_prefix, ICODE_GEN_BUILTINS), testcase):
            # Build the program.
            text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            source = build.BuildSource('prog.py', 'prog', text)

            try:
                ctext = emitmodule.compile_module_to_c(
                    sources=[source],
                    module_name='prog',
                    options=options,
                    alt_lib_path=test_temp_dir)
                out = ctext.splitlines()
            except CompileError as e:
                out = e.messages

            # Verify output.
            assert_string_arrays_equal_wildcards(testcase.output, out,
                                                 'Invalid output ({}, line {})'.format(
                                                     testcase.file, testcase.line))
