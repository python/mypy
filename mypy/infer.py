"""Utilities for type argument inference."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple, NewType, cast
from typing_extensions import TypeIs

from mypy.constraints import (
    SUBTYPE_OF,
    SUPERTYPE_OF,
    infer_constraints,
    infer_constraints_for_callable,
)
from mypy.nodes import ARG_POS, ArgKind, TypeInfo
from mypy.solve import solve_constraints
from mypy.tuple_normal_form import TupleNormalForm
from mypy.typeops import make_simplified_union
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    ParamSpecType,
    ProperType,
    TupleType,
    Type,
    TypeList,
    TypeOfAny,
    TypeVarId,
    TypeVarLikeType,
    TypeVarTupleType,
    TypeVarType,
    UninhabitedType,
    UnionType,
    UnpackType,
    flatten_nested_tuples,
    get_proper_type,
)

IterableType = NewType("IterableType", Instance)
"""Represents an instance of `Iterable[T]`."""
TupleInstanceType = NewType("TupleInstanceType", Instance)
"""Represents an instance of `tuple[T, ...]`."""


class ArgumentInferContext(NamedTuple):
    """Type argument inference context.

    We need this because we pass around ``Mapping`` and ``Iterable`` types.
    These types are only known by ``TypeChecker`` itself.
    It is required for ``*`` and ``**`` argument inference.

    https://github.com/python/mypy/issues/11144
    """

    mapping_type: Instance
    iterable_type: Instance
    function_type: Instance
    tuple_typeinfo: TypeInfo

    @property
    def fallback_tuple(self) -> Instance:
        r"""Canonical fallback tuple type tuple[Any, ...]."""
        # NOTE: This must use ``TypeOfAny.special_form`` and not ``TypeOfAny.from_omitted_generics``,
        #   otherwise this leads to errors in dmypy SuggestionEngine.
        return Instance(self.tuple_typeinfo, [AnyType(TypeOfAny.special_form)])

    def is_iterable(self, typ: Type) -> bool:
        """Check if the type is an iterable, i.e. implements the Iterable Protocol."""
        from mypy.subtypes import is_subtype

        return is_subtype(typ, self.iterable_type)

    def is_iterable_instance_type(self, typ: Type) -> TypeIs[IterableType]:
        """Check if the type is an Iterable[T]."""
        p_t = get_proper_type(typ)
        return isinstance(p_t, Instance) and p_t.type == self.iterable_type.type

    def is_tuple_instance_type(self, typ: Type) -> TypeIs[TupleInstanceType]:
        """Check if the type is a tuple instance, i.e. tuple[T, ...]."""
        p_t = get_proper_type(typ)
        return isinstance(p_t, Instance) and p_t.type == self.tuple_typeinfo

    def make_tuple_instance_type(self, arg: Type) -> TupleInstanceType:
        """Create a TupleInstance type with the given argument type."""
        value = Instance(self.tuple_typeinfo, [arg])
        return cast(TupleInstanceType, value)

    def make_iterable_instance_type(self, arg: Type) -> IterableType:
        value = Instance(self.iterable_type.type, [arg])
        return cast(IterableType, value)

    def make_tuple_type(self, items: Sequence[Type], /) -> TupleType:
        r"""Create a proper TupleType from the given item types."""
        tnf = TupleNormalForm.from_items(items)
        return tnf.materialize(context=self)

    def materialize_tnf(self, tnf: TupleNormalForm) -> TupleType:
        r"""Construct an actual TupleType from a TupleNormalForm.

        Combines all members of the variadic part into a single tuple[T, ...] type.
        This creates an upper bound for the original `star_args` argument.

        Pays special attention to the variadic part, which may contain unexpected
        `UnpackType` members, namely `UnionType[TypeList]`.
        """

        # parse the variadic part. UninhabitedType indicated no variadic part.
        # AnyType indicates we could not properly parse the variadic part.
        parsed_variadic_part = self._parse_variadic_type(tnf.variadic)

        # check whether the unpack is considered empty
        unpacked = get_proper_type(parsed_variadic_part.type)
        is_empty_unpack = isinstance(unpacked, UninhabitedType)

        if is_empty_unpack:
            assert not tnf.suffix, f"Failed to correctly parse TupleNormalForm: {tnf}"
            return TupleType([*tnf.prefix], fallback=self.fallback_tuple)

        return TupleType(
            [*tnf.prefix, parsed_variadic_part, *tnf.suffix], fallback=self.fallback_tuple
        )

    def as_iterable_type(self, typ: Type) -> IterableType | AnyType:
        r"""Reinterpret a type as Iterable[T], or return AnyType if not possible.

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
                iterable_types = cast("list[IterableType]", converted_types)
                arg = make_simplified_union([it.args[0] for it in iterable_types])
                return self.make_iterable_instance_type(arg)
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
            return self.make_iterable_instance_type(make_simplified_union(args))
        elif isinstance(p_t, UnpackType):
            return self.as_iterable_type(p_t.type)
        elif isinstance(p_t, TypeVarType):
            # for a regular TypeVar, check the upper bound.
            return self.as_iterable_type(p_t.upper_bound)
        elif isinstance(p_t, TypeVarTupleType):
            # TVT -> tuple[T₁, T₂, ..., Tₙ]
            # since this is always iterable, but the variables are not known,
            # we return Iterable[Any]
            error_type = AnyType(TypeOfAny.from_error)
            return self.make_iterable_instance_type(error_type)
        elif self.is_iterable(p_t):
            # TODO: add a 'fast path' (needs measurement) that uses the map_instance_to_supertype
            #   mechanism? (Only if it works: gh-19662)
            return self._solve_as_iterable(p_t)

        # failure case, return AnyType
        return AnyType(TypeOfAny.from_error)

    def _solve_as_iterable(self, typ: Type, /) -> IterableType | AnyType:
        r"""Use the solver to cast a type as Iterable[T].

        Returns `AnyType` if solving fails.
        """
        from mypy.constraints import infer_constraints_for_callable
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
        target = self.make_iterable_instance_type(T)
        upcast_callable = CallableType(
            variables=[T],
            arg_types=[target],
            arg_kinds=[ARG_POS],
            arg_names=[None],
            ret_type=target,
            fallback=self.function_type,
        )
        constraints = infer_constraints_for_callable(
            upcast_callable, [typ], [ARG_POS], [None], [[0]], self
        )

        (sol,), _ = solve_constraints([T], constraints)

        if sol is None:  # solving failed, return AnyType fallback
            error_type = AnyType(TypeOfAny.from_error)
            return self.make_iterable_instance_type(error_type)
        return self.make_iterable_instance_type(sol)

    def _parse_variadic_type(self, typ: UnpackType, /) -> UnpackType:
        r"""Parse the (dirty) UnpackType of a TupleNormalForm.

        A TupleNormalForm's unpack may contain the following unexpected types:

        1. UninhabitedType: indicates no variadic part
        2. TypeList: indicates concatenation of multiple variadic parts
        3. UnionType: indicates union of multiple variadic parts

        After processing with this function, the result is guaranteed to be one of:

        1. UninhabitedType: indicates no variadic part
        2. regular UnpackType content.
        """

        unpacked = get_proper_type(typ.type)

        if isinstance(unpacked, UninhabitedType):
            # this is used to indicate no variadic part
            return typ

        if isinstance(unpacked, TypeList):
            return self._materialize_variadic_concatenation(unpacked)

        elif isinstance(unpacked, UnionType):
            return self._materialize_variadic_union(unpacked)

        elif isinstance(
            unpacked, (ParamSpecType, TypeVarTupleType)
        ) or self.is_tuple_instance_type(unpacked):
            # already a proper element. Just return it.
            return typ

        # otherwise, cast to Iterable[T] using the solver, and then return tuple[T, ...]
        r = self.as_iterable_type(unpacked)
        if isinstance(r, AnyType):
            return UnpackType(self.make_tuple_instance_type(r))
        return UnpackType(self.make_tuple_instance_type(r.args[0]))

    def _materialize_variadic_concatenation(self, unpacked: TypeList) -> UnpackType:
        """Convert a concatenation of UnpackType / items into a single UnpackType."""
        parsed_items: list[ProperType] = []
        for proper_item in map(get_proper_type, unpacked.items):
            if isinstance(proper_item, UnpackType):
                # recurse when seeing UnpackType
                proper_item = self._parse_variadic_type(proper_item)
            parsed_items.append(proper_item)

        if not parsed_items:
            # empty concatenation, return UnpackType[Never] to indicate no variadic part
            return UnpackType(UninhabitedType())

        if len(parsed_items) == 1 and isinstance(unpack := parsed_items[0], UnpackType):
            # single unpack, just return it directly
            return unpack

        # more than one unpack: cast every member as Iterable[T] and unify the T's
        item_types: list[Type] = []
        for item in parsed_items:
            if isinstance(item, UnpackType):
                # cast to Iterable[T] (or Any.from_error)
                iterable_type = self.as_iterable_type(item.type)
                item_type = (
                    iterable_type.args[0] if isinstance(iterable_type, Instance) else iterable_type
                )
                item_types.append(item_type)
            else:
                item_types.append(item)
        unified_item_type = make_simplified_union(item_types)
        return UnpackType(self.make_tuple_instance_type(unified_item_type))

    def _materialize_variadic_union(self, unpacked: UnionType) -> UnpackType:
        """Convert a Union of UnpackType into a single UnpackType."""
        # Currently, Union of star args are not part of the typing spec.
        # Therefore, we need to reunify such unpackings.
        # We create an upper bound by converting each union item to an iterable,
        # and then returning the tuple unpacking *tuple[U₁ | U₂ | ... | Uₙ, ...]
        # See Also: https://discuss.python.org/t/should-unions-of-tuples-tvts-be-allowed-inside-unpack/102608

        # NOTE: We want to use set here, but we actually need stable ordering for unit tests.
        parsed_items: list[UnpackType] = []
        seen_items: set[UnpackType] = set()
        for proper_item in unpacked.proper_items:
            # unions members should all be UnpackType themselves
            assert isinstance(proper_item, UnpackType)
            parsed_item = self._parse_variadic_type(proper_item)
            if parsed_item not in seen_items:
                parsed_items.append(parsed_item)
            seen_items.add(parsed_item)

        if not parsed_items:
            return UnpackType(UninhabitedType())

        if len(parsed_items) == 1:
            return parsed_items[0]

        # more than one unpack: cast every member as Iterable[T] and unify the T's
        item_types: list[Type] = []
        for item in parsed_items:
            # cast to Iterable[T] (or Any.from_error)
            iterable_type = self.as_iterable_type(item.type)
            item_type = (
                iterable_type.args[0] if isinstance(iterable_type, Instance) else iterable_type
            )
            item_types.append(item_type)
        unified_item_type = make_simplified_union(item_types)
        return UnpackType(self.make_tuple_instance_type(unified_item_type))

    def _unify_multiple_unpacks(self, items: list[Type]) -> list[Type]:
        r"""If multiple UnpackType are present, unify them into a single Unpack[tuple[T, ...]]."""
        # algorithm very similar to TupleNormalForm.from_items
        seen_unpacks = 0
        prefix_items: list[Type] = []
        unpack_items: list[Type] = []
        suffix_items: list[Type] = []

        for item in flatten_nested_tuples(items):
            if isinstance(item, UnpackType):
                seen_unpacks += 1
                unpack_items.extend(suffix_items)
                unpack_items.append(item)
                suffix_items.clear()
            elif seen_unpacks:
                suffix_items.append(item)
            else:
                prefix_items.append(item)

        if seen_unpacks <= 1:
            # we can just use the original list
            return items

        # unify all members of unpack_items into a single tuple[T, ...]
        item_types = []
        for item in unpack_items:
            if isinstance(item, UnpackType):
                # cast to Iterable[T] (or Any.from_error)
                iterable_type = self.as_iterable_type(item.type)
                item_type = (
                    iterable_type.args[0] if isinstance(iterable_type, Instance) else iterable_type
                )
                item_types.append(item_type)
            else:
                item_types.append(item)

        unified_item_type = make_simplified_union(item_types)
        unified_unpacked = UnpackType(self.make_tuple_instance_type(unified_item_type))
        return [*prefix_items, unified_unpacked, *suffix_items]


def infer_function_type_arguments(
    callee_type: CallableType,
    arg_types: Sequence[Type | None],
    arg_kinds: list[ArgKind],
    arg_names: Sequence[str | None] | None,
    formal_to_actual: list[list[int]],
    context: ArgumentInferContext,
    strict: bool = True,
    allow_polymorphic: bool = False,
) -> tuple[list[Type | None], list[TypeVarLikeType]]:
    """Infer the type arguments of a generic function.

    Return an array of lower bound types for the type variables -1 (at
    index 0), -2 (at index 1), etc. A lower bound is None if a value
    could not be inferred.

    Arguments:
      callee_type: the target generic function
      arg_types: argument types at the call site (each optional; if None,
                 we are not considering this argument in the current pass)
      arg_kinds: nodes.ARG_* values for arg_types
      formal_to_actual: mapping from formal to actual variable indices
    """
    # Infer constraints.
    constraints = infer_constraints_for_callable(
        callee_type, arg_types, arg_kinds, arg_names, formal_to_actual, context
    )

    # Solve constraints.
    type_vars = callee_type.variables
    return solve_constraints(type_vars, constraints, strict, allow_polymorphic)


def infer_type_arguments(
    type_vars: Sequence[TypeVarLikeType],
    template: Type,
    actual: Type,
    is_supertype: bool = False,
    skip_unsatisfied: bool = False,
) -> list[Type | None]:
    # Like infer_function_type_arguments, but only match a single type
    # against a generic type.
    constraints = infer_constraints(template, actual, SUPERTYPE_OF if is_supertype else SUBTYPE_OF)
    return solve_constraints(type_vars, constraints, skip_unsatisfied=skip_unsatisfied)[0]
