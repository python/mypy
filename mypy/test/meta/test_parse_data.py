"""
A "meta test" which tests the parsing of .test files. This is not meant to become exhaustive
but to ensure we maintain a basic level of ergonomics for mypy contributors.
"""
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

from mypy.test.config import test_data_prefix
from mypy.test.helpers import Suite


class ParseTestDataSuite(Suite):
    def _dedent(self, s: str) -> str:
        return textwrap.dedent(s).lstrip()

    def _run_pytest(self, data_suite: str) -> str:
        p_test_data = Path(test_data_prefix)
        p_root = p_test_data.parent.parent
        p = p_test_data / f"check-meta-{uuid.uuid4()}.test"
        assert not p.exists()
        try:
            p.write_text(data_suite)
            test_nodeid = f"mypy/test/testcheck.py::TypeCheckSuite::{p.name}"
            args = [sys.executable, "-m", "pytest", "-n", "0", "-s", test_nodeid]
            proc = subprocess.run(args, cwd=p_root, capture_output=True, check=False)
            return proc.stdout.decode()
        finally:
            p.unlink()

    def test_parse_invalid_case(self) -> None:
        # Arrange
        data = self._dedent(
            """
            [case abc]
            s: str
            [case foo-XFAIL]
            s: str
            """
        )

        # Act
        actual = self._run_pytest(data)

        # Assert
        assert "Invalid testcase id 'foo-XFAIL'" in actual

    def test_parse_invalid_section(self) -> None:
        # Arrange
        data = self._dedent(
            """
            [case abc]
            s: str
            [unknownsection]
            abc
            """
        )

        # Act
        actual = self._run_pytest(data)

        # Assert
        expected_lineno = data.splitlines().index("[unknownsection]") + 1
        expected = (
            f".test:{expected_lineno}: Invalid section header [unknownsection] in case 'abc'"
        )
        assert expected in actual

    def test_bad_ge_version_check(self) -> None:
        # Arrange
        data = self._dedent(
            """
            [case abc]
            s: str
            [out version>=3.8]
            abc
            """
        )

        # Act
        actual = self._run_pytest(data)

        # Assert
        assert "version>=3.8 always true since minimum runtime version is (3, 8)" in actual

    def test_bad_eq_version_check(self) -> None:
        # Arrange
        data = self._dedent(
            """
            [case abc]
            s: str
            [out version==3.7]
            abc
            """
        )

        # Act
        actual = self._run_pytest(data)

        # Assert
        assert "version==3.7 always false since minimum runtime version is (3, 8)" in actual
