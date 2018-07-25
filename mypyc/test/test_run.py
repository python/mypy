"""Test cases for building an C extension and running it."""

import os.path
import subprocess
import sys
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.config import test_temp_dir, PREFIX
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc import buildc
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output,
    show_c_error, heading,
)

import pytest  # type: ignore  # no pytest in typeshed

files = [
    'run-functions.test',
    'run.test',
    'run-classes.test',
    'run-traits.test',
    'run-multimodule.test',
    'run-bench.test',
    'run-mypy-sim.test',
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
            options.export_types = True

            workdir = 'build'
            os.mkdir(workdir)

            os.mkdir('tmp/py')
            source_path = 'tmp/py/native.py'
            with open(source_path, 'w') as f:
                f.write(text)
            with open('tmp/interpreted.py', 'w') as f:
                f.write(text)

            source = build.BuildSource(source_path, 'native', text)
            sources = [source]
            module_names = ['native']

            # Hard code another module name to compile in the same compilation unit.
            to_delete = []
            for fn, text in testcase.files:
                if os.path.basename(fn).startswith('other'):
                    name = os.path.basename(fn).split('.')[0]
                    module_names.append(name)
                    sources.append(build.BuildSource(fn, name, text))
                    to_delete.append(fn)

            try:
                ctext = emitmodule.compile_modules_to_c(
                    sources=sources,
                    module_names=module_names,
                    options=options,
                    use_shared_lib=len(module_names) > 1,
                    alt_lib_path=test_temp_dir)
            except CompileError as e:
                for line in e.messages:
                    print(line)
                assert False, 'Compile error'

            # If compiling more than one native module, compile a shared
            # library that contains all the modules. Also generate shims that
            # just call into the shared lib.
            use_shared_lib = len(module_names) > 1

            if use_shared_lib:
                common_path = os.path.abspath(os.path.join(test_temp_dir, '__shared_stuff.c'))
                with open(common_path, 'w') as f:
                    f.write(ctext)
                try:
                    shared_lib = buildc.build_shared_lib_for_modules(common_path, module_names,
                                                                     workdir)
                except buildc.BuildError as err:
                    show_c_error(common_path, err.output)
                    raise

            for mod in module_names:
                cpath = os.path.abspath(os.path.join(test_temp_dir, '%s.c' % mod))
                with open(cpath, 'w') as f:
                    f.write(ctext)

                try:
                    if use_shared_lib:
                        native_lib_path = buildc.build_c_extension_shim(mod, shared_lib, workdir)
                    else:
                        native_lib_path = buildc.build_c_extension(cpath, mod, workdir)
                except buildc.BuildError as err:
                    show_c_error(cpath, err.output)
                    raise

            # # TODO: is the location of the shared lib good?
            # shared_lib = buildc.build_shared_lib_for_modules(cpath)

            for p in to_delete:
                os.remove(p)

            driver_path = os.path.join(test_temp_dir, 'driver.py')
            env = os.environ.copy()
            path = [os.path.dirname(native_lib_path), os.path.join(PREFIX, 'extensions')]
            env['PYTHONPATH'] = ':'.join(path)
            env['MYPYC_RUN_BENCH'] = '1' if bench else '0'
            lib_env = 'DYLD_LIBRARY_PATH' if sys.platform == 'darwin' else 'LD_LIBRARY_PATH'
            env[lib_env] = workdir

            # XXX: This is an ugly hack.
            if 'MYPYC_RUN_GDB' in os.environ:
                subprocess.check_call(['gdb', '--args', 'python', driver_path], env=env)
                assert False, "Test can't pass in gdb mode. (And remember to pass -s to pytest)"

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
