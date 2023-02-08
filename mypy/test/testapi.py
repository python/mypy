from __future__ import annotations

import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp

import mypy.api
from mypy.test.helpers import Suite


class APISuite(Suite):
    def setUp(self) -> None:
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        sys.stdout = self.stdout = StringIO()
        sys.stderr = self.stderr = StringIO()
        with NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"x: int = 5\n")
        self.tmp_path = Path(tmp.name)
        self.tmp_cache_dir = Path(mkdtemp())

    def tearDown(self) -> None:
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        assert self.stdout.getvalue() == ""
        assert self.stderr.getvalue() == ""
        self.tmp_path.unlink()
        shutil.rmtree(self.tmp_cache_dir)

    def test_capture_bad_opt(self) -> None:
        """stderr should be captured when a bad option is passed."""
        _, stderr, _ = mypy.api.run(["--some-bad-option"])
        assert isinstance(stderr, str)
        assert stderr != ""

    def test_capture_empty(self) -> None:
        """stderr should be captured when a bad option is passed."""
        _, stderr, _ = mypy.api.run([])
        assert isinstance(stderr, str)
        assert stderr != ""

    def test_capture_help(self) -> None:
        """stdout should be captured when --help is passed."""
        stdout, _, _ = mypy.api.run(["--help"])
        assert isinstance(stdout, str)
        assert stdout != ""

    def test_capture_version(self) -> None:
        """stdout should be captured when --version is passed."""
        stdout, _, _ = mypy.api.run(["--version"])
        assert isinstance(stdout, str)
        assert stdout != ""

    def test_default_encoding_warnings(self) -> None:
        """No EncodingWarnings should be emitted."""
        for empty_cache in [True, False]:
            res = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import mypy.api;"
                    "mypy.api.run("
                    f"['--cache-dir', '{self.tmp_cache_dir}', '{self.tmp_path}']"
                    ")",
                ],
                capture_output=True,
                env={"PYTHONWARNDEFAULTENCODING": "1"},
            )
            assert b"EncodingWarning" not in res.stderr
