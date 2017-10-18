"""Generate fine-grained dependencies for AST nodes."""

from typing import Dict, List, Set, Optional, Tuple

from mypy.checkmember import bind_self
from mypy.nodes import (
    Node, Expression, MypyFile, FuncDef, ClassDef, AssignmentStmt, NameExpr, MemberExpr, Import,
    ImportFrom, CallExpr, CastExpr, TypeVarExpr, TypeApplication, IndexExpr, UnaryExpr, OpExpr,
    ComparisonExpr, GeneratorExpr, DictionaryComprehension, StarExpr, PrintStmt, ForStmt, WithStmt,
    TupleExpr, ListExpr, OperatorAssignmentStmt, DelStmt, YieldFromExpr, Decorator, TypeInfo, Var,
    LDEF, MDEF, GDEF, op_methods, reverse_op_methods, ops_with_inplace_method
)
from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, Instance, AnyType, NoneTyp, TypeVisitor, CallableType, DeletedType, PartialType,
    TupleType, TypeType, TypeVarType, TypedDictType, UnboundType, UninhabitedType, UnionType,
    FunctionLike, ForwardRef, Overloaded
)
from mypy.server.trigger import make_trigger


def get_dependencies(prefix: str, node: Node,
                     type_map: Dict[Expression, Type],
                     python_version: Tuple[int, int]) -> Dict[str, Set[str]]:
    """Get all dependencies of a node, recursively."""
    visitor = DependencyVisitor(prefix, type_map, python_version)
    node.accept(visitor)
    return visitor.map


def get_dependencies_of_target(prefix: str, node: Node,
                               type_map: Dict[Expression, Type],
                               python_version: Tuple[int, int]) -> Dict[str, Set[str]]:
    """Get dependencies of a target -- don't recursive into nested targets."""
    visitor = DependencyVisitor(prefix, type_map, python_version)
    if isinstance(node, MypyFile):
        for defn in node.defs:
            if not isinstance(defn, (ClassDef, FuncDef)):
                defn.accept(visitor)
    else:
        node.accept(visitor)
    return visitor.map


class DependencyVisitor(TraverserVisitor):
    def __init__(self, prefix: str, type_map: Dict[Expression, Type],
                 python_version: Tuple[int, int]) -> None:
        self.stack = [prefix]
        self.target_stack = [prefix]
        self.scope_stack = []  # type: List[Node]
        self.type_map = type_map
        self.python2 = python_version[0] == 2
        self.map = {}  # type: Dict[str, Set[str]]
        self.is_class = False

    # TODO
    #   decorated functions
    #   overloads
    #   from m import *
    #   await

    def visit_mypy_file(self, o: MypyFile) -> None:
        # TODO: Do we need to anything here?
        self.enter_scope(o)
        super().visit_mypy_file(o)
        self.leave_scope()

    def visit_func_def(self, o: FuncDef) -> None:
        if not isinstance(self.current_scope(), FuncDef):
            new_scope = True
            self.enter_scope(o)
            target = self.push(o.name())
        else:
            new_scope = False
            target = self.current()
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
        if new_scope:
            self.leave_scope()

    def visit_decorator(self, o: Decorator) -> None:
        self.add_dependency(make_trigger(o.func.fullname()))
        super().visit_decorator(o)

    def visit_class_def(self, o: ClassDef) -> None:
        self.enter_scope(o)
        target = self.push_class(o.name)
        self.add_dependency(make_trigger(target), target)
        old_is_class = self.is_class
        self.is_class = True
        # Add dependencies to type variables of a generic class.
        for tv in o.type_vars:
            self.add_dependency(make_trigger(tv.fullname), target)
        # Add dependencies to base types.
        for base in o.info.bases:
            self.add_type_dependencies(base, target=target)
        # TODO: Add dependencies based on remaining attributes.
        super().visit_class_def(o)
        self.is_class = old_is_class
        info = o.info
        for name, node in info.names.items():
            if isinstance(node.node, Var):
                for base_info in non_trivial_bases(info):
                    # If the type of an attribute changes in a base class, we make references
                    # to the attribute in the subclass stale.
                    self.add_dependency(make_trigger(base_info.fullname() + '.' + name),
                                        target=make_trigger(info.fullname() + '.' + name))
        for base_info in non_trivial_bases(info):
            for name, node in base_info.names.items():
                self.add_dependency(make_trigger(base_info.fullname() + '.' + name),
                                    target=make_trigger(info.fullname() + '.' + name))
            self.add_dependency(make_trigger(base_info.fullname() + '.__init__'),
                                target=make_trigger(info.fullname() + '.__init__'))
        self.pop()
        self.leave_scope()

    def visit_import(self, o: Import) -> None:
        for id, as_id in o.ids:
            # TODO: as_id
            self.add_dependency(make_trigger(id), self.current())

    def visit_import_from(self, o: ImportFrom) -> None:
        assert o.relative == 0  # Relative imports not supported
        for name, as_name in o.names:
            self.add_dependency(make_trigger(o.id + '.' + name))

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        if isinstance(o.rvalue, CallExpr) and isinstance(o.rvalue.analyzed, TypeVarExpr):
            analyzed = o.rvalue.analyzed
            # TODO: implement all special forms
            self.add_type_dependencies(analyzed.upper_bound,
                                       target=make_trigger(analyzed.fullname()))
        else:
            super().visit_assignment_stmt(o)
            for lvalue in o.lvalues:
                self.process_lvalue(lvalue)
            items = o.lvalues + [o.rvalue]
            for i in range(len(items) - 1):
                lvalue = items[i]
                rvalue = items[i + 1]
                if isinstance(lvalue, (TupleExpr, ListExpr)):
                    self.add_attribute_dependency_for_expr(rvalue, '__iter__')
            if o.type:
                for trigger in get_type_dependencies(o.type):
                    self.add_dependency(trigger)

    def process_lvalue(self, lvalue: Expression) -> None:
        if isinstance(lvalue, IndexExpr):
            self.add_indexing_method_dependency(lvalue, lvalue=True)
        elif isinstance(lvalue, NameExpr):
            if lvalue.kind in (MDEF, GDEF):
                # Assignment to an attribute in the class body, or direct assignment to a
                # global variable.
                lvalue_type = self.type_map[lvalue]
                type_triggers = get_type_dependencies(lvalue_type)
                attr_trigger = make_trigger('%s.%s' % (self.target_stack[-1], lvalue.name))
                for type_trigger in type_triggers:
                    self.add_dependency(type_trigger, attr_trigger)
        elif isinstance(lvalue, MemberExpr):
            if lvalue.kind is None:
                # Reference to a non-module attribute
                object_type = self.type_map[lvalue.expr]
                lvalue_type = self.type_map[lvalue]
                type_triggers = get_type_dependencies(lvalue_type)
                for attr_trigger in self.attribute_triggers(object_type, lvalue.name):
                    for type_trigger in type_triggers:
                        self.add_dependency(type_trigger, attr_trigger)
        elif isinstance(lvalue, (ListExpr, TupleExpr)):
            for item in lvalue.items:
                self.process_lvalue(item)
        # TODO: star lvalue

    def visit_operator_assignment_stmt(self, o: OperatorAssignmentStmt) -> None:
        super().visit_operator_assignment_stmt(o)
        self.process_lvalue(o.lvalue)
        method = op_methods[o.op]
        self.add_attribute_dependency_for_expr(o.lvalue, method)
        if o.op in ops_with_inplace_method:
            inplace_method = '__i' + method[2:]
            self.add_attribute_dependency_for_expr(o.lvalue, inplace_method)

    def visit_for_stmt(self, o: ForStmt) -> None:
        super().visit_for_stmt(o)
        self.add_attribute_dependency_for_expr(o.expr, '__iter__')
        self.process_lvalue(o.index)
        if isinstance(o.index, (TupleExpr, ListExpr)):
            # Process multiple assignment to index variables.
            item_type = o.inferred_item_type
            if item_type:
                self.add_attribute_dependency(item_type, '__iter__')
        if o.index_type:
            self.add_type_dependencies(o.index_type)

    def visit_with_stmt(self, o: WithStmt) -> None:
        super().visit_with_stmt(o)
        for e in o.expr:
            self.add_attribute_dependency_for_expr(e, '__enter__')
            self.add_attribute_dependency_for_expr(e, '__exit__')
        if o.target_type:
            self.add_type_dependencies(o.target_type)

    def visit_print_stmt(self, o: PrintStmt) -> None:
        super().visit_print_stmt(o)
        if o.target:
            self.add_attribute_dependency_for_expr(o.target, 'write')

    def visit_del_stmt(self, o: DelStmt) -> None:
        super().visit_del_stmt(o)
        if isinstance(o.expr, IndexExpr):
            self.add_attribute_dependency_for_expr(o.expr.base, '__delitem__')

    # Expressions

    # TODO
    #   dependency on __init__ (e.g. ClassName())
    #   super()

    def visit_name_expr(self, o: NameExpr) -> None:
        if o.kind == LDEF:
            # We don't track depdendencies to local variables, since they
            # aren't externally visible.
            return
        if o.kind == MDEF:
            # Direct reference to member is only possible in the scope that
            # defined the name, so no dependency is required.
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
            self.add_attribute_dependency(typ, e.name)

    def visit_call_expr(self, e: CallExpr) -> None:
        super().visit_call_expr(e)
        callee_type = self.type_map.get(e.callee)
        if isinstance(callee_type, FunctionLike) and callee_type.is_type_obj():
            class_name = callee_type.type_object().fullname()
            self.add_dependency(make_trigger(class_name + '.__init__'))

    def visit_cast_expr(self, e: CastExpr) -> None:
        super().visit_cast_expr(e)
        self.add_type_dependencies(e.type)

    def visit_type_application(self, e: TypeApplication) -> None:
        super().visit_type_application(e)
        for typ in e.types:
            self.add_type_dependencies(typ)

    def visit_index_expr(self, e: IndexExpr) -> None:
        super().visit_index_expr(e)
        self.add_indexing_method_dependency(e, lvalue=False)

    def add_indexing_method_dependency(self, e: IndexExpr, lvalue: bool) -> None:
        method = '__setitem__' if lvalue else '__getitem__'
        self.add_operator_method_dependency(e.base, method)

    def visit_unary_expr(self, e: UnaryExpr) -> None:
        super().visit_unary_expr(e)
        if e.op == '-':
            method = '__neg__'
        elif e.op == '+':
            method = '__pos__'
        elif e.op == '~':
            method = '__invert__'
        else:
            return
        self.add_operator_method_dependency(e.expr, method)

    def visit_op_expr(self, e: OpExpr) -> None:
        super().visit_op_expr(e)
        self.process_binary_op(e.op, e.left, e.right)

    def visit_comparison_expr(self, e: ComparisonExpr) -> None:
        super().visit_comparison_expr(e)
        for i, op in enumerate(e.operators):
            left = e.operands[i]
            right = e.operands[i + 1]
            self.process_binary_op(op, left, right)
            if self.python2 and op in ('==', '!=', '<', '<=', '>', '>='):
                self.add_operator_method_dependency(left, '__cmp__')
                self.add_operator_method_dependency(right, '__cmp__')

    def process_binary_op(self, op: str, left: Expression, right: Expression) -> None:
        method = op_methods.get(op)
        if method:
            if op != 'in':
                self.add_operator_method_dependency(left, method)
            else:
                self.add_operator_method_dependency(right, method)
            rev_method = reverse_op_methods.get(method)
            if rev_method:
                self.add_operator_method_dependency(right, rev_method)

    def add_operator_method_dependency(self, e: Expression, method: str) -> None:
        typ = self.type_map.get(e)
        if typ is not None:
            self.add_operator_method_dependency_for_type(typ, method)

    def add_operator_method_dependency_for_type(self, typ: Type, method: str) -> None:
        # Note that we operator methods can't be (non-metaclass) methods of type objects.
        # TODO: TypedDict
        # TODO: metaclasses
        if isinstance(typ, TypeVarType):
            typ = typ.upper_bound
        if isinstance(typ, TupleType):
            typ = typ.fallback
        if isinstance(typ, Instance):
            trigger = make_trigger(typ.type.fullname() + '.' +  method)
            self.add_dependency(trigger)
        elif isinstance(typ, UnionType):
            for item in typ.items:
                self.add_operator_method_dependency_for_type(item, method)

    def visit_generator_expr(self, e: GeneratorExpr) -> None:
        super().visit_generator_expr(e)
        for seq in e.sequences:
            self.add_iter_dependency(seq)

    def visit_dictionary_comprehension(self, e: DictionaryComprehension) -> None:
        super().visit_dictionary_comprehension(e)
        for seq in e.sequences:
            self.add_iter_dependency(seq)

    def visit_star_expr(self, e: StarExpr) -> None:
        super().visit_star_expr(e)
        self.add_iter_dependency(e.expr)

    def visit_yield_from_expr(self, e: YieldFromExpr) -> None:
        super().visit_yield_from_expr(e)
        self.add_iter_dependency(e.expr)

    # Helpers

    def add_dependency(self, trigger: str, target: Optional[str] = None) -> None:
        """Add depedency from trigger to a target.

        If the target is not given explicitly, use the current target.
        """
        if target is None:
            target = self.current()
        if trigger.startswith(('<builtins.', '<typing.')):
            # Don't track dependencies to certain builtins to keep the size of
            # the dependencies manageable. These dependencies should only
            # change on mypy version updates, which will require a full rebuild
            # anyway.
            return
        self.map.setdefault(trigger, set()).add(target)

    def add_type_dependencies(self, typ: Type, target: Optional[str] = None) -> None:
        for trigger in get_type_dependencies(typ):
            self.add_dependency(trigger, target)

    def add_attribute_dependency(self, typ: Type, name: str) -> None:
        # TODO: use attribute_triggers
        if isinstance(typ, TypeVarType):
            typ = typ.upper_bound
        if isinstance(typ, TupleType):
            typ = typ.fallback
        if isinstance(typ, Instance):
            member = '%s.%s' % (typ.type.fullname(), name)
            self.add_dependency(make_trigger(member))
        elif isinstance(typ, FunctionLike) and typ.is_type_obj():
            member = '%s.%s' % (typ.type_object().fullname(), name)
            self.add_dependency(make_trigger(member))
        elif isinstance(typ, UnionType):
            for item in typ.items:
                self.add_attribute_dependency(item, name)

    def attribute_triggers(self, typ: Type, name: str) -> List[str]:
        if isinstance(typ, TypeVarType):
            typ = typ.upper_bound
        if isinstance(typ, TupleType):
            typ = typ.fallback
        if isinstance(typ, Instance):
            member = '%s.%s' % (typ.type.fullname(), name)
            return [make_trigger(member)]
        elif isinstance(typ, FunctionLike) and typ.is_type_obj():
            member = '%s.%s' % (typ.type_object().fullname(), name)
            return [make_trigger(member)]
        elif isinstance(typ, UnionType):
            targets = []
            for item in typ.items:
                targets.extend(self.attribute_triggers(item, name))
            return targets
        else:
            return []

    def add_attribute_dependency_for_expr(self, e: Expression, name: str) -> None:
        typ = self.type_map.get(e)
        if typ is not None:
            self.add_attribute_dependency(typ, name)

    def add_iter_dependency(self, node: Expression) -> None:
        typ = self.type_map.get(node)
        if typ:
            self.add_attribute_dependency(typ, '__iter__')

    def push(self, component: str) -> str:
        target = '%s.%s' % (self.target_stack[-1], component)
        self.stack.append(target)
        self.target_stack.append(target)
        return target

    def push_class(self, name: str) -> str:
        self.stack.append(self.stack[-1])
        target = '%s.%s' % (self.target_stack[-1], name)
        self.target_stack.append(target)
        return target

    def pop(self) -> None:
        self.stack.pop()
        self.target_stack.pop()

    def current(self) -> str:
        """Return the current target."""
        return self.stack[-1]

    def enter_scope(self, node: Node) -> None:
        self.scope_stack.append(node)

    def leave_scope(self) -> None:
        self.scope_stack.pop()

    def current_scope(self) -> Node:
        return self.scope_stack[-1]


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
        # TODO: fallback?
        triggers = []
        for arg in typ.arg_types:
            triggers.extend(get_type_dependencies(arg))
        triggers.extend(get_type_dependencies(typ.ret_type))
        return triggers

    def visit_overloaded(self, typ: Overloaded) -> List[str]:
        triggers = []
        for item in typ.items():
            triggers.extend(get_type_dependencies(item))
        return triggers

    def visit_deleted_type(self, typ: DeletedType) -> List[str]:
        return []

    def visit_partial_type(self, typ: PartialType) -> List[str]:
        assert False, "Should not see a partial type here"

    def visit_tuple_type(self, typ: TupleType) -> List[str]:
        triggers = []
        for item in typ.items:
            triggers.extend(get_type_dependencies(item))
        triggers.extend(get_type_dependencies(typ.fallback))
        return triggers

    def visit_type_type(self, typ: TypeType) -> List[str]:
        return get_type_dependencies(typ.item)

    def visit_forwardref_type(self, typ: ForwardRef) -> List[str]:
        assert False, 'Internal error: Leaked forward reference object {}'.format(typ)

    def visit_type_var(self, typ: TypeVarType) -> List[str]:
        # TODO: bound (values?)
        triggers = []
        if typ.fullname:
            triggers.append(make_trigger(typ.fullname))
        return triggers

    def visit_typeddict_type(self, typ: TypedDictType) -> List[str]:
        raise NotImplementedError

    def visit_unbound_type(self, typ: UnboundType) -> List[str]:
        return []

    def visit_uninhabited_type(self, typ: UninhabitedType) -> List[str]:
        return []

    def visit_union_type(self, typ: UnionType) -> List[str]:
        triggers = []
        for item in typ.items:
            triggers.extend(get_type_dependencies(item))
        return triggers


def non_trivial_bases(info: TypeInfo) -> List[TypeInfo]:
    return [base for base in info.mro[1:]
            if base.fullname() != 'builtins.object']


def dump_all_dependencies(modules: Dict[str, MypyFile],
                          type_map: Dict[Expression, Type],
                          python_version: Tuple[int, int]) -> None:
    for id, node in modules.items():
        if id in ('builtins', 'typing') or 'typeshed' in node.path:
            continue
        print('[%s]' % id)
        deps = get_dependencies(id, node, type_map, python_version)
        for trigger, targets in deps.items():
            print('%s: %s' % (trigger, sorted(targets)))
