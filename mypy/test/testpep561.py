from contextlib import contextmanager
import os
import shutil
import sys
from typing import Iterator, List
from unittest import TestCase, main

import mypy.api
from mypy.build import _get_site_packages_dirs
from mypy.test.config import package_path, test_temp_dir
from mypy.test.helpers import run_command
from mypy.util import try_find_python2_interpreter

test_dir = 'test-packages-data'

SIMPLE_PROGRAM = """
from typedpkg.sample import ex
a = ex([''])
reveal_type(a)
"""


def make_venv(pkg: str, python_executable: str) -> str:
    """Create virtualenv and return path to new executable"""
    base = os.path.join(package_path, pkg + 'venv')
    run_command([sys.executable, '-m', 'virtualenv', '-p{}'.format(python_executable), base], cwd=package_path)
    if sys.platform == 'win32':
        return os.path.abspath(os.path.join(base, 'Scripts', 'python.exe'))
    else:
        return os.path.abspath(os.path.join(base, 'bin', 'python2'))


def check_mypy_run(cmd_line: List[str],
                   expected_out: str,
                   expected_err: str = '',
                   expected_returncode: int = 1) -> None:
    """Helper to run mypy and check the output."""
    out, err, returncode = mypy.api.run(cmd_line)
    assert out == expected_out, err
    assert err == expected_err, out
    assert returncode == expected_returncode, returncode


def is_in_venv() -> bool:
    """Returns whether we are running inside a venv.

    Based on https://stackoverflow.com/a/42580137.

    """
    if hasattr(sys, 'real_prefix'):
        return True
    else:
        return hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix


class TestPEP561(TestCase):
    @contextmanager
    def install_package(self, pkg: str, editable: bool = False,
                        use_pip: bool = True, virtualenv: bool = False,
                        python_executable: str = sys.executable) -> Iterator[None]:
        """Context manager to temporarily install a package from test-data/packages/pkg/"""
        working_dir = os.path.join(package_path, pkg)
        if use_pip:
            install_cmd = ['-m', 'pip', 'install']
            if editable:
                install_cmd.append('-e')
            install_cmd.append('.')
        else:
            install_cmd = ['setup.py', 'install']
        # if we aren't in a virtualenv, install in the
        # user package directory so we don't need sudo
        if (not is_in_venv() or python_executable != sys.executable) and not virtualenv:
            install_cmd.append('--user')
        returncode, lines = run_command([python_executable] + install_cmd, cwd=working_dir)
        if returncode != 0:
            self.fail('\n'.join(lines))
        try:
            yield
        finally:
            returncode, lines = run_command([python_executable, '-m', 'pip', 'uninstall',
                                             '-y', pkg], cwd=package_path)
            if returncode != 0:
                self.fail('\n'.join(lines))

    def test_get_pkg_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = _get_site_packages_dirs(sys.executable)
        assert dirs

    def test_typed_pkg(self) -> None:
        """Tests type checking based on installed packages.

        This test CANNOT be split up, concurrency means that simultaneously
        installing/uninstalling will break tests.
        """
        test_file = 'simple.py'
        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)
        old_cwd = os.getcwd()
        os.chdir(test_dir)
        with open(test_file, 'w') as f:
            f.write(SIMPLE_PROGRAM)
        try:
            # First test each type of install works

            # Normal pip and install (most packages are installed this way)
            with self.install_package('typedpkg-stubs'):
                check_mypy_run(
                    [test_file],
                    "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                )
            # Editable install (test egg-links)
            with self.install_package('typedpkg-stubs', editable=True):
                check_mypy_run(
                    [test_file],
                    "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                )
            # Uncompressed egg install (setuptools with zip_safe=False)
            with self.install_package('typedpkg-stubs', use_pip=False):
                check_mypy_run(
                    [test_file],
                    "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                )

            # The Python 2 tests are intentionally placed after Python 3 tests to check
            # the package_dir_cache is behaving correctly.
            python2 = try_find_python2_interpreter()
            if python2:
                py2 = make_venv('typedpkg-stubs', python2)
                with self.install_package('typedpkg-stubs', python_executable=py2, virtualenv=True):
                    check_mypy_run(
                        ['--python-executable={}'.format(py2), test_file],
                        "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                    )
                shutil.rmtree(os.path.join(package_path, 'typedpkg-stubsvenv'))

            # Now test ordering of module resolution order
            with self.install_package('typedpkg'):
                check_mypy_run(
                    [test_file],
                    "simple.py:4: error: Revealed type is 'builtins.tuple[builtins.str]'\n"
                )

            with self.install_package('typedpkg'):
                with self.install_package('typedpkg-stubs'):
                    check_mypy_run(
                        [test_file],
                        "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                    )
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(test_dir)


if __name__ == '__main__':
    main()
