from typing import cast, List, Dict

from mypy.types import (
    Type, AnyType, UnboundType, TypeVisitor, ErrorType, Void, NoneTyp,
    Instance, TypeVar, Callable, TupleType, UnionType, Overloaded, ErasedType, TypeList,
    is_named_instance
)
import mypy.applytype
import mypy.constraints
from mypy import messages, sametypes
from mypy.nodes import TypeInfo
from mypy.expandtype import expand_type
from mypy.maptype import map_instance_to_supertype


def is_immutable(t: Instance) -> bool:
    # TODO: The name is confusing, since the values need not be immutable.
    return t.type.fullname() in ('typing.Iterable',
                                 'typing.Sequence',
                                 'typing.Reversible',
                                 )


def is_subtype(left: Type, right: Type) -> bool:
    """Is 'left' subtype of 'right'?

    Also consider Any to be a subtype of any type, and vice versa. This
    recursively applies to components of composite types (List[int] is subtype
    of List[Any], for example).
    """
    if (isinstance(right, AnyType) or isinstance(right, UnboundType)
            or isinstance(right, ErasedType)):
        return True
    elif isinstance(left, UnionType):
        return all(is_subtype(item, right) for item in left.items)
    elif isinstance(right, UnionType):
        return any(is_subtype(left, item) for item in right.items)
    else:
        return left.accept(SubtypeVisitor(right))


def is_equivalent(a: Type, b: Type) -> bool:
    return is_subtype(a, b) and is_subtype(b, a)


class SubtypeVisitor(TypeVisitor[bool]):
    def __init__(self, right: Type) -> None:
        self.right = right

    # visit_x(left) means: is left (which is an instance of X) a subtype of
    # right?

    def visit_unbound_type(self, left: UnboundType) -> bool:
        return True

    def visit_error_type(self, left: ErrorType) -> bool:
        return False

    def visit_type_list(self, t: TypeList) -> bool:
        assert False, 'Not supported'

    def visit_any(self, left: AnyType) -> bool:
        return True

    def visit_void(self, left: Void) -> bool:
        return isinstance(self.right, Void)

    def visit_none_type(self, left: NoneTyp) -> bool:
        return not isinstance(self.right, Void)

    def visit_erased_type(self, left: ErasedType) -> bool:
        return True

    def visit_instance(self, left: Instance) -> bool:
        right = self.right
        if isinstance(right, Instance):
            if left.type.ducktype and is_subtype(left.type.ducktype,
                                                 self.right):
                return True
            rname = right.type.fullname()
            if not left.type.has_base(rname) and rname != 'builtins.object':
                return False

            # Map left type to corresponding right instances.
            t = map_instance_to_supertype(left, right.type)
            if not is_immutable(right):
                result = all(is_equivalent(ta, ra) for (ta, ra) in
                             zip(t.args, right.args))
            else:
                result = all(is_subtype(ta, ra) for (ta, ra) in
                             zip(t.args, right.args))
            return result
        else:
            return False

    def visit_type_var(self, left: TypeVar) -> bool:
        right = self.right
        if isinstance(right, TypeVar):
            return left.name == right.name
        else:
            return is_named_instance(self.right, 'builtins.object')

    def visit_callable(self, left: Callable) -> bool:
        right = self.right
        if isinstance(right, Callable):
            return is_callable_subtype(left, right)
        elif isinstance(right, Overloaded):
            return all(is_subtype(left, item) for item in right.items())
        elif is_named_instance(right, 'builtins.object'):
            return True
        elif (is_named_instance(right, 'builtins.type') and
              left.is_type_obj()):
            return True
        else:
            return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        right = self.right
        if isinstance(right, Instance):
            if (is_named_instance(right, 'builtins.object') or
                    is_named_instance(right, 'builtins.tuple')):
                return True
            elif (is_named_instance(right, 'typing.Iterable') or
                  is_named_instance(right, 'typing.Sequence') or
                  is_named_instance(right, 'typing.Reversible')):
                iter_type = right.args[0]
                return all(is_subtype(li, iter_type) for li in left.items)
            return False
        elif isinstance(right, TupleType):
            if len(left.items) != len(right.items):
                return False
            for i in range(len(left.items)):
                if not is_subtype(left.items[i], right.items[i]):
                    return False
            return True
        else:
            return False

    def visit_overloaded(self, left: Overloaded) -> bool:
        right = self.right
        if is_named_instance(right, 'builtins.object'):
            return True
        elif isinstance(right, Callable) or is_named_instance(
                right, 'builtins.type'):
            for item in left.items():
                if is_subtype(item, right):
                    return True
            return False
        elif isinstance(right, Overloaded):
            # TODO: this may be too restrictive
            if len(left.items()) != len(right.items()):
                return False
            for i in range(len(left.items())):
                if not is_subtype(left.items()[i], right.items()[i]):
                    return False
            return True
        elif isinstance(right, UnboundType):
            return True
        else:
            return False


def is_callable_subtype(left: Callable, right: Callable) -> bool:
    """Is left a subtype of right?"""
    # TODO: Support named arguments, **args, etc.
    # Non-type cannot be a subtype of type.
    if right.is_type_obj() and not left.is_type_obj():
        return False
    if right.variables:
        # Subtyping is not currently supported for generic function as the supertype.
        return False
    if left.variables:
        # Apply generic type variables away in left via type inference.
        left = unify_generic_callable(left, right)
        if left is None:
            return False

    # Check return types.
    if not is_subtype(left.ret_type, right.ret_type):
        return False

    # Check argument types.
    if len(left.arg_types) < len(right.arg_types):
        return False
    if left.min_args > right.min_args:
        return False
    for i in range(len(right.arg_types)):
        if not is_subtype(right.arg_types[i], left.arg_types[i]):
            return False
    if right.is_var_arg and not left.is_var_arg:
        return False
    if (left.is_var_arg and not right.is_var_arg and
            len(left.arg_types) <= len(right.arg_types)):
        return False

    return True


def unify_generic_callable(type: Callable, target: Callable) -> Callable:
    """Try to unify a generic callable type with another callable type.

    Return unified Callable if successful; otherwise, return None.
    """
    constraints = []  # type: List[mypy.constraints.Constraint]
    for arg_type, target_arg_type in zip(type.arg_types, target.arg_types):
        c = mypy.constraints.infer_constraints(
            arg_type, target_arg_type, mypy.constraints.SUPERTYPE_OF)
        constraints.extend(c)
    type_var_ids = [tvar.id for tvar in type.variables]
    inferred_vars = mypy.solve.solve_constraints(type_var_ids, constraints)
    if None in inferred_vars:
        return None
    msg = messages.temp_message_builder()
    applied = mypy.applytype.apply_generic_arguments(type, inferred_vars, msg, context=target)
    if msg.is_errors() or not isinstance(applied, Callable):
        return None
    return cast(Callable, applied)


def restrict_subtype_away(t: Type, s: Type) -> Type:
    """Return a supertype of (t intersect not s)

    Currently just remove elements of a union type.
    """
    if isinstance(t, UnionType):
        new_items = [item for item in t.items if not is_subtype(item, s)]
        return UnionType.make_union(new_items)
    else:
        return t


def is_proper_subtype(t: Type, s: Type) -> bool:
    """Check if t is a proper subtype of s?

    For proper subtypes, there's no need to rely on compatibility due to
    Any types. Any instance type t is also a proper subtype of t.
    """
    # FIX tuple types
    if isinstance(t, Instance):
        if isinstance(s, Instance):
            if not t.type.has_base(s.type.fullname()):
                return False
            t = map_instance_to_supertype(t, s.type)
            if not is_immutable(s):
                return all(sametypes.is_same_type(ta, ra) for (ta, ra) in
                           zip(t.args, s.args))
            else:
                return all(is_proper_subtype(ta, ra) for (ta, ra) in
                           zip(t.args, s.args))
        return False
    else:
        return sametypes.is_same_type(t, s)


def is_more_precise(t: Type, s: Type) -> bool:
    """Check if t is a more precise type than s.

    A t is a proper subtype of s, t is also more precise than s. Also, if
    s is Any, t is more precise than s for any t. Finally, if t is the same
    type as s, t is more precise than s.
    """
    # TODO Should List[int] be more precise than List[Any]?
    if isinstance(s, AnyType):
        return True
    if isinstance(s, Instance):
        return is_proper_subtype(t, s)
    return sametypes.is_same_type(t, s)
