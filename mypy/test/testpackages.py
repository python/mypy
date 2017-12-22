import os
import sys

from mypy.build import find_module, get_package_dirs
from mypy.test.config import package_path
from unittest import TestCase, main
from mypy.test.helpers import run


class TestPackages(TestCase):

    def install_pkg(self, pkg: str) -> None:
        working_dir = os.path.join(package_path, pkg)
        out, lines = run([sys.executable, 'setup.py', 'install'],
                         cwd=working_dir)
        if out != 0:
            self.fail('\n'.join(lines))

    def setUp(self) -> None:
        self.install_pkg('typed')
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
        self.find_package('typedpkg')
        self.find_package('typedpkg.sample')

    def test_find_stub_pacakage(self) -> None:
        self.install_pkg('stubs')
        self.find_package('typedpkg')
        self.find_package('typedpkg.sample')


if __name__ == '__main__':
    main()
