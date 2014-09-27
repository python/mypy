from typing import cast, List

from mypy.join import is_similar_callables, combine_similar_callables
from mypy.types import (
    Type, AnyType, TypeVisitor, UnboundType, Void, ErrorType, NoneTyp, TypeVar,
    Instance, Callable, TupleType, ErasedType, TypeList, UnionType
)
from mypy.sametypes import is_same_type
from mypy.subtypes import is_subtype
from mypy.nodes import TypeInfo

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
    elif not is_overlapping_types(s, t):
        return Void()
    else:
        if default_right:
            return t
        else:
            return s


def meet_simple_away(s: Type, t: Type) -> Type:
    if isinstance(s, UnionType):
        return UnionType.make_simplified_union([x for x in s.items
                                                if not is_subtype(x, t)])
    elif not isinstance(s, AnyType) and is_subtype(s, t):
        return Void()
    else:
        return s


def is_overlapping_types(t: Type, s: Type) -> bool:
    """Can a value of type t be a value of type s, or vice versa?"""
    if isinstance(t, Instance):
        if isinstance(s, Instance):
            # If the classes are explicitly declared as disjoint, they can't
            # overlap.
            if t.type in s.type.disjoint_classes:
                return False

            # Built-in classes in the mro affect whether two types can be
            # overlapping.
            # TODO Find the most distant ancestor with the same memory layout,
            #      since multiple inheritance seems possible if the memory
            #      layout is the same.
            tbuiltin = nearest_builtin_ancestor(t.type)
            sbuiltin = nearest_builtin_ancestor(s.type)
            if not sbuiltin or not tbuiltin:
                return True

            # If one is a base class of other, the types overlap, unless there
            # is an explicit disjointclass constraint.
            if tbuiltin in sbuiltin.mro or sbuiltin in tbuiltin.mro:
                return True
            return tbuiltin == sbuiltin
    # We conservatively assume that non-instance types can overlap any other
    # types.
    return True


def nearest_builtin_ancestor(type: TypeInfo) -> TypeInfo:
    for base in type.mro:
        if base.defn.is_builtinclass:
            return base
    else:
        return None
        assert False, 'No built-in ancestor found for {}'.format(type.name())


class TypeMeetVisitor(TypeVisitor[Type]):
    def __init__(self, s: Type) -> None:
        self.s = s

    def visit_unbound_type(self, t: UnboundType) -> Type:
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        elif isinstance(self.s, NoneTyp):
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
            meets = List[Type]()
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
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            return t
        else:
            return ErrorType()

    def visit_erased_type(self, t: ErasedType) -> Type:
        return self.s

    def visit_type_var(self, t: TypeVar) -> Type:
        if isinstance(self.s, TypeVar) and (cast(TypeVar, self.s)).id == t.id:
            return self.s
        else:
            return self.default(self.s)

    def visit_instance(self, t: Instance) -> Type:
        if isinstance(self.s, Instance):
            si = cast(Instance, self.s)
            if t.type == si.type:
                if is_subtype(t, self.s):
                    # Combine type arguments. We could have used join below
                    # equivalently.
                    args = []  # type: List[Type]
                    for i in range(len(t.args)):
                        args.append(self.meet(t.args[i], si.args[i]))
                    return Instance(t.type, args)
                else:
                    return NoneTyp()
            else:
                if is_subtype(t, self.s):
                    return t
                elif is_subtype(self.s, t):
                    # See also above comment.
                    return self.s
                else:
                    return NoneTyp()
        else:
            return self.default(self.s)

    def visit_callable(self, t: Callable) -> Type:
        if isinstance(self.s, Callable) and is_similar_callables(
                t, cast(Callable, self.s)):
            return combine_similar_callables(t, cast(Callable, self.s))
        else:
            return self.default(self.s)

    def visit_tuple_type(self, t: TupleType) -> Type:
        if isinstance(self.s, TupleType) and (
                cast(TupleType, self.s).length() == t.length()):
            items = []  # type: List[Type]
            for i in range(t.length()):
                items.append(self.meet(t.items[i],
                                       (cast(TupleType, self.s)).items[i]))
            # TODO: What if the fallbacks are different?
            return TupleType(items, t.fallback)
        else:
            return self.default(self.s)

    def visit_intersection(self, t):
        # TODO Obsolete; target overload types instead?
        # Only support very rudimentary meets between intersection types.
        if is_same_type(self.s, t):
            return self.s
        else:
            return self.default(self.s)

    def meet(self, s, t):
        return meet_types(s, t)

    def default(self, typ):
        if isinstance(typ, UnboundType):
            return AnyType()
        elif isinstance(typ, Void) or isinstance(typ, ErrorType):
            return ErrorType()
        else:
            return NoneTyp()
