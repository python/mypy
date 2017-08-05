from typing import List, Dict, Sequence, Tuple

import mypy.subtypes
from mypy.sametypes import is_same_type
from mypy.expandtype import expand_type
from mypy.types import (
    Type, TypeVarId, TypeVarType, TypeVisitor, CallableType, AnyType, PartialType,
    Instance, UnionType
)
from mypy.messages import MessageBuilder
from mypy.nodes import Context


def apply_generic_arguments(callable: CallableType, types: List[Type],
                            msg: MessageBuilder, context: Context) -> CallableType:
    """Apply generic type arguments to a callable type.

    For example, applying [int] to 'def [T] (T) -> T' results in
    'def (int) -> int'.

    Note that each type can be None; in this case, it will not be applied.
    """
    tvars = callable.variables
    assert len(tvars) == len(types)
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
                if isinstance(type, PartialType) or mypy.subtypes.is_subtype(type, value):
                    types[i] = value
                    break
            else:
                constraints = get_inferred_object_constraints(msg, callable.arg_types, type, i + 1)
                if constraints:
                    constrained_indeces = get_inferred_object_arg_indeces(
                        msg, constraints, callable.arg_types)
                    msg.incompatible_inferred_object_arguments(
                        callable, constrained_indeces, constraints, context)
                else:
                    msg.incompatible_typevar_value(callable, i + 1, type, context)
        upper_bound = callable.variables[i].upper_bound
        if (type and not isinstance(type, PartialType) and
                not mypy.subtypes.is_subtype(type, upper_bound)):
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


def get_inferred_object_constraints(msg: MessageBuilder,
                                    arg_types: Sequence[Type],
                                    type: Type,
                                    index: int) -> Dict[str, Tuple[str, ...]]:
    """Gets incompatible function arguments that are inferred as object based on the type
    constraints.

    An example of a constrained type is AnyStr which must be all str or all byte. When there is a
    mismatch of arguments with a constrained type like AnyStr, then the inferred type is object.
    """
    constraints = {}  # type: Dict[str, Tuple[str, ...]]
    if isinstance(type, Instance) and type.type.fullname() == 'builtins.object':
        if index == len(arg_types):
            # Index is off by one for '*' arguments
            constraints = add_inferred_object_arg_constraints(
                msg, constraints, arg_types[index - 1])
        else:
            constraints = add_inferred_object_arg_constraints(msg, constraints, arg_types[index])
    return constraints


def add_inferred_object_arg_constraints(msg: MessageBuilder,
                                        constraints: Dict[str, Tuple[str, ...]],
                                        arg_type: Type) -> Dict[str, Tuple[str, ...]]:
    if (isinstance(arg_type, TypeVarType) and
            arg_type.values and
            len(arg_type.values) > 1 and
            arg_type.name not in constraints.keys()):
        constraints[arg_type.name] = tuple(msg.format(val) for val in arg_type.values)
    elif isinstance(arg_type, UnionType):
        for item in arg_type.items:
            constraints = add_inferred_object_arg_constraints(msg, constraints, item)
    return constraints


def get_inferred_object_arg_indeces(msg: MessageBuilder,
                                    constraints: Dict[str, Tuple[str, ...]],
                                    arg_types: List[Type]) -> Dict[str, List[str]]:
    """Get the indeces of all arguments with inferred type of object and the same constraint.
    """
    indeces = {}  # type: Dict[str, List[str]]
    for constrained_type in constraints.keys():
        indeces[constrained_type] = []
        for i, type in enumerate(arg_types):
            if constrained_type in msg.format(type):
                indeces[constrained_type].append(str(i + 1))
    return indeces
