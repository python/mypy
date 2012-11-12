import os.path
from unittest import Suite, AssertionFailure
from testdata import parse_test_cases
from testhelpers import assert_string_arrays_equal
from testconfig import test_data_prefix
from parse import parse
from errors import CompileError


# The file name shown in test case output. This is displayed in error
# messages, and must match the file name in the test case descriptions.
INPUT_FILE_NAME = 'file.alo'


class ParseErrorSuite(Suite):
    def cases(self):
        # Test case descriptions are in an external file.
        return parse_test_cases(os.path.join(test_data_prefix,
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
