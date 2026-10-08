from __future__ import annotations

import os
import sys
import tempfile
import unittest

from mypy.metastore import SqliteMetadataStore


@unittest.skipIf(
    sys.platform == "win32",
    "POSIX chmod semantics: os.chmod(dir, 0o555) does not prevent writes on Windows",
)
class TestSqliteMetadataStore(unittest.TestCase):
    def test_init_degrades_to_noop_when_cache_dir_not_creatable(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            os.chmod(parent, 0o555)

            cache_dir = os.path.join(parent, "mypy_cache")

            # Must not raise.
            store = SqliteMetadataStore(cache_dir)

            # Degraded to no-op state, matching the os.devnull short-circuit
            # and FilesystemMetadataStore's behavior on read-only filesystems.
            self.assertEqual(store.dbs, [])
            self.assertFalse(store.write("foo.meta.json", b"{}"))
            with self.assertRaises(FileNotFoundError):
                store.read("foo.meta.json")
            with self.assertRaises(FileNotFoundError):
                store.getmtime("foo.meta.json")
            self.assertEqual(list(store.list_all()), [])
            # commit/close must be safe on an empty store
            store.commit()
            store.close()


if __name__ == "__main__":
    unittest.main()
