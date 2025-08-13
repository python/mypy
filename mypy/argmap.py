"""Utilities for mapping between actual and formal arguments (and their types)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Callable
from typing_extensions import TypeGuard

from mypy import nodes
from mypy.maptype import map_instance_to_supertype
from mypy.typeops import make_simplified_union
from mypy.types import (
    AnyType,
    Instance,
    ParamSpecType,
    ProperType,
    TupleType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeVarTupleType,
    UnionType,
    UnpackType,
    get_proper_type,
)

if TYPE_CHECKING:
    from mypy.infer import ArgumentInferContext


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
        self.kwargs_used: set[str] = set()
        # Type context for `*` and `**` arg kinds.
        self.context = context

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ArgTypeExpander):
            return (
                self.tuple_index == other.tuple_index
                and self.kwargs_used == other.kwargs_used
                and self.context == other.context
            )
        return NotImplemented

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
            if isinstance(actual_type, UnionType):
                proper_types = [get_proper_type(t) for t in actual_type.items]
                # special case: union of equal sized tuples.  (e.g. `tuple[int, int] | tuple[None, None]`)
                if is_equal_sized_tuples(proper_types):
                    # transform union of tuples into a tuple of unions
                    # e.g. tuple[A, B, C] | tuple[None, None, None] -> tuple[A | None, B | None, C | None]
                    tuple_args: list[Type] = [
                        make_simplified_union(items)
                        for items in zip(*(t.items for t in proper_types))
                    ]
                    actual_type = TupleType(
                        tuple_args,
                        # use Iterable[A | B | C] as the fallback type
                        fallback=Instance(
                            self.context.iterable_type.type, [UnionType.make_union(tuple_args)]
                        ),
                    )
                else:
                    # reinterpret all union items as iterable types (if possible)
                    # and return the union of the iterable item types results.
                    from mypy.subtypes import is_subtype

                    iterable_type = self.context.iterable_type

                    def as_iterable_type(t: Type) -> Type:
                        """Map a type to the iterable supertype if it is a subtype."""
                        p_t = get_proper_type(t)
                        if isinstance(p_t, Instance) and is_subtype(t, iterable_type):
                            return map_instance_to_supertype(p_t, iterable_type.type)
                        if isinstance(p_t, TupleType):
                            # Convert tuple[A, B, C] to Iterable[A | B | C].
                            return Instance(iterable_type.type, [make_simplified_union(p_t.items)])
                        return t

                    # create copies of self for each item in the union
                    sub_expanders = [
                        ArgTypeExpander(context=self.context) for _ in actual_type.items
                    ]
                    for expander in sub_expanders:
                        expander.tuple_index = int(self.tuple_index)
                        expander.kwargs_used = set(self.kwargs_used)

                    candidate_type = make_simplified_union(
                        [
                            e.expand_actual_type(
                                as_iterable_type(item),
                                actual_kind,
                                formal_name,
                                formal_kind,
                                allow_unpack,
                            )
                            for e, item in zip(sub_expanders, actual_type.items)
                        ]
                    )
                    assert all(expander == sub_expanders[0] for expander in sub_expanders)
                    # carry over the new state if all sub-expanders are the same state
                    self.tuple_index = int(sub_expanders[0].tuple_index)
                    self.kwargs_used = set(sub_expanders[0].kwargs_used)
                    return candidate_type

            if isinstance(actual_type, TypeVarTupleType):
                # This code path is hit when *Ts is passed to a callable and various
                # special-handling didn't catch this. The best thing we can do is to use
                # the upper bound.
                actual_type = get_proper_type(actual_type.upper_bound)
            if isinstance(actual_type, Instance) and actual_type.args:
                from mypy.subtypes import is_subtype

                if is_subtype(actual_type, self.context.iterable_type):
                    return map_instance_to_supertype(
                        actual_type, self.context.iterable_type.type
                    ).args[0]
                else:
                    # We cannot properly unpack anything other
                    # than `Iterable` type with `*`.
                    # Just return `Any`, other parts of code would raise
                    # a different error for improper use.
                    return AnyType(TypeOfAny.from_error)
            elif isinstance(actual_type, TupleType):
                # Get the next tuple item of a tuple *arg.
                if self.tuple_index >= len(actual_type.items):
                    # Exhausted a tuple -- continue to the next *args.
                    self.tuple_index = 1
                else:
                    self.tuple_index += 1
                item = actual_type.items[self.tuple_index - 1]
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
            elif isinstance(actual_type, ParamSpecType):
                # ParamSpec is valid in *args but it can't be unpacked.
                return actual_type
            else:
                return AnyType(TypeOfAny.from_error)
        elif actual_kind == nodes.ARG_STAR2:
            from mypy.subtypes import is_subtype

            if isinstance(actual_type, TypedDictType):
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


def is_equal_sized_tuples(types: Sequence[ProperType]) -> TypeGuard[Sequence[TupleType]]:
    """Check if all types are tuples of the same size."""
    if not types:
        return True

    iterator = iter(types)
    first = next(iterator)
    if not isinstance(first, TupleType):
        return False
    size = first.length()

    for item in iterator:
        if not isinstance(item, TupleType) or item.length() != size:
            return False
    return True
