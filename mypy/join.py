"""Calculation of the least upper bound types (joins)."""

from collections import OrderedDict
from typing import cast, List, Optional

from mypy.types import (
    Type, AnyType, NoneTyp, TypeVisitor, Instance, UnboundType, TypeVarType, CallableType,
    TupleType, TypedDictType, ErasedType, TypeList, UnionType, FunctionLike, Overloaded,
    PartialType, DeletedType, UninhabitedType, TypeType, true_or_false, TypeOfAny
)
from mypy.maptype import map_instance_to_supertype
from mypy.subtypes import (
    is_subtype, is_equivalent, is_subtype_ignoring_tvars, is_proper_subtype,
    is_protocol_implementation
)

from mypy import experiments


def join_simple(declaration: Optional[Type], s: Type, t: Type) -> Type:
    """Return a simple least upper bound given the declared type."""

    if (s.can_be_true, s.can_be_false) != (t.can_be_true, t.can_be_false):
        # if types are restricted in different ways, use the more general versions
        s = true_or_false(s)
        t = true_or_false(t)

    if isinstance(s, AnyType):
        return s

    if isinstance(s, ErasedType):
        return t

    if is_proper_subtype(s, t):
        return t

    if is_proper_subtype(t, s):
        return s

    if isinstance(declaration, UnionType):
        return UnionType.make_simplified_union([s, t])

    if isinstance(s, NoneTyp) and not isinstance(t, NoneTyp):
        s, t = t, s

    if isinstance(s, UninhabitedType) and not isinstance(t, UninhabitedType):
        s, t = t, s

    value = t.accept(TypeJoinVisitor(s))

    if value is None:
        # XXX this code path probably should be avoided.
        # It seems to happen when a line (x = y) is a type error, and
        # it's not clear that assuming that x is arbitrary afterward
        # is a good idea.
        return declaration

    if declaration is None or is_subtype(value, declaration):
        return value

    return declaration


def join_types(s: Type, t: Type) -> Type:
    """Return the least upper bound of s and t.

    For example, the join of 'int' and 'object' is 'object'.
    """
    if (s.can_be_true, s.can_be_false) != (t.can_be_true, t.can_be_false):
        # if types are restricted in different ways, use the more general versions
        s = true_or_false(s)
        t = true_or_false(t)

    if isinstance(s, AnyType):
        return s

    if isinstance(s, ErasedType):
        return t

    if isinstance(s, UnionType) and not isinstance(t, UnionType):
        s, t = t, s

    if isinstance(s, NoneTyp) and not isinstance(t, NoneTyp):
        s, t = t, s

    if isinstance(s, UninhabitedType) and not isinstance(t, UninhabitedType):
        s, t = t, s

    # Use a visitor to handle non-trivial cases.
    return t.accept(TypeJoinVisitor(s))


class TypeJoinVisitor(TypeVisitor[Type]):
    """Implementation of the least upper bound algorithm.

    Attributes:
      s: The other (left) type operand.
    """

    def __init__(self, s: Type) -> None:
        self.s = s

    def visit_unbound_type(self, t: UnboundType) -> Type:
        return AnyType(TypeOfAny.special_form)

    def visit_union_type(self, t: UnionType) -> Type:
        if is_subtype(self.s, t):
            return t
        else:
            return UnionType.make_simplified_union([self.s, t])

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        if experiments.STRICT_OPTIONAL:
            if isinstance(self.s, (NoneTyp, UninhabitedType)):
                return t
            elif isinstance(self.s, UnboundType):
                return AnyType(TypeOfAny.special_form)
            else:
                return UnionType.make_simplified_union([self.s, t])
        else:
            return self.s

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return self.s

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return self.s

    def visit_erased_type(self, t: ErasedType) -> Type:
        return self.s

    def visit_type_var(self, t: TypeVarType) -> Type:
        if isinstance(self.s, TypeVarType) and self.s.id == t.id:
            return self.s
        else:
            return self.default(self.s)

    def visit_instance(self, t: Instance) -> Type:
        if isinstance(self.s, Instance):
            nominal = join_instances(t, self.s)
            structural = None  # type: Optional[Instance]
            if t.type.is_protocol and is_protocol_implementation(self.s, t):
                structural = t
            elif self.s.type.is_protocol and is_protocol_implementation(t, self.s):
                structural = self.s
            # Structural join is preferred in the case where we have found both
            # structural and nominal and they have same MRO length (see two comments
            # in join_instances_via_supertype). Otherwise, just return the nominal join.
            if not structural or is_better(nominal, structural):
                return nominal
            return structural
        elif isinstance(self.s, FunctionLike):
            return join_types(t, self.s.fallback)
        elif isinstance(self.s, TypeType):
            return join_types(t, self.s)
        elif isinstance(self.s, TypedDictType):
            return join_types(t, self.s)
        else:
            return self.default(self.s)

    def visit_callable_type(self, t: CallableType) -> Type:
        if isinstance(self.s, CallableType) and is_similar_callables(t, self.s):
            if is_equivalent(t, self.s):
                return combine_similar_callables(t, self.s)
            result = join_similar_callables(t, self.s)
            if any(isinstance(tp, (NoneTyp, UninhabitedType)) for tp in result.arg_types):
                # We don't want to return unusable Callable, attempt fallback instead.
                return join_types(t.fallback, self.s)
            return result
        elif isinstance(self.s, Overloaded):
            # Switch the order of arguments to that we'll get to visit_overloaded.
            return join_types(t, self.s)
        else:
            return join_types(t.fallback, self.s)

    def visit_overloaded(self, t: Overloaded) -> Type:
        # This is more complex than most other cases. Here are some
        # examples that illustrate how this works.
        #
        # First let's define a concise notation:
        #  - Cn are callable types (for n in 1, 2, ...)
        #  - Ov(C1, C2, ...) is an overloaded type with items C1, C2, ...
        #  - Callable[[T, ...], S] is written as [T, ...] -> S.
        #
        # We want some basic properties to hold (assume Cn are all
        # unrelated via Any-similarity):
        #
        #   join(Ov(C1, C2), C1) == C1
        #   join(Ov(C1, C2), Ov(C1, C2)) == Ov(C1, C2)
        #   join(Ov(C1, C2), Ov(C1, C3)) == C1
        #   join(Ov(C2, C2), C3) == join of fallback types
        #
        # The presence of Any types makes things more interesting. The join is the
        # most general type we can get with respect to Any:
        #
        #   join(Ov([int] -> int, [str] -> str), [Any] -> str) == Any -> str
        #
        # We could use a simplification step that removes redundancies, but that's not
        # implemented right now. Consider this example, where we get a redundancy:
        #
        #   join(Ov([int, Any] -> Any, [str, Any] -> Any), [Any, int] -> Any) ==
        #       Ov([Any, int] -> Any, [Any, int] -> Any)
        #
        # TODO: Consider more cases of callable subtyping.
        result = []  # type: List[CallableType]
        s = self.s
        if isinstance(s, FunctionLike):
            # The interesting case where both types are function types.
            for t_item in t.items():
                for s_item in s.items():
                    if is_similar_callables(t_item, s_item):
                        if is_equivalent(t_item, s_item):
                            result.append(combine_similar_callables(t_item, s_item))
                        elif is_subtype(t_item, s_item):
                            result.append(s_item)
            if result:
                # TODO: Simplify redundancies from the result.
                if len(result) == 1:
                    return result[0]
                else:
                    return Overloaded(result)
            return join_types(t.fallback, s.fallback)
        return join_types(t.fallback, s)

    def visit_tuple_type(self, t: TupleType) -> Type:
        if isinstance(self.s, TupleType) and self.s.length() == t.length():
            items = []  # type: List[Type]
            for i in range(t.length()):
                items.append(self.join(t.items[i], self.s.items[i]))
            fallback = join_instances(self.s.fallback, t.fallback)
            assert isinstance(fallback, Instance)
            return TupleType(items, fallback)
        else:
            return self.default(self.s)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        if isinstance(self.s, TypedDictType):
            items = OrderedDict([
                (item_name, s_item_type)
                for (item_name, s_item_type, t_item_type) in self.s.zip(t)
                if (is_equivalent(s_item_type, t_item_type) and
                    (item_name in t.required_keys) == (item_name in self.s.required_keys))
            ])
            mapping_value_type = join_type_list(list(items.values()))
            fallback = self.s.create_anonymous_fallback(value_type=mapping_value_type)
            # We need to filter by items.keys() since some required keys present in both t and
            # self.s might be missing from the join if the types are incompatible.
            required_keys = set(items.keys()) & t.required_keys & self.s.required_keys
            return TypedDictType(items, required_keys, fallback)
        elif isinstance(self.s, Instance):
            return join_types(self.s, t.fallback)
        else:
            return self.default(self.s)

    def visit_partial_type(self, t: PartialType) -> Type:
        # We only have partial information so we can't decide the join result. We should
        # never get here.
        assert False, "Internal error"

    def visit_type_type(self, t: TypeType) -> Type:
        if isinstance(self.s, TypeType):
            return TypeType.make_normalized(self.join(t.item, self.s.item), line=t.line)
        elif isinstance(self.s, Instance) and self.s.type.fullname() == 'builtins.type':
            return self.s
        else:
            return self.default(self.s)

    def join(self, s: Type, t: Type) -> Type:
        return join_types(s, t)

    def default(self, typ: Type) -> Type:
        if isinstance(typ, Instance):
            return object_from_instance(typ)
        elif isinstance(typ, UnboundType):
            return AnyType(TypeOfAny.special_form)
        elif isinstance(typ, TupleType):
            return self.default(typ.fallback)
        elif isinstance(typ, TypedDictType):
            return self.default(typ.fallback)
        elif isinstance(typ, FunctionLike):
            return self.default(typ.fallback)
        elif isinstance(typ, TypeVarType):
            return self.default(typ.upper_bound)
        else:
            return AnyType(TypeOfAny.special_form)


def join_instances(t: Instance, s: Instance) -> Type:
    """Calculate the join of two instance types.
    """
    if t.type == s.type:
        # Simplest case: join two types with the same base type (but
        # potentially different arguments).
        if is_subtype(t, s) or is_subtype(s, t):
            # Compatible; combine type arguments.
            args = []  # type: List[Type]
            for i in range(len(t.args)):
                args.append(join_types(t.args[i], s.args[i]))
            return Instance(t.type, args)
        else:
            # Incompatible; return trivial result object.
            return object_from_instance(t)
    elif t.type.bases and is_subtype_ignoring_tvars(t, s):
        return join_instances_via_supertype(t, s)
    else:
        # Now t is not a subtype of s, and t != s. Now s could be a subtype
        # of t; alternatively, we need to find a common supertype. This works
        # in of the both cases.
        return join_instances_via_supertype(s, t)


def join_instances_via_supertype(t: Instance, s: Instance) -> Type:
    # Give preference to joins via duck typing relationship, so that
    # join(int, float) == float, for example.
    if t.type._promote and is_subtype(t.type._promote, s):
        return join_types(t.type._promote, s)
    elif s.type._promote and is_subtype(s.type._promote, t):
        return join_types(t, s.type._promote)
    # Compute the "best" supertype of t when joined with s.
    # The definition of "best" may evolve; for now it is the one with
    # the longest MRO.  Ties are broken by using the earlier base.
    best = None  # type: Optional[Type]
    for base in t.type.bases:
        mapped = map_instance_to_supertype(t, base.type)
        res = join_instances(mapped, s)
        if best is None or is_better(res, best):
            best = res
    assert best is not None
    return best


def is_better(t: Type, s: Type) -> bool:
    # Given two possible results from join_instances_via_supertype(),
    # indicate whether t is the better one.
    if isinstance(t, Instance):
        if not isinstance(s, Instance):
            return True
        # Use len(mro) as a proxy for the better choice.
        if len(t.type.mro) > len(s.type.mro):
            return True
    return False


def is_similar_callables(t: CallableType, s: CallableType) -> bool:
    """Return True if t and s have identical numbers of
    arguments, default arguments and varargs.
    """

    return (len(t.arg_types) == len(s.arg_types) and t.min_args == s.min_args and
            t.is_var_arg == s.is_var_arg)


def join_similar_callables(t: CallableType, s: CallableType) -> CallableType:
    from mypy.meet import meet_types
    arg_types = []  # type: List[Type]
    for i in range(len(t.arg_types)):
        arg_types.append(meet_types(t.arg_types[i], s.arg_types[i]))
    # TODO in combine_similar_callables also applies here (names and kinds)
    # The fallback type can be either 'function' or 'type'. The result should have 'type' as
    # fallback only if both operands have it as 'type'.
    if t.fallback.type.fullname() != 'builtins.type':
        fallback = t.fallback
    else:
        fallback = s.fallback
    return t.copy_modified(arg_types=arg_types,
                           ret_type=join_types(t.ret_type, s.ret_type),
                           fallback=fallback,
                           name=None)


def combine_similar_callables(t: CallableType, s: CallableType) -> CallableType:
    arg_types = []  # type: List[Type]
    for i in range(len(t.arg_types)):
        arg_types.append(join_types(t.arg_types[i], s.arg_types[i]))
    # TODO kinds and argument names
    # The fallback type can be either 'function' or 'type'. The result should have 'type' as
    # fallback only if both operands have it as 'type'.
    if t.fallback.type.fullname() != 'builtins.type':
        fallback = t.fallback
    else:
        fallback = s.fallback
    return t.copy_modified(arg_types=arg_types,
                           ret_type=join_types(t.ret_type, s.ret_type),
                           fallback=fallback,
                           name=None)


def object_from_instance(instance: Instance) -> Instance:
    """Construct the type 'builtins.object' from an instance type."""
    # Use the fact that 'object' is always the last class in the mro.
    res = Instance(instance.type.mro[-1], [])
    return res


def join_type_list(types: List[Type]) -> Type:
    if not types:
        # This is a little arbitrary but reasonable. Any empty tuple should be compatible
        # with all variable length tuples, and this makes it possible.
        return UninhabitedType()
    joined = types[0]
    for t in types[1:]:
        joined = join_types(joined, t)
    return joined
