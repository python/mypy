"""Utilities for calculating and reporting statistics about types."""

import os
import typing

from collections import Counter
from typing import Dict, List, cast, Optional

from mypy.traverser import TraverserVisitor
from mypy.typeanal import collect_all_inner_types
from mypy.types import (
    Type, AnyType, Instance, FunctionLike, TupleType, TypeVarType, TypeQuery, CallableType,
    TypeOfAny
)
from mypy import nodes
from mypy.nodes import (
    Expression, FuncDef, TypeApplication, AssignmentStmt, NameExpr, CallExpr, MypyFile,
    MemberExpr, OpExpr, ComparisonExpr, IndexExpr, UnaryExpr, YieldFromExpr, RefExpr, ClassDef
)

MYPY = False
if MYPY:
    from typing_extensions import Final


TYPE_EMPTY = 0  # type: Final
TYPE_UNANALYZED = 1  # type: Final  # type of non-typechecked code
TYPE_PRECISE = 2  # type: Final
TYPE_IMPRECISE = 3  # type: Final
TYPE_ANY = 4  # type: Final

precision_names = [
    'empty',
    'unanalyzed',
    'precise',
    'imprecise',
    'any',
]  # type: Final


class StatisticsVisitor(TraverserVisitor):
    def __init__(self,
                 inferred: bool,
                 filename: str,
                 typemap: Optional[Dict[Expression, Type]] = None,
                 all_nodes: bool = False,
                 visit_untyped_defs: bool = True) -> None:
        self.inferred = inferred
        self.filename = filename
        self.typemap = typemap
        self.all_nodes = all_nodes
        self.visit_untyped_defs = visit_untyped_defs

        self.num_precise_exprs = 0
        self.num_imprecise_exprs = 0
        self.num_any_exprs = 0

        self.num_simple_types = 0
        self.num_generic_types = 0
        self.num_tuple_types = 0
        self.num_function_types = 0
        self.num_typevar_types = 0
        self.num_complex_types = 0
        self.num_any_types = 0

        self.line = -1

        self.line_map = {}  # type: Dict[int, int]

        self.type_of_any_counter = Counter()  # type: typing.Counter[int]
        self.any_line_map = {}  # type: Dict[int, List[AnyType]]

        self.output = []  # type: List[str]

        TraverserVisitor.__init__(self)

    def visit_func_def(self, o: FuncDef) -> None:
        self.line = o.line
        if len(o.expanded) > 1 and o.expanded != [o] * len(o.expanded):
            if o in o.expanded:
                print('{}:{}: ERROR: cycle in function expansion; skipping'.format(self.filename,
                                                                                   o.get_line()))
                return
            for defn in o.expanded:
                self.visit_func_def(cast(FuncDef, defn))
        else:
            if o.type:
                sig = cast(CallableType, o.type)
                arg_types = sig.arg_types
                if (sig.arg_names and sig.arg_names[0] == 'self' and
                        not self.inferred):
                    arg_types = arg_types[1:]
                for arg in arg_types:
                    self.type(arg)
                self.type(sig.ret_type)
            elif self.all_nodes:
                self.record_line(self.line, TYPE_ANY)
            if not o.is_dynamic() or self.visit_untyped_defs:
                super().visit_func_def(o)

    def visit_class_def(self, o: ClassDef) -> None:
        # Override this method because we don't want to analyze base_type_exprs (base_type_exprs
        # are base classes in a class declaration).
        # While base_type_exprs are technically expressions, type analyzer does not visit them and
        # they are not in the typemap.
        for d in o.decorators:
            d.accept(self)
        o.defs.accept(self)

    def visit_type_application(self, o: TypeApplication) -> None:
        self.line = o.line
        for t in o.types:
            self.type(t)
        super().visit_type_application(o)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        self.line = o.line
        if (isinstance(o.rvalue, nodes.CallExpr) and
                isinstance(o.rvalue.analyzed, nodes.TypeVarExpr)):
            # Type variable definition -- not a real assignment.
            return
        if o.type:
            self.type(o.type)
        elif self.inferred and not self.all_nodes:
            # if self.all_nodes is set, lvalues will be visited later
            for lvalue in o.lvalues:
                if isinstance(lvalue, nodes.TupleExpr):
                    items = lvalue.items
                else:
                    items = [lvalue]
                for item in items:
                    if isinstance(item, RefExpr) and item.is_inferred_def:
                        if self.typemap is not None:
                            self.type(self.typemap.get(item))
        super().visit_assignment_stmt(o)

    def visit_name_expr(self, o: NameExpr) -> None:
        self.process_node(o)
        super().visit_name_expr(o)

    def visit_yield_from_expr(self, o: YieldFromExpr) -> None:
        if o.expr:
            o.expr.accept(self)

    def visit_call_expr(self, o: CallExpr) -> None:
        self.process_node(o)
        if o.analyzed:
            o.analyzed.accept(self)
        else:
            o.callee.accept(self)
            for a in o.args:
                a.accept(self)

    def visit_member_expr(self, o: MemberExpr) -> None:
        self.process_node(o)
        super().visit_member_expr(o)

    def visit_op_expr(self, o: OpExpr) -> None:
        self.process_node(o)
        super().visit_op_expr(o)

    def visit_comparison_expr(self, o: ComparisonExpr) -> None:
        self.process_node(o)
        super().visit_comparison_expr(o)

    def visit_index_expr(self, o: IndexExpr) -> None:
        self.process_node(o)
        super().visit_index_expr(o)

    def visit_unary_expr(self, o: UnaryExpr) -> None:
        self.process_node(o)
        super().visit_unary_expr(o)

    def process_node(self, node: Expression) -> None:
        if self.all_nodes:
            if self.typemap is not None:
                self.line = node.line
                self.type(self.typemap.get(node))

    def type(self, t: Optional[Type]) -> None:
        if not t:
            # If an expression does not have a type, it is often due to dead code.
            # Don't count these because there can be an unanalyzed value on a line with other
            # analyzed expressions, which overwrite the TYPE_UNANALYZED.
            self.record_line(self.line, TYPE_UNANALYZED)
            return

        if isinstance(t, AnyType) and t.type_of_any == TypeOfAny.special_form:
            # This is not a real Any type, so don't collect stats for it.
            return

        if isinstance(t, AnyType):
            self.log('  !! Any type around line %d' % self.line)
            self.num_any_exprs += 1
            self.record_line(self.line, TYPE_ANY)
        elif ((not self.all_nodes and is_imprecise(t)) or
              (self.all_nodes and is_imprecise2(t))):
            self.log('  !! Imprecise type around line %d' % self.line)
            self.num_imprecise_exprs += 1
            self.record_line(self.line, TYPE_IMPRECISE)
        else:
            self.num_precise_exprs += 1
            self.record_line(self.line, TYPE_PRECISE)

        for typ in collect_all_inner_types(t) + [t]:
            if isinstance(typ, AnyType):
                if typ.type_of_any == TypeOfAny.from_another_any:
                    assert typ.source_any
                    assert typ.source_any.type_of_any != TypeOfAny.from_another_any
                    typ = typ.source_any
                self.type_of_any_counter[typ.type_of_any] += 1
                self.num_any_types += 1
                if self.line in self.any_line_map:
                    self.any_line_map[self.line].append(typ)
                else:
                    self.any_line_map[self.line] = [typ]
            elif isinstance(typ, Instance):
                if typ.args:
                    if any(is_complex(arg) for arg in typ.args):
                        self.num_complex_types += 1
                    else:
                        self.num_generic_types += 1
                else:
                    self.num_simple_types += 1
            elif isinstance(typ, FunctionLike):
                self.num_function_types += 1
            elif isinstance(typ, TupleType):
                if any(is_complex(item) for item in typ.items):
                    self.num_complex_types += 1
                else:
                    self.num_tuple_types += 1
            elif isinstance(typ, TypeVarType):
                self.num_typevar_types += 1

    def log(self, string: str) -> None:
        self.output.append(string)

    def record_line(self, line: int, precision: int) -> None:
        self.line_map[line] = max(precision,
                                  self.line_map.get(line, TYPE_EMPTY))


def dump_type_stats(tree: MypyFile, path: str, inferred: bool = False,
                    typemap: Optional[Dict[Expression, Type]] = None) -> None:
    if is_special_module(path):
        return
    print(path)
    visitor = StatisticsVisitor(inferred, filename=tree.fullname(), typemap=typemap)
    tree.accept(visitor)
    for line in visitor.output:
        print(line)
    print('  ** precision **')
    print('  precise  ', visitor.num_precise_exprs)
    print('  imprecise', visitor.num_imprecise_exprs)
    print('  any      ', visitor.num_any_exprs)
    print('  ** kinds **')
    print('  simple   ', visitor.num_simple_types)
    print('  generic  ', visitor.num_generic_types)
    print('  function ', visitor.num_function_types)
    print('  tuple    ', visitor.num_tuple_types)
    print('  TypeVar  ', visitor.num_typevar_types)
    print('  complex  ', visitor.num_complex_types)
    print('  any      ', visitor.num_any_types)


def is_special_module(path: str) -> bool:
    return os.path.basename(path) in ('abc.pyi', 'typing.pyi', 'builtins.pyi')


def is_imprecise(t: Type) -> bool:
    return t.accept(HasAnyQuery())


class HasAnyQuery(TypeQuery[bool]):
    def __init__(self) -> None:
        super().__init__(any)

    def visit_any(self, t: AnyType) -> bool:
        return True

    def visit_instance(self, t: Instance) -> bool:
        if t.type.fullname() == 'builtins.tuple':
            return True
        else:
            return super().visit_instance(t)


def is_imprecise2(t: Type) -> bool:
    return t.accept(HasAnyQuery2())


class HasAnyQuery2(HasAnyQuery):
    def visit_callable_type(self, t: CallableType) -> bool:
        # We don't want to flag references to functions with some Any
        # argument types (etc.) since they generally don't mean trouble.
        return False


def is_generic(t: Type) -> bool:
    return isinstance(t, Instance) and bool(t.args)


def is_complex(t: Type) -> bool:
    return is_generic(t) or isinstance(t, (FunctionLike, TupleType,
                                           TypeVarType))


def ensure_dir_exists(dir: str) -> None:
    if not os.path.exists(dir):
        os.makedirs(dir)
