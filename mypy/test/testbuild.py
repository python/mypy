"""Tests for incremental build behavior."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mypy.test.helpers import Suite


class BuildSuite(Suite):
    def test_reuses_cache_when_dependency_order_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_path = Path(temporary_directory)
            site = tmp_path / "site"
            typed_subpackage = site / "ns" / "sub"
            typed_subpackage.mkdir(parents=True)
            (typed_subpackage / "__init__.py").write_text("", encoding="utf8")
            (typed_subpackage / "py.typed").touch()

            (tmp_path / "a.py").write_text(
                "import ns.missing\nimport os\n\ny = os.environ\n", encoding="utf8"
            )
            (tmp_path / "b.py").write_text("import ns.sub\n", encoding="utf8")
            (tmp_path / "e.py").write_text("import b\n", encoding="utf8")

            env = os.environ.copy()
            env.pop("MYPY_CACHE_DIR", None)
            env["PYTHONPATH"] = str(site)
            command = [
                sys.executable,
                "-m",
                "mypy",
                "-v",
                f"--cache-dir={tmp_path / 'cache'}",
                "a.py",
                "e.py",
            ]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
                )

            first_run = run()
            second_run = run()

            stale_log = "Scheduling SCC singleton (a) as inherently stale"
            first_output = first_run.stdout + first_run.stderr
            second_output = second_run.stdout + second_run.stderr
            assert first_run.returncode == second_run.returncode == 1
            assert stale_log in first_output
            assert stale_log not in second_output
