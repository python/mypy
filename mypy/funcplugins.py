"""Plugins that implement special type checking rules for individual functions.

The plugins infer better types for tricky functions such as "open".
"""

from typing import Tuple, Dict, Callable, List

from mypy.nodes import Expression, StrExpr
from mypy.types import Type, Instance, CallableType


# A callback that infers the return type of a function with a special signature.
#
# A no-op callback would just return the inferred return type, but a useful callback
# at least sometimes can infer a more precise type.
PluginCallback = Callable[
    [
        List[List[Type]],        # List of types caller provides for each formal argument
        List[List[Expression]],  # Actual argument expressions for each formal argument
        Type,                    # Return type for call inferred using the regular signature
        Callable[[str, List[Type]], Type]  # Callable for constructing a named instance type
    ],
    Type  # Return type inferred by the callback
]


def get_function_plugin_callbacks(python_version: Tuple[int, int]) -> Dict[str, PluginCallback]:
    """Return all available function plugins for a given Python version."""
    if python_version[0] == 3:
        return {
            'builtins.open': open_callback,
            'contextlib.contextmanager': contextmanager_callback,
        }
    else:
        return {
            'contextlib.contextmanager': contextmanager_callback,
        }


def open_callback(
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'open'.

    Infer TextIO or BinaryIO as the return value if the mode argument is not
    given or is a literal.
    """
    mode = None
    if not arg_types or len(arg_types[1]) != 1:
        mode = 'r'
    elif isinstance(args[1][0], StrExpr):
        mode = args[1][0].value
    if mode is not None:
        assert isinstance(inferred_return_type, Instance)
        if 'b' in mode:
            return named_generic_type('typing.BinaryIO', [])
        else:
            return named_generic_type('typing.TextIO', [])
    return inferred_return_type


def contextmanager_callback(
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    # Be defensive, just in case.
    if arg_types and len(arg_types[0]) == 1:
        arg_type = arg_types[0][0]
        if isinstance(arg_type, CallableType) and isinstance(inferred_return_type, CallableType):
            # The stub signature doesn't preserve information about arguments so
            # add them back here.
            return inferred_return_type.copy_modified(
                arg_types=arg_type.arg_types,
                arg_kinds=arg_type.arg_kinds,
                arg_names=arg_type.arg_names)
    return inferred_return_type
