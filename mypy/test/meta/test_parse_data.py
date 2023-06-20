"""
A "meta test" which tests the parsing of .test files. This is not meant to become exhaustive
but to ensure we maintain a basic level of ergonomics for mypy contributors.
"""
from mypy.test.helpers import Suite
from mypy.test.meta._pytest import PytestResult, run_type_check_suite


class ParseTestDataSuite(Suite):
    def _run_pytest(self, data_suite: str) -> PytestResult:
        return run_type_check_suite(data_suite, extra_args=[], max_attempts=1)

    def test_parse_invalid_case(self) -> None:
        # Act
        result = self._run_pytest(
            """
            [case abc]
            s: str
            [case foo-XFAIL]
            s: str
            """
        )

        # Assert
        assert "Invalid testcase id 'foo-XFAIL'" in result.stdout

    def test_parse_invalid_section(self) -> None:
        # Act
        result = self._run_pytest(
            """
            [case abc]
            s: str
            [unknownsection]
            abc
            """
        )

        # Assert
        expected_lineno = result.source.splitlines().index("[unknownsection]") + 1
        expected = (
            f".test:{expected_lineno}: Invalid section header [unknownsection] in case 'abc'"
        )
        assert expected in result.stdout
