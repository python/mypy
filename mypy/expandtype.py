from typing import Dict, Tuple, List, cast, Undefined

from mypy.types import (
    Type, Instance, Callable, TypeVisitor, UnboundType, ErrorType, AnyType,
    Void, NoneTyp, TypeVar, Overloaded, TupleType, UnionType, ErasedType, TypeList
)


def expand_type(typ: Type, map: Dict[int, Type]) -> Type:
    """Substitute any type variable references in a type with given values."""

    return typ.accept(ExpandTypeVisitor(map))


def expand_type_by_instance(typ: Type, instance: Instance) -> Type:
    """Substitute type variables in type using values from an Instance."""

    if instance.args == []:
        return typ
    else:
        variables = {}  # type: Dict[int, Type]
        for i in range(len(instance.args)):
            variables[i + 1] = instance.args[i]
        typ = expand_type(typ, variables)
        if isinstance(typ, Callable):
            bounds = []  # type: List[Tuple[int, Type]]
            for j in range(len(instance.args)):
                bounds.append((j + 1, instance.args[j]))
            typ = update_callable_implicit_bounds(cast(Callable, typ), bounds)
        else:
            pass
        return typ


class ExpandTypeVisitor(TypeVisitor[Type]):
    """Visitor that substitutes type variables with values."""

    variables = Undefined(Dict[int, Type])  # typevar id -> value

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

    def visit_erased_type(self, t: ErasedType) -> Type:
        # Should not get here.
        raise RuntimeError()

    def visit_instance(self, t: Instance) -> Type:
        args = self.expand_types(t.args)
        return Instance(t.type, args, t.line, t.repr)

    def visit_type_var(self, t: TypeVar) -> Type:
        repl = self.variables.get(t.id, t)
        if isinstance(repl, Instance):
            inst = cast(Instance, repl)
            # Return copy of instance with type erasure flag on.
            return Instance(inst.type, inst.args, inst.line, inst.repr, True)
        else:
            return repl

    def visit_callable(self, t: Callable) -> Type:
        return Callable(self.expand_types(t.arg_types),
                        t.arg_kinds,
                        t.arg_names,
                        t.ret_type.accept(self),
                        t.fallback,
                        t.name,
                        t.variables,
                        self.expand_bound_vars(t.bound_vars), t.line, t.repr)

    def visit_overloaded(self, t: Overloaded) -> Type:
        items = []  # type: List[Callable]
        for item in t.items():
            items.append(cast(Callable, item.accept(self)))
        return Overloaded(items)

    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.expand_types(t.items), t.fallback, t.line, t.repr)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.expand_types(t.items), t.line, t.repr)

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
        t: Callable, arg_types: List[Tuple[int, Type]]) -> Callable:
    # FIX what if there are existing bounds?
    return Callable(t.arg_types,
                    t.arg_kinds,
                    t.arg_names,
                    t.ret_type,
                    t.fallback,
                    t.name,
                    t.variables,
                    arg_types, t.line, t.repr)


def expand_caller_var_args(arg_types: List[Type],
                           fixed_argc: int) -> Tuple[List[Type], Type]:
    """Expand the caller argument types in a varargs call.

    Fixedargc is the maximum number of fixed arguments that the target
    function accepts.

    Return (fixed argument types, type of the rest of the arguments). Return
    (None, None) if the last (vararg) argument had an invalid type. If the
    vararg argument was not an array (nor dynamic), the last item in the
    returned tuple is None.
    """

    if isinstance(arg_types[-1], TupleType):
        return arg_types[:-1] + (cast(TupleType, arg_types[-1])).items, None
    else:
        item_type = Undefined  # type: Type
        if isinstance(arg_types[-1], AnyType):
            item_type = AnyType()
        elif isinstance(arg_types[-1], Instance) and (
                cast(Instance, arg_types[-1]).type.fullname() ==
                'builtins.list'):
            # List.
            item_type = (cast(Instance, arg_types[-1])).args[0]
        else:
            return None, None

        if len(arg_types) > fixed_argc:
            return arg_types[:-1], item_type
        else:
            return (arg_types[:-1] +
                    [item_type] * (fixed_argc - len(arg_types) + 1), item_type)
