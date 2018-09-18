"""Test cases for building an C extension and running it."""

import os.path
import platform
import subprocess
import contextlib
import sys
from typing import List, Iterator

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase
from mypy.test.config import test_temp_dir, PREFIX
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc import emitmodule
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output,
    show_c_error, heading,
)

from distutils.core import run_setup

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

setup_format = """\
from distutils.core import setup
from mypyc.build import mypycify, MypycifyBuildExt

setup(name='test_run_output',
      ext_modules=mypycify({}, skip_cgen=True),
      cmdclass={{'build_ext': MypycifyBuildExt}},
)
"""


@contextlib.contextmanager
def chdir_manager(target: str) -> Iterator[None]:
    dir = os.getcwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(dir)


class TestRun(MypycDataSuite):
    """Test cases that build a C extension and run code."""
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        bench = testcase.config.getoption('--bench', False) and 'Benchmark' in testcase.name

        # setup.py wants to be run from the root directory of the package, which we accommodate
        # by chdiring into tmp/
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase), (
                chdir_manager('tmp')):
            text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.strict_optional = True
            options.python_version = (3, 6)
            options.export_types = True

            workdir = 'build'
            os.mkdir(workdir)

            source_path = 'native.py'
            with open(source_path, 'w') as f:
                f.write(text)
            with open('interpreted.py', 'w') as f:
                f.write(text)

            source = build.BuildSource(source_path, 'native', text)
            sources = [source]
            module_names = ['native']
            module_paths = [os.path.abspath('native.py')]

            # Hard code another module name to compile in the same compilation unit.
            to_delete = []
            for fn, text in testcase.files:
                fn = os.path.relpath(fn, test_temp_dir)

                if os.path.basename(fn).startswith('other'):
                    name = os.path.basename(fn).split('.')[0]
                    module_names.append(name)
                    sources.append(build.BuildSource(fn, name, text))
                    to_delete.append(fn)
                    module_paths.append(os.path.abspath(fn))

            for source in sources:
                options.per_module_options.setdefault(source.module, {})['mypyc'] = True

            try:
                result = emitmodule.parse_and_typecheck(
                    sources=sources,
                    options=options,
                    alt_lib_path='.')
                ctext = emitmodule.compile_modules_to_c(
                    result,
                    module_names=module_names,
                    use_shared_lib=len(module_names) > 1)
            except CompileError as e:
                for line in e.messages:
                    print(line)
                assert False, 'Compile error'

            cpath = os.path.abspath(os.path.join(workdir, '__native.c'))
            with open(cpath, 'w') as f:
                f.write(ctext)

            setup_file = os.path.abspath(os.path.join(workdir, 'setup.py'))
            with open(setup_file, 'w') as f:
                f.write(setup_format.format(module_paths))

            run_setup(setup_file, ['build_ext', '--inplace'])

            for p in to_delete:
                os.remove(p)

            driver_path = 'driver.py'
            env = os.environ.copy()
            env['MYPYC_RUN_BENCH'] = '1' if bench else '0'

            # XXX: This is an ugly hack.
            if 'MYPYC_RUN_GDB' in os.environ:
                if platform.system() == 'Darwin':
                    subprocess.check_call(['lldb', '--', 'python', driver_path], env=env)
                    assert False, ("Test can't pass in lldb mode. (And remember to pass -s to "
                                   "pytest)")
                elif platform.system() == 'Linux':
                    subprocess.check_call(['gdb', '--args', 'python', driver_path], env=env)
                    assert False, ("Test can't pass in gdb mode. (And remember to pass -s to "
                                   "pytest)")
                else:
                    assert False, 'Unsupported OS'

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
