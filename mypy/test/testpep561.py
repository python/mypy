from contextlib import contextmanager
import os
import sys
import tempfile
from typing import Tuple, List, Generator, Optional
from unittest import TestCase, main

import mypy.api
from mypy.build import _get_site_packages_dirs
from mypy.test.config import package_path
from mypy.test.helpers import run_command
from mypy.util import try_find_python2_interpreter

SIMPLE_PROGRAM = """
from typedpkg.sample import ex
from typedpkg import dne
a = ex([''])
reveal_type(a)
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
        with tempfile.TemporaryDirectory() as venv_dir:
            run_command([sys.executable, '-m', 'virtualenv', '-p{}'.format(python_executable),
                        venv_dir], cwd=os.getcwd())
            if sys.platform == 'win32':
                yield venv_dir, os.path.abspath(os.path.join(venv_dir, 'Scripts', 'python'))
            else:
                yield venv_dir, os.path.abspath(os.path.join(venv_dir, 'bin', 'python'))

    def install_package(self, pkg: str,
                        python_executable: str = sys.executable) -> None:
        """Context manager to temporarily install a package from test-data/packages/pkg/"""
        working_dir = os.path.join(package_path, pkg)
        install_cmd = [python_executable, '-m', 'pip', 'install', '.']
        returncode, lines = run_command(install_cmd, cwd=working_dir)
        if returncode != 0:
            self.fail('\n'.join(lines))

    def setUp(self) -> None:
        self.temp_file_dir = tempfile.TemporaryDirectory()
        self.tempfile = os.path.join(self.temp_file_dir.name, 'simple.py')
        with open(self.tempfile, 'w+') as file:
            file.write(SIMPLE_PROGRAM)
        self.msg_dne = \
            "{}:3: error: Module 'typedpkg' has no attribute 'dne'\n".format(self.tempfile)
        self.msg_list = \
            "{}:5: error: Revealed type is 'builtins.list[builtins.str]'\n".format(self.tempfile)
        self.msg_tuple = \
            "{}:5: error: Revealed type is 'builtins.tuple[builtins.str]'\n".format(self.tempfile)

    def tearDown(self) -> None:
        self.temp_file_dir.cleanup()

    def test_get_pkg_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = _get_site_packages_dirs(sys.executable)
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


if __name__ == '__main__':
    main()
