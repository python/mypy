from contextlib import contextmanager
from enum import Enum
import os
import sys
import tempfile
from typing import Tuple, List, Generator, Optional, Any
from unittest import TestCase, main

import mypy.api
from mypy.modulefinder import get_site_packages_dirs
from mypy.test.config import package_path
from mypy.test.helpers import run_command
from mypy.util import try_find_python2_interpreter

# NOTE: options.use_builtins_fixtures should not be set in these
# tests, otherwise mypy will ignore installed third-party packages.

SIMPLE_PROGRAM = """
from typedpkg.sample import ex
from typedpkg import dne
a = ex([''])
reveal_type(a)
"""

_NAMESPACE_PROGRAM = """
{import_style}

nested_func("abc")
alpha_func(False)

nested_func(False)
alpha_func(2)
"""

C_EXT_PROGRAM = """
from typedpkg_c_ext.foo import speak
from typedpkg_c_ext.hello import helloworld
"""


class NamespaceProgramImportStyle(Enum):
    from_import = """\
from typedpkg_nested.nested_package.nested_module import nested_func
from typedpkg_namespace.alpha.alpha_module import alpha_func"""
    import_as = """\
import typedpkg_nested.nested_package.nested_module as nm; nested_func = nm.nested_func
import typedpkg_namespace.alpha.alpha_module as am; alpha_func = am.alpha_func"""
    regular_import = """\
import typedpkg_nested.nested_package.nested_module; \
nested_func = typedpkg_nested.nested_package.nested_module.nested_func
import typedpkg_namespace.alpha.alpha_module; \
alpha_func = typedpkg_namespace.alpha.alpha_module.alpha_func"""


class SimpleProgramMessage(Enum):
    msg_dne = "{tempfile}:3: error: Module 'typedpkg' has no attribute 'dne'"
    msg_list = "{tempfile}:5: error: Revealed type is 'builtins.list[builtins.str]'"
    msg_tuple = "{tempfile}:5: error: Revealed type is 'builtins.tuple[builtins.str]'"


class NamespaceProgramMessage(Enum):
    bool_str = ('{tempfile}:8: error: Argument 1 to "nested_func" has incompatible type '
                '"bool"; expected "str"')
    int_bool = ('{tempfile}:9: error: Argument 1 to "alpha_func" has incompatible type '
                '"int"; expected "bool"')


def create_namespace_program_source(import_style: NamespaceProgramImportStyle) -> str:
    return _NAMESPACE_PROGRAM.format(import_style=import_style.value)


class ExampleProgram(object):
    _fname = 'test_program.py'

    def __init__(self, source_code: str) -> None:
        self._source_code = source_code

        self._temp_dir = None  # type: Optional[tempfile.TemporaryDirectory[Any]]
        self._full_fname = ''

    def init(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._full_fname = os.path.join(self._temp_dir.name, self._fname)
        with open(self._full_fname, 'w+') as f:
            f.write(self._source_code)

    def cleanup(self) -> None:
        if self._temp_dir:
            self._temp_dir.cleanup()

    def build_msg(self, *msgs: Enum) -> str:
        return '\n'.join(
            msg.value.format(tempfile=self._full_fname)
            for msg in msgs
        ) + '\n'

    def check_mypy_run(self,
                       python_executable: str,
                       expected_out: List[Enum],
                       expected_err: str = '',
                       expected_returncode: int = 1,
                       venv_dir: Optional[str] = None) -> None:
        """Helper to run mypy and check the output."""
        cmd_line = [self._full_fname]
        if venv_dir is not None:
            old_dir = os.getcwd()
            os.chdir(venv_dir)
        try:
            if python_executable != sys.executable:
                cmd_line.append('--python-executable={}'.format(python_executable))
            out, err, returncode = mypy.api.run(cmd_line)
            assert out == self.build_msg(*expected_out), err
            assert err == expected_err, out
            assert returncode == expected_returncode, returncode
        finally:
            if venv_dir is not None:
                os.chdir(old_dir)


class TestPEP561(TestCase):

    @contextmanager
    def virtualenv(self,
                   python_executable: str = sys.executable
                   ) -> Generator[Tuple[str, str], None, None]:
        """Context manager that creates a virtualenv in a temporary directory

        returns the path to the created Python executable"""
        # Sadly, we need virtualenv, as the Python 3 venv module does not support creating a venv
        # for Python 2, and Python 2 does not have its own venv.
        with tempfile.TemporaryDirectory() as venv_dir:
            returncode, lines = run_command([sys.executable,
                                             '-m',
                                             'virtualenv',
                                             '-p{}'.format(python_executable),
                                            venv_dir], cwd=os.getcwd())
            if returncode != 0:
                err = '\n'.join(lines)
                self.fail("Failed to create venv. Do you have virtualenv installed?\n" + err)
            if sys.platform == 'win32':
                yield venv_dir, os.path.abspath(os.path.join(venv_dir, 'Scripts', 'python'))
            else:
                yield venv_dir, os.path.abspath(os.path.join(venv_dir, 'bin', 'python'))

    def install_package(self, pkg: str,
                        python_executable: str = sys.executable,
                        use_pip: bool = True,
                        editable: bool = False) -> None:
        """Context manager to temporarily install a package from test-data/packages/pkg/"""
        working_dir = os.path.join(package_path, pkg)
        if use_pip:
            install_cmd = [python_executable, '-m', 'pip', 'install']
            if editable:
                install_cmd.append('-e')
            install_cmd.append('.')
        else:
            install_cmd = [python_executable, 'setup.py']
            if editable:
                install_cmd.append('develop')
            else:
                install_cmd.append('install')
        returncode, lines = run_command(install_cmd, cwd=working_dir)
        if returncode != 0:
            self.fail('\n'.join(lines))

    def setUp(self) -> None:
        self.simple_example_program = ExampleProgram(SIMPLE_PROGRAM)
        self.from_namespace_example_program = ExampleProgram(
            create_namespace_program_source(NamespaceProgramImportStyle.from_import))
        self.import_as_namespace_example_program = ExampleProgram(
            create_namespace_program_source(NamespaceProgramImportStyle.from_import))
        self.regular_import_namespace_example_program = ExampleProgram(
            create_namespace_program_source(NamespaceProgramImportStyle.from_import))
        self.c_ext_example_program = ExampleProgram(C_EXT_PROGRAM)

    def tearDown(self) -> None:
        self.simple_example_program.cleanup()
        self.from_namespace_example_program.cleanup()
        self.import_as_namespace_example_program.cleanup()
        self.regular_import_namespace_example_program.cleanup()
        self.c_ext_example_program.cleanup()

    def test_get_pkg_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = get_site_packages_dirs(sys.executable)
        assert dirs

    def test_typedpkg_stub_package(self) -> None:
        self.simple_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg-stubs', python_executable)
            self.simple_example_program.check_mypy_run(
                python_executable,
                [SimpleProgramMessage.msg_dne,
                 SimpleProgramMessage.msg_list],
                venv_dir=venv_dir,
            )

    def test_typedpkg(self) -> None:
        self.simple_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable)
            self.simple_example_program.check_mypy_run(
                python_executable,
                [SimpleProgramMessage.msg_tuple],
                venv_dir=venv_dir,
            )

    def test_stub_and_typed_pkg(self) -> None:
        self.simple_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable)
            self.install_package('typedpkg-stubs', python_executable)
            self.simple_example_program.check_mypy_run(
                python_executable,
                [SimpleProgramMessage.msg_list],
                venv_dir=venv_dir,
            )

    def test_typedpkg_stubs_python2(self) -> None:
        self.simple_example_program.init()
        python2 = try_find_python2_interpreter()
        if python2:
            with self.virtualenv(python2) as venv:
                venv_dir, py2 = venv
                self.install_package('typedpkg-stubs', py2)
                self.simple_example_program.check_mypy_run(
                    py2,
                    [SimpleProgramMessage.msg_dne,
                     SimpleProgramMessage.msg_list],
                    venv_dir=venv_dir,
                )

    def test_typedpkg_python2(self) -> None:
        self.simple_example_program.init()
        python2 = try_find_python2_interpreter()
        if python2:
            with self.virtualenv(python2) as venv:
                venv_dir, py2 = venv
                self.install_package('typedpkg', py2)
                self.simple_example_program.check_mypy_run(
                    py2,
                    [SimpleProgramMessage.msg_tuple],
                    venv_dir=venv_dir,
                )

    def test_typedpkg_egg(self) -> None:
        self.simple_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable, use_pip=False)
            self.simple_example_program.check_mypy_run(
                python_executable,
                [SimpleProgramMessage.msg_tuple],
                venv_dir=venv_dir,
            )

    def test_typedpkg_editable(self) -> None:
        self.simple_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable, editable=True)
            self.simple_example_program.check_mypy_run(
                python_executable,
                [SimpleProgramMessage.msg_tuple],
                venv_dir=venv_dir,
            )

    def test_nested_and_namespace_from_import(self) -> None:
        self.from_namespace_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg_nested', python_executable)
            self.install_package('typedpkg_namespace-alpha', python_executable)
            self.from_namespace_example_program.check_mypy_run(
                python_executable,
                [NamespaceProgramMessage.bool_str,
                 NamespaceProgramMessage.int_bool],
                venv_dir=venv_dir,
            )

    def test_nested_and_namespace_import_as(self) -> None:
        self.import_as_namespace_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg_nested', python_executable)
            self.install_package('typedpkg_namespace-alpha', python_executable)
            self.import_as_namespace_example_program.check_mypy_run(
                python_executable,
                [NamespaceProgramMessage.bool_str,
                 NamespaceProgramMessage.int_bool],
                venv_dir=venv_dir,
            )

    def test_nested_and_namespace_regular_import(self) -> None:
        # This test case addresses https://github.com/python/mypy/issues/5767
        self.regular_import_namespace_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg_nested', python_executable)
            self.install_package('typedpkg_namespace-alpha', python_executable)
            self.regular_import_namespace_example_program.check_mypy_run(
                python_executable,
                [NamespaceProgramMessage.bool_str,
                 NamespaceProgramMessage.int_bool],
                venv_dir=venv_dir,
            )

    def test_c_ext_from_import(self) -> None:
        self.c_ext_example_program.init()
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg_c_ext', python_executable)
            self.c_ext_example_program.check_mypy_run(
                python_executable,
                [],
                venv_dir=venv_dir,
            )


if __name__ == '__main__':
    main()
