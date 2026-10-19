"""Unit tests for mypy cache behavior."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from mypy import build
from mypy.errors import CompileError
from mypy.modulefinder import BuildSource
from mypy.options import Options

DEP_SOURCE = "x: int = 1\n"


class CorruptCacheSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.tempdir, ".mypy_cache")
        self.mypy_path = os.path.join(self.tempdir, "src")
        os.mkdir(self.mypy_path)
        self.dep_path = os.path.join(self.mypy_path, "dep.py")
        with open(self.dep_path, "w") as f:
            f.write(DEP_SOURCE)
        # Messages flushed during a build, including from failing builds.
        self.flushed: list[str] = []

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir)

    def make_options(self) -> Options:
        options = Options()
        options.cache_dir = self.cache_dir
        options.mypy_path = [self.mypy_path]
        options.hide_error_codes = True
        # Use the file-based fixed-format cache so we can corrupt the cache
        # data files directly.
        options.sqlite_cache = False
        options.fixed_format_cache = True
        return options

    def run_build(self, options: Options, main_source: str) -> bool:
        """Run a build, collecting flushed messages.

        Return True if the build failed with a (clean) CompileError, False if
        it succeeded.
        """
        sources = [BuildSource("main", "__main__", main_source)]
        try:
            build.build(
                sources=sources,
                options=options,
                flush_errors=lambda _fn, msgs, _serious: self.flushed.extend(msgs),
            )
        except CompileError:
            return True
        return False

    def data_file(self, options: Options) -> str:
        cache_prefix = os.path.join(self.cache_dir, "%d.%d" % options.python_version)
        return os.path.join(cache_prefix, "dep.data.ff")

    def corrupt_dep_data_file(self, options: Options) -> None:
        data_file = self.data_file(options)
        assert os.path.isfile(data_file)
        st = os.stat(data_file)
        with open(data_file, "wb") as f:
            f.write(b"this is not a valid cache data file")
        # Keep the mtime intact so that the cache metadata still validates.
        os.utime(data_file, (st.st_atime, st.st_mtime))

    def test_corrupt_cache_data_file(self) -> None:
        # Populate the cache.
        options = self.make_options()
        assert not self.run_build(options, "import dep\n")

        # Corrupt the cached data of the dep module.
        self.corrupt_dep_data_file(options)

        # A module that requires the (now corrupt) dep cache to be loaded must
        # produce a clean, actionable error instead of an INTERNAL ERROR.
        self.flushed = []
        failed = self.run_build(options, "import dep\ny: int = dep.x\n")
        assert failed, "build with corrupt cache should fail"
        assert any("corrupt cache" in msg for msg in self.flushed), self.flushed
        assert not any("INTERNAL ERROR" in msg for msg in self.flushed), self.flushed


if __name__ == "__main__":
    unittest.main()
