"""Test cases for AST diff (used for fine-grained incremental checking)"""

import os
from typing import List, Tuple, Dict, Optional

from mypy import build
from mypy.build import BuildSource
from mypy.errors import CompileError
from mypy.nodes import MypyFile
from mypy.options import Options
from mypy.server.astdiff import compare_symbol_tables
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal


files = [
    'diff.test'
]


class ASTDiffSuite(DataSuite):

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        first_src = '\n'.join(testcase.input)
        files_dict = dict(testcase.files)
        second_src = files_dict['tmp/next.py']

        messages1, files1 = self.build(first_src)
        messages2, files2 = self.build(second_src)

        a = []
        if messages1:
            a.extend(messages1)
        if messages2:
            a.append('== next ==')
            a.extend(messages2)

        assert files1 is not None and files2 is not None, ('cases where CompileError'
                                                           ' occurred should not be run')
        diff = compare_symbol_tables(
            '__main__',
            files1['__main__'].names,
            files2['__main__'].names)
        for trigger in sorted(diff):
            a.append(trigger)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))

    def build(self, source: str) -> Tuple[List[str], Optional[Dict[str, MypyFile]]]:
        options = Options()
        options.use_builtins_fixtures = True
        options.show_traceback = True
        options.cache_dir = os.devnull
        try:
            result = build.build(sources=[BuildSource('main', None, source)],
                                 options=options,
                                 alt_lib_path=test_temp_dir)
        except CompileError as e:
            # TODO: Is it okay to return None?
            return e.messages, None
        return result.errors, result.files
