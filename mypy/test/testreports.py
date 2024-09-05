"""Test cases for reports generated by mypy."""

from __future__ import annotations

import textwrap
import tempfile
from mypy.report import CoberturaPackage, get_line_rate, CoberturaXmlReporter, Reports
from mypy.test.helpers import Suite, assert_equal

try:
    import lxml  # type: ignore[import-untyped]
except ImportError:
    lxml = None

import pytest


class CoberturaReportSuite(Suite):
    @pytest.mark.skipif(lxml is None, reason="Cannot import lxml. Is it installed?")
    def test_get_line_rate(self) -> None:
        assert_equal("1.0", get_line_rate(0, 0))
        assert_equal("0.3333", get_line_rate(1, 3))

    @pytest.mark.skipif(lxml is None, reason="Cannot import lxml. Is it installed?")
    def test_as_xml(self) -> None:
        import lxml.etree as etree  # type: ignore[import-untyped]

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
        with tempfile.TemporaryDirectory() as tempdir:
            reports = Reports(data_dir=tempdir, report_dirs={"dummy_report": tempdir})

        cobertura_reporter = CoberturaXmlReporter(reports, ".")
        cobertura_reporter.root_package = cobertura_package
        cobertura_reporter.on_finish()

        # Convert the XML document to a string
        xml_str = etree.tostring(cobertura_reporter.doc, pretty_print=True).decode("utf-8")

        # Check that the required attributes are present
        assert f'lines-covered="{cobertura_package.covered_lines}"' in xml_str
        assert f'lines-valid="{cobertura_package.total_lines}"' in xml_str

