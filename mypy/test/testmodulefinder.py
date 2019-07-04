import os

from mypy.options import Options
from mypy.modulefinder import FindModuleCache, SearchPaths

from mypy.test.helpers import Suite, assert_equal
from mypy.test.config import package_path
data_path = os.path.relpath(os.path.join(package_path, "modulefinder"))


class ModuleFinderSuite(Suite):

    def setUp(self) -> None:
        self.search_paths = SearchPaths(
            python_path=(),
            mypy_path=(
                os.path.join(data_path, "nsx-pkg1"),
                os.path.join(data_path, "nsx-pkg2"),
                os.path.join(data_path, "nsx-pkg3"),
                os.path.join(data_path, "nsy-pkg1"),
                os.path.join(data_path, "nsy-pkg2"),
                os.path.join(data_path, "pkg1"),
                os.path.join(data_path, "pkg2"),
            ),
            package_path=(),
            typeshed_path=(),
        )
        options = Options()
        options.namespace_packages = True
        self.fmc_ns = FindModuleCache(self.search_paths, options=options)

        options = Options()
        options.namespace_packages = False
        self.fmc_nons = FindModuleCache(self.search_paths, options=options)

    def test__no_namespace_packages__nsx(self) -> None:
        """
        If namespace_packages is False, we shouldn't find nsx
        """
        found_module = self.fmc_nons.find_module("nsx")
        self.assertIsNone(found_module)

    def test__no_namespace_packages__nsx_a(self) -> None:
        """
        If namespace_packages is False, we shouldn't find nsx.a.
        """
        found_module = self.fmc_nons.find_module("nsx.a")
        self.assertIsNone(found_module)

    def test__no_namespace_packages__find_a_in_pkg1(self) -> None:
        """
        Find find pkg1/a.py for "a" with namespace_packages False.
        """
        found_module = self.fmc_nons.find_module("a")
        expected = os.path.join(data_path, "pkg1", "a.py")
        assert_equal(expected, found_module)

    def test__no_namespace_packages__find_b_in_pkg2(self) -> None:
        found_module = self.fmc_ns.find_module("b")
        expected = os.path.join(data_path, "pkg2", "b", "__init__.py")
        assert_equal(expected, found_module)

    def test__find_nsx_as_namespace_pkg_in_pkg1(self) -> None:
        """
        There's no __init__.py in any of the nsx dirs, return
        the path to the first one found in mypypath.
        """
        found_module = self.fmc_ns.find_module("nsx")
        expected = os.path.join(data_path, "nsx-pkg1", "nsx")
        assert_equal(expected, found_module)

    def test__find_nsx_a_init_in_pkg1(self) -> None:
        """
        Find nsx-pkg1/nsx/a/__init__.py for "nsx.a" in namespace mode.
        """
        found_module = self.fmc_ns.find_module("nsx.a")
        expected = os.path.join(data_path, "nsx-pkg1", "nsx", "a", "__init__.py")
        assert_equal(expected, found_module)

    def test__find_nsx_b_init_in_pkg2(self) -> None:
        """
        Find nsx-pkg2/nsx/b/__init__.py for "nsx.b" in namespace mode.
        """
        found_module = self.fmc_ns.find_module("nsx.b")
        expected = os.path.join(data_path, "nsx-pkg2", "nsx", "b", "__init__.py")
        assert_equal(expected, found_module)

    def test__find_nsx_c_c_in_pkg3(self) -> None:
        """
        Find nsx-pkg3/nsx/c/c.py for "nsx.c.c" in namespace mode.
        """
        found_module = self.fmc_ns.find_module("nsx.c.c")
        expected = os.path.join(data_path, "nsx-pkg3", "nsx", "c", "c.py")
        assert_equal(expected, found_module)

    def test__find_nsy_a__init_pyi(self) -> None:
        """
        Prefer nsy-pkg1/a/__init__.pyi file over __init__.py.
        """
        found_module = self.fmc_ns.find_module("nsy.a")
        expected = os.path.join(data_path, "nsy-pkg1", "nsy", "a", "__init__.pyi")
        assert_equal(expected, found_module)

    def test__find_nsy_b__init_py(self) -> None:
        """
        There is a nsy-pkg2/nsy/b.pyi, but also a nsy-pkg2/nsy/b/__init__.py.
        We expect to find the latter when looking up "nsy.b" as
        a package is preferred over a module.
        """
        found_module = self.fmc_ns.find_module("nsy.b")
        expected = os.path.join(data_path, "nsy-pkg2", "nsy", "b", "__init__.py")
        assert_equal(expected, found_module)

    def test__find_nsy_c_pyi(self) -> None:
        """
        There is a nsy-pkg2/nsy/c.pyi and nsy-pkg2/nsy/c.py
        We expect to find the former when looking up "nsy.b" as
        .pyi is preferred over .py.
        """
        found_module = self.fmc_ns.find_module("nsy.c")
        expected = os.path.join(data_path, "nsy-pkg2", "nsy", "c.pyi")
        assert_equal(expected, found_module)

    def test__find_a_in_pkg1(self) -> None:
        found_module = self.fmc_ns.find_module("a")
        expected = os.path.join(data_path, "pkg1", "a.py")
        assert_equal(expected, found_module)

    def test__find_b_init_in_pkg2(self) -> None:
        found_module = self.fmc_ns.find_module("b")
        expected = os.path.join(data_path, "pkg2", "b", "__init__.py")
        assert_equal(expected, found_module)

    def test__find_d_nowhere(self) -> None:
        found_module = self.fmc_ns.find_module("d")
        self.assertIsNone(found_module)
