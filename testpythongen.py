import os.path
from unittest import Suite
from testconfig import test_data_prefix, test_temp_dir
from testdata import parse_test_cases
from testhelpers import assert_string_arrays_equal
from testoutput import fix_path, remove_prefix
from build import build
from pythongen import PythonGenerator
from errors import CompileError


# Files which contain test case descriptions.
python_generation_files = ['pythongen.test']


class PythonGenerationSuite(Suite):
    def cases(self):
        c = []
        for f in python_generation_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f), test_python_generation, test_temp_dir, True)
        return c


# Perform a mypy-to-Python source code transformation test case.
def test_python_generation(testcase):
    any a
    expected = testcase.output
    # By default, assume an identity translation. This is useful for dynamically
    # typed code.
    if expected == []:
        expected = testcase.input
    try:
        src = '\n'.join(testcase.input)
        # Parse and semantically analyze the source program.
        trees, symtable, infos, types = build(src, 'main', True, test_temp_dir)
        a = []
        first = True
        # Produce an output containing the pretty-printed forms (with original
        # formatting) of all the relevant source files.
        for t in trees:
            # Omit the builtins module and files marked for omission.
            if not t.path.endswith(os.sep + 'builtins.py') and '-skip.' not in t.path:
                # Add file name + colon for files other than the first.
                if not first:
                    a.append('{}:'.format(fix_path(remove_prefix(t.path, test_temp_dir))))
                
                v = PythonGenerator()
                t.accept(v)
                s = v.output()
                if s != '':
                    a += s.split('\n')
            first = False
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal(expected, a, 'Invalid source code output ({}, line {})'.format(testcase.file, testcase.line))
