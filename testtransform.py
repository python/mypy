import os
import os.path
import shutil
import sys

from build import build
from myunit import Suite, run_test
from testhelpers import assert_string_arrays_equal_wildcards
from testdata import parse_test_cases
from testconfig import test_data_prefix, test_temp_dir
from testoutput import remove_prefix
from transform import DyncheckTransformVisitor
from pprinter import PrettyPrintVisitor
from errors import CompileError


# The builtins stub used during transformation in test cases.
TRANSFORM_BUILTINS = 'fixtures/transform.py'


class DyncheckTransformSuite(Suite):
    test_case_files = ['dyncheck-trans-basic.test',
                       'dyncheck-trans-generics.test',
                       'dyncheck-trans-generic-inheritance.test']
    
    def cases(self):
        c = []
        for f in self.test_case_files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                builtins_wrapper(test_transform,
                                 os.path.join(test_data_prefix,
                                              TRANSFORM_BUILTINS)),
                test_temp_dir, True)
        return c


def test_transform(testcase):
    """Perform a runtime checking transformation test case."""
    expected = remove_comment_lines(testcase.output)
    try:
        # Construct input as a single single.
        src = '\n'.join(testcase.input)
        # Parse and type check the input program.
        trees, symtable, infos, types = build(program_text=src,
                                              program_file_name='main',
                                              use_test_builtins=False,
                                              alt_lib_path=test_temp_dir,
                                              do_type_check=True)
        a = []
        first = True
        # Transform each file separately.
        for t in trees:
            # Skip the builtins module and files with '_skip.' in the path.
            if not t.path.endswith('/builtins.py') and '_skip.' not in t.path:
                if not first:
                    # Display path for files other than the first.
                    a.append('{}:'.format(remove_prefix(t.path,
                                                        test_temp_dir)))
                
                # Transform parse tree and produce pretty-printed output.
                v = DyncheckTransformVisitor(types, symtable, True)
                t.accept(v)
                # Pretty print the transformed tree.
                v2 = PrettyPrintVisitor()
                t.accept(v2)
                s = v2.output()
                if s != '':
                    a += s.split('\n')
            first = False
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal_wildcards(
        expected, a,
        'Invalid source code output ({}, line {})'.format(testcase.file,
                                                          testcase.line))


def remove_comment_lines(a):
    """Return a copy of array with comments removed.

    Lines starting with '--' (but not with '---') are removed.
    """
    r = []
    for s in a:
        if s.strip().startswith('--') and not s.strip().startswith('---'):
            pass
        else:
            r.append(s)
    return r


def builtins_wrapper(func, path):
    """Decorate a function that implements a data-driven test case to copy an
    alternative builtins module implementation in place before performing the
    test case. Clean up after executing the test case.
    """
    return lambda testcase: perform_test(func, path, testcase)


def perform_test(func, path, testcase):
    for path, _ in testcase.files:
        if os.path.basename(path) == 'builtins.py':
            default_builtins = False
            break
    else:
        # Use default builtins.
        builtins = os.path.join(test_temp_dir, 'builtins.py')
        shutil.copyfile(path, builtins)
        default_builtins = True

    # Actually peform the test case.
    func(testcase)
    
    if default_builtins:
        # Clean up.
        os.remove(builtins)


if __name__ == '__main__':
    run_test(DyncheckTransformSuite(), sys.argv[1:])
