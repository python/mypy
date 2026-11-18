from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest import TestCase

from mypy.test.data import DataDrivenTestCase, DataFileFix
from mypy.test.update_data import _iter_fixes


class UpdateDataSuite(TestCase):
    def test_preserves_escaped_section_header_like_file_line(self) -> None:
        testcase = cast(
            DataDrivenTestCase,
            SimpleNamespace(
                data="[file foo.ini]\n\\[mypy]\npython_version = 3.14\n", line=1, name="testCase"
            ),
        )

        fixes = [fix for fix in _iter_fixes(testcase, [], incremental_step=1) if fix.lines]

        assert fixes == [
            DataFileFix(lineno=3, end_lineno=5, lines=["\\[mypy]", "python_version = 3.14"])
        ]

    def test_escapes_updated_source_line_that_looks_like_section_header(self) -> None:
        testcase = cast(
            DataDrivenTestCase, SimpleNamespace(data="\\[1] + 1\n", line=1, name="testCase")
        )
        actual = ["main:1: error: Something sus  [sus]"]

        fixes = list(_iter_fixes(testcase, actual, incremental_step=1))

        assert fixes == [
            DataFileFix(lineno=2, end_lineno=3, lines=["\\[1] + 1  # E: Something sus  [sus]"])
        ]
