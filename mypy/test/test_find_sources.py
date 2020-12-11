from mypy.modulefinder import BuildSource
import os
import unittest
from typing import List, Optional, Set, Tuple
from mypy.find_sources import SourceFinder
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource
from mypy.options import Options


class FakeFSCache(FileSystemCache):
    def __init__(self, files: Set[str]) -> None:
        self.files = {os.path.abspath(f) for f in files}

    def isfile(self, file: str) -> bool:
        return file in self.files

    def isdir(self, dir: str) -> bool:
        if not dir.endswith(os.sep):
            dir += os.sep
        return any(f.startswith(dir) for f in self.files)

    def listdir(self, dir: str) -> List[str]:
        if not dir.endswith(os.sep):
            dir += os.sep
        return list(set(f[len(dir):].split(os.sep)[0] for f in self.files if f.startswith(dir)))

    def init_under_package_root(self, file: str) -> bool:
        return False


def normalise_path(path: str) -> str:
    path = os.path.splitdrive(path)[1]
    path = path.replace(os.sep, "/")
    return path


def normalise_build_source_list(sources: List[BuildSource]) -> List[Tuple[str, Optional[str]]]:
    return sorted(
        (s.module, (normalise_path(s.base_dir) if s.base_dir is not None else None))
        for s in sources
    )


def crawl(finder: SourceFinder, f: str) -> Tuple[str, str]:
    module, base_dir = finder.crawl_up(f)
    return module, normalise_path(base_dir)


def find_sources(finder: SourceFinder, f: str) -> List[Tuple[str, Optional[str]]]:
    return normalise_build_source_list(finder.find_sources_in_dir(os.path.abspath(f)))


class SourceFinderSuite(unittest.TestCase):
    def test_crawl_no_namespace(self) -> None:
        options = Options()
        options.namespace_packages = False

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert crawl(finder, "/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/b/c/setup.py") == ("c.setup", "/a/b")

    def test_crawl_namespace(self) -> None:
        options = Options()
        options.namespace_packages = True

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert crawl(finder, "/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("a.b.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/b/c/setup.py") == ("a.b.c.setup", "/")

    def test_crawl_namespace_explicit_base(self) -> None:
        options = Options()
        options.namespace_packages = True
        options.explicit_package_bases = True

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert crawl(finder, "/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert crawl(finder, "/a/b/setup.py") == ("a.b.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/b/c/setup.py") == ("a.b.c.setup", "/")

        # set mypy path, so we actually have some explicit base dirs
        options.mypy_path = ["/a/b"]

        finder = SourceFinder(FakeFSCache({"/a/b/c/setup.py"}), options)
        assert crawl(finder, "/a/b/c/setup.py") == ("c.setup", "/a/b")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert crawl(finder, "/a/b/c/setup.py") == ("c.setup", "/a/b")

        options.mypy_path = ["/a/b", "/a/b/c"]
        finder = SourceFinder(FakeFSCache({"/a/b/c/setup.py"}), options)
        assert crawl(finder, "/a/b/c/setup.py") == ("setup", "/a/b/c")

    def test_crawl_namespace_multi_dir(self) -> None:
        options = Options()
        options.namespace_packages = True
        options.explicit_package_bases = True
        options.mypy_path = ["/a", "/b"]

        finder = SourceFinder(FakeFSCache({"/a/pkg/a.py", "/b/pkg/b.py"}), options)
        assert crawl(finder, "/a/pkg/a.py") == ("pkg.a", "/a")
        assert crawl(finder, "/b/pkg/b.py") == ("pkg.b", "/b")

    def test_find_sources_no_namespace(self) -> None:
        options = Options()
        options.namespace_packages = False

        files = {
            "/pkg/a1/b/c/d/e.py",
            "/pkg/a1/b/f.py",
            "/pkg/a2/__init__.py",
            "/pkg/a2/b/c/d/e.py",
            "/pkg/a2/b/f.py",
        }
        finder = SourceFinder(FakeFSCache(files), options)
        assert find_sources(finder, "/") == [
            ("a2", "/pkg"),
            ("e", "/pkg/a1/b/c/d"),
            ("e", "/pkg/a2/b/c/d"),
            ("f", "/pkg/a1/b"),
            ("f", "/pkg/a2/b"),
        ]

    def test_find_sources_namespace(self) -> None:
        options = Options()
        options.namespace_packages = True

        files = {
            "/pkg/a1/b/c/d/e.py",
            "/pkg/a1/b/f.py",
            "/pkg/a2/__init__.py",
            "/pkg/a2/b/c/d/e.py",
            "/pkg/a2/b/f.py",
        }
        finder = SourceFinder(FakeFSCache(files), options)
        assert find_sources(finder, "/") == [
            ("a2", "/pkg"),
            ("a2.b.c.d.e", "/pkg"),
            ("a2.b.f", "/pkg"),
            ("e", "/pkg/a1/b/c/d"),
            ("f", "/pkg/a1/b"),
        ]

    def test_find_sources_namespace_explicit_base(self) -> None:
        options = Options()
        options.namespace_packages = True
        options.explicit_package_bases = True
        options.mypy_path = ["/"]

        files = {
            "/pkg/a1/b/c/d/e.py",
            "/pkg/a1/b/f.py",
            "/pkg/a2/__init__.py",
            "/pkg/a2/b/c/d/e.py",
            "/pkg/a2/b/f.py",
        }
        finder = SourceFinder(FakeFSCache(files), options)
        assert find_sources(finder, "/") == [
            ("pkg.a1.b.c.d.e", "/"),
            ("pkg.a1.b.f", "/"),
            ("pkg.a2", "/"),
            ("pkg.a2.b.c.d.e", "/"),
            ("pkg.a2.b.f", "/"),
        ]

        options.mypy_path = ["/pkg"]
        finder = SourceFinder(FakeFSCache(files), options)
        assert find_sources(finder, "/") == [
            ("a1.b.c.d.e", "/pkg"),
            ("a1.b.f", "/pkg"),
            ("a2", "/pkg"),
            ("a2.b.c.d.e", "/pkg"),
            ("a2.b.f", "/pkg"),
        ]

    def test_find_sources_namespace_multi_dir(self) -> None:
        options = Options()
        options.namespace_packages = True
        options.explicit_package_bases = True
        options.mypy_path = ["/a", "/b"]

        finder = SourceFinder(FakeFSCache({"/a/pkg/a.py", "/b/pkg/b.py"}), options)
        assert find_sources(finder, "/") == [("pkg.a", "/a"), ("pkg.b", "/b")]
