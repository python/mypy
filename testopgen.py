"""Test Alore type operation generation (OBSOLETE)."""

import os.path
import sys

from build import build
from myunit import Suite, run_test
from testconfig import test_data_prefix, test_temp_dir
from testhelpers import assert_string_arrays_equal_wildcards
from testdata import parse_test_cases
from testoutput import remove_prefix
from testtransform import (
    remove_comment_lines, builtins_wrapper, TRANSFORM_BUILTINS
)
from transform import DyncheckTransformVisitor
from opgen import generate_runtime_support
from errors import CompileError


class DyncheckOpGenSuite(Suite):
    test_case_files = ['dyncheck-opgen.test']
    
    def cases(self):
        c = []
        for f in self.test_case_files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                builtins_wrapper(test_op_gen,
                                 os.path.join(test_data_prefix,
                                              TRANSFORM_BUILTINS)),
                test_temp_dir, True)
        return c


def test_op_gen(testcase):
    """Perform a type operation support data and code genereation test case."""
    any a
    expected = remove_comment_lines(testcase.output)
    try:
        src = '\n'.join(testcase.input)
        # Parse and type check the input program.
        trees, symtable, infos, types = build(src, 'main', False,
                                              test_temp_dir, True)
        a = []
        first = True
        # Transform each file separately.
        for t in trees:
            # Skip the builtins module and files with '_skip.' in the path.
            if not t.path.endswith('/builtins.py') and '_skip.' not in t.path:
                if not first:
                    # Display path for files other than the first.
                    a.append('{}:'.format(
                        remove_prefix(t.path, test_temp_dir)))
                
                # Transform parse tree and produce the code for operations.
                # Note that currently we generate this for each file
                # separately; this needs to be fixed eventually.
                v = DyncheckTransformVisitor(types, symtable, True)
                t.accept(v)
                s = generate_runtime_support(t)
                if s != '':
                    a += s.split('\n')
            first = False
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal_wildcards(
        expected, a,
        'Invalid source code output ({}, line {})'.format(testcase.file,
                                                          testcase.line))

    
if __name__ == '__main__':
    run_test(DyncheckOpGenSuite(), sys.argv[1:])
