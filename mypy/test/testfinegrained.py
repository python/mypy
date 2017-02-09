"""Test cases for fine-grained incremental checking.

Each test cases runs a batch build followed by one or more fine-grained
incremental steps. We verify that each step produces the expected output.

See the comment at the top of test-data/unit/fine-grained.test for more
information.
"""

import os.path
import re
import shutil
from typing import List, Tuple, Dict

from mypy import build
from mypy.build import BuildManager, BuildSource, Graph
from mypy.errors import Errors, CompileError
from mypy.nodes import Node, MypyFile, SymbolTable, SymbolTableNode, TypeInfo, Expression
from mypy.options import Options
from mypy.server.astmerge import merge_asts
from mypy.server.subexpr import get_subexpressions
from mypy.server.update import get_all_dependencies, update_build
from mypy.strconv import StrConv, indent
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.testtypegen import ignore_node
from mypy.types import TypeStrVisitor, Type
from mypy.util import short_type


files = [
    'fine-grained.test'
]


class FineGrainedSuite(DataSuite):
    def __init__(self, *, update_data: bool) -> None:
        pass

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
            a.extend(messages)

        deps = get_all_dependencies(manager)

        steps = find_steps()
        for changed_paths in steps:
            modules = []
            for module, path in changed_paths:
                new_path = re.sub(r'\.[0-9]+$', '', path)
                shutil.copy(path, new_path)
                modules.append(module)

            new_messages = update_build(manager, graph, deps, modules)
            new_messages = [re.sub('^tmp' + re.escape(os.sep), '', message)
                            for message in new_messages]

            a.append('==')
            a.extend(new_messages)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))

    def build(self, source: str) -> Tuple[List[str], BuildManager, Graph]:
        options = Options()
        options.use_builtins_fixtures = True
        options.show_traceback = True
        try:
            result = build.build(sources=[BuildSource('main', None, source)],
                                 options=options,
                                 alt_lib_path=test_temp_dir)
        except CompileError as e:
            # TODO: We need a manager and a graph in this case as well
            return e.messages, None, None
        return result.errors, result.manager, result.graph


def find_steps() -> List[List[Tuple[str, str]]]:
    """Return a list of build step representations.

    Each build step is a list of (module id, path) tuples, and each
    path is of form 'dir/mod.py.2' (where 2 is the step number).
    """
    steps = {}  # type: Dict[int, List[Tuple[str, str]]]
    for dn, dirs, files in os.walk(test_temp_dir):
        dnparts = dn.split(os.sep)
        assert dnparts[0] == test_temp_dir
        del dnparts[0]
        for filename in files:
            m = re.match(r'.*\.([0-9]+)$', filename)
            if m:
                num = int(m.group(1))
                assert num >= 2
                name = re.sub(r'\.py.*', '', filename)
                module = '.'.join(dnparts + [name])
                path = os.path.join(dn, filename)
                steps.setdefault(num, []).append((module, path))
    max_step = max(steps)
    return [steps[num] for num in range(2, max_step + 1)]
