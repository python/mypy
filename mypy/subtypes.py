from typing import cast, List, Dict, Callable

from mypy.types import (
    Type, AnyType, UnboundType, TypeVisitor, ErrorType, Void, NoneTyp,
    Instance, TypeVarType, CallableType, TupleType, UnionType, Overloaded,
    ErasedType, TypeList, PartialType, DeletedType, UninhabitedType, TypeType, is_named_instance
)
import mypy.applytype
import mypy.constraints
# Circular import; done in the function instead.
# import mypy.solve
from mypy import messages, sametypes
from mypy.nodes import CONTRAVARIANT, COVARIANT
from mypy.maptype import map_instance_to_supertype

from mypy import experiments


TypeParameterChecker = Callable[[Type, Type, int], bool]


def check_type_parameter(lefta: Type, righta: Type, variance: int) -> bool:
    if variance == COVARIANT:
        return is_subtype(lefta, righta, check_type_parameter)
    elif variance == CONTRAVARIANT:
        return is_subtype(righta, lefta, check_type_parameter)
    else:
        return is_equivalent(lefta, righta, check_type_parameter)


def is_subtype(left: Type, right: Type,
               type_parameter_checker: TypeParameterChecker = check_type_parameter) -> bool:
    """Is 'left' subtype of 'right'?

    Also consider Any to be a subtype of any type, and vice versa. This
    recursively applies to components of composite types (List[int] is subtype
    of List[Any], for example).

    type_parameter_checker is used to check the type parameters (for example,
    A with B in is_subtype(C[A], C[B]). The default checks for subtype relation
    between the type arguments (e.g., A and B), taking the variance of the
    type var into account.
    """
    if (isinstance(right, AnyType) or isinstance(right, UnboundType)
            or isinstance(right, ErasedType)):
        return True
    elif isinstance(right, UnionType) and not isinstance(left, UnionType):
        return any(is_subtype(left, item, type_parameter_checker)
                   for item in right.items)
    else:
        return left.accept(SubtypeVisitor(right, type_parameter_checker))


def is_subtype_ignoring_tvars(left: Type, right: Type) -> bool:
    def ignore_tvars(s: Type, t: Type, v: int) -> bool:
        return True
    return is_subtype(left, right, ignore_tvars)


def is_equivalent(a: Type, b: Type,
                  type_parameter_checker: TypeParameterChecker = check_type_parameter) -> bool:
    return is_subtype(a, b, type_parameter_checker) and is_subtype(b, a, type_parameter_checker)


def satisfies_upper_bound(a: Type, upper_bound: Type) -> bool:
    """Is 'a' valid value for a type variable with the given 'upper_bound'?

    Same as is_subtype except that Void is considered to be a subtype of
    any upper_bound. This is needed in a case like

        def f(g: Callable[[], T]) -> T: ...
        def h() -> None: ...
        f(h)
    """
    return isinstance(a, Void) or is_subtype(a, upper_bound)


class SubtypeVisitor(TypeVisitor[bool]):

    def __init__(self, right: Type,
                 type_parameter_checker: TypeParameterChecker) -> None:
        self.right = right
        self.check_type_parameter = type_parameter_checker

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
        if experiments.STRICT_OPTIONAL:
            return (isinstance(self.right, NoneTyp) or
                    is_named_instance(self.right, 'builtins.object'))
        else:
            return not isinstance(self.right, Void)

    def visit_uninhabited_type(self, left: UninhabitedType) -> bool:
        return not isinstance(self.right, Void)

    def visit_erased_type(self, left: ErasedType) -> bool:
        return True

    def visit_deleted_type(self, left: DeletedType) -> bool:
        return True

    def visit_instance(self, left: Instance) -> bool:
        if left.type.fallback_to_any:
            return True
        right = self.right
        if isinstance(right, Instance):
            if left.type._promote and is_subtype(left.type._promote,
                                                 self.right,
                                                 self.check_type_parameter):
                return True
            rname = right.type.fullname()
            if not left.type.has_base(rname) and rname != 'builtins.object':
                return False

            # Map left type to corresponding right instances.
            t = map_instance_to_supertype(left, right.type)

            return all(self.check_type_parameter(lefta, righta, tvar.variance)
                       for lefta, righta, tvar in
                       zip(t.args, right.args, right.type.defn.type_vars))
        else:
            return False

    def visit_type_var(self, left: TypeVarType) -> bool:
        right = self.right
        if isinstance(right, TypeVarType):
            return left.id == right.id
        else:
            return is_subtype(left.upper_bound, self.right)

    def visit_callable_type(self, left: CallableType) -> bool:
        right = self.right
        if isinstance(right, CallableType):
            return is_callable_subtype(left, right)
        elif isinstance(right, Overloaded):
            return all(is_subtype(left, item, self.check_type_parameter)
                       for item in right.items())
        elif isinstance(right, Instance):
            return is_subtype(left.fallback, right)
        elif isinstance(right, TypeType):
            # This is unsound, we don't check the __init__ signature.
            return left.is_type_obj() and is_subtype(left.ret_type, right.item)
        else:
            return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        right = self.right
        if isinstance(right, Instance):
            if is_named_instance(right, 'typing.Sized'):
                return True
            elif (is_named_instance(right, 'builtins.tuple') or
                  is_named_instance(right, 'typing.Iterable') or
                  is_named_instance(right, 'typing.Container') or
                  is_named_instance(right, 'typing.Sequence') or
                  is_named_instance(right, 'typing.Reversible')):
                iter_type = right.args[0]
                return all(is_subtype(li, iter_type) for li in left.items)
            elif is_subtype(left.fallback, right, self.check_type_parameter):
                return True
            return False
        elif isinstance(right, TupleType):
            if len(left.items) != len(right.items):
                return False
            for l, r in zip(left.items, right.items):
                if not is_subtype(l, r, self.check_type_parameter):
                    return False
            if not is_subtype(left.fallback, right.fallback, self.check_type_parameter):
                return False
            return True
        else:
            return False

    def visit_overloaded(self, left: Overloaded) -> bool:
        right = self.right
        if isinstance(right, Instance):
            return is_subtype(left.fallback, right)
        elif isinstance(right, CallableType) or is_named_instance(
                right, 'builtins.type'):
            for item in left.items():
                if is_subtype(item, right, self.check_type_parameter):
                    return True
            return False
        elif isinstance(right, Overloaded):
            # TODO: this may be too restrictive
            if len(left.items()) != len(right.items()):
                return False
            for i in range(len(left.items())):
                if not is_subtype(left.items()[i], right.items()[i], self.check_type_parameter):
                    return False
            return True
        elif isinstance(right, UnboundType):
            return True
        elif isinstance(right, TypeType):
            # All the items must have the same type object status, so
            # it's sufficient to query only (any) one of them.
            # This is unsound, we don't check the __init__ signature.
            return left.is_type_obj() and is_subtype(left.items()[0].ret_type, right.item)
        else:
            return False

    def visit_union_type(self, left: UnionType) -> bool:
        return all(is_subtype(item, self.right, self.check_type_parameter)
                   for item in left.items)

    def visit_partial_type(self, left: PartialType) -> bool:
        # This is indeterminate as we don't really know the complete type yet.
        raise RuntimeError

    def visit_type_type(self, left: TypeType) -> bool:
        right = self.right
        if isinstance(right, TypeType):
            return is_subtype(left.item, right.item)
        if isinstance(right, CallableType):
            # This is unsound, we don't check the __init__ signature.
            return right.is_type_obj() and is_subtype(left.item, right.ret_type)
        if (isinstance(right, Instance) and
                right.type.fullname() in ('builtins.type', 'builtins.object')):
            # Treat builtins.type the same as Type[Any];
            # treat builtins.object the same as Any.
            return True
        return False


def is_callable_subtype(left: CallableType, right: CallableType,
                        ignore_return: bool = False) -> bool:
    """Is left a subtype of right?"""
    # TODO: Support named arguments, **args, etc.
    # Non-type cannot be a subtype of type.
    if right.is_type_obj() and not left.is_type_obj():
        return False

    # A callable L is a subtype of a generic callable R if L is a
    # subtype of every type obtained from R by substituting types for
    # the variables of R. We can check this by simply leaving the
    # generic variables of R as type variables, effectively varying
    # over all possible values.

    # It's okay even if these variables share ids with generic
    # type variables of L, because generating and solving
    # constraints for the variables of L to make L a subtype of R
    # (below) treats type variables on the two sides as independent.

    if left.variables:
        # Apply generic type variables away in left via type inference.
        left = unify_generic_callable(left, right, ignore_return=ignore_return)
        if left is None:
            return False

    # Check return types.
    if not ignore_return and not is_subtype(left.ret_type, right.ret_type):
        return False

    if right.is_ellipsis_args:
        return True

    # Check argument types.
    if left.min_args > right.min_args:
        return False
    if left.is_var_arg:
        return is_var_arg_callable_subtype_helper(left, right)
    if right.is_var_arg:
        return False
    if len(left.arg_types) < len(right.arg_types):
        return False
    for i in range(len(right.arg_types)):
        if not is_subtype(right.arg_types[i], left.arg_types[i]):
            return False
    return True


def is_var_arg_callable_subtype_helper(left: CallableType, right: CallableType) -> bool:
    """Is left a subtype of right, assuming left has *args?

    See also is_callable_subtype for additional assumptions we can make.
    """
    left_fixed = left.max_fixed_args()
    right_fixed = right.max_fixed_args()
    num_fixed_matching = min(left_fixed, right_fixed)
    for i in range(num_fixed_matching):
        if not is_subtype(right.arg_types[i], left.arg_types[i]):
            return False
    if not right.is_var_arg:
        for i in range(num_fixed_matching, len(right.arg_types)):
            if not is_subtype(right.arg_types[i], left.arg_types[-1]):
                return False
        return True
    else:
        for i in range(left_fixed, right_fixed):
            if not is_subtype(right.arg_types[i], left.arg_types[-1]):
                return False
        for i in range(right_fixed, left_fixed):
            if not is_subtype(right.arg_types[-1], left.arg_types[i]):
                return False
        return is_subtype(right.arg_types[-1], left.arg_types[-1])


def unify_generic_callable(type: CallableType, target: CallableType,
                           ignore_return: bool) -> CallableType:
    """Try to unify a generic callable type with another callable type.

    Return unified CallableType if successful; otherwise, return None.
    """
    import mypy.solve
    constraints = []  # type: List[mypy.constraints.Constraint]
    for arg_type, target_arg_type in zip(type.arg_types, target.arg_types):
        c = mypy.constraints.infer_constraints(
            arg_type, target_arg_type, mypy.constraints.SUPERTYPE_OF)
        constraints.extend(c)
    if not ignore_return:
        c = mypy.constraints.infer_constraints(
            type.ret_type, target.ret_type, mypy.constraints.SUBTYPE_OF)
        constraints.extend(c)
    type_var_ids = [tvar.id for tvar in type.variables]
    inferred_vars = mypy.solve.solve_constraints(type_var_ids, constraints)
    if None in inferred_vars:
        return None
    msg = messages.temp_message_builder()
    applied = mypy.applytype.apply_generic_arguments(type, inferred_vars, msg, context=target)
    if msg.is_errors() or not isinstance(applied, CallableType):
        return None
    return applied


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

            def check_argument(left: Type, right: Type, variance: int) -> bool:
                if variance == COVARIANT:
                    return is_proper_subtype(left, right)
                elif variance == CONTRAVARIANT:
                    return is_proper_subtype(right, left)
                else:
                    return sametypes.is_same_type(left, right)

            # Map left type to corresponding right instances.
            t = map_instance_to_supertype(t, s.type)

            return all(check_argument(ta, ra, tvar.variance) for ta, ra, tvar in
                       zip(t.args, s.args, s.type.defn.type_vars))
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
        if isinstance(t, CallableType):
            # Fall back to subclass check and ignore other properties of the callable.
            return is_proper_subtype(t.fallback, s)
        return is_proper_subtype(t, s)
    return sametypes.is_same_type(t, s)
