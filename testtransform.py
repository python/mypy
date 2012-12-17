import os
import os.path
import shutil

from build import build
from myunit import Suite
from testhelpers import assert_string_arrays_equal_wildcards
from testdata import parse_test_cases
from testconfig import test_data_prefix, test_temp_dir
from testoutput import remove_prefix
from transform import DyncheckTransformVisitor
from pprinter import PrettyPrintVisitor
from errors import CompileError


# The std module stub used during transformation in test cases (note that
# evaluation uses the full std module).
TRANSFORM_STD_MODULE = 'fixtures/transform.py'


class DyncheckTransformSuite(Suite):
    test_case_files = ['dyncheck-trans-basic.test', 'dyncheck-trans-generics.test', 'dyncheck-trans-generic-inheritance.test']
    
    def cases(self):
        c = []
        for f in self.test_case_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f), std_wrapper(test_transform, os.path.join(test_data_prefix, TRANSFORM_STD_MODULE)), test_temp_dir, True)
        return c


# Perform a runtime checking transformation test case.
def test_transform(testcase):
    any a
    expected = remove_comment_lines(testcase.output)
    try:
        # Construct input as a single single.
        src = '\n'.join(testcase.input)
        # Parse and type check the input program.
        trees, symtable, infos, types = build(src, 'main', False, test_temp_dir, True)
        a = []
        first = True
        # Transform each file separately.
        for t in trees:
            # Skip the std module and files with '-skip.' in the path.
            if not t.path.endswith('/std.alo') and '-skip.' not in t.path:
                if not first:
                    # Display path for files other than the first.
                    a.append('{}:'.format(remove_prefix(t.path, test_temp_dir)))
                
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
    assert_string_arrays_equal_wildcards(expected, a, 'Invalid source code output ({}, line {})'.format(testcase.file, testcase.line))


# Return a copy of array with comment lines starting with '--' (but not with
# '---') removed.
def remove_comment_lines(a):
    r = []
    for s in a:
        if s.strip().startswith('--') and not s.strip().startswith('---'):
            pass
        else:
            r.append(s)
    return r


# Decorate a function that implements a data-driven test case to copy an
# alternative std module implementation in place before performing the test
# case. Clean up after executing the test case.
def std_wrapper(func, path):
    return lambda testcase: perform_test(func, path, testcase)


def perform_test(func, path, testcase):        
    dir = os.path.join(test_temp_dir, 'std')
    new_dir = not os.path.isdir(dir)
    if new_dir:
        os.makedirs(dir)
    try:
        if new_dir:
            shutil.copyfile(path, os.path.join(dir, 'std.alo'))
        func(testcase)
    finally:
        # Note that if the test case used a custom std module, the std
        # directory might be handled by the test case (setUp and tearDown).
        # Therefore only remove the directory if we created it ourselves.
        if new_dir:
            shutil.rmtree(dir)
