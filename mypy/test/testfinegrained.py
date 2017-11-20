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
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.testtypegen import ignore_node
from mypy.types import TypeStrVisitor, Type
from mypy.util import short_type


files = [
    'fine-grained.test',
    'fine-grained-cycles.test',
    'fine-grained-blockers.test',
    'fine-grained-modules.test',
]


class FineGrainedSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        main_src = '\n'.join(testcase.input)
        messages, manager, graph = self.build(main_src)

        a = []
        if messages:
            a.extend(normalize_messages(messages))

        fine_grained_manager = FineGrainedBuildManager(manager, graph)

        steps = find_steps(testcase.deleted_paths)
        for changed_paths in steps:
            modules = []
            for module, path in changed_paths:
                new_path = re.sub(r'\.[0-9]+$', '', path)
                if new_path != path:
                    # Modify/create file
                    shutil.copy(path, new_path)
                    modules.append((module, new_path))
                else:
                    # Delete file
                    modules.append((module, path))
                    os.remove(path)
            new_messages = fine_grained_manager.update(modules)
            new_messages = normalize_messages(new_messages)

            a.append('==')
            a.extend(new_messages)

        # Normalize paths in test output (for Windows).
        a = [line.replace('\\', '/') for line in a]

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
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


def find_steps(deleted: Dict[int, Set[str]]) -> List[List[Tuple[str, str]]]:
    """Return a list of build step representations.

    Each build step is a list of (module id, path) tuples, and each
    path of a modified file is of form 'dir/mod.py.2' (where 2 is the step number);
    if a path has no .N suffix, it will be deleted.
    """
    steps = {}  # type: Dict[int, List[Tuple[str, str]]]
    for dn, dirs, files in os.walk(test_temp_dir):
        for filename in files:
            m = re.match(r'.*\.([0-9]+)$', filename)
            if m:
                num = int(m.group(1))
                assert num >= 2
                name = re.sub(r'\.py.*', '', filename)
                module = module_from_path(os.path.join(dn, name))
                path = os.path.join(dn, filename)
                steps.setdefault(num, []).append((module, path))
    for num, paths in deleted.items():
        assert num >= 2
        for path in paths:
            module = module_from_path(path)
            steps.setdefault(num, []).append((module, path))
    print(steps)
    max_step = max(steps)
    return [steps[num] for num in range(2, max_step + 1)]


def module_from_path(path: str) -> str:
    path = re.sub(r'\.py$', '', path)
    parts = path.split(os.sep)
    assert parts[0] == test_temp_dir
    del parts[0]
    module = '.'.join(parts)
    module = re.sub(r'\.__init__$', '', module)
    return module


def normalize_messages(messages: List[str]) -> List[str]:
    return [re.sub('^tmp' + re.escape(os.sep), '', message)
            for message in messages]
