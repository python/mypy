"""Plugins that implement special type checking rules for individual functions.

The plugins infer better types for tricky functions such as "open".
"""

from typing import Tuple, Dict, Callable, List

from mypy.nodes import Expression, StrExpr
from mypy.types import Type, Instance, CallableType


PluginCallback = Callable[[List[Type],
                           Type,
                           List[Expression],
                           Callable[[str, List[Type]], Type]],
                          Type]


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
        arg_types: List[Type],
        inferred_return_type: Type,
        args: List[Expression],
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'open'.

    Infer IO[str] or IO[bytes] as the return value if the mode argument is not
    given or is a literal.
    """
    mode = None
    if arg_types[1] is None:
        mode = 'r'
    elif isinstance(args[1], StrExpr):
        mode = args[1].value
    if mode is not None:
        assert isinstance(inferred_return_type, Instance)
        if 'b' in mode:
            arg = named_generic_type('builtins.bytes', [])
        else:
            arg = named_generic_type('builtins.str', [])
        return Instance(inferred_return_type.type, [arg])
    return inferred_return_type


def contextmanager_callback(
        arg_types: List[Type],
        inferred_return_type: Type,
        args: List[Expression],
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    arg_type = arg_types[0]
    if isinstance(arg_type, CallableType) and isinstance(inferred_return_type, CallableType):
        # The stub signature doesn't preserve information about arguments so
        # add them back here.
        return inferred_return_type.copy_modified(
            arg_types=arg_type.arg_types,
            arg_kinds=arg_type.arg_kinds,
            arg_names=arg_type.arg_names)
    return inferred_return_type
