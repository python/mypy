"""Always defined attribute analysis.

An always defined attribute has a set of statements in __init__ that
always initialize the attribute when evaluated (and only one of which
is ever evaluated), and that is never read before initialization.

As soon as we encounter something that can execute arbitrary code, we
must stop inferring always defined attributes, since this code could
read the attribute values. We only allow a fairly restricted set of
operations.

We require that __del__ methods don't call gc.get_objects() and then
access partially initialized objects. Code like this could potentially
cause a segfault with a null pointer reference:

- enter __init__ of a native class C
- allocate an empty object (e.g. a list) in __init__
- cyclic garbage collector runs and calls __del__ that accesses the x
  attribute of C which has not been initialized -> segfault
- (if gc would not run) initialize the x attribute to a non-null value

This runs after mypyc.irbuild.prepare but before actual IR building,
since we need to know properties of classes inferred during the prepare
step, and we also use the results of this analysis during IR building.

This runs over the mypy AST so that we can directly generate optimized
IR. Since we only run this on __init__ methods, this analysis pass
will be quick.
"""

from typing import Dict, Set

from mypy.nodes import (
    TypeInfo, FuncDef, Var, NameExpr, AssignmentStmt, MemberExpr, IfStmt, Block,
    Expression, ComparisonExpr, OpExpr, UnaryExpr, IntExpr, FloatExpr, StrExpr, BytesExpr,
    ListExpr, SetExpr, DictExpr, RefExpr, MypyFile, LDEF
)
from mypy.types import Type, NoneType, Instance, get_proper_type

from mypyc.ir.class_ir import ClassIR
from mypyc.irbuild.mapper import Mapper


def analyze_always_defined_attrs(
        info: TypeInfo,
        cl: ClassIR,
        types: Dict[Expression, Type],
        mapper: Mapper) -> Set[MemberExpr]:
    """Find always initialized attributes for a class.

    TODO: Also determine if __init__ might access any attributes defined in subclasses.
    This can be used to optimize for super().__init__() calls.
    """
    if (cl.is_trait
            or cl.inherits_python
            or cl.allow_interpreted_subclasses
            or cl.builtin_base is not None
            or cl.children is None
            or cl.children != []):
        # Give up
        return set()

    m = info.get_method('__init__')
    if m is None or not isinstance(m, FuncDef):
        return set()

    self_var = m.arguments[0].variable
    result = Analyzer(self_var, types, mapper).analyze_block(m.body)
    cl._always_initialized_attrs = result.always_defined
    return result.initializers


class State:
    def __init__(self) -> None:
        self.always_defined = set()  # type: Set[str]
        self.maybe_defined = set()  # type: Set[str]
        self.initializers = set()  # type: Set[MemberExpr]
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def record_defined(self, name: str) -> bool:
        if name not in self.maybe_defined:
            self.always_defined.add(name)
            self.maybe_defined.add(name)
            return True
        return False

    def record_maybe_defined(self, name: str) -> None:
        self.maybe_defined.add(name)


class Analyzer:
    def __init__(self, self_var: Var, types: Dict[Expression, Type], mapper: Mapper) -> None:
        self.self_var = self_var
        self.types = types
        self.mapper = mapper

    def analyze_block(self, block: Block) -> State:
        state = State()
        for stmt in block.body:
            if isinstance(stmt, AssignmentStmt):
                self.analyze_assignment(stmt, state)
            elif isinstance(stmt, IfStmt):
                self.analyze_if(stmt, state)
            else:
                state.stop()
            if state.stopped:
                return state
        return state

    def analyze_assignment(self, stmt: AssignmentStmt, state: State) -> None:
        if not self.is_safe_expr(stmt.rvalue):
            state.stop()
            return
        for lvalue in stmt.lvalues:
            if (isinstance(lvalue, MemberExpr)
                    and isinstance(lvalue.expr, NameExpr)
                    and lvalue.expr.node == self.self_var):
                if state.record_defined(lvalue.name):
                    state.initializers.add(lvalue)
                else:
                    return
            elif not (isinstance(lvalue, NameExpr) and lvalue.kind == LDEF):
                state.stop()
                return

    def analyze_if(self, stmt: IfStmt, state: State) -> None:
        results = [self.analyze_block(b) for b in stmt.body]
        if stmt.else_body:
            results.append(self.analyze_block(stmt.else_body))
        else:
            results.append(State())

        always_defined = set.intersection(*(r.always_defined for r in results))
        for name in always_defined:
            state.record_defined(name)

        maybe_defined = set.union(*(r.maybe_defined for r in results)) - always_defined
        for name in maybe_defined:
            state.record_maybe_defined(name)

        for r in results:
            state.initializers |= r.initializers

        if any(r.stopped for r in results):
            state.stop()

    def is_safe_condition(self, expr: Expression) -> bool:
        if isinstance(expr, NameExpr):
            # TODO: References to local variables without custom __bool__ are generally fine
            return False
        elif isinstance(expr, OpExpr):
            if expr.op in ('and', 'or'):
                return self.is_safe_condition(expr.left) and self.is_safe_condition(expr.right)
        elif isinstance(expr, UnaryExpr):
            if expr.op == 'not':
                return self.is_safe_condition(expr.expr)
        # TODO: This may not be fine
        return self.is_safe_expr(expr)

    def is_safe_expr(self, expr: Expression) -> bool:
        if isinstance(expr, NameExpr):
            return self.is_safe_ref(expr)
        elif isinstance(expr, MemberExpr):
            return self.is_safe_expr(expr.expr) and self.is_safe_ref(expr)
        elif isinstance(expr, (IntExpr, FloatExpr, StrExpr, BytesExpr)):
            return True
        elif isinstance(expr, OpExpr):
            return self.has_safe_type(expr.left) and self.has_safe_type(expr.right)
        elif isinstance(expr, UnaryExpr):
            return self.has_safe_type(expr.expr)
        elif isinstance(expr, ComparisonExpr):
            for op, left, right in expr.pairwise():
                if not self.is_safe_expr(left) or not self.is_safe_expr(right):
                    return False
                if op not in ('is', 'is not'):
                    if not self.has_safe_type(left) or not self.has_safe_type(right):
                        return False
            return True
        elif isinstance(expr, (ListExpr, SetExpr)):
            return all(self.is_safe_expr(item) for item in expr.items)
        elif isinstance(expr, DictExpr):
            return all((key is None or self.is_safe_expr(key)) and self.is_safe_expr(value)
                       for key, value in expr.items)
        return False

    def has_safe_type(self, expr: Expression) -> bool:
        typ = self.types.get(expr)
        typ = get_proper_type(typ)
        if isinstance(typ, NoneType):
            return True
        elif isinstance(typ, Instance):
            return typ.type.fullname in ('builtins.int', 'builtins.bool')
        return False

    def is_safe_ref(self, expr: RefExpr) -> bool:
        if isinstance(expr.node, TypeInfo):
            return True
        if isinstance(expr.node, MypyFile):
            return True
        if not isinstance(expr.node, Var):
            return False
        if expr.node.fullname in ('builtins.None', 'builtins.True', 'builtins.False'):
            return True
        if expr.node.is_final and self.mapper.is_native_module_ref_expr(expr):
            return True
        return expr.kind == LDEF and expr.node is not self.self_var
