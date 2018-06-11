"""Test cases for IR generation."""

import os.path
import re
import shutil
from typing import List

from mypy import build
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options
from mypy import experiments

from mypyc import genops
from mypyc.ops import format_func

from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS, use_custom_builtins, MypycDataSuite, assert_test_output
)

files = [
    'genops-basic.test',
    'genops-lists.test',
    'genops-dict.test',
    'genops-statements.test',
    'genops-classes.test',
    'genops-optional.test',
    'genops-tuple.test',
    'genops-any.test',
    'genops-generics.test',
]


class TestGenOps(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a runtime checking transformation test case."""
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)

            program_text = '\n'.join(testcase.input)

            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            options.strict_optional = True
            options.python_version = (3, 6)

            source = build.BuildSource('main', '__main__', program_text)
            try:
                # Construct input as a single single.
                # Parse and type check the input program.
                result = build.build(sources=[source],
                                     options=options,
                                     alt_lib_path=test_temp_dir)
            except CompileError as e:
                actual = e.messages
            else:
                if result.errors:
                    actual = result.errors
                else:
                    module = genops.build_ir(result.files['__main__'], result.types)
                    actual = []
                    for fn in module.functions:
                        actual.extend(format_func(fn))

            assert_test_output(testcase, actual, 'Invalid source code output',
                               expected_output)


# TODO: Use these to filter things?
def get_func_names(expected: List[str]) -> List[str]:
    res = []
    for s in expected:
        m = re.match(r'def ([_a-zA-Z0-9.*$]+)\(', s)
        if m:
            res.append(m.group(1))
    return res


def remove_comment_lines(a: List[str]) -> List[str]:
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
