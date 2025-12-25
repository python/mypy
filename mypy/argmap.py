"""Utilities for mapping between actual and formal arguments (and their types)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from mypy import nodes
from mypy.maptype import map_instance_to_supertype
from mypy.nodes import ARG_NAMED, ARG_NAMED_OPT, ARG_OPT, ARG_POS, ARG_STAR, ARG_STAR2
from mypy.tuple_normal_form import TupleHelper, TupleNormalForm
from mypy.types import (
    AnyType,
    Instance,
    ParamSpecType,
    TupleType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeVarTupleType,
    UninhabitedType,
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

    The actual_arg_type argument should evaluate to the type of the actual
    argument with the given index.
    """
    nformals = len(formal_kinds)
    formal_to_actual: list[list[int]] = [[] for i in range(nformals)]
    ambiguous_actual_kwargs: list[int] = []
    fi = 0
    for ai, actual_kind in enumerate(actual_kinds):
        if actual_kind == ARG_POS:
            if fi < nformals:
                if formal_kinds[fi] in (ARG_POS, ARG_OPT):
                    formal_to_actual[fi].append(ai)
                    fi += 1
                elif formal_kinds[fi] == ARG_STAR:
                    formal_to_actual[fi].append(ai)
        elif actual_kind == ARG_STAR:
            # convert the actual argument type to a tuple-like type
            star_arg_type = TupleNormalForm.from_star_argument(actual_arg_type(ai))

            # for a variadic argument use a negative value, so it remains truthy when decremented
            # otherwise, use the length of the prefix.
            num_actual_items = -1 if star_arg_type.is_variadic else len(star_arg_type.prefix)
            # note: empty tuple star-args will not get mapped to anything
            while fi < nformals and num_actual_items:
                if formal_kinds[fi] in (ARG_POS, ARG_OPT, ARG_STAR):
                    formal_to_actual[fi].append(ai)
                    num_actual_items -= 1
                if formal_kinds[fi] in (ARG_STAR, ARG_NAMED, ARG_NAMED_OPT, ARG_STAR2):
                    break
                fi += 1
        elif actual_kind.is_named():
            assert actual_names is not None, "Internal error: named kinds without names given"
            name = actual_names[ai]
            if name in formal_names and formal_kinds[formal_names.index(name)] != nodes.ARG_STAR:
                formal_to_actual[formal_names.index(name)].append(ai)
            elif ARG_STAR2 in formal_kinds:
                formal_to_actual[formal_kinds.index(ARG_STAR2)].append(ai)
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

    def parse_star_argument(self, star_arg: Type, /) -> TupleType:
        r"""Parse the type of ``*args`` argument into a tuple type.

        Note: For star parameters, use `parse_star_parameter` instead.
        """
        tnf = TupleNormalForm.from_star_argument(star_arg)
        return tnf.materialize(self.context)

    def parse_star_parameter(self, star_param: Type, /) -> TupleType:
        r"""Parse the type of a ``*args: T`` parameter into a tuple type.

        This is different from `parse_star_argument` since mypy does some translation
        for certain annotations. Below are some examples of how this works.

        | annotation            | semanal result        | parsed result           |
        |-----------------------|-----------------------|-------------------------|
        | *args: int            | int                   | tuple[*tuple[int, ...]] |
        | *args: *tuple[T, ...] | Unpack[tuple[T, ...]] | tuple[*tuple[T, ...]]   |
        | *args: *tuple[A, B]   | Unpack[tuple[A, B]]   | tuple[A, B]             |
        | *args: *Ts            | Unpack[Ts]            | tuple[*Ts]              |
        | *args: P.args         | P.args                | tuple[*P.args]          |
        """
        p_t = get_proper_type(star_param)
        if isinstance(p_t, UnpackType):
            unpacked = get_proper_type(p_t.type)
            if isinstance(unpacked, TupleType):
                return unpacked
            return TupleType([p_t], fallback=self.context.fallback_tuple)

        elif isinstance(p_t, ParamSpecType):
            # We put the ParamSpec inside an UnpackType.
            parsed = UnpackType(p_t)
            return TupleType([parsed], fallback=self.context.fallback_tuple)

        else:  # e.g. *args: int  --> *args: *tuple[int, ...]
            parsed = UnpackType(self.context.make_tuple_instance_type(p_t))
            return TupleType([parsed], fallback=self.context.fallback_tuple)

    @staticmethod
    def unparse_star_parameter(t: Type, /) -> Type:
        r"""Reverse normalizations done by parse_star_parameter.

        tuple[*tuple[T, ...]]  -> T
        tuple[A, B]            -> *tuple[A, B]
        tuple[*Ts]             -> *Ts
        tuple[*P.args]         -> P.args
        """
        p_t = get_proper_type(t)
        assert isinstance(p_t, TupleType), f"Expected a parsed star argument, got {t}"
        simplified_type = p_t.simplify()

        # convert tuple[T, ...] to plain T.
        if isinstance(simplified_type, Instance):
            assert simplified_type.type.fullname == "builtins.tuple"
            return simplified_type.args[0]
        # wrap tuple and Ts in UnpackType
        elif isinstance(simplified_type, (TupleType, TypeVarTupleType)):
            return UnpackType(simplified_type)
        # return ParamSpec as is.
        elif isinstance(simplified_type, ParamSpecType):
            return simplified_type
        else:
            assert False, f"Unexpected unpack content {simplified_type!r}"

    def expand_actual_type(
        self,
        actual_type: Type,
        actual_kind: nodes.ArgKind,
        formal_name: str | None,
        formal_kind: nodes.ArgKind,
    ) -> Type:
        """Return the actual (caller) type(s) of a formal argument with the given kinds.

        If the actual argument is a star argument *args, then:
            1. If the formal argument is positional, return the next individual tuple item that
               maps to the formal arg.
               If the tuple is exhausted, returns UninhabitedType.
            2. If the formal argument is a star parameter, returns a tuple type with the items
               that map to the formal arg by slicing.
               If the tuple is exhausted, returns an empty tuple type.

        If the actual argument is a TypedDict **kwargs, return the next matching typed dict
        value type based on formal argument name and kind.

        This is supposed to be called for each formal, in order. Call multiple times per
        formal if multiple actuals map to a formal.
        """
        original_actual = actual_type
        actual_type = get_proper_type(actual_type)

        if actual_kind == ARG_STAR:
            assert formal_kind in (ARG_POS, ARG_OPT, ARG_STAR)
            # parse *args into a TupleType.
            tuple_helper = TupleHelper(self.context.tuple_typeinfo)
            star_args_type = self.parse_star_argument(actual_type)

            # # star_args_type failed to parse. treat as if it were tuple[Any, ...]
            # if isinstance(star_args_type, AnyType):
            #     any_tuple = self.context.make_tuple_instance_type(AnyType(TypeOfAny.from_error))
            #     star_args_type = self.context.make_tuple_type([UnpackType(any_tuple)])

            assert isinstance(star_args_type, TupleType)

            # we are mapping an actual *args to positional arguments.
            if formal_kind in (ARG_POS, ARG_OPT):
                value = tuple_helper.get_item(star_args_type, self.tuple_index)
                self.tuple_index += 1

                # FIXME: In principle, None should indicate out-of-bounds access
                #   caused by an error in formal_to_actual mapping.
                # assert value is not None, "error in formal_to_actual mapping"
                # However, in some cases due to lack of machinery it can happen:
                # For example f(*[]). Then formal_to_actual is ignorant of the fact
                # that the list is empty, but when materializing the tuple we actually get an empty tuple.
                # Therefore, we currently just return UninhabitedType in this case.
                value = UninhabitedType() if value is None else value

                # if the argument is exhausted, reset the index
                if (
                    not star_args_type.is_variadic
                    and self.tuple_index >= star_args_type.minimum_length
                ):
                    self.tuple_index = 0
                return value

            # we are mapping an actual *args input to a *args formal argument.
            elif formal_kind == ARG_STAR:
                # get the slice from the current index to the end of the tuple.
                r = tuple_helper.get_slice(star_args_type, self.tuple_index, None)
                # r = star_args_type.slice(
                #     self.tuple_index, None, None, fallback=self.context.tuple_type
                # )
                self.tuple_index = 0
                # assert r is not None, f"failed to slice {star_args_type} at {self.tuple_index}"
                return r

            else:
                raise AssertionError(f"Unexpected formal kind {formal_kind} for *args")

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
