from mypy.modulefinder import BuildSource
import os
from typing import Any, List, Optional, Set, Tuple, cast
from unittest import TestCase
from mypy.find_sources import SourceFinder
from mypy.modulefinder import BuildSource
from mypy.options import Options


class _FakeFSCache:
    def __init__(self, files: Set[str]) -> None:
        assert all(os.path.isabs(f) for f in files)
        self.files = files

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


FakeFSCache = cast(Any, _FakeFSCache)


def normalise_build_source_list(sources: List[BuildSource]) -> List[Tuple[str, Optional[str]]]:
    return sorted((s.module, s.base_dir) for s in sources)


class SourceFinderSuite(TestCase):
    def test_crawl_no_namespace(self) -> None:
        options = Options()
        options.namespace_packages = False

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert finder.crawl_up("/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/b/c/setup.py") == ("c.setup", "/a/b")

    def test_crawl_namespace(self) -> None:
        options = Options()
        options.namespace_packages = True

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert finder.crawl_up("/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("a.b.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/b/c/setup.py") == ("a.b.c.setup", "/")

    def test_crawl_namespace_explicit_base(self) -> None:
        options = Options()
        options.namespace_packages = True
        options.explicit_package_bases = True

        finder = SourceFinder(FakeFSCache({"/setup.py"}), options)
        assert finder.crawl_up("/setup.py") == ("setup", "/")

        finder = SourceFinder(FakeFSCache({"/a/setup.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("setup", "/a")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("setup", "/a/b")

        finder = SourceFinder(FakeFSCache({"/a/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/setup.py") == ("a.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/invalid-name/setup.py", "/a/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/invalid-name/setup.py") == ("setup", "/a/invalid-name")

        finder = SourceFinder(FakeFSCache({"/a/b/setup.py", "/a/__init__.py"}), options)
        assert finder.crawl_up("/a/b/setup.py") == ("a.b.setup", "/")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/b/c/setup.py") == ("a.b.c.setup", "/")

        # set mypy path, so we actually have some explicit base dirs
        options.mypy_path = ["/a/b"]

        finder = SourceFinder(FakeFSCache({"/a/b/c/setup.py"}), options)
        assert finder.crawl_up("/a/b/c/setup.py") == ("c.setup", "/a/b")

        finder = SourceFinder(
            FakeFSCache({"/a/b/c/setup.py", "/a/__init__.py", "/a/b/c/__init__.py"}),
            options,
        )
        assert finder.crawl_up("/a/b/c/setup.py") == ("c.setup", "/a/b")

        options.mypy_path = ["/a/b", "/a/b/c"]
        finder = SourceFinder(FakeFSCache({"/a/b/c/setup.py"}), options)
        assert finder.crawl_up("/a/b/c/setup.py") == ("setup", "/a/b/c")

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
        assert normalise_build_source_list(finder.find_sources_in_dir("/")) == [
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
        assert normalise_build_source_list(finder.find_sources_in_dir("/")) == [
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
        assert normalise_build_source_list(finder.find_sources_in_dir("/")) == [
            ("pkg.a1.b.c.d.e", "/"),
            ("pkg.a1.b.f", "/"),
            ("pkg.a2", "/"),
            ("pkg.a2.b.c.d.e", "/"),
            ("pkg.a2.b.f", "/"),
        ]

        options.mypy_path = ["/pkg"]
        finder = SourceFinder(FakeFSCache(files), options)
        assert normalise_build_source_list(finder.find_sources_in_dir("/")) == [
            ("a1.b.c.d.e", "/pkg"),
            ("a1.b.f", "/pkg"),
            ("a2", "/pkg"),
            ("a2.b.c.d.e", "/pkg"),
            ("a2.b.f", "/pkg"),
        ]
