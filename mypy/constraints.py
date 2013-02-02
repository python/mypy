from mypy.mtypes import (
    Callable, Type, TypeVisitor, UnboundType, Any, Void, NoneTyp, TypeVar,
    Instance, TupleType, Overloaded, ErasedType
)
from mypy.expandtype import expand_caller_var_args
from mypy.subtypes import map_instance_to_supertype
from mypy import nodes


SUBTYPE_OF = 0
SUPERTYPE_OF = 1


Constraint[] infer_constraints_for_callable(
                 Callable callee, Type[] arg_types, int[] arg_kinds,
                 int[][] formal_to_actual):
    """Infer type variable constraints for a callable and actual arguments.
    
    Return a list of constraints.
    """
    Constraint[] constraints = []
    tuple_counter = [0]
    
    for i, actuals in enumerate(formal_to_actual):
        for actual in actuals:
            actual_type = get_actual_type(arg_types[actual], arg_kinds[actual],
                                          tuple_counter)
            c = infer_constraints(callee.arg_types[i], actual_type,
                                  SUPERTYPE_OF)
            constraints.extend(c)

    return constraints


Type get_actual_type(Type arg_type, int kind, int[] tuple_counter):
    """Return the type of an actual argument with the given kind.

    If the argument is a *arg, return the individual argument item.
    """
    if kind == nodes.ARG_STAR:
        if isinstance(arg_type, Instance) and (
                ((Instance)arg_type).type.full_name() == 'builtins.list'):
            # List *arg. TODO any iterable
            return ((Instance)arg_type).args[0]
        elif isinstance(arg_type, TupleType):
            # Get the next tuple item of a tuple *arg.
            tuplet = (TupleType)arg_type
            tuple_counter[0] += 1
            return tuplet.items[tuple_counter[0] - 1]
        else:
            return Any()
    elif kind == nodes.ARG_STAR2:
        if isinstance(arg_type, Instance) and (
                ((Instance)arg_type).type.full_name() == 'builtins.dict'):
            # Dict **arg. TODO more general (Mapping)
            return ((Instance)arg_type).args[1]
        else:
            return Any()
    else:
        # No translation for other kinds.
        return arg_type


Constraint[] infer_constraints(Type template, Type actual, int direction):
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
      (X<T>, X<Y>)      -->  T <: Y and T :> Y
      ((T, T), (X, Y))  -->  T :> X and T :> Y
      ((T, S), (X, Y))  -->  T :> X and S :> Y
      (X<T>, dynamic)   -->  T <: dynamic and T :> dynamic
    
    The constraints are represented as Constraint objects.
    """
    return template.accept(ConstraintBuilderVisitor(actual, direction))


class Constraint:
    """A representation of a type constraint, either T <: type or T :>
    type (T is a type variable).
    """
    int type_var   # Type variable id
    int op         # SUBTYPE_OF or SUPERTYPE_OF
    Type target
    
    str __repr__(self):
        op_str = '<:'
        if self.op == SUPERTYPE_OF:
            op_str = ':>'
        return '{} {} {}'.format(self.type_var, op_str, self.target)
    
    void __init__(self, int type_var, int op, Type target):
        self.type_var = type_var
        self.op = op
        self.target = target


class ConstraintBuilderVisitor(TypeVisitor<Constraint[]>):
    """Visitor class for inferring type constraints."""
    
    Type actual # The type that is compared against a template
    
    void __init__(self, Type actual, int direction):
        # Direction must be SUBTYPE_OF or SUPERTYPE_OF.
        self.actual = actual
        self.direction = direction
    
    # Trivial leaf types
    
    Constraint[] visit_unbound_type(self, UnboundType template):
        return []
    
    Constraint[] visit_any(self, Any template):
        return []
    
    Constraint[] visit_void(self, Void template):
        return []
    
    Constraint[] visit_none_type(self, NoneTyp template):
        return []

    Constraint[] visit_erased_type(self, ErasedType template):
        return []
    
    # Non-trivial leaf type
    
    Constraint[] visit_type_var(self, TypeVar template):
        return [Constraint(template.id, SUPERTYPE_OF, self.actual)]
    
    # Non-leaf types
    
    Constraint[] visit_instance(self, Instance template):
        actual = self.actual
        if isinstance(actual, Instance):
            res = <Constraint> []
            instance = (Instance)actual
            if (self.direction == SUBTYPE_OF and
                    template.type.has_base(instance.type.full_name())):
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
                    instance.type.has_base(template.type.full_name())):
                mapped = map_instance_to_supertype(instance, template.type)
                for j in range(len(template.args)):
                    # The constraints for generic type parameters are
                    # invariant.
                    cb = infer_constraints(template.args[j], mapped.args[j],
                                           self.direction)
                    res.extend(cb)
                    res.extend(negate_constraints(cb))
                return res
        if isinstance(actual, Any):
            # IDEA: Include both ways, i.e. add negation as well?
            return self.infer_against_any(template.args)
        else:
            return []
    
    Constraint[] visit_callable(self, Callable template):
        if isinstance(self.actual, Callable):
            cactual = (Callable)self.actual
            # FIX verify argument counts
            # FIX what if one of the functions is generic
            Constraint[] res = []
            for i in range(len(template.arg_types)):
                # Negate constraints due function argument type contravariance.
                res.extend(negate_constraints(infer_constraints(
                    template.arg_types[i], cactual.arg_types[i],
                    self.direction)))
            res.extend(infer_constraints(template.ret_type, cactual.ret_type,
                                         self.direction))
            return res
        elif isinstance(self.actual, Any):
            # FIX what if generic
            res = self.infer_against_any(template.arg_types)
            res.extend(infer_constraints(template.ret_type, Any(),
                                         self.direction))
            return res
        elif isinstance(self.actual, Overloaded):
            return self.infer_against_overloaded((Overloaded)self.actual,
                                                 template)
        else:
            return []

    Constraint[] infer_against_overloaded(self, Overloaded overloaded,
                                          Callable template):
        # Create constraints by matching an overloaded type against a template.
        # This is tricky to do in general. We cheat by only matching against
        # the first overload item, and by only matching the return type. This
        # seems to work somewhat well, but we should really use a more
        # reliable technique.
        item = overloaded.items()[0]
        return infer_constraints(template.ret_type, item.ret_type,
                                 self.direction)
    
    Constraint[] visit_tuple_type(self, TupleType template):
        actual = self.actual
        if (isinstance(actual, TupleType) and
                len(((TupleType)actual).items) == len(template.items)):
            Constraint[] res = []
            for i in range(len(template.items)):
                res.extend(infer_constraints(template.items[i],
                                             ((TupleType)actual).items[i],
                                             self.direction))
            return res
        elif isinstance(actual, Any):
            return self.infer_against_any(template.items)
        else:
            return []
    
    Constraint[] infer_against_any(self, Type[] types):
        Constraint[] res = []
        for t in types:
            res.extend(infer_constraints(t, Any(), self.direction))
        return res


Constraint[] negate_constraints(Constraint[] constraints):
    Constraint[] res = []
    for c in constraints:
        res.append(Constraint(c.type_var, neg_op(c.op), c.target))
    return res


int neg_op(int op):
    """Map SubtypeOf to SupertypeOf and vice versa."""
    if op == SUBTYPE_OF:
        return SUPERTYPE_OF
    elif op == SUPERTYPE_OF:
        return SUBTYPE_OF
    else:
        raise ValueError('Invalid operator {}'.format(op))
