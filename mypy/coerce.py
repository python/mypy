from typing import cast

from mypy.nodes import Node, TypeInfo, CoerceExpr, JavaCast
from mypy.types import (
    Type, Instance, Void, NoneTyp, AnyType
)
from mypy.sametypes import is_same_type
from mypy.subtypes import is_proper_subtype
from mypy.rttypevars import translate_runtime_type_vars_in_context


def coerce(expr: Node, target_type: Type, source_type: Type, context: TypeInfo,
           is_wrapper_class: bool = False, is_java: bool = False) -> Node:
    """Build an expression that coerces expr from source_type to target_type.

    Return bare expr if the coercion is trivial (always a no-op).
    """
    if is_trivial_coercion(target_type, source_type, is_java):
        res = expr
    else:
        # Translate type variables to expressions that fetch the value of a
        # runtime type variable.
        target = translate_runtime_type_vars_in_context(target_type, context,
                                                        is_java)
        source = translate_runtime_type_vars_in_context(source_type, context,
                                                        is_java)
        res = CoerceExpr(expr, target, source, is_wrapper_class)

    if is_java and ((isinstance(source_type, Instance) and
                     (cast(Instance, source_type)).erased)
                    or (isinstance(res, CoerceExpr) and
                        isinstance(target_type, Instance))):
        res = JavaCast(res, target_type)

    return res


def is_trivial_coercion(target_type: Type, source_type: Type,
                        is_java: bool) -> bool:
    """Is an implicit coercion from source_type to target_type a no-op?

    Note that we omit coercions of form any <= C, unless C is a primitive that
    may have a special representation.
    """
    # FIX: Replace type vars in source type with any?
    if isinstance(source_type, Void) or is_same_type(target_type, source_type):
        return True

    # Coercions from a primitive type to any other type are non-trivial, since
    # we may have to change the representation.
    if not is_java and is_special_primitive(source_type):
        return False

    return (is_proper_subtype(source_type, target_type)
            or isinstance(source_type, NoneTyp)
            or isinstance(target_type, AnyType))


def is_special_primitive(type: Type) -> bool:
    """Is type a primitive with a special runtime representation?

    There needs to be explicit corcions to/from special primitive types. For
    example, floats need to boxed/unboxed. The special primitive types include
    int, float and bool.
    """
    return (isinstance(type, Instance)
            and (cast(Instance, type)).type.fullname() in ['builtins.int',
                                                           'builtins.float',
                                                           'builtins.bool'])
