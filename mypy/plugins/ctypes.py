"""Plugin to provide accurate types for some parts of the ctypes module."""

from typing import Optional

# Fully qualified instead of "from mypy.plugin import ..." to avoid circular import problems.
import mypy.plugin
from mypy.types import CallableType, Instance, Type, UnionType

def _find_simplecdata_base_arg(tp: Instance) -> Optional[Type]:
    """Try to find a parametrized _SimpleCData in tp's bases and return its single type argument.

    None is returned if _SimpleCData appears nowhere in tp's (direct or indirect) bases,
    or if it doesn't have a single type argument.
    """

    for mro_type in tp.type.mro:
        for base in mro_type.bases:
            if len(base.args) == 1:
                return base.args[0]
    return None

def _autoconvertible_to_cdata(tp: Type, api: 'mypy.plugin.CheckerPluginInterface') -> Type:
    """Get a type that is compatible with all types that can be implicitly converted to the given
    CData type.

    Examples:
    * c_int -> Union[c_int, int]
    * c_char_p -> Union[c_char_p, bytes, int, NoneType]
    * MyStructure -> MyStructure
    """

    # Every type can be converted from itself (obviously).
    allowed_types = [tp]
    if isinstance(tp, Instance):
        unboxed = _find_simplecdata_base_arg(tp)
        if unboxed is not None:
            # If _SimpleCData appears in tp's (direct or indirect) bases, its type argument
            # specifies the type's "unboxed" version, which can always be converted back to
            # the original "boxed" type.
            allowed_types.append(unboxed)

            if tp.type.has_base('ctypes._PointerLike'):
                # Pointer-like _SimpleCData subclasses can also be converted from an int or None.
                allowed_types.append(api.named_generic_type('builtins.int', []))
                allowed_types.append(api.named_generic_type('builtins.NoneType', []))

    return UnionType.make_simplified_union(allowed_types)

def _autounboxed_cdata(tp: Type) -> Type:
    """Get the auto-unboxed version of a CData type, if applicable.

    For *direct* _SimpleCData subclasses, the only type argument of _SimpleCData in the bases list
    is returned.
    For all other CData types, including indirect _SimpleCData subclasses, tp is returned as-is.
    """

    if isinstance(tp, Instance):
        for base in tp.type.bases:
            if base.type.fullname() == 'ctypes._SimpleCData':
                # If tp has _SimpleCData as a direct base class,
                # the auto-unboxed type is the single type argument of the _SimpleCData type.
                assert len(base.args) == 1
                return base.args[0]
    # If tp is not a concrete type, or if there is no _SimpleCData in the bases,
    # the type is not auto-unboxed.
    return tp

def _get_array_element_type(tp: Instance) -> Optional[Type]:
    """Get the element type of the Array type tp, or None if not specified."""

    assert tp.type.fullname() == 'ctypes.Array'
    if len(tp.args) == 1:
        return tp.args[0]
    else:
        return None

# TODO Untested
def array_init_callback(ctx: 'mypy.plugin.MethodSigContext') -> CallableType:
    """Callback to provide an accurate signature for ctypes.Array.__init__."""
    print(f"array_init_callback({ctx!r})")  # XXX debugging

    et = _get_array_element_type(ctx.type)
    if et is not None:
        allowed = _autoconvertible_to_cdata(et, ctx.api)
        return ctx.default_signature.copy_modified(arg_types=[allowed])
    return ctx.default_signature

def array_getitem_callback(ctx: 'mypy.plugin.MethodContext') -> Type:
    """Callback to provide an accurate return type for ctypes.Array.__getitem__."""
    print(f"array_getitem_callback({ctx!r})")  # XXX debugging

    et = _get_array_element_type(ctx.type)
    if et is not None:
        unboxed = _autounboxed_cdata(et)
        assert len(ctx.arg_types) == 1
        assert len(ctx.arg_types[0]) == 1
        index_type = ctx.arg_types[0][0]
        if isinstance(index_type, Instance):
            if index_type.type.has_base('builtins.int'):
                return unboxed
            elif index_type.type.has_base('builtins.slice'):
                return ctx.api.named_generic_type('builtins.list', [unboxed])
    return ctx.default_return_type

# TODO Would a signature callback be better?
'''
def array_getitem_callback(ctx: 'mypy.plugin.MethodSigContext') -> CallableType:
    """Callback to provide an accurate signature for ctypes.Array.__getitem__."""
    print(f"array_getitem_callback({ctx!r})")  # XXX debugging

    et = _get_array_element_type(ctx.type)
    print(et)
    if et is not None:
        unboxed = _autounboxed_cdata(et)
        assert len(ctx.default_signature.arg_types) == 1
        index_type = ctx.default_signature.arg_types[0]
        if isinstance(index_type, Instance):
            if index_type.type.has_base('builtins.int'):
                return ctx.default_signature.copy_modified(ret_type=unboxed)
            elif index_type.type.has_base('builtins.slice'):
                return ctx.default_signature.copy_modified(
                    ret_type=ctx.api.named_generic_type('builtins.list', [unboxed])
                )
    return ctx.default_signature
#'''

def array_iter_callback(ctx: 'mypy.plugin.MethodContext') -> Type:
    """Callback to provide an accurate return type for ctypes.Array.__iter__."""
    print(f"array_iter_callback({ctx!r})")  # XXX debugging

    et = _get_array_element_type(ctx.type)
    if et is not None:
        unboxed = _autounboxed_cdata(et)
        return ctx.api.named_generic_type('typing.Iterator', [unboxed])
    return ctx.default_return_type
