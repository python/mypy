import os.path

from myunit import Suite
from testhelpers import assert_string_arrays_equal
from testdata import parse_test_cases
from build import build
from errors import CompileError
from testconfig import test_data_prefix, test_temp_dir


# Semantic analyser test cases: dump parse tree

# Semantic analysis test case description files.
semanal_files = ['semanal-basic.test',
                 'semanal-expressions.test',
                 'semanal-classes.test',
                 'semanal-types.test',
                 'semanal-modules.test',
                 'semanal-statements.test',
                 'semanal-interfaces.test']

class SemAnalSuite(Suite):
    def cases(self):
        c = []
        for f in semanal_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_semanal, test_temp_dir)
        return c

def test_semanal(testcase):
    """Perform a semantic analysis test case. The testcase argument contains a
    description of the test case (inputs and output).
    """
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
                    and not os.path.basename(t.path).startswith('_')
                    and not os.path.splitext(
                        os.path.basename(t.path))[0].endswith('_')):
                a += str(t).split('\n')
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(
        testcase.output, a,
        'Invalid semantic analyzer output ({}, line {})'.format(testcase.file,
                                                                testcase.line))

# Semantic analyser error test cases

# Paths to files containing test case descriptions.
semanal_error_files = ['semanal-errors.test']

class SemAnalErrorSuite(Suite):
    def cases(self):
        # Read test cases from test case description files.
        c = []
        for f in semanal_error_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_semanal_error, test_temp_dir)
        return c

def test_semanal_error(testcase):
    """Perform a test case."""
    try:
        src = '\n'.join(testcase.input)
        build(src, 'main', True, test_temp_dir)
        raise AssertionError('No errors reported in {}, line {}'.format(
            testcase.file, testcase.line))
    except CompileError as e:
        # Verify that there was a compile error and that the error messages
        # are equivalent.
        assert_string_arrays_equal(
            testcase.output, normalize_error_messages(e.messages),
            'Invalid compiler output ({}, line {})'.format(testcase.file,
                                                           testcase.line))

def normalize_error_messages(messages):
    """Translate an array of error messages to use / as path separator."""
    a = []
    for m in messages:
        a.append(m.replace(os.sep, '/'))
    return a


# Symbol table export test cases

# Test case descriptions
semanal_symtable_files = ['semanal-symtable.test']
    
class SemAnalSymtableSuite(Suite):
    def cases(self):
        c = []
        for f in semanal_symtable_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  self.run_test, test_temp_dir)
        return c
    
    def run_test(self, testcase):
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            trees, symtable, infos, types = build(src, 'main', True,
                                                  test_temp_dir)
            # The output is the symbol table converted into a string.
            a = []      
            for f in sorted(symtable.keys()):
                if f != 'builtins':
                    a.append('{}:'.format(f))
                    for s in str(symtable[f].names).split('\n'):
                        a.append('  ' + s)
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line))


# Type info export test cases

semanal_typeinfo_files = ['semanal-typeinfo.test']
    
class SemAnalTypeInfoSuite(Suite):
    def cases(self):
        """Test case descriptions"""
        c = []
        for f in semanal_typeinfo_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  self.run_test, test_temp_dir)
        return c
    
    def run_test(self, testcase):
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(testcase.input)
            trees, symtable, infos, types = build(src, 'main', True,
                                                  test_temp_dir)
            # The output is the symbol table converted into a string.
            a = str(infos).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                testcase.file, testcase.line))
