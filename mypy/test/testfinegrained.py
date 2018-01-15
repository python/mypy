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
from mypy.test.data import (
    parse_test_cases, DataDrivenTestCase, DataSuite, UpdateFile, module_from_path
)
from mypy.test.helpers import assert_string_arrays_equal, parse_options
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
        sources_override = self.parse_sources(main_src)
        messages, manager, graph = self.build(main_src, testcase, sources_override)

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
            if sources_override is not None:
                modules = [(module, path)
                           for module, path in sources_override
                           if any(m == module for m, _ in modules)]
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

    def build(self,
              source: str,
              testcase: DataDrivenTestCase,
              sources_override: Optional[List[Tuple[str, str]]]) -> Tuple[List[str],
                                                                          BuildManager,
                                                                          Graph]:
        # This handles things like '# flags: --foo'.
        options = parse_options(source, testcase, incremental_step=1)
        options.incremental = True
        options.use_builtins_fixtures = True
        options.show_traceback = True
        main_path = os.path.join(test_temp_dir, 'main')
        with open(main_path, 'w') as f:
            f.write(source)
        if sources_override is not None:
            sources = [BuildSource(path, module, None)
                       for module, path in sources_override]
        else:
            sources = [BuildSource(main_path, None, None)]
        try:
            result = build.build(sources=sources,
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

    def parse_sources(self, program_text: str) -> Optional[List[Tuple[str, str]]]:
        """Return target (module, path) tuples for a test case, if not using the defaults.

        These are defined through a comment like '# cmd: main a.py' in the test case
        description.
        """
        # TODO: Support defining separately for each incremental step.
        m = re.search('# cmd: mypy ([a-zA-Z0-9_./ ]+)$', program_text, flags=re.MULTILINE)
        if m:
            # The test case wants to use a non-default set of files.
            paths = m.group(1).strip().split()
            result = []
            for path in paths:
                path = os.path.join(test_temp_dir, path)
                module = module_from_path(path)
                if module == 'main':
                    module = '__main__'
                result.append((module, path))
            return result
        return None


def normalize_messages(messages: List[str]) -> List[str]:
    return [re.sub('^tmp' + re.escape(os.sep), '', message)
            for message in messages]
