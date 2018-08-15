"""Test cases for compiling from mypy to C extension modules."""

import os.path
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output
)


files = ['module-output.test']


class TestCompiler(MypycDataSuite):
    """Test cases that compile to C and perform checks on the C code."""

    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            # Build the program.
            text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.strict_optional = True
            options.python_version = (3, 6)
            options.export_types = True
            source = build.BuildSource('prog.py', 'prog', text)

            try:
                result = emitmodule.parse_and_typecheck(
                    sources=[source],
                    options=options,
                    alt_lib_path=test_temp_dir)
                ctext = emitmodule.compile_modules_to_c(
                    result, module_names=['prog'], use_shared_lib=False)
                out = ctext.splitlines()
            except CompileError as e:
                out = e.messages

            # Verify output.
            assert_test_output(testcase, out, 'Invalid output')
