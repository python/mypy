"""Utilities for type argument inference."""

from typing import List

from mypy.constraints import infer_constraints, infer_constraints_for_callable
from mypy.types import Type, Callable
from mypy.solve import solve_constraints
from mypy.constraints import SUBTYPE_OF


def infer_function_type_arguments(callee_type: Callable,
                                  arg_types: List[Type],
                                  arg_kinds: List[int],
                                  formal_to_actual: List[List[int]]) -> List[Type]:
    """Infer the type arguments of a generic function.

    Return an array of lower bound types for the type variables -1 (at
    index 0), -2 (at index 1), etc. A lower bound is None if a value
    could not be inferred.

    Arguments:
      callee_type: the target generic function
      arg_types: argument types at the call site
      arg_kinds: nodes.ARG_* values for arg_types
      formal_to_actual: mapping from formal to actual variable indices
    """
    # Infer constraints.
    constraints = infer_constraints_for_callable(
        callee_type, arg_types, arg_kinds, formal_to_actual)

    # Solve constraints.
    type_vars = callee_type.type_var_ids()
    return solve_constraints(type_vars, constraints)


def infer_type_arguments(type_var_ids: List[int],
                         template: Type, actual: Type) -> List[Type]:
    # Like infer_function_type_arguments, but only match a single type
    # against a generic type.
    constraints = infer_constraints(template, actual, SUBTYPE_OF)
    return solve_constraints(type_var_ids, constraints)
