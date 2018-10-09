from contextlib import contextmanager
import os
import sys
import tempfile
from typing import Tuple, List, Generator, Optional
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

NAMESPACE_PROGRAM = """
from typedpkg_nested.nested_package.nested_module import nested_func
from typedpkg_namespace.alpha.alpha_module import alpha_func

nested_func("abc")
alpha_func(False)

nested_func(False)
alpha_func(2)
"""


def check_mypy_run(cmd_line: List[str],
                   python_executable: str = sys.executable,
                   expected_out: str = '',
                   expected_err: str = '',
                   expected_returncode: int = 1,
                   venv_dir: Optional[str] = None) -> None:
    """Helper to run mypy and check the output."""
    if venv_dir is not None:
        old_dir = os.getcwd()
        os.chdir(venv_dir)
    try:
        if python_executable != sys.executable:
            cmd_line.append('--python-executable={}'.format(python_executable))
        out, err, returncode = mypy.api.run(cmd_line)
        assert out == expected_out, err
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
        self.temp_file_dir = tempfile.TemporaryDirectory()
        self.tempfile = os.path.join(self.temp_file_dir.name, 'simple.py')
        with open(self.tempfile, 'w+') as file:
            file.write(SIMPLE_PROGRAM)
        self.namespace_tempfile = os.path.join(self.temp_file_dir.name, 'namespace_program.py')
        with open(self.namespace_tempfile, 'w+') as file:
            file.write(NAMESPACE_PROGRAM)

        self.msg_dne = \
            "{}:3: error: Module 'typedpkg' has no attribute 'dne'\n".format(self.tempfile)
        self.msg_list = \
            "{}:5: error: Revealed type is 'builtins.list[builtins.str]'\n".format(self.tempfile)
        self.msg_tuple = \
            "{}:5: error: Revealed type is 'builtins.tuple[builtins.str]'\n".format(self.tempfile)

        self.namespace_msg_bool_str = (
            '{0}:8: error: Argument 1 to "nested_func" has incompatible type "bool"; '
            'expected "str"\n'.format(self.namespace_tempfile))
        self.namespace_msg_int_bool = (
            '{0}:9: error: Argument 1 to "alpha_func" has incompatible type "int"; '
            'expected "bool"\n'.format(self.namespace_tempfile))

    def tearDown(self) -> None:
        self.temp_file_dir.cleanup()

    def test_get_pkg_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = get_site_packages_dirs(sys.executable)
        assert dirs

    def test_typedpkg_stub_package(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg-stubs', python_executable)
            check_mypy_run(
                [self.tempfile],
                python_executable,
                expected_out=self.msg_dne + self.msg_list,
                venv_dir=venv_dir,
            )

    def test_typedpkg(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable)
            check_mypy_run(
                [self.tempfile],
                python_executable,
                expected_out=self.msg_tuple,
                venv_dir=venv_dir,
            )

    def test_stub_and_typed_pkg(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable)
            self.install_package('typedpkg-stubs', python_executable)
            check_mypy_run(
                [self.tempfile],
                python_executable,
                expected_out=self.msg_list,
                venv_dir=venv_dir,
            )

    def test_typedpkg_stubs_python2(self) -> None:
        python2 = try_find_python2_interpreter()
        if python2:
            with self.virtualenv(python2) as venv:
                venv_dir, py2 = venv
                self.install_package('typedpkg-stubs', py2)
                check_mypy_run(
                    [self.tempfile],
                    py2,
                    expected_out=self.msg_dne + self.msg_list,
                    venv_dir=venv_dir,
                )

    def test_typedpkg_python2(self) -> None:
        python2 = try_find_python2_interpreter()
        if python2:
            with self.virtualenv(python2) as venv:
                venv_dir, py2 = venv
                self.install_package('typedpkg', py2)
                check_mypy_run(
                    [self.tempfile],
                    py2,
                    expected_out=self.msg_tuple,
                    venv_dir=venv_dir,
                )

    def test_typedpkg_egg(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable, use_pip=False)
            check_mypy_run(
                [self.tempfile],
                python_executable,
                expected_out=self.msg_tuple,
                venv_dir=venv_dir,
            )

    def test_typedpkg_editable(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg', python_executable, editable=True)
            check_mypy_run(
                [self.tempfile],
                python_executable,
                expected_out=self.msg_tuple,
                venv_dir=venv_dir,
            )

    def test_nested_and_namespace(self) -> None:
        with self.virtualenv() as venv:
            venv_dir, python_executable = venv
            self.install_package('typedpkg_nested', python_executable)
            self.install_package('typedpkg_namespace-alpha', python_executable)
            check_mypy_run(
                [self.namespace_tempfile],
                python_executable,
                expected_out=self.namespace_msg_bool_str + self.namespace_msg_int_bool,
                venv_dir=venv_dir,
            )


if __name__ == '__main__':
    main()
