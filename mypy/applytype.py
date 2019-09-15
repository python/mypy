from typing import Dict, Sequence, Optional, Callable

import mypy.subtypes
import mypy.sametypes
from mypy.expandtype import expand_type
from mypy.types import (
    Type, TypeVarId, TypeVarType, CallableType, AnyType, PartialType, get_proper_types
)
from mypy.nodes import Context


def apply_generic_arguments(
        callable: CallableType, orig_types: Sequence[Optional[Type]],
        report_incompatible_typevar_value: Callable[[CallableType, Type, str, Context], None],
        context: Context,
        skip_unsatisfied: bool = False) -> CallableType:
    """Apply generic type arguments to a callable type.

    For example, applying [int] to 'def [T] (T) -> T' results in
    'def (int) -> int'.

    Note that each type can be None; in this case, it will not be applied.

    If `skip_unsatisfied` is True, then just skip the types that don't satisfy type variable
    bound or constraints, instead of giving an error.
    """
    tvars = callable.variables
    assert len(tvars) == len(orig_types)
    # Check that inferred type variable values are compatible with allowed
    # values and bounds.  Also, promote subtype values to allowed values.
    types = get_proper_types(orig_types)
    for i, type in enumerate(types):
        assert not isinstance(type, PartialType), "Internal error: must never apply partial type"
        values = get_proper_types(callable.variables[i].values)
        if type is None:
            continue
        if values:
            if isinstance(type, AnyType):
                continue
            if isinstance(type, TypeVarType) and type.values:
                # Allow substituting T1 for T if every allowed value of T1
                # is also a legal value of T.
                if all(any(mypy.sametypes.is_same_type(v, v1) for v in values)
                       for v1 in type.values):
                    continue
            matching = []
            for value in values:
                if mypy.subtypes.is_subtype(type, value):
                    matching.append(value)
            if matching:
                best = matching[0]
                # If there are more than one matching value, we select the narrowest
                for match in matching[1:]:
                    if mypy.subtypes.is_subtype(match, best):
                        best = match
                types[i] = best
            else:
                if skip_unsatisfied:
                    types[i] = None
                else:
                    report_incompatible_typevar_value(callable, type, callable.variables[i].name,
                                                      context)
        else:
            upper_bound = callable.variables[i].upper_bound
            if not mypy.subtypes.is_subtype(type, upper_bound):
                if skip_unsatisfied:
                    types[i] = None
                else:
                    report_incompatible_typevar_value(callable, type, callable.variables[i].name,
                                                      context)

    # Create a map from type variable id to target type.
    id_to_type = {}  # type: Dict[TypeVarId, Type]
    for i, tv in enumerate(tvars):
        typ = types[i]
        if typ:
            id_to_type[tv.id] = typ

    # Apply arguments to argument types.
    arg_types = [expand_type(at, id_to_type) for at in callable.arg_types]

    # The callable may retain some type vars if only some were applied.
    remaining_tvars = [tv for tv in tvars if tv.id not in id_to_type]

    return callable.copy_modified(
        arg_types=arg_types,
        ret_type=expand_type(callable.ret_type, id_to_type),
        variables=remaining_tvars,
    )
