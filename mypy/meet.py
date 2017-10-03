from collections import OrderedDict
from typing import List, Optional, cast, Tuple

from mypy.join import is_similar_callables, combine_similar_callables, join_type_list
from mypy.types import (
    Type, AnyType, TypeVisitor, UnboundType, NoneTyp, TypeVarType, Instance, CallableType,
    TupleType, TypedDictType, ErasedType, TypeList, UnionType, PartialType, DeletedType,
    UninhabitedType, TypeType, TypeOfAny
)
from mypy.subtypes import is_equivalent, is_subtype, is_protocol_implementation

from mypy import experiments

# TODO Describe this module.


def meet_types(s: Type, t: Type) -> Type:
    """Return the greatest lower bound of two types."""
    if isinstance(s, ErasedType):
        return s
    if isinstance(s, AnyType):
        return t
    if isinstance(s, UnionType) and not isinstance(t, UnionType):
        s, t = t, s
    return t.accept(TypeMeetVisitor(s))


def narrow_declared_type(declared: Type, narrowed: Type) -> Type:
    """Return the declared type narrowed down to another type."""
    if declared == narrowed:
        return declared
    if isinstance(declared, UnionType):
        return UnionType.make_simplified_union([narrow_declared_type(x, narrowed)
                                                for x in declared.relevant_items()])
    elif not is_overlapping_types(declared, narrowed, use_promotions=True):
        if experiments.STRICT_OPTIONAL:
            return UninhabitedType()
        else:
            return NoneTyp()
    elif isinstance(narrowed, UnionType):
        return UnionType.make_simplified_union([narrow_declared_type(declared, x)
                                                for x in narrowed.relevant_items()])
    elif isinstance(narrowed, AnyType):
        return narrowed
    elif isinstance(declared, (Instance, TupleType)):
        return meet_types(declared, narrowed)
    elif isinstance(declared, TypeType) and isinstance(narrowed, TypeType):
        return TypeType.make_normalized(narrow_declared_type(declared.item, narrowed.item))
    return narrowed


def is_overlapping_types(t: Type, s: Type, use_promotions: bool = False) -> bool:
    """Can a value of type t be a value of type s, or vice versa?

    Note that this effectively checks against erased types, since type
    variables are erased at runtime and the overlapping check is based
    on runtime behavior. The exception is protocol types, it is not safe,
    but convenient and is an opt-in behavior.

    If use_promotions is True, also consider type promotions (int and
    float would only be overlapping if it's True).

    This does not consider multiple inheritance. For example, A and B in
    the following example are not considered overlapping, even though
    via C they can be overlapping:

        class A: ...
        class B: ...
        class C(A, B): ...

    The rationale is that this case is usually very unlikely as multiple
    inheritance is rare. Also, we can't reliably determine whether
    multiple inheritance actually occurs somewhere in a program, due to
    stub files hiding implementation details, dynamic loading etc.

    TODO: Don't consider tuples always overlapping.
    TODO: Don't consider callables always overlapping.
    TODO: Don't consider type variables with values always overlapping.
    """
    # Any overlaps with everything
    if isinstance(t, AnyType) or isinstance(s, AnyType):
        return True

    # Since we are effectively working with the erased types, we only
    # need to handle occurrences of TypeVarType at the top level.
    if isinstance(t, TypeVarType):
        t = t.erase_to_union_or_bound()
    if isinstance(s, TypeVarType):
        s = s.erase_to_union_or_bound()
    if isinstance(t, TypedDictType):
        t = t.as_anonymous().fallback
    if isinstance(s, TypedDictType):
        s = s.as_anonymous().fallback
    if isinstance(t, Instance):
        if isinstance(s, Instance):
            # Consider two classes non-disjoint if one is included in the mro
            # of another.
            if use_promotions:
                # Consider cases like int vs float to be overlapping where
                # there is only a type promotion relationship but not proper
                # subclassing.
                if t.type._promote and is_overlapping_types(t.type._promote, s):
                    return True
                if s.type._promote and is_overlapping_types(s.type._promote, t):
                    return True
            if t.type in s.type.mro or s.type in t.type.mro:
                return True
            if t.type.is_protocol and is_protocol_implementation(s, t):
                return True
            if s.type.is_protocol and is_protocol_implementation(t, s):
                return True
            return False
    if isinstance(t, UnionType):
        return any(is_overlapping_types(item, s)
                   for item in t.relevant_items())
    if isinstance(s, UnionType):
        return any(is_overlapping_types(t, item)
                   for item in s.relevant_items())
    if isinstance(t, TypeType) and isinstance(s, TypeType):
        # If both types are TypeType, compare their inner types.
        return is_overlapping_types(t.item, s.item, use_promotions)
    elif isinstance(t, TypeType) or isinstance(s, TypeType):
        # If exactly only one of t or s is a TypeType, check if one of them
        # is an `object` or a `type` and otherwise assume no overlap.
        one = t if isinstance(t, TypeType) else s
        other = s if isinstance(t, TypeType) else t
        if isinstance(other, Instance):
            return other.type.fullname() in {'builtins.object', 'builtins.type'}
        else:
            return isinstance(other, CallableType) and is_subtype(other, one)
    if experiments.STRICT_OPTIONAL:
        if isinstance(t, NoneTyp) != isinstance(s, NoneTyp):
            # NoneTyp does not overlap with other non-Union types under strict Optional checking
            return False
    # We conservatively assume that non-instance, non-union, and non-TypeType types can overlap
    # any other types.
    return True


class TypeMeetVisitor(TypeVisitor[Type]):
    def __init__(self, s: Type) -> None:
        self.s = s

    def visit_unbound_type(self, t: UnboundType) -> Type:
        if isinstance(self.s, NoneTyp):
            if experiments.STRICT_OPTIONAL:
                return AnyType(TypeOfAny.special_form)
            else:
                return self.s
        elif isinstance(self.s, UninhabitedType):
            return self.s
        else:
            return AnyType(TypeOfAny.special_form)

    def visit_any(self, t: AnyType) -> Type:
        return self.s

    def visit_union_type(self, t: UnionType) -> Type:
        if isinstance(self.s, UnionType):
            meets = []  # type: List[Type]
            for x in t.items:
                for y in self.s.items:
                    meets.append(meet_types(x, y))
        else:
            meets = [meet_types(x, self.s)
                     for x in t.items]
        return UnionType.make_simplified_union(meets)

    def visit_none_type(self, t: NoneTyp) -> Type:
        if experiments.STRICT_OPTIONAL:
            if isinstance(self.s, NoneTyp) or (isinstance(self.s, Instance) and
                                               self.s.type.fullname() == 'builtins.object'):
                return t
            else:
                return UninhabitedType()
        else:
            return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        if isinstance(self.s, NoneTyp):
            if experiments.STRICT_OPTIONAL:
                return t
            else:
                return self.s
        elif isinstance(self.s, UninhabitedType):
            return self.s
        else:
            return t

    def visit_erased_type(self, t: ErasedType) -> Type:
        return self.s

    def visit_type_var(self, t: TypeVarType) -> Type:
        if isinstance(self.s, TypeVarType) and self.s.id == t.id:
            return self.s
        else:
            return self.default(self.s)

    def visit_instance(self, t: Instance) -> Type:
        if isinstance(self.s, Instance):
            si = self.s
            if t.type == si.type:
                if is_subtype(t, self.s) or is_subtype(self.s, t):
                    # Combine type arguments. We could have used join below
                    # equivalently.
                    args = []  # type: List[Type]
                    for i in range(len(t.args)):
                        args.append(self.meet(t.args[i], si.args[i]))
                    return Instance(t.type, args)
                else:
                    if experiments.STRICT_OPTIONAL:
                        return UninhabitedType()
                    else:
                        return NoneTyp()
            else:
                if is_subtype(t, self.s):
                    return t
                elif is_subtype(self.s, t):
                    # See also above comment.
                    return self.s
                else:
                    if experiments.STRICT_OPTIONAL:
                        return UninhabitedType()
                    else:
                        return NoneTyp()
        elif isinstance(self.s, TypeType):
            return meet_types(t, self.s)
        elif isinstance(self.s, TupleType):
            return meet_types(t, self.s)
        else:
            return self.default(self.s)

    def visit_callable_type(self, t: CallableType) -> Type:
        if isinstance(self.s, CallableType) and is_similar_callables(t, self.s):
            if is_equivalent(t, self.s):
                return combine_similar_callables(t, self.s)
            result = meet_similar_callables(t, self.s)
            if isinstance(result.ret_type, UninhabitedType):
                # Return a plain None or <uninhabited> instead of a weird function.
                return self.default(self.s)
            return result
        else:
            return self.default(self.s)

    def visit_tuple_type(self, t: TupleType) -> Type:
        if isinstance(self.s, TupleType) and self.s.length() == t.length():
            items = []  # type: List[Type]
            for i in range(t.length()):
                items.append(self.meet(t.items[i], self.s.items[i]))
            # TODO: What if the fallbacks are different?
            return TupleType(items, t.fallback)
        # meet(Tuple[t1, t2, <...>], Tuple[s, ...]) == Tuple[meet(t1, s), meet(t2, s), <...>].
        elif (isinstance(self.s, Instance) and
              self.s.type.fullname() == 'builtins.tuple' and self.s.args):
            return t.copy_modified(items=[meet_types(it, self.s.args[0]) for it in t.items])
        elif (isinstance(self.s, Instance) and t.fallback.type == self.s.type):
            # Uh oh, a broken named tuple type (https://github.com/python/mypy/issues/3016).
            # Do something reasonable until that bug is fixed.
            return t
        else:
            return self.default(self.s)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        if isinstance(self.s, TypedDictType):
            for (name, l, r) in self.s.zip(t):
                if (not is_equivalent(l, r) or
                        (name in t.required_keys) != (name in self.s.required_keys)):
                    return self.default(self.s)
            item_list = []  # type: List[Tuple[str, Type]]
            for (item_name, s_item_type, t_item_type) in self.s.zipall(t):
                if s_item_type is not None:
                    item_list.append((item_name, s_item_type))
                else:
                    # at least one of s_item_type and t_item_type is not None
                    assert t_item_type is not None
                    item_list.append((item_name, t_item_type))
            items = OrderedDict(item_list)
            mapping_value_type = join_type_list(list(items.values()))
            fallback = self.s.create_anonymous_fallback(value_type=mapping_value_type)
            required_keys = t.required_keys | self.s.required_keys
            return TypedDictType(items, required_keys, fallback)
        else:
            return self.default(self.s)

    def visit_partial_type(self, t: PartialType) -> Type:
        # We can't determine the meet of partial types. We should never get here.
        assert False, 'Internal error'

    def visit_type_type(self, t: TypeType) -> Type:
        if isinstance(self.s, TypeType):
            typ = self.meet(t.item, self.s.item)
            if not isinstance(typ, NoneTyp):
                typ = TypeType.make_normalized(typ, line=t.line)
            return typ
        elif isinstance(self.s, Instance) and self.s.type.fullname() == 'builtins.type':
            return t
        else:
            return self.default(self.s)

    def meet(self, s: Type, t: Type) -> Type:
        return meet_types(s, t)

    def default(self, typ: Type) -> Type:
        if isinstance(typ, UnboundType):
            return AnyType(TypeOfAny.special_form)
        else:
            if experiments.STRICT_OPTIONAL:
                return UninhabitedType()
            else:
                return NoneTyp()


def meet_similar_callables(t: CallableType, s: CallableType) -> CallableType:
    from mypy.join import join_types
    arg_types = []  # type: List[Type]
    for i in range(len(t.arg_types)):
        arg_types.append(join_types(t.arg_types[i], s.arg_types[i]))
    # TODO in combine_similar_callables also applies here (names and kinds)
    # The fallback type can be either 'function' or 'type'. The result should have 'function' as
    # fallback only if both operands have it as 'function'.
    if t.fallback.type.fullname() != 'builtins.function':
        fallback = t.fallback
    else:
        fallback = s.fallback
    return t.copy_modified(arg_types=arg_types,
                           ret_type=meet_types(t.ret_type, s.ret_type),
                           fallback=fallback,
                           name=None)
