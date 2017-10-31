"""Test cases for generating node-level dependencies (for fine-grained incremental checking)"""

import os
from typing import List, Tuple, Dict, Optional

from mypy import build, defaults
from mypy.build import BuildSource
from mypy.errors import CompileError
from mypy.nodes import MypyFile, Expression
from mypy.options import Options
from mypy.server.deps import get_dependencies
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.types import Type

files = [
    'deps.test',
    'deps-types.test',
    'deps-generics.test',
    'deps-expressions.test',
    'deps-statements.test',
]


class GetDependenciesSuite(DataSuite):

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        src = '\n'.join(testcase.input)
        if testcase.name.endswith('python2'):
            python_version = defaults.PYTHON2_VERSION
        else:
            python_version = defaults.PYTHON3_VERSION
        messages, files, type_map = self.build(src, python_version)
        a = messages
        if files is None or type_map is None:
            if not a:
                a = ['Unknown compile error (likely syntax error in test case or fixture)']
        else:
            deps = get_dependencies(files['__main__'], type_map, python_version)

            for source, targets in sorted(deps.items()):
                line = '%s -> %s' % (source, ', '.join(sorted(targets)))
                # Clean up output a bit
                line = line.replace('__main__', 'm')
                a.append(line)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))

    def build(self,
              source: str,
              python_version: Tuple[int, int]) -> Tuple[List[str],
                                                        Optional[Dict[str, MypyFile]],
                                                        Optional[Dict[Expression, Type]]]:
        options = Options()
        options.use_builtins_fixtures = True
        options.show_traceback = True
        options.cache_dir = os.devnull
        options.python_version = python_version
        try:
            result = build.build(sources=[BuildSource('main', None, source)],
                                 options=options,
                                 alt_lib_path=test_temp_dir)
        except CompileError as e:
            # TODO: Should perhaps not return None here.
            return e.messages, None, None
        return result.errors, result.files, result.types
