from contextlib import contextmanager
import os
import sys

from mypy.build import find_module, get_package_dirs
from mypy.test.config import package_path
from unittest import TestCase, main
from mypy.test.helpers import run


class TestPackages(TestCase):

    @contextmanager
    def installed_package(self, pkg: str) -> None:
        working_dir = os.path.join(package_path, pkg)
        out, lines = run([sys.executable, 'setup.py', 'install'],
                         cwd=working_dir)
        if out != 0:
            self.fail('\n'.join(lines))
        yield
        out, _ = run([sys.executable, '-m', 'pip', 'uninstall', '-y', pkg], cwd=working_dir)
        assert out == 0

    def setUp(self) -> None:
        self.dirs = get_package_dirs(None)
        self.assertNotEqual(self.dirs, [])

    def find_package(self, pkg: str) -> None:
        path = find_module(pkg, [], None)
        assert path is not None
        self.assertTrue(os.path.exists(path))
        for dir in self.dirs:
            if path.startswith(dir):
                break
        else:
            self.fail("Could not locate {}, path is {}".format(pkg, path))

    def test_find_typed_package(self) -> None:
        with self.installed_package('typedpkg'):
            self.find_package('typedpkg')
            self.find_package('typedpkg.sample')

    def test_find_stub_pacakage(self) -> None:
        with self.installed_package('typedpkg_stubs'):
            self.find_package('typedpkg')
            self.find_package('typedpkg.sample')


if __name__ == '__main__':
    main()
