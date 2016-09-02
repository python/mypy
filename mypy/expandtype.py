from typing import Dict, Tuple, List, cast

from mypy.types import (
    Type, Instance, CallableType, TypeVisitor, UnboundType, ErrorType, AnyType,
    Void, NoneTyp, TypeVarType, Overloaded, TupleType, UnionType, ErasedType, TypeList,
    PartialType, DeletedType, UninhabitedType, TypeType, TypeVarId
)


def expand_type(typ: Type, env: Dict[TypeVarId, Type]) -> Type:
    """Substitute any type variable references in a type given by a type
    environment.
    """

    return typ.accept(ExpandTypeVisitor(env))


def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    """Substitute type variables in type using values from an Instance.
    Type variables are considered to be bound by the class declaration."""

    if instance.args == []:
        return typ
    else:
        variables = {}  # type: Dict[TypeVarId, Type]
        for binder, arg in zip(instance.type.defn.type_vars, instance.args):
            variables[binder.id] = arg
        return expand_type(typ, variables)


class ExpandTypeVisitor(TypeVisitor[Type]):
    """Visitor that substitutes type variables with values."""

    variables = None  # type: Dict[TypeVarId, Type]  # TypeVar id -> TypeVar value

    def __init__(self, variables: Dict[TypeVarId, Type]) -> None:
        self.variables = variables

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return t

    def visit_error_type(self, t: ErrorType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        assert False, 'Not supported'

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_void(self, t: Void) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        # Should not get here.
        raise RuntimeError()

    def visit_instance(self, t: Instance) -> Type:
        args = self.expand_types(t.args)
        return Instance(t.type, args, t.line)

    def visit_type_var(self, t: TypeVarType) -> Type:
        repl = self.variables.get(t.id, t)
        if isinstance(repl, Instance):
            inst = repl
            # Return copy of instance with type erasure flag on.
            return Instance(inst.type, inst.args, inst.line, True)
        else:
            return repl

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.expand_types(t.arg_types),
                               ret_type=t.ret_type.accept(self))

    def visit_overloaded(self, t: Overloaded) -> Type:
        items = []  # type: List[CallableType]
        for item in t.items():
            items.append(cast(CallableType, item.accept(self)))
        return Overloaded(items)

    def visit_tuple_type(self, t: TupleType) -> Type:
        return t.copy_modified(items=self.expand_types(t.items))

    def visit_union_type(self, t: UnionType) -> Type:
        # After substituting for type variables in t.items,
        # some of the resulting types might be subtypes of others.
        return UnionType.make_simplified_union(self.expand_types(t.items), t.line)

    def visit_partial_type(self, t: PartialType) -> Type:
        return t

    def visit_type_type(self, t: TypeType) -> Type:
        # TODO: Verify that the new item type is valid (instance or
        # union of instances or Any).  Sadly we can't report errors
        # here yet.
        item = t.item.accept(self)
        return TypeType(item)

    def expand_types(self, types: List[Type]) -> List[Type]:
        a = []  # type: List[Type]
        for t in types:
            a.append(t.accept(self))
        return a
