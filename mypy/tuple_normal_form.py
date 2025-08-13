from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import chain
from typing import TYPE_CHECKING, Callable, NamedTuple, NewType, cast
from typing_extensions import TypeGuard, TypeIs

from mypy.maptype import map_instance_to_supertype
from mypy.nodes import TypeInfo
from mypy.typeops import make_simplified_union
from mypy.types import (
    AnyType,
    Instance,
    ParamSpecType,
    TupleType,
    Type,
    TypeList,
    TypeOfAny,
    TypeVarTupleType,
    UninhabitedType,
    UnionType,
    UnpackType,
    flatten_nested_tuples,
    get_proper_type,
)

if TYPE_CHECKING:
    from mypy.infer import ArgumentInferContext, TupleInstanceType

DirtyUnpackType = NewType("DirtyUnpackType", UnpackType)
r"""An UnpackType that may contain unexpected members, such as TypeList or UnionType."""


def is_variadic_tuple(typ: Type, /) -> bool:
    p_t = get_proper_type(typ)
    return isinstance(p_t, TupleType) and p_t.is_variadic


def get_std_tuple_typeinfo(typ: TupleType, /) -> TypeInfo:
    """Extract the TypeInfo of 'builtins.tuple' from a TupleType."""
    fallback = typ.partial_fallback
    if fallback.type.fullname == "builtins.tuple":
        return fallback.type

    # this can happen for instance for named tuples
    for base in fallback.type.mro:
        if base.fullname == "builtins.tuple":
            return base
    raise RuntimeError("Could not find builtins.tuple in the MRO of the fallback type")


class TupleHelper:
    """Helper class for certain tuple operations."""

    tuple_typeinfo: TypeInfo

    def __init__(self, tuple_type: TypeInfo | TupleType | Instance, /) -> None:
        if isinstance(tuple_type, Instance):
            tuple_type = tuple_type.type

        if isinstance(tuple_type, TupleType):
            tuple_type = get_std_tuple_typeinfo(tuple_type)

        if tuple_type.fullname != "builtins.tuple":
            raise ValueError(f"Expected 'builtins.tuple' TypeInfo, got {tuple_type}")
        self.tuple_typeinfo = tuple_type

    @property
    def std_tuple(self) -> Instance:
        """return tuple[Any, ...]"""
        return Instance(self.tuple_typeinfo, [AnyType(TypeOfAny.from_omitted_generics)])

    def is_tuple_instance_type(self, typ: Type, /) -> TypeIs[TupleInstanceType]:
        """Check if the type is a tuple instance, i.e. tuple[T, ...]."""
        p_t = get_proper_type(typ)
        return isinstance(p_t, Instance) and p_t.type == self.tuple_typeinfo

    def is_tuple_instance_subtype(self, typ: Type, /) -> TypeGuard[Instance]:
        """Check if the type is a subtype of tuple[T, ...] for some T."""
        from mypy.subtypes import is_subtype

        p_t = get_proper_type(typ)

        if not isinstance(p_t, Instance):
            return False
        if p_t.type == self.tuple_typeinfo:
            return True
        # otherwise, check if it is a subtype of tuple[Any, ...]
        return is_subtype(typ, self.std_tuple)

    def as_tuple_instance_type(self, typ: Type, /) -> TupleInstanceType:
        r"""Upcast a subtype of tuple[T, ...] to tuple[T, ...]."""
        if not self.is_tuple_instance_subtype(typ):
            raise ValueError(f"Type {typ} is not a subtype of tuple[T, ...]")

        # TODO: does this always give the same result as the solver?
        tuple_instance = map_instance_to_supertype(typ, self.tuple_typeinfo)
        return cast("TupleInstanceType", tuple_instance)

    def make_tuple_instance_type(self, arg: Type, /) -> TupleInstanceType:
        """Create a TupleInstance type with the given argument type."""
        value = Instance(self.tuple_typeinfo, [arg])
        return cast("TupleInstanceType", value)

    def make_tuple_type(self, items: Sequence[Type], /) -> TupleType:
        r"""Create a proper TupleType from the given item types."""
        self._validate_items_for_tuple_type(items)
        # make the fallback type
        fallback = self._make_fallback_for_tuple_items(items)
        return TupleType(items, fallback=fallback)

    def get_variadic_fallback(self, unpack: UnpackType, /) -> TupleInstanceType:
        """Get a tuple fallback for the content of an UnpackType."""
        unpacked = get_proper_type(unpack.type)

        if self.is_tuple_instance_type(unpacked):
            return unpacked

        elif isinstance(unpacked, TypeVarTupleType):
            tuple_fallback = unpacked.tuple_fallback.copy_modified(
                args=[AnyType(TypeOfAny.implementation_artifact)]
            )
            assert self.is_tuple_instance_type(tuple_fallback)
            return tuple_fallback

        elif isinstance(unpacked, ParamSpecType):
            upper_bound = get_proper_type(unpacked.upper_bound)
            assert self.is_tuple_instance_type(upper_bound)
            tuple_fallback = upper_bound.copy_modified(
                args=[AnyType(TypeOfAny.implementation_artifact)]
            )
            assert self.is_tuple_instance_type(tuple_fallback)
            return tuple_fallback

        elif isinstance(unpacked, TupleType):
            raise TypeError(f"Expected unpack to be a pure variadic type, got {unpacked}")

        else:
            raise TypeError(f"Got unexpected unpack type {unpacked}")

    def _make_fallback_for_tuple_items(self, items: Sequence[Type], /) -> Instance:
        item_types = []
        for item in flatten_nested_tuples(items):
            if isinstance(item, UnpackType):
                unpacked = get_proper_type(item.type)
                if self.is_tuple_instance_type(unpacked):
                    item_types.append(unpacked.args[0])
                elif isinstance(unpacked, TypeVarTupleType):
                    item_types.append(AnyType(TypeOfAny.from_omitted_generics))
                elif isinstance(unpacked, ParamSpecType):
                    item_types.append(AnyType(TypeOfAny.from_omitted_generics))
                else:
                    assert False, f"Unexpected unpacked type: {unpacked}"
            else:
                item_types.append(item)

        combined_item_type = make_simplified_union(item_types)
        return self.make_tuple_instance_type(combined_item_type)

    def _validate_items_for_tuple_type(self, items: Sequence[Type], /) -> None:
        """Validate that the items are valid for a TupleType."""
        seen_unpack = 0
        for item in flatten_nested_tuples(items):
            if isinstance(item, UnpackType):
                seen_unpack += 1
                unpacked = get_proper_type(item.type)
                if not (
                    self.is_tuple_instance_type(unpacked)
                    or isinstance(unpacked, (TypeVarTupleType, ParamSpecType))
                ):
                    raise ValueError(
                        f"UnpackType must contain tuple[T, ...] or TypeVarTuple, got {unpacked}"
                    )
        if seen_unpack > 1:
            raise ValueError("TupleType can only have one UnpackType")

    def _get_variadic_item_type(self, tup: TupleType, /) -> Type | None:
        """Get the type of the variadic part of a tuple, or None if there is no variadic part."""
        unpack_index = tup.unpack_index
        if unpack_index is None:
            return None

        item = tup.flattened_items[unpack_index]
        assert isinstance(item, UnpackType)

        return self._get_variadic_item_type_from_unpack(item)

    def _get_variadic_item_type_from_unpack(self, unpack: UnpackType, /) -> Type:
        """Get the type of the variadic part from an UnpackType."""
        unpacked = get_proper_type(unpack.type)
        if self.is_tuple_instance_type(unpacked):
            # unpacked is tuple[T, ...], return T
            return unpacked.args[0]
        elif isinstance(unpacked, TypeVarTupleType):
            # unpacked is a TypeVarTuple, return Any
            return AnyType(TypeOfAny.from_omitted_generics)
        elif isinstance(unpacked, ParamSpecType):
            # need for some specific cases like
            return unpack
        else:
            assert False, f"Unexpected unpacked type: {unpacked}"

    def get_item(self, tup: TupleType, /, index: int) -> Type | None:
        r"""Get the item at the given index, treating the variadic part as arbitrarily long.

        Returns:
            None: If the index is out of bounds and the tuple has no variadic part.
            Type: If the index is in bounds or the tuple has no variadic part.

            Otherwise, pretend the variadic part has arbitrarily many items of the appropriate type.

            tuple[P1, ..., Pn, *Vs, S1, ..., Sm] @ index =
                Iterable_type[Vs]  if index < -m
                S[index]           if -m ≤ index < 0
                P[index]           if 0 ≤ index < n
                Iterable_type[Vs]  if index ≥ n
        """
        flattened_items = tup.flattened_items
        unpack_index = tup.unpack_index

        if unpack_index is None:
            try:
                return flattened_items[index]
            except IndexError:
                return None

        N = len(flattened_items)
        if unpack_index - N < index < unpack_index:
            return flattened_items[index]

        item = flattened_items[unpack_index]
        assert isinstance(item, UnpackType)
        return self._get_variadic_item_type_from_unpack(item)

    def get_slice(
        self, tup: TupleType, /, start: int | None, stop: int | None, step: int = 1
    ) -> TupleType:
        r"""Get a slice of the tuple, treating the variadic part as arbitrarily long.

        Returns:
            TupleType: The sliced tuple type.

                If the tuple has no variadic part, this works like regular slicing.
                If the tuple has a variadic part, the shape of the slice depends on the signs
                of start and stop, as described below:

                1. If both start and stop are same signed integers (both non-negative or both negative),
                   then we slice as if the variadic part was expanded into an infinite sequence
                   of items (whose type we get by casting the unpack type to Iterable[T] and taking T)
                2. In all other cases, this works like regular slicing, treating the variadic part as a single item.
                   However, only step=1 and step=-1 are supported in this case.

        t = tuple[P1, ..., Pn, *Vs, S1, ..., Sm]

        Depending on the sign of start, the starting point is determined as follows:
           If start ≥ 0, then start = min(start, n)
           If start < 0, then start = max(start, -m)
        which corresponds to taking items from the prefix if start is non-negative,
        and from the suffix if start is negative, but never going beyond the variadic part.

        slices that 'traverse' the variadic part always include the entire variadic part,
        irrespective of the step size.

        The slice is constructed as follows:
        - if both start and stop are within the prefix or both within the suffix,
          just do regular slicing
        - If they traverse the variadic part, create two slices and glue them with the variadic part in between.
        """
        # NOTE: This works differently from TupleType.slice!
        flattened_items = tup.flattened_items
        unpack_index = tup.unpack_index

        if unpack_index is None:
            return self.make_tuple_type(flattened_items[start:stop:step])

        variadic_part = flattened_items[unpack_index]
        assert isinstance(variadic_part, UnpackType)
        iterable_type = self._get_variadic_item_type_from_unpack(variadic_part)

        prefix_length = len(tup.prefix)
        suffix_length = len(tup.suffix)

        # clip start and stop to the valid range [-suffix_length, +prefix_length]
        clip: Callable[[int], int] = lambda x: max(min(-suffix_length, -1), min(x, prefix_length))
        start = None if start is None else clip(start)
        stop = None if stop is None else clip(stop)
        assert step != 0, "slice step cannot be zero"

        # a slice within the prefix
        if (start is None or start >= 0) and (stop is not None and stop >= 0):
            start = 0 if start is None else start
            items = [
                flattened_items[i] if i < prefix_length else iterable_type
                for i in range(start, stop, step)
            ]
        # a slice within the suffix
        elif (start is not None and start < 0) and (stop is None or stop < 0):
            stop = 0 if stop is None else stop
            items = [
                flattened_items[i] if i >= -suffix_length else iterable_type
                for i in range(start, stop, step)
            ]
        # a slice that traverses the variadic part in the forward direction
        elif (start is None or start >= 0) and (stop is None or stop < 0) and step > 0:
            assert step == 1, "Only step=+1 supported when slicing forward across variadic part"
            items = [
                *flattened_items[start:unpack_index:step],
                variadic_part,
                *flattened_items[unpack_index + 1 : stop : step],
            ]
        # a slice that traverses the variadic part in the backward direction
        elif (start is None or start < 0) and (stop is None or stop >= 0) and step < 0:
            assert step == -1, "Only step=-1 supported when slicing backward across variadic part"
            items = [
                *flattened_items[start : unpack_index + 1 : step],
                variadic_part,
                *flattened_items[unpack_index - 1 : stop : step],
            ]
        # empty slice
        else:
            items = []

        return self.make_tuple_type(items)


def _is_empty_unpack(typ: Type, /) -> TypeGuard[UnpackType]:
    """Check if the variadic part is empty."""
    proper_arg = get_proper_type(typ)
    if not isinstance(proper_arg, UnpackType):
        return False

    content = get_proper_type(proper_arg.type)
    if isinstance(content, UninhabitedType):
        return True
    elif isinstance(content, (TypeList, UnionType, TupleType)):
        return all(_is_empty_unpack(item) for item in content.items)
    # fallback: TypeVarTupleType, tuple[T, ...], list[T], etc.
    # TODO: should we try converting to Iterable[T] and check if T is UninhabitedType?
    return False


def _is_non_empty_unpack(typ: Type, /) -> TypeGuard[UnpackType]:
    """Check if the variadic part is non-empty."""
    proper_arg = get_proper_type(typ)
    if not isinstance(proper_arg, UnpackType):
        return False

    content = get_proper_type(proper_arg.type)
    if isinstance(content, UninhabitedType):
        return False
    elif isinstance(content, (TypeList, UnionType, TupleType)):
        return any(_is_non_empty_unpack(item) for item in content.items)
    # fallback: TypeVarTupleType, tuple[T, ...], list[T], etc.
    # TODO: should we try converting to Iterable[T] and check if T is UninhabitedType?
    return True


class TupleNormalForm(NamedTuple):
    r"""For a given tuple type `t`, it's Normal Form is defined as the representation:

        t = tuple[P1, ..., Pn, *Vs?, S1, ..., Sm]

    where:

        - P1, ..., Pn is the maximal statically known finite prefix of the tuple,
        - Vs is the (potentially missing) variable part of the tuple,
        - S1, ..., Sm is the maximal statically known finite suffix of the tuple
        - If the tuple has no variable part, both Vs and S1, ..., Sm are empty.

    Note:
        Special attention must be paid when constructing a tuple from a TupleNormalForm,
        since the variadic part contains unexpected `UnpackType` members,
        specifically `TypeList`, `UnionType`, `UninhabitedType` and potentially `ParamSpecType`.

        - `UnpackType[TypeList[T1, ..., Tn]]` should be interpreted as unpacking
           a concatenation of multiple variadic parts, e.g. `f(*[T1, ..., Tn])`
        - `UnpackType[UnionType[T1, ..., Tn]]` should be interpreted as unpacking
            a union of multiple variadic items `x: T1 | T2 | ... | Tn; f(*x)`
        - Note that ``*Union[A, B] is equivalent to ``Union[*A, *B]``
        - Note that ``*TypeList[*TypeList[A1, ..., An], *TypeList[B1, ... Bm]]``
          is equivalent to ``*TypeList[A1, ..., An, B1, ..., Bm]``

    Attributes:
        - prefix: the longest statically known finite prefix of the tuple
        - variadic: an improper `UnpackType` representing the variable part of the tuple
          - This can contain things that are usually not allowed in `UnpackType`, in particular:
            - `TypeList` representing concatenation of multiple variadic parts
            - `UnionType` representing a union of multiple variadic parts
            - `ParamSpecType` representing `*P.args`
        - suffix: the longest statically known finite suffix of the remaining tuple
    """

    prefix: Sequence[Type]
    variadic: DirtyUnpackType
    suffix: Sequence[Type]

    @property
    def is_variadic(self) -> bool:
        """Inspect if the tuple has a variable part."""
        return not _is_empty_unpack(self.variadic)

    @property
    def minimum_length(self) -> int:
        """The minimum length of the tuple represented by this TupleNormalForm.

        If the tuple is not variadic, this coincides with the actual length.
        """
        # NOTE: Technically the variadic part could produce additional items,
        #    if multiple unpacks are present, e.g.
        #    tuple[int, *tuple[int, ...], str, *tuple[str, ...], str]
        #    is at least length 3.
        #    However we treat this as if it were tuple[int, *tuple[T, ...], str]
        return len(self.prefix) + len(self.suffix)

    def materialize(self, context: ArgumentInferContext) -> TupleType:
        """Construct the actual TupleType from the TupleNormalForm.

        Since this method needs access to the `TypeInfo` of `builtins.tuple`
        and `typing.Iterable`, we require the caller to provide an `ArgumentInferContext`.
        """
        return context.materialize_tnf(self)

    @staticmethod
    def from_star_parameter(star_param: Type, /) -> TupleNormalForm:
        """Create a TupleNormalForm from the type of a ``*args: T`` annotation.

        During Semantic Analysis, the type of `*args: T` is not always wrapped in `UnpackType`.
        in particular, ``*args: int`` just gives `int`.

        See Also: `from_star_arg` for types passed as star arguments.
        """
        p_t = get_proper_type(star_param)
        if isinstance(p_t, UnpackType):
            # we can use the same logic as from_star_argument
            return TupleNormalForm.from_star_argument(p_t)
        elif isinstance(p_t, ParamSpecType):
            # ParamSpecType is always variadic
            variadic_part = UnpackType(p_t, from_star_syntax=True)
            return TupleNormalForm([], DirtyUnpackType(variadic_part), [])
        else:
            # otherwise we have an annotation like `*args: int`
            # this should be treated as if it were `*args: *tuple[int, ...]`
            # we deal with this by representing it as Unpack[<TypeList int>]
            # despite being conceptually equal to a single item, during materialization
            # this will be converted back to tuple[int, ...] in
            variadic_part = UnpackType(TypeList([p_t]), from_star_syntax=True)
            return TupleNormalForm([], DirtyUnpackType(variadic_part), [])

    @staticmethod
    def from_star_argument(star_arg: Type, /) -> TupleNormalForm:
        """Create a TupleNormalForm from a type that was passed as a star argument.

        Uses special cases for tuple types and unions of tuples.
        Note that during typ analysis, the types are not wrapped in `UnpackType`,
        so we should not see `UnpackType` here.

        On the flipside, when we see *any* variadic type, including
        `TypeVarTupleType`, `ParamSpec.args`, `list[T]`, etc., then we wrap it in
        an `UnpackType` when adding it to the variadic part of the TupleNormalForm.

        Examples:
            - list[int]                    -> [], [list[int]], []
            - tuple[int, str]              -> [int, str], [], []
            - tuple[*tuple[str, ...], str] -> [], [*tuple[str, ...]], [str]
            - Ts                           -> [], [*Ts], []
            - P.args                       -> [], [P], []
            - list[Never]                  -> [], [list[Never]], []

        Some special casing is applied to unions:
            - list[int] | list[str] -> [], [list[int] | list[str]], []
            - tuple[int, str] | list[str] -> [], [tuple[int, str] | list[str]], []

        """
        p_t = get_proper_type(star_arg)
        if isinstance(p_t, UnpackType):
            # Note: mypy is inconsistent regarding wrapping types in UnpackType.
            # def foo(*args: *tuple[int, ...]): ...;
            # def outer(*args: *tuple[int, ...]):
            #     foo(*x)    # x --> Instance(tuple), not UnpackType
            # def bar(*args: *Ts): ...;
            # def outer(*args: *Ts): ...
            #     bar(*args)  # args --> UnpackType(TypeVarTupleType)
            p_t = get_proper_type(p_t.type)

        assert not isinstance(p_t, UnpackType), f"Unexpected UnpackType: {star_arg}"

        # special case single tuple
        if isinstance(p_t, TupleType):
            return TupleNormalForm.from_items(p_t.items)

        # special case union of tuples
        elif isinstance(p_t, UnionType):
            # if all items are tuples, we can split them
            tnfs = [TupleNormalForm.from_star_argument(x) for x in p_t.proper_items]
            return TupleNormalForm.combine_union(tnfs)

        # assume that the star args is some variadic type,
        #    e.g. ParamSpec, TypeVarTupleType, tuple[T, ...], list[T], etc.
        # wrap it in UnpackType[TypeList].
        else:
            variadic_part = UnpackType(star_arg, from_star_syntax=True)
            return TupleNormalForm([], DirtyUnpackType(variadic_part), [])

    @staticmethod
    def from_items(items: Iterable[Type], /) -> TupleNormalForm:
        r"""Split a tuple (or list of items) into 3 parts: head part, body part and tail part.

        1. A head part which is the longest finite prefix of the tuple
        2. A body part which covers all items from the first variable item to the last variable item
        3. A tail part which is the longest finite suffix of the remaining tuple

        If the body part is empty, the tail part is empty as well.
        The body part, if non-empty, always starts and ends with a variable item (UnpackType).
        Note that according to the current specification, the body part may contain at maximum
        a single variable item (UnpackType), so the body part actually should at maximum be
        of length 1. This implementation should still work if that specification changes in the future.

        Examples:
            - tuple[int, str] -> ([int, str], [], [])
            - tuple[int, *tuple[int, ...]] -> ([int], [*tuple[int, ...]], [])
            - tuple[*tuple[int, ...], int] -> ([], [*tuple[int, ...]], [int])
            - tuple[int, *tuple[int, ...], int] -> ([int], [*tuple[int, ...]], [int])
            - tuple[int, *tuple[int, ...], str, *tuple[str, ...], int]
              -> ([int], [*tuple[int, ...], str, *tuple[str, ...]], [int])
        """
        head_items: list[Type] = []
        tail_items: list[Type] = []
        body_items: list[Type] = []
        seen_variadic = False

        # determine the head, body and tail parts
        for item in flatten_nested_tuples(items):
            if _is_empty_unpack(item):
                # skip empty unpacks
                continue
            elif _is_non_empty_unpack(item):
                seen_variadic = True
                body_items.extend(tail_items)
                body_items.append(item)
                tail_items.clear()
            elif seen_variadic:
                tail_items.append(item)
            else:
                head_items.append(item)

        # the variadic part is the unpacking of the concatenation of all body items
        # formally represented by a UnpackType[TypeList[...]]
        body = UnpackType(TypeList(body_items), from_star_syntax=True)
        return TupleNormalForm(head_items, DirtyUnpackType(body), tail_items)

    @staticmethod
    def combine_union(args: Sequence[TupleNormalForm], /) -> TupleNormalForm:
        """Combine a union of TupleNormalForm into a single TupleNormalForm.

        - The head will be the element-wise union of all heads, stopping when one of the heads is exhausted.
        - the body will be a special UnionType[TypeList[...]] construct
        - The tail will be the element-wise union of all tails, stopping when one of the tails is exhausted.
          Note that for body-less union members, any head items that were not consumed when creating the
          joint head are prepended to the tail.

        In particular, if any single one of the inputs is head-less, then the resulting head is also empty.

        Examples:
            tuple[int, int], tuple[None, None]
                --> [int | None], *TypeList[], [int | None]

            tuple[int, *tuple[int, ...], int],
            tuple[None, *tuple[None, ...], None]
                --> [int | None],
                    *Union[
                        TypeList[*tuple[int, ...]],
                        TypeList[*tuple[None, ...]]
                    ],
                    Unpack[*tuple[int, ...] | *tuple[None, ...]]
                    [int | None]

            tuple[int, *tuple[int, ...], str, *tuple[str, ...], int]
            tuple[None, *tuple[None, ...], None]
                -->  [int | None],
                    *Union[
                        TypeList[*tuple[int, ...], str, *tuple[str, ...]],
                        TypeList[*tuple[None, ...]],
                    ],
                    [int | None]

            tuple[int, str], list[None]
                --> [],
                    *Union[
                        TypeList[int, str],
                        TypeList[*list[None]]
                    ],
                    []

            tuple[int, int] | tuple[*tuple[int, ...], int]
                --> [], [[[int], [*tuple[int, ...]]], [int]
        """
        # split each tuple
        heads: tuple[list[Type], ...]
        bodies: tuple[UnpackType, ...]
        tails: tuple[list[Type], ...]
        heads, bodies, tails = zip(*args)

        # setup
        remaining_head_items: list[list[Type]]
        remaining_tail_items: list[list[Type]]
        remaining_body_items: list[list[Type]]
        target_head_items: list[Type] = []
        target_tail_items: list[Type] = []

        # 1. process all heads in parallel, stopping when one of the heads is exhausted
        shared_head_length = min(len(head) for head in heads)
        for items in zip(*(head[:shared_head_length] for head in heads)):
            # append the union of the items to the head part
            target_head_items.append(make_simplified_union(items))
        # collect all the remaining head items from generators that were not exhausted
        remaining_head_items = [head[shared_head_length:] for head in heads]

        # If a tuple has no body items, prepend the remaining head items to the tail.
        # This addresses cases like combining `tuple[A, B, C]` with `tuple[X, *tuple[Y, ...], Z]`.
        # which should yield tuple[A | X, *tuple[B | Y, ...], C | Z]
        for remaining_head, body, tail in zip(remaining_head_items, bodies, tails):
            if _is_empty_unpack(body):
                # move all remaining head items to the start of the tail
                _tail = tail[:]
                tail.clear()
                tail.extend(remaining_head)
                tail.extend(_tail)
                remaining_head.clear()

        # 2. process all tails in parallel, in reverse, stopping when one of the tails is exhausted
        shared_tail_length = min(len(tail) for tail in tails)
        for items in zip(*(tail[-1 : -shared_tail_length - 1 : -1] for tail in tails)):
            # append the union of the items to the tail part
            target_tail_items.append(make_simplified_union(items))
        # collect all the remaining tail items from generators that were not exhausted
        target_tail_items.reverse()  # reverse to maintain original order
        remaining_tail_items = [tail[: len(tail) - shared_tail_length] for tail in tails]
        # note: do not use tail[:-shared_tail_length]; breaks when shared_tail_length=0

        # 3. process all bodies
        assert len(remaining_head_items) == len(remaining_tail_items) == len(bodies)
        remaining_body_items = [
            [
                *remaining_head,
                body,
                *remaining_tail,
            ]  # TODO: expand body in case like Unpack[<TypeList >] ?
            for remaining_head, body, remaining_tail in zip(
                remaining_head_items, bodies, remaining_tail_items
            )
        ]

        # 4. collected all items that will be put into the variable part
        # Note: if the collection is empty, this will give UninhabitedType.
        joined_bodies = UnionType.make_union(
            [UnpackType(TypeList(body_items)) for body_items in remaining_body_items]
        )
        variadic_part = UnpackType(joined_bodies, from_star_syntax=True)

        # 5. combine all parts into a TupleNormalForm
        return TupleNormalForm(
            target_head_items, DirtyUnpackType(variadic_part), target_tail_items
        )

    @staticmethod
    def combine_concat(tnfs: Sequence[TupleNormalForm], /) -> TupleNormalForm:
        """Combine sequence of TupleNormalForm into a single TupleNormalForm.

        essentially converts ``(*x1, ..., *xn)`` -> ``*x` where x = [*x1, ..., *xn]``
        """
        if len(tnfs) == 0:
            return TupleNormalForm([], DirtyUnpackType(UnpackType(UninhabitedType())), [])

        if len(tnfs) == 1:
            return tnfs[0]

        items = (
            item
            for item in chain.from_iterable(
                (*tnf.prefix, tnf.variadic, *tnf.suffix) for tnf in tnfs
            )
        )
        return TupleNormalForm.from_items(items)
