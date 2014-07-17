"""Utilities for calculating and reporting statistics about types."""

from os.path import basename

from typing import Any, Dict, cast
    
from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, AnyType, Instance, FunctionLike, TupleType, Void, TypeVar,
    TypeQuery, ANY_TYPE_STRATEGY, Callable
)
from mypy import nodes
from mypy.nodes import Node, FuncDef, TypeApplication, AssignmentStmt


class StatisticsVisitor(TraverserVisitor):
    def __init__(self, inferred: bool, typemap: Dict[Node, Type] = None) -> None:
        self.inferred = inferred
        self.typemap = typemap
        
        self.num_precise = 0
        self.num_imprecise = 0
        self.num_any = 0

        self.num_simple = 0
        self.num_generic = 0
        self.num_tuple = 0
        self.num_function = 0
        self.num_typevar = 0
        self.num_complex = 0

        self.line = -1

        self.line_map = Dict[int, int]()
        
        TraverserVisitor.__init__(self)
    
    def visit_func_def(self, o: FuncDef) -> None:
        self.line = o.line
        if len(o.expanded) > 1:
            for defn in o.expanded:
                self.visit_func_def(cast(FuncDef, defn))
        else:
            if o.type:
                sig = cast(Callable, o.type)
                arg_types = sig.arg_types
                if (sig.arg_names and sig.arg_names[0] == 'self' and
                    not self.inferred):
                    arg_types = arg_types[1:]
                for arg in arg_types:
                    self.type(arg)
                self.type(sig.ret_type)
            super().visit_func_def(o)

    def visit_type_application(self, o: TypeApplication) -> None:
        self.line = o.line
        for t in o.types:
            self.type(t)
        super().visit_type_application(o)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        self.line = o.line
        if (isinstance(o.rvalue, nodes.CallExpr) and
            isinstance(cast(nodes.CallExpr, o.rvalue).analyzed,
                       nodes.TypeVarExpr)):
            # Type variable definition -- not a real assignment.
            return
        if o.type:
            self.type(o.type)
        elif self.inferred:
            for lvalue in o.lvalues:
                lvalue_ref = lvalue
                if isinstance(lvalue_ref, nodes.ParenExpr):
                    lvalue = lvalue_ref.expr
                if isinstance(lvalue, nodes.TupleExpr):
                    items = lvalue.items
                elif isinstance(lvalue, nodes.ListExpr):
                    items = lvalue.items
                else:
                    items = [lvalue]
                for item in items:
                    if hasattr(item, 'is_def') and Any(item).is_def:
                        t = self.typemap.get(item)
                        if t:
                            self.type(t)
                        else:
                            print('  !! No inferred type on line', self.line)
        super().visit_assignment_stmt(o)

    def type(self, t: Type) -> None:
        if isinstance(t, AnyType):
            print('  !! Any type around line', self.line)
            self.num_any += 1
        elif is_imprecise(t):
            print('  !! Imprecise type around line', self.line)
            self.num_imprecise += 1
        else:
            self.num_precise += 1

        if isinstance(t, Instance):
            if t.args:
                if any(is_complex(arg) for arg in t.args):
                    self.num_complex += 1
                else:
                    self.num_generic += 1
            else:
                self.num_simple += 1
        elif isinstance(t, Void):
            self.num_simple += 1
        elif isinstance(t, FunctionLike):
            self.num_function += 1
        elif isinstance(t, TupleType):
            if any(is_complex(item) for item in t.items):
                self.num_complex += 1
            else:
                self.num_tuple += 1
        elif isinstance(t, TypeVar):
            self.num_typevar += 1


def analyze_types(tree: Node, path: str, inferred: bool = False,
                  typemap: Dict[Node, Type] = None) -> None:
    if basename(path) in ('abc.py', 'typing.py', 'builtins.py'):
        return
    print(path)
    v = StatisticsVisitor(inferred, typemap)
    tree.accept(v)
    print('  ** precision **')
    print('  precise  ', v.num_precise)
    print('  imprecise', v.num_imprecise)
    print('  any      ', v.num_any)
    print('  ** kinds **')
    print('  simple   ', v.num_simple)
    print('  generic  ', v.num_generic)
    print('  function ', v.num_function)
    print('  tuple    ', v.num_tuple)
    print('  typevar  ', v.num_typevar)
    print('  complex  ', v.num_complex)
    print('  any      ', v.num_any)


def is_imprecise(t: Type) -> bool:
    return t.accept(HasAnyQuery())


class HasAnyQuery(TypeQuery):
    def __init__(self) -> None:
        super().__init__(False, ANY_TYPE_STRATEGY)

    def visit_any(self, t: AnyType) -> bool:
        return True

    def visit_instance(self, t: Instance) -> bool:
        if t.type.fullname() == 'builtins.tuple':
            return True
        else:
            return super().visit_instance(t)


def is_generic(t: Type) -> bool:
    return isinstance(t, Instance) and bool(cast(Instance, t).args)


def is_complex(t: Type) -> bool:
    return is_generic(t) or isinstance(t, (FunctionLike, TupleType,
                                           TypeVar))
