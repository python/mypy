"""Test cases for reports generated by mypy."""

from __future__ import annotations

import importlib.util
import textwrap
import types

from mypy.report import CoberturaPackage, get_line_rate
from mypy.test.helpers import Suite, assert_equal

if importlib.util.find_spec("lxml") is None:
    lxml2: types.ModuleType | None = None
else:
    import lxml as lxml2

import pytest


class CoberturaReportSuite(Suite):
    @pytest.mark.skipif(lxml2 is None, reason="Cannot import lxml. Is it installed?")
    def test_get_line_rate(self) -> None:
        assert_equal("1.0", get_line_rate(0, 0))
        assert_equal("0.3333", get_line_rate(1, 3))

    @pytest.mark.skipif(lxml2 is None, reason="Cannot import lxml. Is it installed?")
    def test_as_xml(self) -> None:
        import lxml.etree as etree

        cobertura_package = CoberturaPackage("foobar")
        cobertura_package.covered_lines = 21
        cobertura_package.total_lines = 42

        child_package = CoberturaPackage("raz")
        child_package.covered_lines = 10
        child_package.total_lines = 10
        child_package.classes["class"] = etree.Element("class")

        cobertura_package.packages["raz"] = child_package

        expected_output = textwrap.dedent(
            """\
            <package complexity="1.0" name="foobar" branch-rate="0" line-rate="0.5000">
              <classes/>
              <packages>
                <package complexity="1.0" name="raz" branch-rate="0" line-rate="1.0000">
                  <classes>
                    <class/>
                  </classes>
                </package>
              </packages>
            </package>
        """
        ).encode("ascii")
        assert_equal(
            expected_output, etree.tostring(cobertura_package.as_xml(), pretty_print=True)
        )
