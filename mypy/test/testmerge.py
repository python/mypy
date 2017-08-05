"""Test cases for AST merge (used for fine-grained incremental checking)"""

import os
import shutil
from typing import List, Tuple, Dict, Optional

from mypy import build
from mypy.build import BuildManager, BuildSource, State
from mypy.errors import Errors, CompileError
from mypy.nodes import (
    Node, MypyFile, SymbolTable, SymbolTableNode, TypeInfo, Expression
)
from mypy.options import Options
from mypy.server.astmerge import merge_asts
from mypy.server.subexpr import get_subexpressions
from mypy.server.update import build_incremental_step, replace_modules_with_new_variants
from mypy.strconv import StrConv, indent
from mypy.test.config import test_temp_dir, test_data_prefix
from mypy.test.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.test.helpers import assert_string_arrays_equal
from mypy.test.testtypegen import ignore_node
from mypy.types import TypeStrVisitor, Type
from mypy.util import short_type, IdMapper


files = [
    'merge.test'
]


# Which data structures to dump in a test case?
SYMTABLE = 'SYMTABLE'
TYPEINFO = ' TYPEINFO'
TYPES = 'TYPES'
AST = 'AST'


class ASTMergeSuite(DataSuite):
    def __init__(self, *, update_data: bool) -> None:
        super().__init__(update_data=update_data)
        self.str_conv = StrConv(show_ids=True)
        assert self.str_conv.id_mapper is not None
        self.id_mapper = self.str_conv.id_mapper  # type: IdMapper
        self.type_str_conv = TypeStrVisitor(self.id_mapper)

    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        name = testcase.name
        # We use the test case name to decide which data structures to dump.
        # Dumping everything would result in very verbose test cases.
        if name.endswith('_symtable'):
            kind = SYMTABLE
        elif name.endswith('_typeinfo'):
            kind = TYPEINFO
        elif name.endswith('_types'):
            kind = TYPES
        else:
            kind = AST

        main_src = '\n'.join(testcase.input)
        messages, manager, graph = self.build(main_src)
        assert manager is not None, 'cases where CompileError occurred should not be run'

        a = []
        if messages:
            a.extend(messages)

        shutil.copy(os.path.join(test_temp_dir, 'target.py.next'),
                    os.path.join(test_temp_dir, 'target.py'))

        a.extend(self.dump(manager.modules, graph, kind))

        old_modules = dict(manager.modules)
        old_subexpr = get_subexpressions(old_modules['target'])

        new_file, new_types = self.build_increment(manager, 'target')
        replace_modules_with_new_variants(manager,
                                          graph,
                                          old_modules,
                                          {'target': new_file},
                                          {'target': new_types})

        a.append('==>')
        a.extend(self.dump(manager.modules, graph, kind))

        for expr in old_subexpr:
            # Verify that old AST nodes are removed from the expression type map.
            assert expr not in new_types

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))

    def build(self, source: str) -> Tuple[List[str], Optional[BuildManager], Dict[str, State]]:
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
            return e.messages, None, {}
        return result.errors, result.manager, result.graph

    def build_increment(self, manager: BuildManager,
                        module_id: str) -> Tuple[MypyFile,
                                                 Dict[Expression, Type]]:
        module_dict, type_maps = build_incremental_step(manager, [module_id])
        return module_dict[module_id], type_maps[module_id]

    def dump(self,
             modules: Dict[str, MypyFile],
             graph: Dict[str, State],
             kind: str) -> List[str]:
        if kind == AST:
            return self.dump_asts(modules)
        elif kind == TYPEINFO:
            return self.dump_typeinfos(modules)
        elif kind == SYMTABLE:
            return self.dump_symbol_tables(modules)
        elif kind == TYPES:
            return self.dump_types(graph)
        assert False, 'Invalid kind %s' % kind

    def dump_asts(self, modules: Dict[str, MypyFile]) -> List[str]:
        a = []
        for m in sorted(modules):
            if m == 'builtins':
                # We don't support incremental checking of changes to builtins.
                continue
            s = modules[m].accept(self.str_conv)
            a.extend(s.splitlines())
        return a

    def dump_symbol_tables(self, modules: Dict[str, MypyFile]) -> List[str]:
        a = []
        for id in sorted(modules):
            if id == 'builtins':
                # We don't support incremental checking of changes to builtins.
                continue
            a.extend(self.dump_symbol_table(id, modules[id].names))
        return a

    def dump_symbol_table(self, module_id: str, symtable: SymbolTable) -> List[str]:
        a = ['{}:'.format(module_id)]
        for name in sorted(symtable):
            if name.startswith('__'):
                continue
            a.append('    {}: {}'.format(name, self.format_symbol_table_node(symtable[name])))
        return a

    def format_symbol_table_node(self, node: SymbolTableNode) -> str:
        if node is None:
            return 'None'
        if isinstance(node.node, Node):
            return '{}<{}>'.format(str(type(node.node).__name__),
                                   self.id_mapper.id(node.node))
        # TODO: type_override?
        return '?'

    def dump_typeinfos(self, modules: Dict[str, MypyFile]) -> List[str]:
        a = []
        for id in sorted(modules):
            if id == 'builtins':
                continue
            a.extend(self.dump_typeinfos_recursive(modules[id].names))
        return a

    def dump_typeinfos_recursive(self, names: SymbolTable) -> List[str]:
        a = []
        for name, node in sorted(names.items(), key=lambda x: x[0]):
            if isinstance(node.node, TypeInfo):
                a.extend(self.dump_typeinfo(node.node))
                a.extend(self.dump_typeinfos_recursive(node.node.names))
        return a

    def dump_typeinfo(self, info: TypeInfo) -> List[str]:
        s = info.dump(str_conv=self.str_conv,
                      type_str_conv=self.type_str_conv)
        return s.splitlines()

    def dump_types(self, graph: Dict[str, State]) -> List[str]:
        a = []
        # To make the results repeatable, we try to generate unique and
        # deterministic sort keys.
        for module_id in sorted(graph):
            if module_id == 'builtins':
                continue
            type_map = graph[module_id].type_checker.type_map
            if type_map:
                a.append('## {}'.format(module_id))
                for expr in sorted(type_map, key=lambda n: (n.line, short_type(n),
                                                            str(n) + str(type_map[n]))):
                    typ = type_map[expr]
                    a.append('{}:{}: {}'.format(short_type(expr),
                                                expr.line,
                                                typ.accept(self.type_str_conv)))
        return a
