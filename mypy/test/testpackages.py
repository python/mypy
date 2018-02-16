from contextlib import contextmanager
import os
import site
import sys
from typing import Generator, List
from unittest import TestCase, main

import mypy.api
from mypy.build import get_package_dirs
from mypy.test.config import package_path
from mypy.test.helpers import run_command
from mypy.util import try_find_python2_interpreter


SIMPLE_PROGRAM = """
from typedpkg.sample import ex
a = ex([''])
reveal_type(a)
"""


class TestPackages(TestCase):

    def tearDownClass(cls) -> None:
        if os.path.isfile('simple.py'):
            os.remove('simple.py')

    @contextmanager
    def install_package(self, pkg: str,
                        python: str = sys.executable) -> Generator[None, None, None]:
        """Context manager to temporarily install a package from test-data/packages/pkg/"""
        working_dir = os.path.join(package_path, pkg)
        install_cmd = [python, '-m', 'pip', 'install', '.']
        # if we aren't in a virtualenv, install in the
        # user package directory so we don't need sudo
        if not hasattr(sys, 'real_prefix') or python != sys.executable:
            install_cmd.append('--user')
        returncode, lines = run_command(install_cmd, cwd=working_dir)
        if returncode != 0:
            self.fail('\n'.join(lines))
        try:
            yield
        finally:
            run_command([python, '-m', 'pip', 'uninstall', '-y', pkg], cwd=package_path)

    def test_get_package_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = get_package_dirs(sys.executable)
        assert dirs

    @staticmethod
    def check_mypy_run(cmd_line: List[str],
                       expected_out: str,
                       expected_err: str = '',
                       expected_returncode: int = 1) -> None:
        """Helper to run mypy and check the output."""
        out, err, returncode = mypy.api.run(cmd_line)
        assert out == expected_out, err
        assert err == expected_err, out
        assert expected_returncode == returncode

    def test_typed_package(self) -> None:
        """Tests type checking based on installed packages.

        This test CANNOT be split up, concurrency means that simultaneously
        installing/uninstalling will break tests"""
        with open('simple.py', 'w') as f:
            f.write(SIMPLE_PROGRAM)

        with self.install_package('typedpkg-stubs'):
            self.check_mypy_run(
                ['simple.py'],
                "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
            )

        # The Python 2 tests are intentionally placed after a Python 3 test to check
        # the package_dir_cache is behaving correctly.
        python2 = try_find_python2_interpreter()
        if python2:
            with self.install_package('typedpkg-stubs', python2):
                self.check_mypy_run(
                    ['--python-executable={}'.format(python2), 'simple.py'],
                    "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                )
            with self.install_package('typedpkg', python2):
                self.check_mypy_run(
                    ['--python-executable={}'.format(python2), 'simple.py'],
                    "simple.py:4: error: Revealed type is 'builtins.tuple[builtins.str]'\n"
                )

            with self.install_package('typedpkg', python2):
                with self.install_package('typedpkg-stubs', python2):
                    self.check_mypy_run(
                        ['--python-executable={}'.format(python2), 'simple.py'],
                        "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                    )

        with self.install_package('typedpkg'):
            self.check_mypy_run(
                ['simple.py'],
                "simple.py:4: error: Revealed type is 'builtins.tuple[builtins.str]'\n"
            )

        with self.install_package('typedpkg'):
            with self.install_package('typedpkg-stubs'):
                self.check_mypy_run(
                    ['simple.py'],
                    "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                )
        os.remove('simple.py')


if __name__ == '__main__':
    main()
