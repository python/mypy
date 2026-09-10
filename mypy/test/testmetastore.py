"""Unit tests for metadata stores."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from mypy import build
from mypy.metastore import FilesystemMetadataStore
from mypy.options import Options


class TestMetadataStore(unittest.TestCase):
    @unittest.skipUnless(
        build.__file__.endswith(".py"), "mock patching is unreliable for compiled mypy"
    )
    def test_create_metastore_falls_back_to_filesystem_when_sqlite_missing(self) -> None:
        options = Options()
        options.sqlite_cache = True

        with tempfile.TemporaryDirectory() as tmpdir:
            options.cache_dir = tmpdir
            with patch(
                "mypy.build.SqliteMetadataStore",
                side_effect=ModuleNotFoundError("No module named '_sqlite3'"),
            ):
                store = build.create_metastore(options, parallel_worker=False)

            try:
                assert isinstance(store, FilesystemMetadataStore)
                assert store.write("example.meta.json", b"{}")
                assert store.read("example.meta.json") == b"{}"
            finally:
                store.close()
