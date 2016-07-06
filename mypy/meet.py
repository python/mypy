from typing import cast, List

from mypy.join import is_similar_callables, combine_similar_callables
from mypy.types import (
    Type, AnyType, TypeVisitor, UnboundType, Void, ErrorType, NoneTyp, TypeVarType,
    Instance, CallableType, TupleType, ErasedType, TypeList, UnionType, PartialType,
    DeletedType, UninhabitedType, TypeType
)
from mypy.subtypes import is_subtype
from mypy.nodes import TypeInfo

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


def meet_simple(s: Type, t: Type, default_right: bool = True) -> Type:
    if s == t:
        return s
    if isinstance(s, UnionType):
        return UnionType.make_simplified_union([meet_types(x, t) for x in s.items])
    elif not is_overlapping_types(s, t, use_promotions=True):
        if experiments.STRICT_OPTIONAL:
            return UninhabitedType()
        else:
            return NoneTyp()
    else:
        if default_right:
            return t
        else:
            return s


def is_overlapping_types(t: Type, s: Type, use_promotions: bool = False) -> bool:
    """Can a value of type t be a value of type s, or vice versa?

    Note that this effectively checks against erased types, since type
    variables are erased at runtime and the overlapping check is based
    on runtime behavior.

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
    # Since we are effectively working with the erased types, we only
    # need to handle occurrences of TypeVarType at the top level.
    if isinstance(t, TypeVarType):
        t = t.erase_to_union_or_bound()
    if isinstance(s, TypeVarType):
        s = s.erase_to_union_or_bound()
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
            return t.type in s.type.mro or s.type in t.type.mro
    if isinstance(t, UnionType):
        return any(is_overlapping_types(item, s)
                   for item in t.items)
    if isinstance(s, UnionType):
        return any(is_overlapping_types(t, item)
                   for item in s.items)
    if isinstance(t, TypeType) and isinstance(s, TypeType):
        # If both types are TypeType, compare their inner types.
        return is_overlapping_types(t.item, s.item, use_promotions)
    elif isinstance(t, TypeType) or isinstance(s, TypeType):
        # If exactly only one of t or s is a TypeType, check if one of them
        # is an `object` or a `type` and otherwise assume no overlap.
        other = s if isinstance(t, TypeType) else t
        if isinstance(other, Instance):
            return other.type.fullname() in {'builtins.object', 'builtins.type'}
        else:
            return False
    if experiments.STRICT_OPTIONAL:
        if isinstance(t, NoneTyp) != isinstance(s, NoneTyp):
            # NoneTyp does not overlap with other non-Union types under strict Optional checking
            return False
    # We conservatively assume that non-instance, non-union, and non-TypeType types can overlap
    # any other types.
    return True


def nearest_builtin_ancestor(type: TypeInfo) -> TypeInfo:
    for base in type.mro:
        if base.defn.is_builtinclass:
            return base
    else:
        return None


class TypeMeetVisitor(TypeVisitor[Type]):
    def __init__(self, s: Type) -> None:
        self.s = s

    def visit_unbound_type(self, t: UnboundType) -> Type:
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        elif isinstance(self.s, NoneTyp):
            if experiments.STRICT_OPTIONAL:
                return AnyType()
            else:
                return self.s
        elif isinstance(self.s, UninhabitedType):
            return self.s
        else:
            return AnyType()

    def visit_error_type(self, t: ErrorType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        assert False, 'Not supported'

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

    def visit_void(self, t: Void) -> Type:
        if isinstance(self.s, Void):
            return t
        else:
            return ErrorType()

    def visit_none_type(self, t: NoneTyp) -> Type:
        if experiments.STRICT_OPTIONAL:
            if isinstance(self.s, NoneTyp) or (isinstance(self.s, Instance) and
                                               self.s.type.fullname() == 'builtins.object'):
                return t
            else:
                return UninhabitedType()
        else:
            if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
                return t
            else:
                return ErrorType()

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            return t
        else:
            return ErrorType()

    def visit_deleted_type(self, t: DeletedType) -> Type:
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            if isinstance(self.s, NoneTyp):
                if experiments.STRICT_OPTIONAL:
                    return t
                else:
                    return self.s
            elif isinstance(self.s, UninhabitedType):
                return self.s
            else:
                return t
        else:
            return ErrorType()

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
        else:
            return self.default(self.s)

    def visit_callable_type(self, t: CallableType) -> Type:
        if isinstance(self.s, CallableType) and is_similar_callables(t, self.s):
            return combine_similar_callables(t, self.s)
        else:
            return self.default(self.s)

    def visit_tuple_type(self, t: TupleType) -> Type:
        if isinstance(self.s, TupleType) and self.s.length() == t.length():
            items = []  # type: List[Type]
            for i in range(t.length()):
                items.append(self.meet(t.items[i], self.s.items[i]))
            # TODO: What if the fallbacks are different?
            return TupleType(items, t.fallback)
        else:
            return self.default(self.s)

    def visit_partial_type(self, t: PartialType) -> Type:
        # We can't determine the meet of partial types. We should never get here.
        assert False, 'Internal error'

    def visit_type_type(self, t: TypeType) -> Type:
        if isinstance(self.s, TypeType):
            typ = self.meet(t.item, self.s.item)
            if not isinstance(typ, NoneTyp):
                typ = TypeType(typ, line=t.line)
            return typ
        elif isinstance(self.s, Instance) and self.s.type.fullname() == 'builtins.type':
            return t
        else:
            return self.default(self.s)

    def meet(self, s: Type, t: Type) -> Type:
        return meet_types(s, t)

    def default(self, typ: Type) -> Type:
        if isinstance(typ, UnboundType):
            return AnyType()
        elif isinstance(typ, Void) or isinstance(typ, ErrorType):
            return ErrorType()
        else:
            if experiments.STRICT_OPTIONAL:
                return UninhabitedType()
            else:
                return NoneTyp()
