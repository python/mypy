import os.path

from myunit import Suite, AssertionFailure
from testhelpers import assert_string_arrays_equal
from testdata import parse_test_cases
import testconfig
from parse import parse
from errors import CompileError


class ParserSuite(Suite):
    def cases(self):
        # The test case descriptions are stored in an external file.
        return parse_test_cases(
            os.path.join(testconfig.test_data_prefix, 'parse.test'),
            test_parser)


def test_parser(testcase):
    """Perform a single parser test case. The argument contains the description
    of the test case.
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
INPUT_FILE_NAME = 'file.alo'


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
