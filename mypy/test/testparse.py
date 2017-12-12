"""Tests for the mypy parser."""
from typing import List

from mypy import defaults
from mypy.myunit import AssertionFailure
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.data import DataDrivenTestCase, DataSuite
from mypy.parse import parse
from mypy.errors import CompileError
from mypy.options import Options


class ParserSuite(DataSuite):
    files = ['parse.test',
             'parse-python2.test']

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_parser(testcase)


def test_parser(testcase: DataDrivenTestCase) -> None:
    """Perform a single parser test case.

    The argument contains the description of the test case.
    """
    options = Options()

    if testcase.file.endswith('python2.test'):
        options.python_version = defaults.PYTHON2_VERSION
    else:
        options.python_version = defaults.PYTHON3_VERSION

    try:
        n = parse(bytes('\n'.join(testcase.input), 'ascii'),
                  fnam='main',
                  errors=None,
                  options=options)
        a = str(n).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(testcase.output, a,
                               'Invalid parser output ({}, line {})'.format(
                                   testcase.file, testcase.line))


# The file name shown in test case output. This is displayed in error
# messages, and must match the file name in the test case descriptions.
INPUT_FILE_NAME = 'file'


class ParseErrorSuite(DataSuite):
    files = ['parse-errors.test']

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_parse_error(testcase)


def test_parse_error(testcase: DataDrivenTestCase) -> None:
    try:
        # Compile temporary file. The test file contains non-ASCII characters.
        parse(bytes('\n'.join(testcase.input), 'utf-8'), INPUT_FILE_NAME, None, Options())
        raise AssertionFailure('No errors reported')
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        assert_string_arrays_equal(
            testcase.output, e.messages,
            'Invalid compiler output ({}, line {})'.format(testcase.file,
                                                           testcase.line))
