import os

from unittest import TestCase, mock
from typing import List, Set, Union

from mypy.build import ModuleDiscovery, find_module_clear_caches


class TestModuleDiscovery(TestCase):
    def setUp(self) -> None:
        self.files = set()  # type: Union[Set[str], List[str]]
        self._setup_mock_filesystem()

    def tearDown(self) -> None:
        self._teardown_mock_filesystem()
        find_module_clear_caches()

    def _list_dir(self, path: str) -> List[str]:
        res = []

        if not path.endswith(os.path.sep):
            path = path + os.path.sep

        for item in self.files:
            if item.startswith(path):
                remnant = item.replace(path, '')
                segments = remnant.split(os.path.sep)
                if segments:
                    res.append(segments[0])

        return res

    def _is_file(self, path: str) -> bool:
        return path in self.files

    def _is_dir(self, path: str) -> bool:
        for item in self.files:
            if not item.endswith(os.path.sep):
                item += os.path.sep
            if item.startswith(path):
                return True
        return False

    def _setup_mock_filesystem(self) -> None:
        self._listdir_patcher = mock.patch('os.listdir', side_effect=self._list_dir)
        self._listdir_mock = self._listdir_patcher.start()
        self._isfile_patcher = mock.patch('os.path.isfile', side_effect=self._is_file)
        self._isfile_mock = self._isfile_patcher.start()
        self._isdir_patcher = mock.patch('os.path.isdir', side_effect=self._is_dir)
        self._isdir_mock = self._isdir_patcher.start()

    def _teardown_mock_filesystem(self) -> None:
        self._listdir_patcher.stop()
        self._isfile_patcher.stop()
        self._isdir_patcher.stop()

    def test_module_vs_package(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod.py'),
            os.path.join('dir2', 'mod', '__init__.py'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=False)
        src = m.find_module('mod')
        assert src is not None
        assert src.path == os.path.join('dir1', 'mod.py')

        m = ModuleDiscovery(['dir2', 'dir1'], namespaces_allowed=False)
        src = m.find_module('mod')
        assert src is not None
        assert src.path == os.path.join('dir2', 'mod', '__init__.py')

    def test_stubs_priority_module(self) -> None:
        self.files = [
            os.path.join('dir1', 'mod.py'),
            os.path.join('dir1', 'mod.pyi'),
        ]
        m = ModuleDiscovery(['dir1'], namespaces_allowed=False)
        src = m.find_module('mod')
        assert src is not None
        assert src.path == os.path.join('dir1', 'mod.pyi')

    def test_package_in_different_directories(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', '__init__.py'),
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', '__init__.py'),
            os.path.join('dir2', 'mod', 'b.py'),
        }
        m = ModuleDiscovery(['./dir1', './dir2'], namespaces_allowed=False)
        src = m.find_module('mod.a')
        assert src is not None
        assert src.path == os.path.join('dir1', 'mod', 'a.py')

        src = m.find_module('mod.b')
        assert src is None

    def test_package_with_stubs(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', '__init__.py'),
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', '__init__.pyi'),
            os.path.join('dir2', 'mod', 'b.pyi'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=False)
        src = m.find_module('mod.a')
        assert src is not None
        assert src.path == os.path.join('dir1', 'mod', 'a.py')

        src = m.find_module('mod.b')
        assert src is None

    def test_namespaces(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', 'b.py'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=True)
        src = m.find_module('mod.a')
        assert src is not None
        assert src.path == os.path.join('dir1', 'mod', 'a.py')

        src = m.find_module('mod.b')
        assert src is not None
        assert src.path == os.path.join('dir2', 'mod', 'b.py')

    def test_find_modules_recursive(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', '__init__.py'),
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', '__init__.pyi'),
            os.path.join('dir2', 'mod', 'b.pyi'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=True)
        srcs = m.find_modules_recursive('mod')
        assert [s.module for s in srcs] == ['mod', 'mod.a']

    def test_find_modules_recursive_with_namespace(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', 'b.py'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=True)
        srcs = m.find_modules_recursive('mod')
        assert [s.module for s in srcs] == ['mod', 'mod.a', 'mod.b']

    def test_find_modules_recursive_with_stubs(self) -> None:
        self.files = {
            os.path.join('dir1', 'mod', '__init__.py'),
            os.path.join('dir1', 'mod', 'a.py'),
            os.path.join('dir2', 'mod', '__init__.pyi'),
            os.path.join('dir2', 'mod', 'a.pyi'),
        }
        m = ModuleDiscovery(['dir1', 'dir2'], namespaces_allowed=True)
        srcs = m.find_modules_recursive('mod')
        assert [s.module for s in srcs] == ['mod', 'mod.a']
