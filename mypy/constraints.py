"""Type inference constraints."""

from typing import List, cast

from mypy.types import (
    CallableType, Type, TypeVisitor, UnboundType, AnyType, Void, NoneTyp, TypeVarType,
    Instance, TupleType, UnionType, Overloaded, ErasedType, PartialType, DeletedType,
    is_named_instance
)
from mypy.maptype import map_instance_to_supertype
from mypy import nodes
import mypy.subtypes


SUBTYPE_OF = 0  # type: int
SUPERTYPE_OF = 1  # type: int


class Constraint:
    """A representation of a type constraint.

    It can be either T <: type or T :> type (T is a type variable).
    """

    type_var = 0   # Type variable id
    op = 0         # SUBTYPE_OF or SUPERTYPE_OF
    target = None  # type: Type

    def __init__(self, type_var: int, op: int, target: Type) -> None:
        self.type_var = type_var
        self.op = op
        self.target = target

    def __repr__(self) -> str:
        op_str = '<:'
        if self.op == SUPERTYPE_OF:
            op_str = ':>'
        return '{} {} {}'.format(self.type_var, op_str, self.target)


def infer_constraints_for_callable(
        callee: CallableType, arg_types: List[Type], arg_kinds: List[int],
        formal_to_actual: List[List[int]]) -> List[Constraint]:
    """Infer type variable constraints for a callable and actual arguments.

    Return a list of constraints.
    """

    constraints = []  # type: List[Constraint]
    tuple_counter = [0]

    for i, actuals in enumerate(formal_to_actual):
        for actual in actuals:
            actual_type = get_actual_type(arg_types[actual], arg_kinds[actual],
                                          tuple_counter)
            c = infer_constraints(callee.arg_types[i], actual_type,
                                  SUPERTYPE_OF)
            constraints.extend(c)

    return constraints


def get_actual_type(arg_type: Type, kind: int,
                    tuple_counter: List[int]) -> Type:
    """Return the type of an actual argument with the given kind.

    If the argument is a *arg, return the individual argument item.
    """

    if kind == nodes.ARG_STAR:
        if isinstance(arg_type, Instance):
            if arg_type.type.fullname() == 'builtins.list':
                # List *arg.
                return arg_type.args[0]
            elif arg_type.args:
                # TODO try to map type arguments to Iterable
                return arg_type.args[0]
            else:
                return AnyType()
        elif isinstance(arg_type, TupleType):
            # Get the next tuple item of a tuple *arg.
            tuplet = cast(TupleType, arg_type)
            tuple_counter[0] += 1
            return tuplet.items[tuple_counter[0] - 1]
        else:
            return AnyType()
    elif kind == nodes.ARG_STAR2:
        if isinstance(arg_type, Instance) and (
                (cast(Instance, arg_type)).type.fullname() == 'builtins.dict'):
            # Dict **arg. TODO more general (Mapping)
            return (cast(Instance, arg_type)).args[1]
        else:
            return AnyType()
    else:
        # No translation for other kinds.
        return arg_type


def infer_constraints(template: Type, actual: Type,
                      direction: int) -> List[Constraint]:
    """Infer type constraints.

    Match a template type, which may contain type variable references,
    recursively against a type which does not contain (the same) type
    variable references. The result is a list of type constrains of
    form 'T is a supertype/subtype of x', where T is a type variable
    present in the the template and x is a type without reference to
    type variables present in the template.

    Assume T and S are type variables. Now the following results can be
    calculated (read as '(template, actual) --> result'):

      (T, X)            -->  T :> X
      (X[T], X[Y])      -->  T <: Y and T :> Y
      ((T, T), (X, Y))  -->  T :> X and T :> Y
      ((T, S), (X, Y))  -->  T :> X and S :> Y
      (X[T], Any)       -->  T <: Any and T :> Any

    The constraints are represented as Constraint objects.
    """

    return template.accept(ConstraintBuilderVisitor(actual, direction))


class ConstraintBuilderVisitor(TypeVisitor[List[Constraint]]):
    """Visitor class for inferring type constraints."""

    # The type that is compared against a template
    # TODO: The value may be None. Is that actually correct?
    actual = None  # type: Type

    def __init__(self, actual: Type, direction: int) -> None:
        # Direction must be SUBTYPE_OF or SUPERTYPE_OF.
        self.actual = actual
        self.direction = direction

    # Trivial leaf types

    def visit_unbound_type(self, template: UnboundType) -> List[Constraint]:
        return []

    def visit_any(self, template: AnyType) -> List[Constraint]:
        return []

    def visit_void(self, template: Void) -> List[Constraint]:
        return []

    def visit_none_type(self, template: NoneTyp) -> List[Constraint]:
        return []

    def visit_erased_type(self, template: ErasedType) -> List[Constraint]:
        return []

    def visit_deleted_type(self, template: DeletedType) -> List[Constraint]:
        return []

    # Errors

    def visit_partial_type(self, template: PartialType) -> List[Constraint]:
        # We can't do anything useful with a partial type here.
        assert False, "Internal error"

    # Non-trivial leaf type

    def visit_type_var(self, template: TypeVarType) -> List[Constraint]:
        if self.actual:
            return [Constraint(template.id, self.direction, self.actual)]
        else:
            return []

    # Non-leaf types

    def visit_instance(self, template: Instance) -> List[Constraint]:
        actual = self.actual
        res = []  # type: List[Constraint]
        if isinstance(actual, Instance):
            instance = cast(Instance, actual)
            if (self.direction == SUBTYPE_OF and
                    template.type.has_base(instance.type.fullname())):
                mapped = map_instance_to_supertype(template, instance.type)
                for i in range(len(instance.args)):
                    # The constraints for generic type parameters are
                    # invariant. Include the default constraint and its
                    # negation to achieve the effect.
                    cb = infer_constraints(mapped.args[i], instance.args[i],
                                           self.direction)
                    res.extend(cb)
                    res.extend(negate_constraints(cb))
                return res
            elif (self.direction == SUPERTYPE_OF and
                    instance.type.has_base(template.type.fullname())):
                mapped = map_instance_to_supertype(instance, template.type)
                for j in range(len(template.args)):
                    # The constraints for generic type parameters are
                    # invariant.
                    cb = infer_constraints(template.args[j], mapped.args[j],
                                           self.direction)
                    res.extend(cb)
                    res.extend(negate_constraints(cb))
                return res
        if isinstance(actual, AnyType):
            # IDEA: Include both ways, i.e. add negation as well?
            return self.infer_against_any(template.args)
        if (isinstance(actual, TupleType) and
            (is_named_instance(template, 'typing.Iterable') or
             is_named_instance(template, 'typing.Sequence') or
             is_named_instance(template, 'typing.Reversible'))
                and self.direction == SUPERTYPE_OF):
            actual = cast(TupleType, actual)
            for item in actual.items:
                cb = infer_constraints(template.args[0], item, SUPERTYPE_OF)
                res.extend(cb)
            return res
        else:
            return []

    def visit_callable_type(self, template: CallableType) -> List[Constraint]:
        if isinstance(self.actual, CallableType):
            cactual = cast(CallableType, self.actual)
            # FIX verify argument counts
            # FIX what if one of the functions is generic
            res = []  # type: List[Constraint]

            # We can't infer constraints from arguments if the template is Callable[..., T] (with
            # literal '...').
            if not template.is_ellipsis_args:
                # The lengths should match, but don't crash (it will error elsewhere).
                for t, a in zip(template.arg_types, cactual.arg_types):
                    # Negate constraints due function argument type contravariance.
                    res.extend(negate_constraints(infer_constraints(t, a, self.direction)))
            res.extend(infer_constraints(template.ret_type, cactual.ret_type,
                                         self.direction))
            return res
        elif isinstance(self.actual, AnyType):
            # FIX what if generic
            res = self.infer_against_any(template.arg_types)
            res.extend(infer_constraints(template.ret_type, AnyType(),
                                         self.direction))
            return res
        elif isinstance(self.actual, Overloaded):
            return self.infer_against_overloaded(cast(Overloaded, self.actual),
                                                 template)
        else:
            return []

    def infer_against_overloaded(self, overloaded: Overloaded,
                                 template: CallableType) -> List[Constraint]:
        # Create constraints by matching an overloaded type against a template.
        # This is tricky to do in general. We cheat by only matching against
        # the first overload item, and by only matching the return type. This
        # seems to work somewhat well, but we should really use a more
        # reliable technique.
        item = find_matching_overload_item(overloaded, template)
        return infer_constraints(template.ret_type, item.ret_type,
                                 self.direction)

    def visit_tuple_type(self, template: TupleType) -> List[Constraint]:
        actual = self.actual
        if (isinstance(actual, TupleType) and
                len((cast(TupleType, actual)).items) == len(template.items)):
            res = []  # type: List[Constraint]
            for i in range(len(template.items)):
                res.extend(infer_constraints(template.items[i],
                                             cast(TupleType, actual).items[i],
                                             self.direction))
            return res
        elif isinstance(actual, AnyType):
            return self.infer_against_any(template.items)
        else:
            return []

    def visit_union_type(self, template: UnionType) -> List[Constraint]:
        res = []  # type: List[Constraint]
        for item in template.items:
            res.extend(infer_constraints(item, self.actual, self.direction))
        return res

    def infer_against_any(self, types: List[Type]) -> List[Constraint]:
        res = []  # type: List[Constraint]
        for t in types:
            res.extend(infer_constraints(t, AnyType(), self.direction))
        return res

    def visit_overloaded(self, type: Overloaded) -> List[Constraint]:
        res = []  # type: List[Constraint]
        for t in type.items():
            res.extend(infer_constraints(t, self.actual, self.direction))
        return res


def negate_constraints(constraints: List[Constraint]) -> List[Constraint]:
    res = []  # type: List[Constraint]
    for c in constraints:
        res.append(Constraint(c.type_var, neg_op(c.op), c.target))
    return res


def neg_op(op: int) -> int:
    """Map SubtypeOf to SupertypeOf and vice versa."""

    if op == SUBTYPE_OF:
        return SUPERTYPE_OF
    elif op == SUPERTYPE_OF:
        return SUBTYPE_OF
    else:
        raise ValueError('Invalid operator {}'.format(op))


def find_matching_overload_item(overloaded: Overloaded, template: CallableType) -> CallableType:
    """Disambiguate overload item against a template."""
    items = overloaded.items()
    for item in items:
        # Return type may be indeterminate in the template, so ignore it when performing a
        # subtype check.
        if mypy.subtypes.is_callable_subtype(item, template, ignore_return=True):
            return item
    # Fall back to the first item if we can't find a match. This is totally arbitrary --
    # maybe we should just bail out at this point.
    return items[0]
