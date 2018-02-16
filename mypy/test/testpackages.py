from contextlib import contextmanager
import os
import sys
from typing import Generator
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

    @contextmanager
    def install_package(self, pkg: str,
                        python: str = sys.executable) -> Generator[None, None, None]:
        """Context manager to temporarily install a package from test-data/packages/pkg/"""
        working_dir = os.path.join(package_path, pkg)
        install_cmd = [python, '-m', 'pip', 'install', '.']
        # if we aren't in a virtualenv, install in the user package directory so we don't need sudo
        if not hasattr(sys, 'real_prefix') or python != sys.executable:
            install_cmd.append('--user')
        returncode, lines = run_command(install_cmd, cwd=working_dir)
        if returncode != 0:
            self.fail('\n'.join(lines))
        try:
            yield
        except AssertionError as e:
            raise AssertionError("Failed to typecheck with installed package {}.\n"
                                 "Package directories checked:\n{}"
                                 "Error:\n{}".format(pkg, get_package_dirs(python), e))
        finally:
            run_command([python, '-m', 'pip', 'uninstall', '-y', pkg], cwd=package_path)

    def test_get_package_dirs(self) -> None:
        """Check that get_package_dirs works."""
        dirs = get_package_dirs(sys.executable)
        assert dirs

    def test_typed_package(self) -> None:
        """Tests type checking based on installed packages.

        This test CANNOT be split up, concurrency means that simultaneously
        installing/uninstalling will break tests"""
        with open('simple.py', 'w') as f:
            f.write(SIMPLE_PROGRAM)

        with self.install_package('typedpkg-stubs'):
            out, err, returncode = mypy.api.run(['simple.py'])
            assert \
                out == "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
            assert returncode == 1
            assert err == ''

        python2 = try_find_python2_interpreter()
        if python2:
            with self.install_package('typedpkg-stubs', python2):
                out, err, returncode = mypy.api.run(
                    ['--python-executable={}'.format(python2), 'simple.py'])
                assert \
                    out == "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                assert returncode == 1
                assert err == ''
            with self.install_package('typedpkg', python2):
                out, err, returncode = mypy.api.run(
                    ['--python-executable={}'.format(python2), 'simple.py'])
                assert out == "simple.py:4: error: Revealed type is " \
                              "'builtins.tuple[builtins.str]'\n"
                assert returncode == 1
                assert err == ''

            with self.install_package('typedpkg', python2):
                with self.install_package('typedpkg-stubs', python2):
                    out, err, returncode = mypy.api.run(
                        ['--python-executable={}'.format(python2), 'simple.py'])
                    assert \
                        out == "simple.py:4: error: Revealed type is " \
                               "'builtins.list[builtins.str]'\n"
                    assert returncode == 1
                    assert err == ''

        with self.install_package('typedpkg'):
            out, err, returncode = mypy.api.run(['simple.py'])
            assert out == "simple.py:4: error: Revealed type is 'builtins.tuple[builtins.str]'\n"
            assert returncode == 1
            assert err == ''

        with self.install_package('typedpkg'):
            with self.install_package('typedpkg-stubs'):
                out, err, returncode = mypy.api.run(['simple.py'])
                assert \
                    out == "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                assert returncode == 1
                assert err == ''
        os.remove('simple.py')


if __name__ == '__main__':
    main()
