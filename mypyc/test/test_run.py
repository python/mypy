"""Test cases for building an C extension and running it."""

import glob
import os.path
import platform
import subprocess
import contextlib
import shutil
import sys
from typing import Iterator, Optional

from mypy import build
from mypy.test.data import DataDrivenTestCase
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import emitmodule
from mypyc.options import CompilerOptions
from mypyc.build import shared_lib_name
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, TESTUTIL_PATH,
    use_custom_builtins, MypycDataSuite, assert_test_output,
    show_c
)

from distutils.core import run_setup

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
from mypyc.build import mypycify

setup(name='test_run_output',
      ext_modules=mypycify({}, skip_cgen=True, strip_asserts=False),
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
    multi_file = False

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
            # N.B: We try to (and ought to!) run with the current
            # version of python, since we are going to link and run
            # against the current version of python.
            # But a lot of the tests use type annotations so we can't say it is 3.5.
            options.python_version = max(sys.version_info[:2], (3, 6))
            options.export_types = True
            options.preserve_asts = True

            # Avoid checking modules/packages named 'unchecked', to provide a way
            # to test interacting with code we don't have types for.
            options.per_module_options['unchecked.*'] = {'follow_imports': 'error'}

            workdir = 'build'
            os.mkdir(workdir)

            source_path = 'native.py'
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(text)
            with open('interpreted.py', 'w', encoding='utf-8') as f:
                f.write(text)

            shutil.copyfile(TESTUTIL_PATH, 'testutil.py')

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

                    shutil.copyfile(fn,
                                    os.path.join(os.path.dirname(fn), name + '_interpreted.py'))

            for source in sources:
                options.per_module_options.setdefault(source.module, {})['mypyc'] = True

            if len(module_names) == 1:
                lib_name = None  # type: Optional[str]
            else:
                lib_name = shared_lib_name([source.module for source in sources])

            try:
                result = emitmodule.parse_and_typecheck(
                    sources=sources,
                    options=options,
                    alt_lib_path='.')
                cfiles = emitmodule.compile_modules_to_c(
                    result,
                    module_names=module_names,
                    shared_lib_name=lib_name,
                    compiler_options=CompilerOptions(multi_file=self.multi_file))
            except CompileError as e:
                for line in e.messages:
                    print(line)
                assert False, 'Compile error'

            for cfile, ctext in cfiles:
                with open(os.path.join(workdir, cfile), 'w', encoding='utf-8') as f:
                    f.write(ctext)

            setup_file = os.path.abspath(os.path.join(workdir, 'setup.py'))
            with open(setup_file, 'w') as f:
                f.write(setup_format.format(module_paths))

            run_setup(setup_file, ['build_ext', '--inplace'])
            # Oh argh run_setup doesn't propagate failure. For now we'll just assert
            # that the file is there.
            suffix = 'pyd' if sys.platform == 'win32' else 'so'
            if not glob.glob('native.*.{}'.format(suffix)):
                show_c(cfiles)
                assert False, "Compilation failed"

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
            output = proc.communicate()[0].decode('utf8')
            outlines = output.splitlines()

            show_c(cfiles)
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


# Run the main multi-module tests in multi-file compliation mode
class TestRunMultiFile(TestRun):
    multi_file = True
    test_name_suffix = '_multi'
    files = [
        'run-multimodule.test',
        'run-mypy-sim.test',
    ]
