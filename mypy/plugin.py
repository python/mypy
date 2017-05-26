"""Plugin architecture for custom type checking rules for specific functions, etc.

A plugin can, for example, infer better types for tricky functions such as "open".
"""

from typing import Callable, List, Tuple, Optional

from mypy.nodes import Expression, StrExpr
from mypy.types import Type, Instance, CallableType


# Create an Instance given full name of class and type arguments.
NamedInstanceCallback = Callable[[str, List[Type]], Type]

# A callback that infers the return type of a function with a special signature.
#
# A no-op callback would just return the inferred return type, but a useful callback
# at least sometimes can infer a more precise type.
FunctionHook = Callable[
    [
        List[List[Type]],        # List of types caller provides for each formal argument
        List[List[Expression]],  # Actual argument expressions for each formal argument
        Type,                    # Return type for call inferred using the regular signature
        NamedInstanceCallback    # Callable for constructing a named instance type
    ],
    Type  # Return type inferred by the callback
]


class Plugin:
    """Base class of type checker plugins.

    This defines a no-op plugin.  Subclasses can override some methods to
    provide some actual functionality.

    All get_ methods are treated as pure functions (you should assume that
    results might be cached).
    """

    # TODO: Way of chaining multiple plugins

    def __init__(self, python_version: Tuple[int, int]) -> None:
        self.python_version = python_version

    def get_function_hook(self, fullname: str) -> Optional[FunctionHook]:
        return None

    # TODO: method / metaclass / class decorator hooks


class DefaultPlugin(Plugin):
    """Type checker plugin that is enabled by default."""

    def get_function_hook(self, fullname: str) -> Optional[FunctionHook]:
        if fullname == 'contextlib.contextmanager':
            return contextmanager_callback
        elif fullname == 'builtins.open' and self.python_version[0] == 3:
            return open_callback
        return None


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
