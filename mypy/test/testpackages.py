from contextlib import contextmanager
import os
import sys
from typing import Generator
from unittest import TestCase, main

from mypy.api import run as run_mypy
from mypy.build import find_module, get_package_dirs
from mypy.test.config import package_path
from mypy.test.helpers import run


SIMPLE_PROGRAM = """
from typedpkg.sample import ex
a = ex([''])
reveal_type(a)
"""


class TestPackages(TestCase):

    def setUp(self) -> None:
        self.dirs = get_package_dirs(None)
        self.assertNotEqual(self.dirs, [])
        with open('simple.py', 'w') as f:
            f.write(SIMPLE_PROGRAM)

    def tearDown(self) -> None:
        os.remove('simple.py')

    @contextmanager
    def installed_package(self, pkg: str) -> Generator[None, None, None]:
        """Context manager to install a package in test-data/packages/pkg/.
        Uninstalls the package afterward."""
        working_dir = os.path.join(package_path, pkg)
        out, lines = run([sys.executable, '-m', 'pip', 'install', '.'],
                         cwd=working_dir)
        if out != 0:
            self.fail('\n'.join(lines))
        try:
            yield
        finally:
            run([sys.executable, '-m', 'pip', 'uninstall', '-y', pkg], cwd=package_path)

    def find_package(self, pkg: str) -> None:
        path = find_module(pkg, [], None)
        assert path is not None, (self.dirs, pkg)
        self.assertTrue(os.path.exists(path), path)
        for dir in self.dirs:
            if path.startswith(dir):
                break
        else:
            self.fail("Could not locate {}, path is {}".format(pkg, path))

    def test_typed_package(self) -> None:
        """Tests checking information based on installed packages.
        This test CANNOT be split up, concurrency means that simultaneously
        installing/uninstalling will break tests"""
        with self.installed_package('typedpkg_stubs'):
            out, err, ret = run_mypy(['simple.py'])
            assert ret == 1
            assert \
                out == "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
            assert err == ''
        with self.installed_package('typedpkg'):
            out, err, ret = run_mypy(['simple.py'])
            assert ret == 1
            assert out == "simple.py:4: error: Revealed type is 'builtins.tuple[builtins.str]'\n"
            assert err == ''
        with self.installed_package('typedpkg'):
            with self.installed_package('typedpkg_stubs'):
                out, err, ret = run_mypy(['simple.py'])
                assert ret == 1
                assert \
                    out == "simple.py:4: error: Revealed type is 'builtins.list[builtins.str]'\n"
                assert err == ''


if __name__ == '__main__':
    main()
