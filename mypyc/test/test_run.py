"""Test cases for building an C extension and running it."""

import os.path
import subprocess
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal_wildcards
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc import buildc
from mypyc.test.testutil import ICODE_GEN_BUILTINS, use_custom_builtins
from mypyc.test.config import test_data_prefix


files = ['run.test',
         'run-classes.test']


class TestRun(DataSuite):
    """Test cases that build a C extension and run code."""

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
            text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.strict_optional = True
            options.python_version = (3, 6)
            source = build.BuildSource('native.py', 'native', text)

            try:
                ctext = emitmodule.compile_module_to_c(
                    sources=[source],
                    module_name='native',
                    options=options,
                    alt_lib_path=test_temp_dir)
            except CompileError as e:
                for line in e.messages:
                    print(line)
                assert False, 'Compile error'

            cpath = os.path.join(test_temp_dir, 'native.c')
            with open(cpath, 'w') as f:
                f.write(ctext)

            try:
                native_lib_path = buildc.build_c_extension(cpath)
            except buildc.BuildError as err:
                heading('Generated C')
                with open(cpath) as f:
                    print(f.read().rstrip())
                heading('End C')
                heading('Build output')
                print(err.output.decode('utf8').rstrip('\n'))
                heading('End output')
                raise

            driver_path = os.path.join(test_temp_dir, 'driver.py')
            env = os.environ.copy()
            env['PYTHONPATH'] = os.path.dirname(native_lib_path)
            proc = subprocess.Popen(['python', driver_path], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env)
            output, _ = proc.communicate()
            output = output.decode('utf8')
            outlines = output.splitlines()

            heading('Generated C')
            with open(cpath) as f:
                print(f.read().rstrip())
            heading('End C')
            if proc.returncode != 0:
                print()
                print('*** Exit status: %d' % proc.returncode)

            # Verify output.
            assert_string_arrays_equal_wildcards(testcase.output, outlines,
                                                 'Invalid output ({}, line {})'.format(
                                                     testcase.file, testcase.line))

            assert proc.returncode == 0


def heading(text):
    print('=' * 20 + ' ' + text + ' ' + '=' * 20)
