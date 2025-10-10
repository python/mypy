"""Utilities for mapping between actual and formal arguments (and their types)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Callable, cast
from typing_extensions import NewType, TypeGuard, TypeIs

from mypy import nodes
from mypy.maptype import map_instance_to_supertype
from mypy.typeops import make_simplified_union
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    ParamSpecType,
    ProperType,
    TupleType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeVarId,
    TypeVarTupleType,
    TypeVarType,
    UnionType,
    UnpackType,
    flatten_nested_tuples,
    get_proper_type,
)

if TYPE_CHECKING:
    from mypy.infer import ArgumentInferContext


IterableType = NewType("IterableType", Instance)
"""Represents an instance of `Iterable[T]`."""


def map_actuals_to_formals(
    actual_kinds: list[nodes.ArgKind],
    actual_names: Sequence[str | None] | None,
    formal_kinds: list[nodes.ArgKind],
    formal_names: Sequence[str | None],
    actual_arg_type: Callable[[int], Type],
) -> list[list[int]]:
    """Calculate mapping between actual (caller) args and formals.

    The result contains a list of caller argument indexes mapping to each
    callee argument index, indexed by callee index.

    The caller_arg_type argument should evaluate to the type of the actual
    argument type with the given index.
    """
    nformals = len(formal_kinds)
    formal_to_actual: list[list[int]] = [[] for i in range(nformals)]
    ambiguous_actual_kwargs: list[int] = []
    fi = 0
    for ai, actual_kind in enumerate(actual_kinds):
        if actual_kind == nodes.ARG_POS:
            if fi < nformals:
                if not formal_kinds[fi].is_star():
                    formal_to_actual[fi].append(ai)
                    fi += 1
                elif formal_kinds[fi] == nodes.ARG_STAR:
                    formal_to_actual[fi].append(ai)
        elif actual_kind == nodes.ARG_STAR:
            # We need to know the actual type to map varargs.
            actualt = get_proper_type(actual_arg_type(ai))

            # Special case for union of equal sized tuples.
            if (
                isinstance(actualt, UnionType)
                and actualt.items
                and is_equal_sized_tuples(
                    proper_types := [get_proper_type(t) for t in actualt.items]
                )
            ):
                # pick an arbitrary member
                actualt = proper_types[0]
            if isinstance(actualt, TupleType):
                # A tuple actual maps to a fixed number of formals.
                for _ in range(len(actualt.items)):
                    if fi < nformals:
                        if formal_kinds[fi] != nodes.ARG_STAR2:
                            formal_to_actual[fi].append(ai)
                        else:
                            break
                        if formal_kinds[fi] != nodes.ARG_STAR:
                            fi += 1
            else:
                # Assume that it is an iterable (if it isn't, there will be
                # an error later).
                while fi < nformals:
                    if formal_kinds[fi].is_named(star=True):
                        break
                    else:
                        formal_to_actual[fi].append(ai)
                    if formal_kinds[fi] == nodes.ARG_STAR:
                        break
                    fi += 1
        elif actual_kind.is_named():
            assert actual_names is not None, "Internal error: named kinds without names given"
            name = actual_names[ai]
            if name in formal_names and formal_kinds[formal_names.index(name)] != nodes.ARG_STAR:
                formal_to_actual[formal_names.index(name)].append(ai)
            elif nodes.ARG_STAR2 in formal_kinds:
                formal_to_actual[formal_kinds.index(nodes.ARG_STAR2)].append(ai)
        else:
            assert actual_kind == nodes.ARG_STAR2
            actualt = get_proper_type(actual_arg_type(ai))
            if isinstance(actualt, TypedDictType):
                for name in actualt.items:
                    if name in formal_names:
                        formal_to_actual[formal_names.index(name)].append(ai)
                    elif nodes.ARG_STAR2 in formal_kinds:
                        formal_to_actual[formal_kinds.index(nodes.ARG_STAR2)].append(ai)
            else:
                # We don't exactly know which **kwargs are provided by the
                # caller, so we'll defer until all the other unambiguous
                # actuals have been processed
                ambiguous_actual_kwargs.append(ai)

    if ambiguous_actual_kwargs:
        # Assume the ambiguous kwargs will fill the remaining arguments.
        #
        # TODO: If there are also tuple varargs, we might be missing some potential
        #       matches if the tuple was short enough to not match everything.
        unmatched_formals = [
            fi
            for fi in range(nformals)
            if (
                formal_names[fi]
                and (
                    not formal_to_actual[fi]
                    or actual_kinds[formal_to_actual[fi][0]] == nodes.ARG_STAR
                )
                and formal_kinds[fi] != nodes.ARG_STAR
            )
            or formal_kinds[fi] == nodes.ARG_STAR2
        ]
        for ai in ambiguous_actual_kwargs:
            for fi in unmatched_formals:
                formal_to_actual[fi].append(ai)

    return formal_to_actual


def map_formals_to_actuals(
    actual_kinds: list[nodes.ArgKind],
    actual_names: Sequence[str | None] | None,
    formal_kinds: list[nodes.ArgKind],
    formal_names: list[str | None],
    actual_arg_type: Callable[[int], Type],
) -> list[list[int]]:
    """Calculate the reverse mapping of map_actuals_to_formals."""
    formal_to_actual = map_actuals_to_formals(
        actual_kinds, actual_names, formal_kinds, formal_names, actual_arg_type
    )
    # Now reverse the mapping.
    actual_to_formal: list[list[int]] = [[] for _ in actual_kinds]
    for formal, actuals in enumerate(formal_to_actual):
        for actual in actuals:
            actual_to_formal[actual].append(formal)
    return actual_to_formal


class ArgTypeExpander:
    """Utility class for mapping actual argument types to formal arguments.

    One of the main responsibilities is to expand caller tuple *args and TypedDict
    **kwargs, and to keep track of which tuple/TypedDict items have already been
    consumed.

    Example:

       def f(x: int, *args: str) -> None: ...
       f(*(1, 'x', 1.1))

    We'd call expand_actual_type three times:

      1. The first call would provide 'int' as the actual type of 'x' (from '1').
      2. The second call would provide 'str' as one of the actual types for '*args'.
      2. The third call would provide 'float' as one of the actual types for '*args'.

    A single instance can process all the arguments for a single call. Each call
    needs a separate instance since instances have per-call state.
    """

    def __init__(self, context: ArgumentInferContext) -> None:
        # Next tuple *args index to use.
        self.tuple_index = 0
        # Keyword arguments in TypedDict **kwargs used.
        self.kwargs_used: set[str] | None = None
        # Type context for `*` and `**` arg kinds.
        self.context = context

    def expand_actual_type(
        self,
        actual_type: Type,
        actual_kind: nodes.ArgKind,
        formal_name: str | None,
        formal_kind: nodes.ArgKind,
        allow_unpack: bool = False,
    ) -> Type:
        """Return the actual (caller) type(s) of a formal argument with the given kinds.

        If the actual argument is a tuple *args, return the next individual tuple item that
        maps to the formal arg.

        If the actual argument is a TypedDict **kwargs, return the next matching typed dict
        value type based on formal argument name and kind.

        This is supposed to be called for each formal, in order. Call multiple times per
        formal if multiple actuals map to a formal.
        """
        original_actual = actual_type
        actual_type = get_proper_type(actual_type)
        if actual_kind == nodes.ARG_STAR:
            # parse *args as one of the following:
            #    IterableType | TupleType | ParamSpecType | AnyType
            star_args_type = self.parse_star_args_type(actual_type)

            if self.is_iterable_instance_type(star_args_type):
                return star_args_type.args[0]
            elif isinstance(star_args_type, TupleType):
                # Get the next tuple item of a tuple *arg.
                if self.tuple_index >= len(star_args_type.items):
                    # Exhausted a tuple -- continue to the next *args.
                    self.tuple_index = 1
                else:
                    self.tuple_index += 1
                item = star_args_type.items[self.tuple_index - 1]
                if isinstance(item, UnpackType) and not allow_unpack:
                    # An unpack item that doesn't have special handling, use upper bound as above.
                    unpacked = get_proper_type(item.type)
                    if isinstance(unpacked, TypeVarTupleType):
                        fallback = get_proper_type(unpacked.upper_bound)
                    else:
                        fallback = unpacked
                    assert (
                        isinstance(fallback, Instance)
                        and fallback.type.fullname == "builtins.tuple"
                    )
                    item = fallback.args[0]
                return item
            elif isinstance(star_args_type, ParamSpecType):
                # ParamSpec is valid in *args but it can't be unpacked.
                return star_args_type
            else:
                return AnyType(TypeOfAny.from_error)
        elif actual_kind == nodes.ARG_STAR2:
            from mypy.subtypes import is_subtype

            if isinstance(actual_type, TypedDictType):
                if self.kwargs_used is None:
                    self.kwargs_used = set()
                if formal_kind != nodes.ARG_STAR2 and formal_name in actual_type.items:
                    # Lookup type based on keyword argument name.
                    assert formal_name is not None
                else:
                    # Pick an arbitrary item if no specified keyword is expected.
                    formal_name = (set(actual_type.items.keys()) - self.kwargs_used).pop()
                self.kwargs_used.add(formal_name)
                return actual_type.items[formal_name]
            elif isinstance(actual_type, Instance) and is_subtype(
                actual_type, self.context.mapping_type
            ):
                # Only `Mapping` type can be unpacked with `**`.
                # Other types will produce an error somewhere else.
                return map_instance_to_supertype(actual_type, self.context.mapping_type.type).args[
                    1
                ]
            elif isinstance(actual_type, ParamSpecType):
                # ParamSpec is valid in **kwargs but it can't be unpacked.
                return actual_type
            else:
                return AnyType(TypeOfAny.from_error)
        else:
            # No translation for other kinds -- 1:1 mapping.
            return original_actual

    def is_iterable(self, typ: Type) -> bool:
        """Check if the type is an iterable, i.e. implements the Iterable Protocol."""
        from mypy.subtypes import is_subtype

        return is_subtype(typ, self.context.iterable_type)

    def is_iterable_instance_type(self, typ: Type) -> TypeIs[IterableType]:
        """Check if the type is an Iterable[T]."""
        p_t = get_proper_type(typ)
        return isinstance(p_t, Instance) and p_t.type == self.context.iterable_type.type

    def _make_iterable_instance_type(self, arg: Type) -> IterableType:
        value = Instance(self.context.iterable_type.type, [arg])
        return cast(IterableType, value)

    def _solve_as_iterable(self, typ: Type) -> IterableType | AnyType:
        r"""Use the solver to cast a type as Iterable[T].

        Returns `AnyType` if solving fails.
        """
        from mypy.constraints import infer_constraints_for_callable
        from mypy.nodes import ARG_POS
        from mypy.solve import solve_constraints

        # We first create an upcast function:
        #    def [T] (Iterable[T]) -> Iterable[T]: ...
        # and then solve for T, given the input type as the argument.
        T = TypeVarType(
            "T",
            "T",
            TypeVarId(-1),
            values=[],
            upper_bound=AnyType(TypeOfAny.from_omitted_generics),
            default=AnyType(TypeOfAny.from_omitted_generics),
        )
        target = self._make_iterable_instance_type(T)
        upcast_callable = CallableType(
            variables=[T],
            arg_types=[target],
            arg_kinds=[ARG_POS],
            arg_names=[None],
            ret_type=target,
            fallback=self.context.function_type,
        )
        constraints = infer_constraints_for_callable(
            upcast_callable, [typ], [ARG_POS], [None], [[0]], self.context
        )

        (sol,), _ = solve_constraints([T], constraints)

        if sol is None:  # solving failed, return AnyType fallback
            return AnyType(TypeOfAny.from_error)
        return self._make_iterable_instance_type(sol)

    def as_iterable_type(self, typ: Type) -> IterableType | AnyType:
        """Reinterpret a type as Iterable[T], or return AnyType if not possible.

        This function specially handles certain types like UnionType, TupleType, and UnpackType.
        Otherwise, the upcasting is performed using the solver.
        """
        p_t = get_proper_type(typ)
        if self.is_iterable_instance_type(p_t) or isinstance(p_t, AnyType):
            return p_t
        elif isinstance(p_t, UnionType):
            # If the type is a union, map each item to the iterable supertype.
            # the return the combined iterable type Iterable[A] | Iterable[B] -> Iterable[A | B]
            converted_types = [self.as_iterable_type(get_proper_type(item)) for item in p_t.items]

            if any(not self.is_iterable_instance_type(it) for it in converted_types):
                # if any item could not be interpreted as Iterable[T], we return AnyType
                return AnyType(TypeOfAny.from_error)
            else:
                # all items are iterable, return Iterable[T₁ | T₂ | ... | Tₙ]
                iterable_types = cast(list[IterableType], converted_types)
                arg = make_simplified_union([it.args[0] for it in iterable_types])
                return self._make_iterable_instance_type(arg)
        elif isinstance(p_t, TupleType):
            # maps tuple[A, B, C] -> Iterable[A | B | C]
            # note: proper_elements may contain UnpackType, for instance with
            #   tuple[None, *tuple[None, ...]]..
            proper_elements = [get_proper_type(t) for t in flatten_nested_tuples(p_t.items)]
            args: list[Type] = []
            for p_e in proper_elements:
                if isinstance(p_e, UnpackType):
                    r = self.as_iterable_type(p_e)
                    if self.is_iterable_instance_type(r):
                        args.append(r.args[0])
                    else:
                        # this *should* never happen, since UnpackType should
                        # only contain TypeVarTuple or a variable length tuple.
                        # However, we could get an `AnyType(TypeOfAny.from_error)`
                        # if for some reason the solver was triggered and failed.
                        args.append(r)
                else:
                    args.append(p_e)
            return self._make_iterable_instance_type(make_simplified_union(args))
        elif isinstance(p_t, UnpackType):
            return self.as_iterable_type(p_t.type)
        elif isinstance(p_t, (TypeVarType, TypeVarTupleType)):
            return self.as_iterable_type(p_t.upper_bound)
        elif self.is_iterable(p_t):
            # TODO: add a 'fast path' (needs measurement) that uses the map_instance_to_supertype
            #   mechanism? (Only if it works: gh-19662)
            return self._solve_as_iterable(p_t)
        return AnyType(TypeOfAny.from_error)

    def parse_star_args_type(
        self, typ: Type
    ) -> TupleType | IterableType | ParamSpecType | AnyType:
        """Parse the type of a ``*args`` argument.

        Returns one of TupleType, IterableType, ParamSpecType or AnyType.
        Returns AnyType(TypeOfAny.from_error) if the type cannot be parsed or is invalid.
        """
        p_t = get_proper_type(typ)
        if isinstance(p_t, (TupleType, ParamSpecType, AnyType)):
            # just return the type as-is
            return p_t
        elif isinstance(p_t, TypeVarTupleType):
            return self.parse_star_args_type(p_t.upper_bound)
        elif isinstance(p_t, UnionType):
            proper_items = [get_proper_type(t) for t in p_t.items]
            # consider 2 cases:
            # 1. Union of equal sized tuples, e.g. tuple[A, B] | tuple[None, None]
            #    In this case transform union of same-sized tuples into a tuple of unions
            #    e.g. tuple[A, B] | tuple[None, None] -> tuple[A | None, B | None]
            if is_equal_sized_tuples(proper_items):

                tuple_args: list[Type] = [
                    make_simplified_union(items) for items in zip(*(t.items for t in proper_items))
                ]
                actual_type = TupleType(
                    tuple_args,
                    # use Iterable[A | B | C] as the fallback type
                    fallback=Instance(
                        self.context.iterable_type.type, [UnionType.make_union(tuple_args)]
                    ),
                )
                return actual_type
            # 2. Union of iterable types, e.g. Iterable[A] | Iterable[B]
            #    In this case return Iterable[A | B]
            #    Note that this covers unions of differently sized tuples as well.
            else:
                converted_types = [self.as_iterable_type(p_i) for p_i in proper_items]
                if all(self.is_iterable_instance_type(it) for it in converted_types):
                    # all items are iterable, return Iterable[T1 | T2 | ... | Tn]
                    iterables = cast(list[IterableType], converted_types)
                    arg = make_simplified_union([it.args[0] for it in iterables])
                    return self._make_iterable_instance_type(arg)
                else:
                    # some items in the union are not iterable, return AnyType
                    return AnyType(TypeOfAny.from_error)
        elif self.is_iterable_instance_type(parsed := self.as_iterable_type(p_t)):
            # in all other cases, we try to reinterpret the type as Iterable[T]
            return parsed
        return AnyType(TypeOfAny.from_error)


def is_equal_sized_tuples(types: Sequence[ProperType]) -> TypeGuard[Sequence[TupleType]]:
    """Check if all types are tuples of the same size.

    We use `flatten_nested_tuples` to deal with nested tuples.
    Note that the result may still contain
    """
    if not types:
        return True

    iterator = iter(types)
    typ = next(iterator)
    if not isinstance(typ, TupleType):
        return False
    flattened_elements = flatten_nested_tuples(typ.items)
    if any(
        isinstance(get_proper_type(member), (UnpackType, TypeVarTupleType))
        for member in flattened_elements
    ):
        # this can happen e.g. with tuple[int, *tuple[int, ...], int]
        return False
    size = len(flattened_elements)

    for typ in iterator:
        if not isinstance(typ, TupleType):
            return False
        flattened_elements = flatten_nested_tuples(typ.items)
        if len(flattened_elements) != size or any(
            isinstance(get_proper_type(member), (UnpackType, TypeVarTupleType))
            for member in flattened_elements
        ):
            # this can happen e.g. with tuple[int, *tuple[int, ...], int]
            return False
    return True
