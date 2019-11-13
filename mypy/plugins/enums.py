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
from mypy.types import Type, Instance, LiteralType, get_proper_type

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

    if isinstance(underlying_type, Instance) and underlying_type.type.fullname == 'enum.auto':
        # TODO: Deduce the correct inferred type when the user uses 'enum.auto'.
        # We should use the same strategy we end up picking up above.
        return ctx.default_attr_type

    return underlying_type


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
