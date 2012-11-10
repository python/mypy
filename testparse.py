import os.path
from unittest import Suite
from test.helpers import assert_string_arrays_equal
from test.testdata import parse_test_cases
from test import config
from parse import parse
from errors import CompileError


class ParserSuite(Suite):
    def cases(self):
        # The test case descriptions are stored in an external file.
        return parse_test_cases(
            os.path.join(config.test_data_prefix, 'parse.test'), test_parser)


# Perform a single parser test case. The argument contains the description
# of the test case.
def test_parser(testcase):
    any a
    try:
        n = parse('\n'.join(testcase.input))
        a = str(n).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(testcase.output, a,
                               'Invalid parser output ({}, line {})'.format(
                                   testcase.file, testcase.line))
