from typing import Dict, Tuple, List, cast

from mypy.types import (
    Type, Instance, CallableType, TypeVisitor, UnboundType, ErrorType, AnyType,
    Void, NoneTyp, TypeVarType, Overloaded, TupleType, UnionType, ErasedType, TypeList,
    PartialType, DeletedType
)


def expand_type(typ: Type, env: Dict[int, Type]) -> Type:
    """Substitute any type variable references in a type given by a type
    environment.
    """

    return typ.accept(ExpandTypeVisitor(env))


def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    """Substitute type variables in type using values from an Instance."""

    if instance.args == []:
        return typ
    else:
        variables = {}  # type: Dict[int, Type]
        for i in range(len(instance.args)):
            variables[i + 1] = instance.args[i]
        typ = expand_type(typ, variables)
        if isinstance(typ, CallableType):
            bounds = []  # type: List[Tuple[int, Type]]
            for j in range(len(instance.args)):
                bounds.append((j + 1, instance.args[j]))
            typ = update_callable_implicit_bounds(cast(CallableType, typ), bounds)
        else:
            pass
        return typ


class ExpandTypeVisitor(TypeVisitor[Type]):
    """Visitor that substitutes type variables with values."""

    variables = None  # type: Dict[int, Type]  # TypeVar id -> TypeVar value

    def __init__(self, variables: Dict[int, Type]) -> None:
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
            inst = cast(Instance, repl)
            # Return copy of instance with type erasure flag on.
            return Instance(inst.type, inst.args, inst.line, True)
        else:
            return repl

    def visit_callable_type(self, t: CallableType) -> Type:
        return t.copy_modified(arg_types=self.expand_types(t.arg_types),
                               ret_type=t.ret_type.accept(self),
                               bound_vars=self.expand_bound_vars(t.bound_vars))

    def visit_overloaded(self, t: Overloaded) -> Type:
        items = []  # type: List[CallableType]
        for item in t.items():
            items.append(cast(CallableType, item.accept(self)))
        return Overloaded(items)

    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.expand_types(t.items), t.fallback, t.line)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.expand_types(t.items), t.line)

    def visit_partial_type(self, t: PartialType) -> Type:
        return t

    def expand_types(self, types: List[Type]) -> List[Type]:
        a = []  # type: List[Type]
        for t in types:
            a.append(t.accept(self))
        return a

    def expand_bound_vars(
            self, types: List[Tuple[int, Type]]) -> List[Tuple[int, Type]]:
        a = []  # type: List[Tuple[int, Type]]
        for id, t in types:
            a.append((id, t.accept(self)))
        return a


def update_callable_implicit_bounds(
        t: CallableType, arg_types: List[Tuple[int, Type]]) -> CallableType:
    # FIX what if there are existing bounds?
    return t.copy_modified(bound_vars=arg_types)
