"""Test cases for building an C extension and running it."""

import os.path
import subprocess
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc import buildc
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output,
)

import pytest  # type: ignore  # no pytest in typeshed

files = [
    'run.test',
    'run-classes.test',
    'run-bench.test',
]


class TestRun(MypycDataSuite):
    """Test cases that build a C extension and run code."""
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        bench = testcase.config.getoption('--bench', False) and 'Benchmark' in testcase.name

        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.strict_optional = True
            options.python_version = (3, 6)

            os.mkdir('tmp/py')
            source_path = 'tmp/py/native.py'
            with open(source_path, 'w') as f:
                f.write(text)
            with open('tmp/interpreted.py', 'w') as f:
                f.write(text)

            source = build.BuildSource(source_path, 'native', text)

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
                native_lib_path = buildc.build_c_extension(cpath, preserve_setup=True)
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
            env['MYPYC_RUN_BENCH'] = '1' if bench else '0'
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
            if bench:
                print('Test output:')
                print(output)
            else:
                assert_test_output(testcase, outlines, 'Invalid output')

            assert proc.returncode == 0


def heading(text: str) -> None:
    print('=' * 20 + ' ' + text + ' ' + '=' * 20)
