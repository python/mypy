"""Generate fine-grained dependencies for AST nodes, for use in the daemon mode.

Dependencies are stored in a map from *triggers* to *sets of affected locations*.

A trigger is a string that represents a program property that has changed, such
as the signature of a specific function. Triggers are written as '<...>' (angle
brackets). When a program property changes, we determine the relevant trigger(s)
and all affected locations. The latter are stale and will have to be reprocessed.

An affected location is a string than can refer to a *target* (a non-nested
function or method, or a module top level), a class, or a trigger (for
recursively triggering other triggers).

Here's an example represention of a simple dependency map (in format
"<trigger> -> locations"):

  <m.A.g> -> m.f
  <m.A> -> <m.f>, m.A, m.f

Assuming 'A' is a class, this means that

1) if a property of 'm.A.g', such as the signature, is changed, we need
   to process target (function) 'm.f'

2) if the MRO or other significant property of class 'm.A' changes, we
   need to process target 'm.f', the entire class 'm.A', and locations
   triggered by trigger '<m.f>' (this explanation is a bit simplified;
   see below for more details).

The triggers to fire are determined using mypy.server.astdiff.

Examples of triggers:

* '<mod.x>' represents a module attribute/function/class. If any externally
  visible property of 'x' changes, this gets fired. For changes within
  classes, only "big" changes cause the class to be triggered (such as a
  change in MRO). Smaller changes, such as changes to some attributes, don't
  trigger the entire class.
* '<mod.Cls.x>' represents the type and kind of attribute/method 'x' of
  class 'mod.Cls'. This can also refer to an attribute inherited from a
  base class (relevant if it's accessed through a value of type 'Cls'
  instead of the base class type).
* '<package.mod>' represents the existence of module 'package.mod'. This
  gets triggered if 'package.mod' is created or deleted, or if it gets
  changed into something other than a module.

Examples of locations:

* 'mod' is the top level of module 'mod' (doesn't include any function bodies,
  but includes class bodies not nested within a function).
* 'mod.f' is function 'f' in module 'mod' (module-level variables aren't separate
  locations but are included in the module top level). Functions also include
  any nested functions and classes -- such nested definitions aren't separate
  locations, for simplicity of implementation.
* 'mod.Cls.f' is method 'f' of 'mod.Cls'. Non-method attributes aren't locations.
* 'mod.Cls' represents each method in class 'mod.Cls' + the top-level of the
  module 'mod'. (To simplify the implementation, there is no location that only
  includes the body of a class without the entire surrounding module top level.)
* Trigger '<...>' as a location is an indirect way of referring to to all
  locations triggered by the trigger. These indirect locations keep the
  dependency map smaller and easier to manage.

Triggers can be triggered by program changes such as these:

* Addition or deletion of an attribute (or module).
* Change of the kind of thing a name represents (such as a change from a function
  to a class).
* Change of the static type of a name.

Changes in the body of a function that aren't reflected in the signature don't
cause the function to be triggered. More generally, we trigger only on changes
that may affect type checking results outside the module that contains the
change.

We don't generate dependencies from builtins and certain other stdlib modules,
since these change very rarely, and they would just increase the size of the
dependency map significantly without significant benefit.

Test cases for this module live in 'test-data/unit/deps*.test'.
"""

from typing import Dict, List, Set, Optional, Tuple, Union, DefaultDict

from mypy.checkmember import bind_self
from mypy.nodes import (
    Node, Expression, MypyFile, FuncDef, ClassDef, AssignmentStmt, NameExpr, MemberExpr, Import,
    ImportFrom, CallExpr, CastExpr, TypeVarExpr, TypeApplication, IndexExpr, UnaryExpr, OpExpr,
    ComparisonExpr, GeneratorExpr, DictionaryComprehension, StarExpr, PrintStmt, ForStmt, WithStmt,
    TupleExpr, ListExpr, OperatorAssignmentStmt, DelStmt, YieldFromExpr, Decorator, Block,
    TypeInfo, FuncBase, OverloadedFuncDef, RefExpr, SuperExpr, Var, NamedTupleExpr, TypedDictExpr,
    LDEF, MDEF, GDEF, FuncItem,
    op_methods, reverse_op_methods, ops_with_inplace_method, unary_op_methods
)
from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, Instance, AnyType, NoneTyp, TypeVisitor, CallableType, DeletedType, PartialType,
    TupleType, TypeType, TypeVarType, TypedDictType, UnboundType, UninhabitedType, UnionType,
    FunctionLike, ForwardRef, Overloaded
)
from mypy.server.trigger import make_trigger
from mypy.util import correct_relative_import


def get_dependencies(target: MypyFile,
                     type_map: Dict[Expression, Type],
                     python_version: Tuple[int, int]) -> Dict[str, Set[str]]:
    """Get all dependencies of a node, recursively."""
    visitor = DependencyVisitor(type_map, python_version)
    visitor.alias_deps = target.alias_deps
    target.accept(visitor)
    return visitor.map


def get_dependencies_of_target(module_id: str,
                               module_tree: MypyFile,
                               target: Node,
                               type_map: Dict[Expression, Type],
                               python_version: Tuple[int, int]) -> Dict[str, Set[str]]:
    """Get dependencies of a target -- don't recursive into nested targets."""
    # TODO: Add tests for this function.
    visitor = DependencyVisitor(type_map, python_version)
    visitor.alias_deps = module_tree.alias_deps
    visitor.scope.enter_file(module_id)
    if isinstance(target, MypyFile):
        # Only get dependencies of the top-level of the module. Don't recurse into
        # functions.
        for defn in target.defs:
            # TODO: Recurse into top-level statements and class bodies but skip functions.
            if not isinstance(defn, (ClassDef, Decorator, FuncDef, OverloadedFuncDef)):
                defn.accept(visitor)
    elif isinstance(target, FuncBase) and target.info:
        # It's a method.
        # TODO: Methods in nested classes.
        visitor.scope.enter_class(target.info)
        target.accept(visitor)
        visitor.scope.leave()
    else:
        target.accept(visitor)
    visitor.scope.leave()
    return visitor.map


class DependencyVisitor(TraverserVisitor):
    alias_deps = None  # type: DefaultDict[Union[MypyFile, FuncItem, ClassDef], Set[str]]

    def __init__(self,
                 type_map: Dict[Expression, Type],
                 python_version: Tuple[int, int]) -> None:
        self.scope = Scope()
        self.type_map = type_map
        self.python2 = python_version[0] == 2
        self.map = {}  # type: Dict[str, Set[str]]
        self.is_class = False
        self.is_package_init_file = False

    # TODO (incomplete):
    #   from m import *
    #   await
    #   protocols
    #   metaclasses
    #   functional enum
    #   type variable with value restriction

    def visit_mypy_file(self, o: MypyFile) -> None:
        self.scope.enter_file(o.fullname())
        self.is_package_init_file = o.is_package_init_file()
        if o in self.alias_deps:
            for alias in self.alias_deps[o]:
                self.add_dependency(make_trigger(alias))
        super().visit_mypy_file(o)
        self.scope.leave()

    def visit_func_def(self, o: FuncDef) -> None:
        self.scope.enter_function(o)
        target = self.scope.current_target()
        if o.type:
            if self.is_class and isinstance(o.type, FunctionLike):
                signature = bind_self(o.type)  # type: Type
            else:
                signature = o.type
            for trigger in get_type_triggers(signature):
                self.add_dependency(trigger)
                self.add_dependency(trigger, target=make_trigger(target))
        if o.info:
            for base in non_trivial_bases(o.info):
                self.add_dependency(make_trigger(base.fullname() + '.' + o.name()))
        if o in self.alias_deps:
            for alias in self.alias_deps[o]:
                self.add_dependency(make_trigger(alias))
        super().visit_func_def(o)
        self.scope.leave()

    def visit_decorator(self, o: Decorator) -> None:
        self.add_dependency(make_trigger(o.func.fullname()))
        super().visit_decorator(o)

    def visit_class_def(self, o: ClassDef) -> None:
        self.scope.enter_class(o.info)
        target = self.scope.current_full_target()
        self.add_dependency(make_trigger(target), target)
        old_is_class = self.is_class
        self.is_class = True
        # Add dependencies to type variables of a generic class.
        for tv in o.type_vars:
            self.add_dependency(make_trigger(tv.fullname), target)
        # Add dependencies to base types.
        for base in o.info.bases:
            self.add_type_dependencies(base, target=target)
        if o.info.tuple_type:
            self.add_type_dependencies(o.info.tuple_type, target=make_trigger(target))
        if o.info.typeddict_type:
            self.add_type_dependencies(o.info.typeddict_type, target=make_trigger(target))
        # TODO: Add dependencies based on remaining TypeInfo attributes.
        super().visit_class_def(o)
        if o in self.alias_deps:
            for alias in self.alias_deps[o]:
                self.add_dependency(make_trigger(alias))
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
        self.scope.leave()

    def visit_import(self, o: Import) -> None:
        for id, as_id in o.ids:
            # TODO: as_id
            self.add_dependency(make_trigger(id), self.scope.current_target())

    def visit_import_from(self, o: ImportFrom) -> None:
        module_id, _ = correct_relative_import(self.scope.current_module_id(),
                                               o.relative,
                                               o.id,
                                               self.is_package_init_file)
        for name, as_name in o.names:
            self.add_dependency(make_trigger(module_id + '.' + name))

    def visit_block(self, o: Block) -> None:
        if not o.is_unreachable:
            super().visit_block(o)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        # TODO: Implement all assignment special forms, including these:
        #   Enum
        #   type aliases
        rvalue = o.rvalue
        if isinstance(rvalue, CallExpr) and isinstance(rvalue.analyzed, TypeVarExpr):
            # TODO: Support type variable value restriction
            analyzed = rvalue.analyzed
            self.add_type_dependencies(analyzed.upper_bound,
                                       target=make_trigger(analyzed.fullname()))
        elif isinstance(rvalue, CallExpr) and isinstance(rvalue.analyzed, NamedTupleExpr):
            # Depend on types of named tuple items.
            info = rvalue.analyzed.info
            prefix = '%s.%s' % (self.scope.current_full_target(), info.name())
            for name, symnode in info.names.items():
                if not name.startswith('_') and isinstance(symnode.node, Var):
                    typ = symnode.node.type
                    if typ:
                        self.add_type_dependencies(typ)
                        self.add_type_dependencies(typ, target=make_trigger(prefix))
                        attr_target = make_trigger('%s.%s' % (prefix, name))
                        self.add_type_dependencies(typ, target=attr_target)
        elif isinstance(rvalue, CallExpr) and isinstance(rvalue.analyzed, TypedDictExpr):
            # Depend on the underlying typeddict type
            info = rvalue.analyzed.info
            assert info.typeddict_type is not None
            prefix = '%s.%s' % (self.scope.current_full_target(), info.name())
            self.add_type_dependencies(info.typeddict_type, target=make_trigger(prefix))
        else:
            # Normal assignment
            super().visit_assignment_stmt(o)
            for lvalue in o.lvalues:
                self.process_lvalue(lvalue)
            items = o.lvalues + [rvalue]
            for i in range(len(items) - 1):
                lvalue = items[i]
                rvalue = items[i + 1]
                if isinstance(lvalue, TupleExpr):
                    self.add_attribute_dependency_for_expr(rvalue, '__iter__')
            if o.type:
                for trigger in get_type_triggers(o.type):
                    self.add_dependency(trigger)

    def process_lvalue(self, lvalue: Expression) -> None:
        """Generate additional dependencies for an lvalue."""
        if isinstance(lvalue, IndexExpr):
            self.add_operator_method_dependency(lvalue.base, '__setitem__')
        elif isinstance(lvalue, NameExpr):
            if lvalue.kind in (MDEF, GDEF):
                # Assignment to an attribute in the class body, or direct assignment to a
                # global variable.
                lvalue_type = self.get_non_partial_lvalue_type(lvalue)
                type_triggers = get_type_triggers(lvalue_type)
                attr_trigger = make_trigger('%s.%s' % (self.scope.current_full_target(),
                                                       lvalue.name))
                for type_trigger in type_triggers:
                    self.add_dependency(type_trigger, attr_trigger)
        elif isinstance(lvalue, MemberExpr):
            if lvalue.kind is None:
                # Reference to a non-module attribute
                if lvalue.expr not in self.type_map:
                    # Unreachable assignment -> not checked so no dependencies to generate.
                    return
                object_type = self.type_map[lvalue.expr]
                lvalue_type = self.get_non_partial_lvalue_type(lvalue)
                type_triggers = get_type_triggers(lvalue_type)
                for attr_trigger in self.attribute_triggers(object_type, lvalue.name):
                    for type_trigger in type_triggers:
                        self.add_dependency(type_trigger, attr_trigger)
        elif isinstance(lvalue, TupleExpr):
            for item in lvalue.items:
                self.process_lvalue(item)
        # TODO: star lvalue

    def get_non_partial_lvalue_type(self, lvalue: RefExpr) -> Type:
        if lvalue not in self.type_map:
            # Likely a block considered unreachable during type checking.
            return UninhabitedType()
        lvalue_type = self.type_map[lvalue]
        if isinstance(lvalue_type, PartialType):
            if isinstance(lvalue.node, Var) and lvalue.node.type:
                lvalue_type = lvalue.node.type
            else:
                # Probably a secondary, non-definition assignment that doesn't
                # result in a non-partial type. We won't be able to infer any
                # dependencies from this so just return something. (The first,
                # definition assignment with a partial type is handled
                # differently, in the semantic analyzer.)
                assert not lvalue.is_new_def
                return UninhabitedType()
        return lvalue_type

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
        # __getitem__ is only used if __iter__ is missing but for simplicity we
        # just always depend on both.
        self.add_attribute_dependency_for_expr(o.expr, '__iter__')
        self.add_attribute_dependency_for_expr(o.expr, '__getitem__')
        self.process_lvalue(o.index)
        if isinstance(o.index, TupleExpr):
            # Process multiple assignment to index variables.
            item_type = o.inferred_item_type
            if item_type:
                # This is similar to above.
                self.add_attribute_dependency(item_type, '__iter__')
                self.add_attribute_dependency(item_type, '__getitem__')
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

    def process_global_ref_expr(self, o: RefExpr) -> None:
        if o.fullname is not None:
            self.add_dependency(make_trigger(o.fullname))

        # If this is a reference to a type, generate a dependency to its
        # constructor.
        # TODO: avoid generating spurious dependencies for isinstancce checks,
        # except statements, class attribute reference, etc, if perf problem.
        typ = self.type_map.get(o)
        if isinstance(typ, FunctionLike) and typ.is_type_obj():
            class_name = typ.type_object().fullname()
            self.add_dependency(make_trigger(class_name + '.__init__'))

    def visit_name_expr(self, o: NameExpr) -> None:
        if o.kind == LDEF:
            # We don't track depdendencies to local variables, since they
            # aren't externally visible.
            return
        if o.kind == MDEF:
            # Direct reference to member is only possible in the scope that
            # defined the name, so no dependency is required.
            return
        self.process_global_ref_expr(o)

    def visit_member_expr(self, e: MemberExpr) -> None:
        super().visit_member_expr(e)
        if e.kind is not None:
            # Reference to a module attribute
            self.process_global_ref_expr(e)
        else:
            # Reference to a non-module attribute
            if e.expr not in self.type_map:
                # No type available -- this happens for unreachable code. Since it's unreachable,
                # it wasn't type checked and we don't need to generate dependencies.
                return
            typ = self.type_map[e.expr]
            self.add_attribute_dependency(typ, e.name)

    def visit_super_expr(self, e: SuperExpr) -> None:
        super().visit_super_expr(e)
        if e.info is not None:
            self.add_dependency(make_trigger(e.info.fullname() + '.' + e.name))

    def visit_call_expr(self, e: CallExpr) -> None:
        super().visit_call_expr(e)

    def visit_cast_expr(self, e: CastExpr) -> None:
        super().visit_cast_expr(e)
        self.add_type_dependencies(e.type)

    def visit_type_application(self, e: TypeApplication) -> None:
        super().visit_type_application(e)
        for typ in e.types:
            self.add_type_dependencies(typ)

    def visit_index_expr(self, e: IndexExpr) -> None:
        super().visit_index_expr(e)
        self.add_operator_method_dependency(e.base, '__getitem__')

    def visit_unary_expr(self, e: UnaryExpr) -> None:
        super().visit_unary_expr(e)
        if e.op not in unary_op_methods:
            return
        method = unary_op_methods[e.op]
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
            if op == 'in':
                self.add_operator_method_dependency(right, method)
            else:
                self.add_operator_method_dependency(left, method)
                rev_method = reverse_op_methods.get(method)
                if rev_method:
                    self.add_operator_method_dependency(right, rev_method)

    def add_operator_method_dependency(self, e: Expression, method: str) -> None:
        typ = self.type_map.get(e)
        if typ is not None:
            self.add_operator_method_dependency_for_type(typ, method)

    def add_operator_method_dependency_for_type(self, typ: Type, method: str) -> None:
        # Note that operator methods can't be (non-metaclass) methods of type objects
        # (that is, TypeType objects or Callables representing a type).
        # TODO: TypedDict
        # TODO: metaclasses
        if isinstance(typ, TypeVarType):
            typ = typ.upper_bound
        if isinstance(typ, TupleType):
            typ = typ.fallback
        if isinstance(typ, Instance):
            trigger = make_trigger(typ.type.fullname() + '.' + method)
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
        """Add dependency from trigger to a target.

        If the target is not given explicitly, use the current target.
        """
        if trigger.startswith(('<builtins.', '<typing.')):
            # Don't track dependencies to certain builtins to keep the size of
            # the dependencies manageable. These dependencies should only
            # change on mypy version updates, which will require a full rebuild
            # anyway.
            return
        if target is None:
            target = self.scope.current_target()
        self.map.setdefault(trigger, set()).add(target)

    def add_type_dependencies(self, typ: Type, target: Optional[str] = None) -> None:
        """Add dependencies to all components of a type.

        Args:
            target: If not None, override the default (current) target of the
                generated dependency.
        """
        # TODO: Use this method in more places where get_type_triggers() + add_dependency()
        #       are called together.
        for trigger in get_type_triggers(typ):
            self.add_dependency(trigger, target)

    def add_attribute_dependency(self, typ: Type, name: str) -> None:
        """Add dependencies for accessing a named attribute of a type."""
        targets = self.attribute_triggers(typ, name)
        for target in targets:
            self.add_dependency(target)

    def attribute_triggers(self, typ: Type, name: str) -> List[str]:
        """Return all triggers associated with the attribute of a type."""
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
        elif isinstance(typ, TypeType):
            # TODO: Metaclass attribute lookup
            return self.attribute_triggers(typ.item, name)
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


class Scope:
    """Track which target we are processing at any given time."""

    def __init__(self) -> None:
        self.module = None  # type: Optional[str]
        self.classes = []  # type: List[TypeInfo]
        self.function = None  # type: Optional[FuncDef]
        # Number of nested scopes ignored (that don't get their own separate targets)
        self.ignored = 0

    def current_module_id(self) -> str:
        assert self.module
        return self.module

    def current_target(self) -> str:
        """Return the current target (non-class; for a class return enclosing module)."""
        assert self.module
        target = self.module
        if self.function:
            if self.classes:
                target += '.' + '.'.join(c.name() for c in self.classes)
            target += '.' + self.function.name()
        return target

    def current_full_target(self) -> str:
        """Return the current target (may be a class)."""
        assert self.module
        target = self.module
        if self.classes:
            target += '.' + '.'.join(c.name() for c in self.classes)
        if self.function:
            target += '.' + self.function.name()
        return target

    def enter_file(self, prefix: str) -> None:
        self.module = prefix
        self.classes = []
        self.function = None
        self.ignored = 0

    def enter_function(self, fdef: FuncDef) -> None:
        if not self.function:
            self.function = fdef
        else:
            # Nested functions are part of the topmost function target.
            self.ignored += 1

    def enter_class(self, info: TypeInfo) -> None:
        """Enter a class target scope."""
        if not self.function:
            self.classes.append(info)
        else:
            # Classes within functions are part of the enclosing function target.
            self.ignored += 1

    def leave(self) -> None:
        """Leave the innermost scope (can be any kind of scope)."""
        if self.ignored:
            # Leave a scope that's included in the enclosing target.
            self.ignored -= 1
        elif self.function:
            # Function is always the innermost target.
            self.function = None
        elif self.classes:
            # Leave the innermost class.
            self.classes.pop()
        else:
            # Leave module.
            assert self.module
            self.module = None


def get_type_triggers(typ: Type) -> List[str]:
    """Return all triggers that correspond to a type becoming stale."""
    return typ.accept(TypeTriggersVisitor())


class TypeTriggersVisitor(TypeVisitor[List[str]]):
    def __init__(self) -> None:
        self.deps = []  # type: List[str]

    def visit_instance(self, typ: Instance) -> List[str]:
        trigger = make_trigger(typ.type.fullname())
        triggers = [trigger]
        for arg in typ.args:
            triggers.extend(get_type_triggers(arg))
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
            triggers.extend(get_type_triggers(arg))
        triggers.extend(get_type_triggers(typ.ret_type))
        return triggers

    def visit_overloaded(self, typ: Overloaded) -> List[str]:
        triggers = []
        for item in typ.items():
            triggers.extend(get_type_triggers(item))
        return triggers

    def visit_deleted_type(self, typ: DeletedType) -> List[str]:
        return []

    def visit_partial_type(self, typ: PartialType) -> List[str]:
        assert False, "Should not see a partial type here"

    def visit_tuple_type(self, typ: TupleType) -> List[str]:
        triggers = []
        for item in typ.items:
            triggers.extend(get_type_triggers(item))
        triggers.extend(get_type_triggers(typ.fallback))
        return triggers

    def visit_type_type(self, typ: TypeType) -> List[str]:
        return get_type_triggers(typ.item)

    def visit_forwardref_type(self, typ: ForwardRef) -> List[str]:
        assert False, 'Internal error: Leaked forward reference object {}'.format(typ)

    def visit_type_var(self, typ: TypeVarType) -> List[str]:
        # TODO: bound (values?)
        triggers = []
        if typ.fullname:
            triggers.append(make_trigger(typ.fullname))
        return triggers

    def visit_typeddict_type(self, typ: TypedDictType) -> List[str]:
        triggers = []
        for item in typ.items.values():
            triggers.extend(get_type_triggers(item))
        triggers.extend(get_type_triggers(typ.fallback))
        return triggers

    def visit_unbound_type(self, typ: UnboundType) -> List[str]:
        return []

    def visit_uninhabited_type(self, typ: UninhabitedType) -> List[str]:
        return []

    def visit_union_type(self, typ: UnionType) -> List[str]:
        triggers = []
        for item in typ.items:
            triggers.extend(get_type_triggers(item))
        return triggers


def non_trivial_bases(info: TypeInfo) -> List[TypeInfo]:
    return [base for base in info.mro[1:]
            if base.fullname() != 'builtins.object']


def dump_all_dependencies(modules: Dict[str, MypyFile],
                          type_map: Dict[Expression, Type],
                          python_version: Tuple[int, int]) -> None:
    """Generate dependencies for all interesting modules and print them to stdout."""
    all_deps = {}  # type: Dict[str, Set[str]]
    for id, node in modules.items():
        # Uncomment for debugging:
        # print('processing', id)
        if id in ('builtins', 'typing') or '/typeshed/' in node.path:
            continue
        assert id == node.fullname()
        deps = get_dependencies(node, type_map, python_version)
        for trigger, targets in deps.items():
            all_deps.setdefault(trigger, set()).update(targets)

    for trigger, targets in sorted(all_deps.items(), key=lambda x: x[0]):
        print(trigger)
        for target in sorted(targets):
            print('    %s' % target)
