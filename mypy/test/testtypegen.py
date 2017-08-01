"""Test cases for the type checker: exporting inferred types"""

import os.path
import re

from typing import Set, List

from mypy import build
from mypy.build import BuildSource
from mypy.test import config
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.util import short_type
from mypy.nodes import (
    NameExpr, TypeVarExpr, CallExpr, Expression, MypyFile, AssignmentStmt, IntExpr
)
from mypy.traverser import TraverserVisitor
from mypy.errors import CompileError
from mypy.options import Options


class TypeExportSuite(DataSuite):
    # List of files that contain test case descriptions.
    files = ['typexport-basic.test']

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in cls.files:
            c += parse_test_cases(os.path.join(config.test_data_prefix, f),
                                  None, config.test_temp_dir)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        try:
            line = testcase.input[0]
            mask = ''
            if line.startswith('##'):
                mask = '(' + line[2:].strip() + ')$'

            src = '\n'.join(testcase.input)
            options = Options()
            options.use_builtins_fixtures = True
            options.show_traceback = True
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=options,
                                 alt_lib_path=config.test_temp_dir)
            a = result.errors
            map = result.types
            nodes = map.keys()

            # Ignore NameExpr nodes of variables with explicit (trivial) types
            # to simplify output.
            searcher = SkippedNodeSearcher()
            for file in result.files.values():
                file.accept(searcher)
            ignored = searcher.nodes

            # Filter nodes that should be included in the output.
            keys = []
            for node in nodes:
                if node.line is not None and node.line != -1 and map[node]:
                    if ignore_node(node) or node in ignored:
                        continue
                    if (re.match(mask, short_type(node))
                            or (isinstance(node, NameExpr)
                                and re.match(mask, node.name))):
                        # Include node in output.
                        keys.append(node)

            for key in sorted(keys,
                              key=lambda n: (n.line, short_type(n),
                                             str(n) + str(map[n]))):
                ts = str(map[key]).replace('*', '')  # Remove erased tags
                ts = ts.replace('__main__.', '')
                a.append('{}({}) : {}'.format(short_type(key), key.line, ts))
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid type checker output ({}, line {})'.format(testcase.file,
                                                               testcase.line))


class SkippedNodeSearcher(TraverserVisitor):
    def __init__(self) -> None:
        self.nodes = set()  # type: Set[Expression]
        self.is_typing = False

    def visit_mypy_file(self, f: MypyFile) -> None:
        self.is_typing = f.fullname() == 'typing' or f.fullname() == 'builtins'
        super().visit_mypy_file(f)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        if s.type or ignore_node(s.rvalue):
            for lvalue in s.lvalues:
                if isinstance(lvalue, NameExpr):
                    self.nodes.add(lvalue)
        super().visit_assignment_stmt(s)

    def visit_name_expr(self, n: NameExpr) -> None:
        self.skip_if_typing(n)

    def visit_int_expr(self, n: IntExpr) -> None:
        self.skip_if_typing(n)

    def skip_if_typing(self, n: Expression) -> None:
        if self.is_typing:
            self.nodes.add(n)


def ignore_node(node: Expression) -> bool:
    """Return True if node is to be omitted from test case output."""

    # We want to get rid of object() expressions in the typing module stub
    # and also TypeVar(...) expressions. Since detecting whether a node comes
    # from the typing module is not easy, we just to strip them all away.
    if isinstance(node, TypeVarExpr):
        return True
    if isinstance(node, NameExpr) and node.fullname == 'builtins.object':
        return True
    if isinstance(node, NameExpr) and node.fullname == 'builtins.None':
        return True
    if isinstance(node, CallExpr) and (ignore_node(node.callee) or
                                       node.analyzed):
        return True

    return False
