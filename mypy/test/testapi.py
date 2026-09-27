from __future__ import annotations

import os
import sys
import tempfile
from io import StringIO

import mypy.api
from mypy.test.helpers import Suite


class APISuite(Suite):
    def setUp(self) -> None:
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        sys.stdout = self.stdout = StringIO()
        sys.stderr = self.stderr = StringIO()

    def tearDown(self) -> None:
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        assert self.stdout.getvalue() == ""
        assert self.stderr.getvalue() == ""

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

    def test_decode_error_is_reported_not_raised(self) -> None:
        """A file that is not valid UTF-8 produces an error, not a crash.

        The native parser reads files as UTF-8 and does not support PEP 263
        'coding' declarations (issue #22055).
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "latin1.py")
            # "s = 'café'" encoded as latin-1: invalid UTF-8 bytes.
            with open(file_path, "wb") as f:
                f.write(b"s = 'caf\xe9'\n")

            stdout, stderr, status = mypy.api.run(["--cache-dir", os.devnull, file_path])
        assert "Cannot decode file" in stderr
        assert "did not contain valid UTF-8" in stderr
        assert "errors prevented further checking" in stdout
        assert status == 2
