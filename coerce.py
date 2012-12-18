from nodes import Node, TypeInfo, CoerceExpr, JavaCast
from mtypes import (
    Typ, Instance, Void, NoneTyp, Any
)
from sametypes import is_same_type
from subtypes import is_proper_subtype
from rttypevars import translate_runtime_type_vars_in_context


Node coerce(Node expr, Typ target_type, Typ source_type, TypeInfo context,
            bool is_wrapper_class=False, bool is_java=False):
    """Build an expression that coerces expr from source_type to
    target_type. Return bare expr if the coercion is trivial (always a
    no-op).
    """
    if is_trivial_cast(target_type, source_type, is_java):
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
                     ((Instance)source_type).erased)
                    or (isinstance(res, CoerceExpr) and
                        isinstance(target_type, Instance))):
        res = JavaCast(res, target_type)
    
    return res                  


bool is_trivial_cast(Typ target_type, Typ source_type, bool is_java):
    """Is an implicit cast from sourceType to targetType a no-op (can it be
    omitted)?
    
    Note that we omit coercions of form dyn <= C, unless C is a primitive that
    may have a special representation.
    """
    # FIX: Replace type vars in source type with dynamic?
    if isinstance(source_type, Void) or is_same_type(target_type, source_type):
        return True
    
    # Coercions from a primitive type to any other type are non-trivial, since
    # we may have to change the representation.
    if (not is_java and isinstance(source_type, Instance)
            and ((Instance)source_type).typ.full_name in ['builtins.int',
                                                          'builtins.float',
                                                          'builtins.bool']):
        return False
    
    return (is_proper_subtype(source_type, target_type)
            or isinstance(source_type, NoneTyp)
            or isinstance(target_type, Any))
