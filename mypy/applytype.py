from typing import List, Dict

import mypy.subtypes
from mypy.sametypes import is_same_type
from mypy.expandtype import expand_type
from mypy.types import Type, TypeVarId, TypeVarType, CallableType, AnyType, Void
from mypy.messages import MessageBuilder
from mypy.nodes import Context


def apply_generic_arguments(callable: CallableType, types: List[Type],
                            msg: MessageBuilder, context: Context) -> Type:
    """Apply generic type arguments to a callable type.

    For example, applying [int] to 'def [T] (T) -> T' results in
    'def (int) -> int'.

    Note that each type can be None; in this case, it will not be applied.
    """
    tvars = callable.variables
    if len(tvars) != len(types):
        msg.incompatible_type_application(len(tvars), len(types), context)
        return AnyType()

    # Check that inferred type variable values are compatible with allowed
    # values and bounds.  Also, promote subtype values to allowed values.
    types = types[:]
    for i, type in enumerate(types):
        values = callable.variables[i].values
        if values and type:
            if isinstance(type, AnyType):
                continue
            if isinstance(type, TypeVarType) and type.values:
                # Allow substituting T1 for T if every allowed value of T1
                # is also a legal value of T.
                if all(any(is_same_type(v, v1) for v in values)
                       for v1 in type.values):
                    continue
            for value in values:
                if mypy.subtypes.is_subtype(type, value):
                    types[i] = value
                    break
            else:
                msg.incompatible_typevar_value(callable, i + 1, type, context)

        upper_bound = callable.variables[i].upper_bound
        if type and not mypy.subtypes.satisfies_upper_bound(type, upper_bound):
            msg.incompatible_typevar_value(callable, i + 1, type, context)

    # Create a map from type variable id to target type.
    id_to_type = {}  # type: Dict[TypeVarId, Type]
    for i, tv in enumerate(tvars):
        if types[i]:
            id_to_type[tv.id] = types[i]

    # Apply arguments to argument types.
    arg_types = [expand_type(at, id_to_type) for at in callable.arg_types]

    # The callable may retain some type vars if only some were applied.
    remaining_tvars = [tv for tv in tvars if tv.id not in id_to_type]

    return callable.copy_modified(
        arg_types=arg_types,
        ret_type=expand_type(callable.ret_type, id_to_type),
        variables=remaining_tvars,
    )
