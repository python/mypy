"""
This file contains a variety of plugins for refining how mypy infers types of
expressions involving Enums.

Currently, this file focuses on providing better inference for expressions like
'SomeEnum.FOO.name' and 'SomeEnum.FOO.value'. Note that the type of both expressions
will vary depending on exactly which instance of SomeEnum we're looking at.

Note that this file does *not* contain all special-cased logic related to enums:
we actually bake some of it directly in to the semantic analysis layer (see
semanal_enum.py).
"""
from typing import Optional
from typing_extensions import Final

import mypy.plugin  # To avoid circular imports.
from mypy.types import Type, Instance, LiteralType, CallableType, ProperType, get_proper_type

# Note: 'enum.EnumMeta' is deliberately excluded from this list. Classes that directly use
# enum.EnumMeta do not necessarily automatically have the 'name' and 'value' attributes.
ENUM_PREFIXES = {'enum.Enum', 'enum.IntEnum', 'enum.Flag', 'enum.IntFlag'}  # type: Final
ENUM_NAME_ACCESS = (
    {'{}.name'.format(prefix) for prefix in ENUM_PREFIXES}
    | {'{}._name_'.format(prefix) for prefix in ENUM_PREFIXES}
)  # type: Final
ENUM_VALUE_ACCESS = (
    {'{}.value'.format(prefix) for prefix in ENUM_PREFIXES}
    | {'{}._value_'.format(prefix) for prefix in ENUM_PREFIXES}
)  # type: Final


def enum_name_callback(ctx: 'mypy.plugin.AttributeContext') -> Type:
    """This plugin refines the 'name' attribute in enums to act as if
    they were declared to be final.

    For example, the expression 'MyEnum.FOO.name' normally is inferred
    to be of type 'str'.

    This plugin will instead make the inferred type be a 'str' where the
    last known value is 'Literal["FOO"]'. This means it would be legal to
    use 'MyEnum.FOO.name' in contexts that expect a Literal type, just like
    any other Final variable or attribute.

    This plugin assumes that the provided context is an attribute access
    matching one of the strings found in 'ENUM_NAME_ACCESS'.
    """
    enum_field_name = _extract_underlying_field_name(ctx.type)
    if enum_field_name is None:
        return ctx.default_attr_type
    else:
        str_type = ctx.api.named_generic_type('builtins.str', [])
        literal_type = LiteralType(enum_field_name, fallback=str_type)
        return str_type.copy_modified(last_known_value=literal_type)


def _infer_value_type_with_auto_fallback(
        ctx: 'mypy.plugin.AttributeContext',
        proper_type: Optional[ProperType]) -> Optional[Type]:
    """Figure out the type of an enum value accounting for `auto()`.

    This method is a no-op for a `None` proper_type and also in the case where
    the type is not "enum.auto"
    """
    if proper_type is None:
        return None
    if (isinstance(proper_type, Instance) and
            proper_type.type.fullname == 'enum.auto'):
        info = ctx.type.type
        # Find the first _generate_next_value_ on the mro.  We need to know
        # if it is `Enum` because `Enum` types say that the return-value of
        #`_generate_next_value_` is `Any`.  In reality the default `auto()`
        # returns an `int` (presumably the `Any` in typeshed is to make it
        # easier to subclass and change the returned type).
        type_with_generate_next_value = next(
            (type_info for type_info in info.mro
                if type_info.names.get('_generate_next_value_')),
            None)
        if type_with_generate_next_value is None:
            return ctx.default_attr_type

        stnode = type_with_generate_next_value.get('_generate_next_value_')
        if stnode is None:
            return ctx.default_attr_type

        # This should be a `CallableType`
        node_type = stnode.type
        if isinstance(node_type, CallableType):
            if type_with_generate_next_value.fullname == 'enum.Enum':
                int_type = ctx.api.named_generic_type('builtins.int', [])
                return int_type
            return get_proper_type(node_type.ret_type)
        return ctx.default_attr_type
    return proper_type


def enum_value_callback(ctx: 'mypy.plugin.AttributeContext') -> Type:
    """This plugin refines the 'value' attribute in enums to refer to
    the original underlying value. For example, suppose we have the
    following:

        class SomeEnum:
            FOO = A()
            BAR = B()

    By default, mypy will infer that 'SomeEnum.FOO.value' and
    'SomeEnum.BAR.value' both are of type 'Any'. This plugin refines
    this inference so that mypy understands the expressions are
    actually of types 'A' and 'B' respectively. This better reflects
    the actual runtime behavior.

    This plugin works simply by looking up the original value assigned
    to the enum. For example, when this plugin sees 'SomeEnum.BAR.value',
    it will look up whatever type 'BAR' had in the SomeEnum TypeInfo and
    use that as the inferred type of the overall expression.

    This plugin assumes that the provided context is an attribute access
    matching one of the strings found in 'ENUM_VALUE_ACCESS'.
    """
    enum_field_name = _extract_underlying_field_name(ctx.type)
    if enum_field_name is None:
        # We do not know the enum field name (perhaps it was passed to a
        # function and we only know that it _is_ a member).  All is not lost
        # however, if we can prove that the all of the enum members have the
        # same value-type, then it doesn't matter which member was passed in.
        # The value-type is still known.
        if isinstance(ctx.type, Instance):
            info = ctx.type.type
            stnodes = (info.get(name) for name in info.names)
            # Enums _can_ have methods.
            # Omit methods for our value inference.
            stnodes_non_method = (
                n for n in stnodes if not isinstance(n.type, CallableType))
            node_types = (
                get_proper_type(n.type) if n else None
                for n in stnodes_non_method)
            proper_types = (
                _infer_value_type_with_auto_fallback(ctx, t)
                for t in node_types)
            underlying_type = next(proper_types, None)
            if underlying_type is None:
                return ctx.default_attr_type
            all_same_value_type = all(
                proper_type is not None and proper_type == underlying_type
                for proper_type in proper_types)
            if all_same_value_type:
                if underlying_type is not None:
                    return underlying_type
        return ctx.default_attr_type

    assert isinstance(ctx.type, Instance)
    info = ctx.type.type
    stnode = info.get(enum_field_name)
    if stnode is None:
        return ctx.default_attr_type

    underlying_type = get_proper_type(stnode.type)
    if underlying_type is None:
        # TODO: Deduce the inferred type if the user omits adding their own default types.
        # TODO: Consider using the return type of `Enum._generate_next_value_` here?
        return ctx.default_attr_type

    return _infer_value_type_with_auto_fallback(ctx, underlying_type)


def _extract_underlying_field_name(typ: Type) -> Optional[str]:
    """If the given type corresponds to some Enum instance, returns the
    original name of that enum. For example, if we receive in the type
    corresponding to 'SomeEnum.FOO', we return the string "SomeEnum.Foo".

    This helper takes advantage of the fact that Enum instances are valid
    to use inside Literal[...] types. An expression like 'SomeEnum.FOO' is
    actually represented by an Instance type with a Literal enum fallback.

    We can examine this Literal fallback to retrieve the string.
    """
    typ = get_proper_type(typ)
    if not isinstance(typ, Instance):
        return None

    if not typ.type.is_enum:
        return None

    underlying_literal = typ.last_known_value
    if underlying_literal is None:
        return None

    # The checks above have verified this LiteralType is representing an enum value,
    # which means the 'value' field is guaranteed to be the name of the enum field
    # as a string.
    assert isinstance(underlying_literal.value, str)
    return underlying_literal.value
