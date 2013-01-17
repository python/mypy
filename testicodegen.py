"""Test cases for icode generation."""

import os.path
import re
import sys

import icode
from build import build
from myunit import Suite, run_test
from testhelpers import assert_string_arrays_equal_wildcards
from testdata import parse_test_cases
from testconfig import test_data_prefix, test_temp_dir
from testoutput import remove_prefix
from testtransform import builtins_wrapper, remove_comment_lines
from transform import DyncheckTransformVisitor
from errors import CompileError


# The builtins stub used during icode generation test cases.
ICODE_GEN_BUILTINS = 'fixtures/icodegen.py'


class IcodeGenerationSuite(Suite):
    test_case_files = ['icode-basic.test']
    
    def cases(self):
        c = []
        for f in self.test_case_files:
            c += parse_test_cases(
                os.path.join(test_data_prefix, f),
                builtins_wrapper(test_transform,
                                 os.path.join(test_data_prefix,
                                              ICODE_GEN_BUILTINS)),
                test_temp_dir, True)
        return c


def test_transform(testcase):
    """Perform a runtime checking transformation test case."""
    expected = remove_comment_lines(testcase.output)

    func_name = get_func_name(expected)

    builder = icode.IcodeBuilder()
    
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
        # Transform each file separately.
        for t in trees:
            # Skip the builtins module and files with '_skip.' in the path.
            if not t.path.endswith('/builtins.py') and '_skip.' not in t.path:
                # Transform parse tree and produce pretty-printed output.
                transform = DyncheckTransformVisitor(types, symtable, True)
                t.accept(transform)
                t.accept(builder)

        for fn in [func_name]:
            a.append('def {}():'.format(fn))
            code = icode.render(builder.generated[fn])
            a.extend(code)
    except CompileError as e:
        a = e.messages
    assert_string_arrays_equal_wildcards(
        expected, a,
        'Invalid source code output ({}, line {})'.format(testcase.file,
                                                          testcase.line))


def get_func_name(expected):
    m = re.match(r'def ([_a-zA-Z]+)', expected[0])
    return m.group(1)


if __name__ == '__main__':
    run_test(IcodeGenerationSuite(), sys.argv[1:])
