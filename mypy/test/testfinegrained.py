"""Test cases for fine-grained incremental checking.

Each test cases runs a batch build followed by one or more fine-grained
incremental steps. We verify that each step produces the expected output.

See the comment at the top of test-data/unit/fine-grained.test for more
information.
"""

import os
import re
import shutil

from typing import List, Tuple, Dict, Optional, Set

from mypy import build
from mypy.build import BuildManager, BuildSource, Graph
from mypy.errors import Errors, CompileError
from mypy.nodes import Node, MypyFile, SymbolTable, SymbolTableNode, TypeInfo, Expression
from mypy.options import Options
from mypy.server.astmerge import merge_asts
from mypy.server.subexpr import get_subexpressions
from mypy.server.update import FineGrainedBuildManager
from mypy.strconv import StrConv, indent
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite, UpdateFile
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.testtypegen import ignore_node
from mypy.types import TypeStrVisitor, Type
from mypy.util import short_type


class FineGrainedSuite(DataSuite):
    files = [
        'fine-grained.test',
        'fine-grained-cycles.test',
        'fine-grained-blockers.test',
        'fine-grained-modules.test',
    ]
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        main_src = '\n'.join(testcase.input)
        messages, manager, graph = self.build(main_src)

        a = []
        if messages:
            a.extend(normalize_messages(messages))

        fine_grained_manager = FineGrainedBuildManager(manager, graph)

        steps = testcase.find_steps()
        all_triggered = []
        for operations in steps:
            modules = []
            for op in operations:
                if isinstance(op, UpdateFile):
                    # Modify/create file
                    shutil.copy(op.source_path, op.target_path)
                    modules.append((op.module, op.target_path))
                else:
                    # Delete file
                    os.remove(op.path)
                    modules.append((op.module, op.path))
            new_messages = fine_grained_manager.update(modules)
            all_triggered.append(fine_grained_manager.triggered)
            new_messages = normalize_messages(new_messages)

            a.append('==')
            a.extend(new_messages)

        # Normalize paths in test output (for Windows).
        a = [line.replace('\\', '/') for line in a]

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))

        if testcase.triggered:
            assert_string_arrays_equal(
                testcase.triggered,
                self.format_triggered(all_triggered),
                'Invalid active triggers ({}, line {})'.format(testcase.file,
                                                               testcase.line))

    def build(self, source: str) -> Tuple[List[str], BuildManager, Graph]:
        options = Options()
        options.incremental = True
        options.use_builtins_fixtures = True
        options.show_traceback = True
        main_path = os.path.join(test_temp_dir, 'main')
        with open(main_path, 'w') as f:
            f.write(source)
        try:
            result = build.build(sources=[BuildSource(main_path, None, None)],
                                 options=options,
                                 alt_lib_path=test_temp_dir)
        except CompileError as e:
            # TODO: We need a manager and a graph in this case as well
            assert False, str('\n'.join(e.messages))
            return e.messages, None, None
        return result.errors, result.manager, result.graph

    def format_triggered(self, triggered: List[List[str]]) -> List[str]:
        result = []
        for n, triggers in enumerate(triggered):
            filtered = [trigger for trigger in triggers
                        if not trigger.endswith('__>')]
            filtered = sorted(filtered)
            result.append(('%d: %s' % (n + 2, ', '.join(filtered))).strip())
        return result


def normalize_messages(messages: List[str]) -> List[str]:
    return [re.sub('^tmp' + re.escape(os.sep), '', message)
            for message in messages]
