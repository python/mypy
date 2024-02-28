"""Utilities for defining primitive ops.

Most of the ops can be automatically generated by matching against AST
nodes and types. For example, a func_op is automatically generated when
a specific function is called with the specific positional argument
count and argument types.

Example op definition:

list_len_op = func_op(name='builtins.len',
                      arg_types=[list_rprimitive],
                      result_type=short_int_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=emit_len)

This op is automatically generated for calls to len() with a single
list argument. The result type is short_int_rprimitive, and this
never raises an exception (ERR_NEVER). The function emit_len is used
to generate C for this op.  The op can also be manually generated using
"list_len_op". Ops that are only generated automatically don't need to
be assigned to a module attribute.

Ops defined with custom_op are only explicitly generated in
mypyc.irbuild and won't be generated automatically. They are always
assigned to a module attribute, as otherwise they won't be accessible.

The actual ops are defined in other submodules of this package, grouped
by category.

Most operations have fallback implementations that apply to all possible
arguments and types. For example, there are generic implementations of
arbitrary function and method calls, and binary operators. These generic
implementations are typically slower than specialized ones, but we tend
to rely on them for infrequently used ops. It's impractical to have
optimized implementations of all ops.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from mypyc.ir.ops import StealsDescription, PrimitiveDescription
from mypyc.ir.rtypes import RType

# Error kind for functions that return negative integer on exception. This
# is only used for primitives. We translate it away during IR building.
ERR_NEG_INT: Final = 10


class CFunctionDescription(NamedTuple):
    name: str
    arg_types: list[RType]
    return_type: RType
    var_arg_type: RType | None
    truncated_type: RType | None
    c_function_name: str
    error_kind: int
    steals: StealsDescription
    is_borrowed: bool
    ordering: list[int] | None
    extra_int_constants: list[tuple[int, RType]]
    priority: int


# A description for C load operations including LoadGlobal and LoadAddress
class LoadAddressDescription(NamedTuple):
    name: str
    type: RType
    src: str  # name of the target to load


# CallC op for method call(such as 'str.join')
method_call_ops: dict[str, list[CFunctionDescription]] = {}

# CallC op for top level function call(such as 'builtins.list')
function_ops: dict[str, list[CFunctionDescription]] = {}

# CallC op for binary ops
binary_ops: dict[str, list[PrimitiveDescription]] = {}

# CallC op for unary ops
unary_ops: dict[str, list[CFunctionDescription]] = {}

builtin_names: dict[str, tuple[RType, str]] = {}

primitive_ops: dict[str, PrimitiveDescription] = {}


def method_op(
    name: str,
    arg_types: list[RType],
    return_type: RType,
    c_function_name: str,
    error_kind: int,
    var_arg_type: RType | None = None,
    truncated_type: RType | None = None,
    ordering: list[int] | None = None,
    extra_int_constants: list[tuple[int, RType]] | None = None,
    steals: StealsDescription = False,
    is_borrowed: bool = False,
    priority: int = 1,
) -> CFunctionDescription:
    """Define a c function call op that replaces a method call.

    This will be automatically generated by matching against the AST.

    Args:
        name: short name of the method (for example, 'append')
        arg_types: argument types; the receiver is always the first argument
        return_type: type of the return value. Use void_rtype to represent void.
        c_function_name: name of the C function to call
        error_kind: how errors are represented in the result (one of ERR_*)
        var_arg_type: type of all variable arguments
        truncated_type: type to truncated to(See Truncate for info)
                        if it's defined both return_type and it should be non-referenced
                        integer types or bool type
        ordering: optional ordering of the arguments, if defined,
                  reorders the arguments accordingly.
                  should never be used together with var_arg_type.
                  all the other arguments(such as arg_types) are in the order
                  accepted by the python syntax(before reordering)
        extra_int_constants: optional extra integer constants as the last arguments to a C call
        steals: description of arguments that this steals (ref count wise)
        is_borrowed: if True, returned value is borrowed (no need to decrease refcount)
        priority: if multiple ops match, the one with the highest priority is picked
    """
    if extra_int_constants is None:
        extra_int_constants = []
    ops = method_call_ops.setdefault(name, [])
    desc = CFunctionDescription(
        name,
        arg_types,
        return_type,
        var_arg_type,
        truncated_type,
        c_function_name,
        error_kind,
        steals,
        is_borrowed,
        ordering,
        extra_int_constants,
        priority,
    )
    ops.append(desc)
    return desc


def function_op(
    name: str,
    arg_types: list[RType],
    return_type: RType,
    c_function_name: str,
    error_kind: int,
    var_arg_type: RType | None = None,
    truncated_type: RType | None = None,
    ordering: list[int] | None = None,
    extra_int_constants: list[tuple[int, RType]] | None = None,
    steals: StealsDescription = False,
    is_borrowed: bool = False,
    priority: int = 1,
) -> CFunctionDescription:
    """Define a c function call op that replaces a function call.

    This will be automatically generated by matching against the AST.

    Most arguments are similar to method_op().

    Args:
        name: full name of the function
        arg_types: positional argument types for which this applies
    """
    if extra_int_constants is None:
        extra_int_constants = []
    ops = function_ops.setdefault(name, [])
    desc = CFunctionDescription(
        name,
        arg_types,
        return_type,
        var_arg_type,
        truncated_type,
        c_function_name,
        error_kind,
        steals,
        is_borrowed,
        ordering,
        extra_int_constants,
        priority,
    )
    ops.append(desc)
    return desc


def binary_op(
    name: str,
    arg_types: list[RType],
    return_type: RType,
    error_kind: int,
    c_function_name: str | None = None,
    primitive_name: str | None = None,
    var_arg_type: RType | None = None,
    truncated_type: RType | None = None,
    ordering: list[int] | None = None,
    extra_int_constants: list[tuple[int, RType]] | None = None,
    steals: StealsDescription = False,
    is_borrowed: bool = False,
    priority: int = 1,
) -> PrimitiveDescription:
    """Define a c function call op for a binary operation.

    This will be automatically generated by matching against the AST.

    Most arguments are similar to method_op(), but exactly two argument types
    are expected.
    """
    assert c_function_name is not None or primitive_name is not None
    assert not (c_function_name is not None and primitive_name is not None)
    if extra_int_constants is None:
        extra_int_constants = []
    ops = binary_ops.setdefault(name, [])
    desc = PrimitiveDescription(
        name=primitive_name or name,
        arg_types=arg_types,
        return_type=return_type,
        var_arg_type=var_arg_type,
        truncated_type=truncated_type,
        c_function_name=c_function_name,
        error_kind=error_kind,
        steals=steals,
        is_borrowed=is_borrowed,
        ordering=ordering,
        extra_int_constants=extra_int_constants,
        priority=priority,
    )
    ops.append(desc)
    return desc


def custom_op(
    arg_types: list[RType],
    return_type: RType,
    c_function_name: str,
    error_kind: int,
    var_arg_type: RType | None = None,
    truncated_type: RType | None = None,
    ordering: list[int] | None = None,
    extra_int_constants: list[tuple[int, RType]] | None = None,
    steals: StealsDescription = False,
    is_borrowed: bool = False,
) -> CFunctionDescription:
    """Create a one-off CallC op that can't be automatically generated from the AST.

    Most arguments are similar to method_op().
    """
    if extra_int_constants is None:
        extra_int_constants = []
    return CFunctionDescription(
        "<custom>",
        arg_types,
        return_type,
        var_arg_type,
        truncated_type,
        c_function_name,
        error_kind,
        steals,
        is_borrowed,
        ordering,
        extra_int_constants,
        0,
    )


def unary_op(
    name: str,
    arg_type: RType,
    return_type: RType,
    c_function_name: str,
    error_kind: int,
    truncated_type: RType | None = None,
    ordering: list[int] | None = None,
    extra_int_constants: list[tuple[int, RType]] | None = None,
    steals: StealsDescription = False,
    is_borrowed: bool = False,
    priority: int = 1,
) -> CFunctionDescription:
    """Define a c function call op for an unary operation.

    This will be automatically generated by matching against the AST.

    Most arguments are similar to method_op(), but exactly one argument type
    is expected.
    """
    if extra_int_constants is None:
        extra_int_constants = []
    ops = unary_ops.setdefault(name, [])
    desc = CFunctionDescription(
        name,
        [arg_type],
        return_type,
        None,
        truncated_type,
        c_function_name,
        error_kind,
        steals,
        is_borrowed,
        ordering,
        extra_int_constants,
        priority,
    )
    ops.append(desc)
    return desc


def load_address_op(name: str, type: RType, src: str) -> LoadAddressDescription:
    assert name not in builtin_names, "already defined: %s" % name
    builtin_names[name] = (type, src)
    return LoadAddressDescription(name, type, src)


"""
def primitive_op(name: str,
                 arg_types: list[RType | None],
                 return_type: RType | int,
                 error_kind: int) -> PrimitiveDescription:
    assert name not in primitive_ops, f"already defined: {name}"
    desc = PrimitiveDescription(
        name=name,
        arg_types=arg_types,
        return_type=return_type,
        steals=False,
        is_borrowed=False,
        error_kind=error_kind)
    primitive_ops[name] = desc
    return desc
"""


# Import various modules that set up global state.
import mypyc.primitives.bytes_ops
import mypyc.primitives.dict_ops
import mypyc.primitives.float_ops
import mypyc.primitives.int_ops
import mypyc.primitives.list_ops
import mypyc.primitives.misc_ops
import mypyc.primitives.str_ops
import mypyc.primitives.tuple_ops  # noqa: F401
