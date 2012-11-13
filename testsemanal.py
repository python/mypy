import os.path
from unittest import Suite
from testhelpers import assert_string_arrays_equal
from testdata import parse_test_cases
from build import build
from os.path import basename, splitext
from errors import CompileError
from testconfig import test_data_prefix, test_temp_dir


# Semantic analysis test case description files.
sem_anal_files = ['semanal-basic.test',
                  'semanal-expressions.test',
                  'semanal-classes.test',
                  'semanal-types.test',
                  'semanal-modules.test',
                  'semanal-statements.test',
                  'semanal-interfaces.test']


class SemAnalSuite(Suite):
    def cases(self):
        c = []
        for f in sem_anal_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_sem_anal, test_temp_dir)
        return c


# Perform a semantic analysis test case. The testcase argument contains a
# description of the test case (inputs and output).
def test_sem_anal(testcase):
    any a
    try:
        src = '\n'.join(testcase.input)
        trees, symtable, infos, types = build(src, 'main', True, test_temp_dir)
        a = []
        # Include string representations of the source files in the actual
        # output.
        for t in trees:
            # Omit the builtins module and files with a special marker in the
            # path.
            # TODO the test is not reliable
            if (not t.path.endswith(os.sep + 'builtins.py')
                    and not basename(t.path).startswith('_')
                    and not splitext(basename(t.path))[0].endswith('_')):
                a += str(t).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, a,
        'Invalid semantic analyzer output ({}, line {})'.format(testcase.file,
                                                                testcase.line))
