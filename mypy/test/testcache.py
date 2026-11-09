"""Tests that unchanged modules are actually loaded from cache on a warm run.

Regression test for #22159: importing a missing submodule of a namespace
package that lives on PYTHONPATH (so it is classified as an installed
package) caused the parent package to be suppressed and then re-added at
the end of the dependency list during graph loading.  State.is_fresh()
compared the dependency lists order-sensitively, so the module was
reported as "inherently stale" on every run and re-checked forever even
though nothing changed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import mypy
from mypy.test.helpers import Suite


class CacheFreshnessSuite(Suite):
    def test_warm_run_reads_cache_for_missing_submodule_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Layout and source from issue #22159: a missing submodule of a
            # namespace package (no __init__.py at the ns level) reachable via
            # PYTHONPATH; the extra "os" import is part of the reported repro.
            (tmp_path / "a.py").write_text(
                "import ns.missing\nimport os\n\ny = os.environ\n", encoding="utf-8"
            )
            (tmp_path / "b.py").write_text("import ns.sub\n", encoding="utf-8")
            (tmp_path / "e.py").write_text("import b\n", encoding="utf-8")
            (tmp_path / "site" / "ns" / "sub").mkdir(parents=True)
            (tmp_path / "site" / "ns" / "sub" / "__init__.py").write_text("", encoding="utf-8")
            (tmp_path / "site" / "ns" / "sub" / "py.typed").write_text("", encoding="utf-8")

            env = os.environ.copy()
            # Make the mypy package importable for "python -m mypy" and put
            # the namespace package on PYTHONPATH (an "installed" location).
            env["PYTHONPATH"] = os.pathsep.join(
                [os.path.dirname(os.path.abspath(mypy.__path__[0])), str(tmp_path / "site")]
            )
            cache_dir = tmp_path / ".mypy_cache"

            def run() -> subprocess.CompletedProcess[str]:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "mypy",
                        "-v",
                        "--cache-dir",
                        str(cache_dir),
                        "a.py",
                        "e.py",
                    ],
                    cwd=tmp_path,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                # Exit status 1 just means the missing-import errors were reported.
                assert proc.returncode in (0, 1), proc.stderr
                return proc

            # Cold run: everything is analyzed and written to the cache.
            first = run()
            assert "Scheduling SCC singleton (a) as inherently stale" in first.stderr

            # Warm run: nothing changed, so nothing may be scheduled as stale
            # and the errors must be replayed from the cache unchanged.
            second = run()
            assert "as inherently stale" not in second.stderr, second.stderr
            assert second.stdout == first.stdout

            # A third run must stay clean as well (no cache flip-flopping).
            third = run()
            assert "as inherently stale" not in third.stderr, third.stderr
            assert third.stdout == first.stdout
