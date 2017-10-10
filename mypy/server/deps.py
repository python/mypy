"""Generate fine-grained dependencies for AST nodes."""

from typing import Dict, List, Set, Optional

from mypy.checkmember import bind_self
from mypy.nodes import (
    Node, Expression, MypyFile, FuncDef, ClassDef, AssignmentStmt, NameExpr, MemberExpr, Import,
    ImportFrom, CallExpr, TypeInfo, Var, LDEF
)
from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, Instance, AnyType, NoneTyp, TypeVisitor, CallableType, DeletedType, PartialType,
    TupleType, TypeType, TypeVarType, TypedDictType, UnboundType, UninhabitedType, UnionType,
    FunctionLike, ForwardRef
)
from mypy.server.trigger import make_trigger


def get_dependencies(prefix: str, node: Node,
                     type_map: Dict[Expression, Type]) -> Dict[str, Set[str]]:
    """Get all dependencies of a node, recursively."""
    visitor = DependencyVisitor(prefix, type_map)
    node.accept(visitor)
    return visitor.map


def get_dependencies_of_target(prefix: str, node: Node,
                               type_map: Dict[Expression, Type]) -> Dict[str, Set[str]]:
    """Get dependencies of a target -- don't recursive into nested targets."""
    visitor = DependencyVisitor(prefix, type_map)
    if isinstance(node, MypyFile):
        for defn in node.defs:
            if not isinstance(defn, (ClassDef, FuncDef)):
                defn.accept(visitor)
    else:
        node.accept(visitor)
    return visitor.map


class DependencyVisitor(TraverserVisitor):
    def __init__(self, prefix: str, type_map: Dict[Expression, Type]) -> None:
        self.stack = [prefix]
        self.type_map = type_map
        self.map = {}  # type: Dict[str, Set[str]]
        self.is_class = False

    # TODO
    #   decorated functions
    #   overloads
    #   from m import *

    def visit_mypy_file(self, o: MypyFile) -> None:
        # TODO: Do we need to anything here?
        super().visit_mypy_file(o)

    def visit_func_def(self, o: FuncDef) -> None:
        target = self.push(o.name())
        if o.type:
            if self.is_class and isinstance(o.type, FunctionLike):
                signature = bind_self(o.type)  # type: Type
            else:
                signature = o.type
            for trigger in get_type_dependencies(signature):
                self.add_dependency(trigger)
                self.add_dependency(trigger, target=make_trigger(target))
        if o.info:
            for base in non_trivial_bases(o.info):
                self.add_dependency(make_trigger(base.fullname() + '.' + o.name()))
        super().visit_func_def(o)
        self.pop()

    def visit_class_def(self, o: ClassDef) -> None:
        target = self.push(o.name)
        self.add_dependency(make_trigger(target))
        old_is_class = self.is_class
        self.is_class = True
        # TODO: Add dependencies based on MRO and other attributes.
        super().visit_class_def(o)
        self.is_class = old_is_class
        info = o.info
        for name, node in info.names.items():
            if isinstance(node.node, Var):
                for base in non_trivial_bases(info):
                    # If the type of an attribute changes in a base class, we make references
                    # to the attribute in the subclass stale.
                    self.add_dependency(make_trigger(base.fullname() + '.' + name),
                                        target=make_trigger(info.fullname() + '.' + name))
        for base in non_trivial_bases(info):
            for name, node in base.names.items():
                self.add_dependency(make_trigger(base.fullname() + '.' + name),
                                    target=make_trigger(info.fullname() + '.' + name))
            self.add_dependency(make_trigger(base.fullname() + '.__init__'),
                                target=make_trigger(info.fullname() + '.__init__'))
        self.pop()

    def visit_import(self, o: Import) -> None:
        for id, as_id in o.ids:
            # TODO: as_id
            self.add_dependency(make_trigger(id), self.current())

    def visit_import_from(self, o: ImportFrom) -> None:
        assert o.relative == 0  # Relative imports not supported
        for name, as_name in o.names:
            assert as_name is None or as_name == name
            self.add_dependency(make_trigger(o.id + '.' + name))

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        super().visit_assignment_stmt(o)
        if o.type:
            for trigger in get_type_dependencies(o.type):
                self.add_dependency(trigger)

    # Expressions

    # TODO
    #   dependency on __init__ (e.g. ClassName())
    #   super()

    def visit_name_expr(self, o: NameExpr) -> None:
        if o.kind == LDEF:
            # We don't track depdendencies to local variables, since they
            # aren't externally visible.
            return
        if o.fullname is not None:
            trigger = make_trigger(o.fullname)
            self.add_dependency(trigger)

    def visit_member_expr(self, e: MemberExpr) -> None:
        super().visit_member_expr(e)
        if e.kind is not None:
            # Reference to a module attribute
            if e.fullname is not None:
                trigger = make_trigger(e.fullname)
                self.add_dependency(trigger)
        else:
            # Reference to a non-module attribute
            typ = self.type_map[e.expr]
            if isinstance(typ, Instance):
                member = '%s.%s' % (typ.type.fullname(), e.name)
                self.add_dependency(make_trigger(member))
            elif isinstance(typ, (AnyType, NoneTyp)):
                pass  # No dependency needed
            elif isinstance(typ, FunctionLike) and typ.is_type_obj():
                member = '%s.%s' % (typ.type_object().fullname(), e.name)
                self.add_dependency(make_trigger(member))

    def visit_call_expr(self, e: CallExpr) -> None:
        super().visit_call_expr(e)
        callee_type = self.type_map.get(e.callee)
        if isinstance(callee_type, FunctionLike) and callee_type.is_type_obj():
            class_name = callee_type.type_object().fullname()
            self.add_dependency(make_trigger(class_name + '.__init__'))

    # Helpers

    def add_dependency(self, trigger: str, target: Optional[str] = None) -> None:
        if target is None:
            target = self.current()
        self.map.setdefault(trigger, set()).add(target)

    def push(self, component: str) -> str:
        target = '%s.%s' % (self.current(), component)
        self.stack.append(target)
        return target

    def pop(self) -> None:
        self.stack.pop()

    def current(self) -> str:
        return self.stack[-1]


def get_type_dependencies(typ: Type) -> List[str]:
    return typ.accept(TypeDependenciesVisitor())


class TypeDependenciesVisitor(TypeVisitor[List[str]]):
    def __init__(self) -> None:
        self.deps = []  # type: List[str]

    def visit_instance(self, typ: Instance) -> List[str]:
        trigger = make_trigger(typ.type.fullname())
        triggers = [trigger]
        for arg in typ.args:
            triggers.extend(get_type_dependencies(arg))
        return triggers

    def visit_any(self, typ: AnyType) -> List[str]:
        return []

    def visit_none_type(self, typ: NoneTyp) -> List[str]:
        return []

    def visit_callable_type(self, typ: CallableType) -> List[str]:
        # TODO: generic callables
        triggers = []
        for arg in typ.arg_types:
            triggers.extend(get_type_dependencies(arg))
        triggers.extend(get_type_dependencies(typ.ret_type))
        return triggers

    def visit_deleted_type(self, typ: DeletedType) -> List[str]:
        return []

    def visit_partial_type(self, typ: PartialType) -> List[str]:
        assert False, "Should not see a partial type here"

    def visit_tuple_type(self, typ: TupleType) -> List[str]:
        raise NotImplementedError

    def visit_type_type(self, typ: TypeType) -> List[str]:
        # TODO: replace with actual implementation
        return []

    def visit_forwardref_type(self, typ: ForwardRef) -> List[str]:
        assert False, 'Internal error: Leaked forward reference object {}'.format(typ)

    def visit_type_var(self, typ: TypeVarType) -> List[str]:
        # TODO: replace with actual implementation
        return []

    def visit_typeddict_type(self, typ: TypedDictType) -> List[str]:
        raise NotImplementedError

    def visit_unbound_type(self, typ: UnboundType) -> List[str]:
        return []

    def visit_uninhabited_type(self, typ: UninhabitedType) -> List[str]:
        return []

    def visit_union_type(self, typ: UnionType) -> List[str]:
        raise NotImplementedError


def non_trivial_bases(info: TypeInfo) -> List[TypeInfo]:
    return [base for base in info.mro[1:]
            if base.fullname() != 'builtins.object']
