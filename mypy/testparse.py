"""Tests for the mypy parser

Test case descriptions are in files test/data/parse[-errors].test."""

import os.path

import typing

from mypy.myunit import Suite, AssertionFailure, run_test
from mypy.testhelpers import assert_string_arrays_equal
from mypy.testdata import parse_test_cases
from mypy import testconfig
from mypy.parse import parse
from mypy.errors import CompileError


class ParserSuite(Suite):
    def cases(self):
        # The test case descriptions are stored in an external file.
        return parse_test_cases(
            os.path.join(testconfig.test_data_prefix, 'parse.test'),
            test_parser)


def test_parser(testcase):
    """Perform a single parser test case.

    The argument contains the description of the test case.
    """
    
    try:
        n = parse('\n'.join(testcase.input))
        a = str(n).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(testcase.output, a,
                               'Invalid parser output ({}, line {})'.format(
                                   testcase.file, testcase.line))


# The file name shown in test case output. This is displayed in error
# messages, and must match the file name in the test case descriptions.
INPUT_FILE_NAME = 'file'


class ParseErrorSuite(Suite):
    def cases(self):
        # Test case descriptions are in an external file.
        return parse_test_cases(os.path.join(testconfig.test_data_prefix,
                                             'parse-errors.test'),
                                test_parse_error)


def test_parse_error(testcase):
    try:
        # Compile temporary file.
        parse('\n'.join(testcase.input), INPUT_FILE_NAME)
        raise AssertionFailure('No errors reported')
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        assert_string_arrays_equal(
            testcase.output, e.messages,
            'Invalid compiler output ({}, line {})'.format(testcase.file,
                                                           testcase.line))


class CombinedParserSuite(Suite):
    def __init__(self):
        self.test_parse = ParserSuite()
        self.test_parse_errors = ParseErrorSuite()
        super().__init__()


if __name__ == '__main__':
    import sys
    run_test(CombinedParserSuite(), sys.argv[1:])
