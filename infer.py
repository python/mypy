import checker
from constraints import infer_constraints, infer_constraints_for_callable
from mtypes import Typ, Callable
from solve import solve_constraints


# Infer the type arguments of a generic function. Return an array of
# lower bound types for the type variables -1 (at index 0), -2 (at index 1),
# etc. A lower bound is nil if a value could not be inferred.
#
#   calleeType: the target generic function
#   argTypes:   argument types at the call site
#   isVarArg:   is the call a vararg call (if yes, last arg type is vararg)
#   basic:      references to basic types which are needed during inference
list<Typ> infer_function_type_arguments(Callable callee_type,
                                        list<Typ> arg_types,
                                        bool is_var_arg,
                                        checker.BasicTypes basic):
    # Infer constraints.
    constraints = infer_constraints_for_callable(callee_type, arg_types,
                                                 is_var_arg)
    
    # Solve constraints.
    type_vars = callee_type.type_var_ids()
    return solve_constraints(type_vars, constraints, basic)


# Like above, but only match a single type against a generic type.
list<Typ> infer_type_arguments(list<int> type_var_ids,
                               Typ template, Typ actual,
                               checker.BasicTypes basic):
    constraints = infer_constraints(template, actual)
    return solve_constraints(type_var_ids, constraints, basic)
