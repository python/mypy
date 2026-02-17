"""Tests for misc/diff-cache.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

_DIFF_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "misc",
    "diff-cache.py",
)


class DiffCacheIntegrationTests(unittest.TestCase):
    """Integration test: run mypy twice with different sources, then diff the caches."""

    def test_diff_cache_produces_valid_json(self) -> None:
        # Use a single source directory with two cache directories so that
        # source paths in the cache metadata are identical between runs.
        # Only b.py changes between the two runs.
        src_dir = tempfile.mkdtemp()
        output_file = os.path.join(tempfile.mkdtemp(), "diff.json")
        try:
            cache1 = os.path.join(src_dir, "cache1")
            cache2 = os.path.join(src_dir, "cache2")

            # Write sources and run mypy for cache1 (using sqlite cache)
            with open(os.path.join(src_dir, "a.py"), "w") as f:
                f.write("x: int = 1\n")
            with open(os.path.join(src_dir, "b.py"), "w") as f:
                f.write("import a\ndef foo() -> int:\n    return 1\n")
            result = subprocess.run(
                [sys.executable, "-m", "mypy", "--sqlite-cache", "--cache-fine-grained",
                 "--cache-dir", cache1, "b.py"],
                cwd=src_dir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"mypy run 1 failed: {result.stderr}"

            # Sleep so that mtimes will be different between runs
            time.sleep(1)

            # Touch a.py to change its mtime without modifying content
            os.utime(os.path.join(src_dir, "a.py"))

            # Modify b.py and add a new c.py, then run mypy for cache2
            with open(os.path.join(src_dir, "b.py"), "w") as f:
                f.write("import a\ndef foo() -> str:\n    return 'hello'\n")
            with open(os.path.join(src_dir, "c.py"), "w") as f:
                f.write("import a\ny: str = 'world'\n")
            result = subprocess.run(
                [sys.executable, "-m", "mypy", "--sqlite-cache", "--cache-fine-grained",
                 "--cache-dir", cache2, "b.py", "c.py"],
                cwd=src_dir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"mypy run 2 failed: {result.stderr}"

            # Find the Python version subdirectory (e.g. "3.14")
            subdirs = [
                e for e in os.listdir(cache1)
                if os.path.isdir(os.path.join(cache1, e)) and e[0].isdigit()
            ]
            assert len(subdirs) == 1, f"Expected one version subdir, got {subdirs}"
            ver = subdirs[0]

            # Run diff-cache.py with --sqlite
            result = subprocess.run(
                [sys.executable, _DIFF_CACHE_PATH, "--sqlite",
                 os.path.join(cache1, ver), os.path.join(cache2, ver), output_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"diff-cache.py failed: {result.stderr}"

            # Verify the output is valid JSON
            with open(output_file) as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert len(data) > 0, "Expected non-empty diff"

            # Only modified or new files should appear in the diff.
            # b.py changed and c.py is new, so both should be present.
            # a.py did not change, so no a.* keys should appear.
            keys = set(data.keys())
            b_keys = {k for k in keys if "/b." in k or k.startswith("b.")}
            c_keys = {k for k in keys if "/c." in k or k.startswith("c.")}
            a_keys = {k for k in keys if "/a." in k or k.startswith("a.")}
            assert len(a_keys) == 0, f"Unexpected a.* entries in diff: {a_keys}"
            assert len(b_keys) == 2, f"Expected 2 b.* entries in diff, got: {b_keys}"
            assert len(c_keys) == 3, f"Expected 3 c.* entries in diff, got: {c_keys}"
        finally:
            shutil.rmtree(src_dir, ignore_errors=True)
            shutil.rmtree(os.path.dirname(output_file), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
