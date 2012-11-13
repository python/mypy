import os.path
from unittest import Suite, AssertionFailure
from test.helpers import parse_test_cases, assert_string_arrays_equal
from build import build
from errors import CompileError
from os import separator


# Paths to files containing test case descriptions.
sem_anal_error_files = ['semanal-errors.test']


class SemAnalErrorSuite(Suite):
    def cases(self):
        # Read test cases from test case description files.
        c = []
        for f in sem_anal_error_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f), test_sem_anal_error, test_temp_dir)
        return c


# Perform a test case.
def test_sem_anal_error(testcase):
    any a
    try:
        src = '\n'.join(testcase.input)
        build(src, 'main', True, test_temp_dir)
        raise AssertionFailure('No errors reported in {}, line {}'.format(testcase.file, testcase.line))
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        assert_string_arrays_equal(testcase.output, normalize_error_messages(e.messages), 'Invalid compiler output ({}, line {})'.format(testcase.file, testcase.line))


# Translate an array of error messages to use / as path separator.
def normalize_error_messages(messages):
    a = []
    for m in messages:
        a.append(m.replace(separator, '/'))
    return a
