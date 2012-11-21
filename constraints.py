from mtypes import (
    Callable, Typ, TypeVisitor, UnboundType, Any, Void, NoneTyp, TypeVar,
    Instance, TupleType
)
from expandtype import expand_caller_var_args
from subtypes import map_instance_to_supertype


list<Constraint> infer_constraints_for_callable(
            Callable callee, list<Typ> arg_types, bool is_var_arg):
    """Infer type variable constraints for a callable and a list of
    argument types.  Return a list of constraints.
    """
    # FIX check argument counts
    
    callee_num_args = callee.max_fixed_args()
    
    list<Constraint> constraints = []
    
    Typ caller_rest = None # Rest of types for varargs calls
    if is_var_arg:
        arg_types, caller_rest = expand_caller_var_args(arg_types,
                                                        callee_num_args)
        if arg_types is None:
            # Invalid varargs arguments.
            return []
        
        if caller_rest is not None and callee.is_var_arg:
            c = infer_constraints(callee.arg_types[-1], caller_rest)
            constraints.extend(c)
    
    caller_num_args = len(arg_types)
    
    # Infer constraints for fixed arguments.
    for i in range(min(callee_num_args, caller_num_args)):
        c = infer_constraints(callee.arg_types[i], arg_types[i])
        constraints.extend(c)
    
    # Infer constraints for varargs.
    if callee.is_var_arg:
        for j in range(callee_num_args, caller_num_args):
            c = infer_constraints(callee.arg_types[-1], arg_types[j])
            constraints.extend(c)
    
    return constraints


list<Constraint> infer_constraints(Typ template, Typ actual):
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
    return template.accept(ConstraintBuilderVisitor(actual))


SUBTYPE_OF = 0
SUPERTYPE_OF = 1


class Constraint:
    """A representation of a type constraint, either T <: type or T :>
    type (T is a type variable).
    """
    int type_var   # Type variable id
    int op         # SUBTYPE_OF or SUPERTYPE_OF
    Typ target
    
    str __str__(self):
        op_str = '<:'
        if self.op == SUPERTYPE_OF:
            op_str = ':>'
        return '{} {} {}'.format(self.type_var, op_str, self.target)
    
    void __init__(self, int type_var, int op, Typ target):
        self.type_var = type_var
        self.op = op
        self.target = target


class ConstraintBuilderVisitor(TypeVisitor<list<Constraint>>):
    """Visitor class for inferring type constraints."""
    
    Typ actual # The type that is compared against a template
    
    void __init__(self, Typ actual):
        self.actual = actual
    
    # Trivial leaf types
    
    list<Constraint> visit_unbound_type(self, UnboundType template):
        return []
    
    list<Constraint> visit_any(self, Any template):
        return []
    
    list<Constraint> visit_void(self, Void template):
        return []
    
    list<Constraint> visit_none_type(self, NoneTyp template):
        return []
    
    # Non-trivial leaf type
    
    list<Constraint> visit_type_var(self, TypeVar template):
        return [Constraint(template.id, SUPERTYPE_OF, self.actual)]
    
    # Non-leaf types
    
    list<Constraint> visit_instance(self, Instance template):
        actual = self.actual
        if (isinstance(actual, Instance) and
                ((Instance)actual).typ.has_base(template.typ.full_name())):
            list<Constraint> res = []
            
            mapped = map_instance_to_supertype((Instance)actual, template.typ)
            for i in range(len(template.args)):
                # The constraints for generic type parameters are invariant.
                # Include the default constraint and its negation to achieve
                # the effect.
                cb = infer_constraints(template.args[i], mapped.args[i])
                res.extend(cb)
                res.extend(negate_constraints(cb))
                
            return res
        elif isinstance(actual, Any):
            # IDEA: Include both ways, i.e. add negation as well?
            return self.infer_against_any(template.args)
        else:
            return []
    
    list<Constraint> visit_callable(self, Callable template):
        if isinstance(self.actual, Callable):
            cactual = (Callable)self.actual
            # FIX verify argument counts
            # FIX what if one of the functions is generic
            list<Constraint> res = []
            for i in range(len(template.arg_types)):
                # Negate constraints due function argument type contravariance.
                res.extend(negate_constraints(infer_constraints(
                    template.arg_types[i], cactual.arg_types[i])))
            res.extend(infer_constraints(template.ret_type, cactual.ret_type))
            return res
        elif isinstance(self.actual, Any):
            # FIX what if generic
            res = self.infer_against_any(template.arg_types)
            res.extend(infer_constraints(template.ret_type, Any()))
            return res
        else:
            return []
    
    list<Constraint> visit_tuple_type(self, TupleType template):
        actual = self.actual
        if (isinstance(actual, TupleType) and
                len(((TupleType)actual).items) == len(template.items)):
            list<Constraint> res = []
            for i in range(len(template.items)):
                res.extend(infer_constraints(template.items[i],
                                             ((TupleType)actual).items[i]))
            return res
        elif isinstance(actual, Any):
            return self.infer_against_any(template.items)
        else:
            return []
    
    list<Constraint> infer_against_any(self, list<Typ> types):
        list<Constraint> res = []
        for t in types:
            res.extend(infer_constraints(t, Any()))
        return res


list<Constraint> negate_constraints(list<Constraint> constraints):
    list<Constraint> res = []
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
