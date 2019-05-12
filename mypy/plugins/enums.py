from typing import Optional
import mypy.plugin  # To avoid circular imports.
from mypy.types import Type, Instance, LiteralType
from mypy.nodes import Var, MDEF

# Note: 'enum.EnumMeta' is deliberately excluded from this list. Classes that directly use
# enum.EnumMeta do not necessarily automatically have the 'name' and 'value' attributes.
ENUM_PREFIXES = ['enum.Enum', 'enum.IntEnum', 'enum.Flag', 'enum.IntFlag']
ENUM_NAME_ACCESS = (
    ['{}.name'.format(prefix) for prefix in ENUM_PREFIXES]
    + ['{}._name_'.format(prefix) for prefix in ENUM_PREFIXES]
)
ENUM_VALUE_ACCESS = (
    ['{}.value'.format(prefix) for prefix in ENUM_PREFIXES]
    + ['{}._value_'.format(prefix) for prefix in ENUM_PREFIXES]
)


def enum_name_callback(ctx: 'mypy.plugin.AttributeContext') -> Type:
    enum_field_name = extract_underlying_field_name(ctx.type)
    if enum_field_name is None:
        return ctx.default_attr_type
    else:
        str_type = ctx.api.named_generic_type('builtins.str', [])
        literal_type = LiteralType(enum_field_name, fallback=str_type)
        return str_type.copy_modified(last_known_value=literal_type)


def enum_value_callback(ctx: 'mypy.plugin.AttributeContext') -> Type:
    enum_field_name = extract_underlying_field_name(ctx.type)
    if enum_field_name is None:
        return ctx.default_attr_type

    assert isinstance(ctx.type, Instance)
    info = ctx.type.type
    stnode = info.get(enum_field_name)
    if stnode is None:
        return ctx.default_attr_type

    underlying_type = stnode.type
    if underlying_type is None:
        # TODO: Deduce the inferred type if the user omits adding their own default types.
        # TODO: Consider using the return type of `Enum._generate_next_value_` here?
        return ctx.default_attr_type

    if isinstance(underlying_type, Instance) and underlying_type.type.fullname() == 'enum.auto':
        # TODO: Deduce the correct inferred type when the user uses 'enum.auto'.
        # We should use the same strategy we end up picking up above.
        return ctx.default_attr_type

    return underlying_type


def extract_underlying_field_name(typ: Type) -> Optional[str]:
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
