from mtypes import (
    Callable, Typ, Any, TypeTranslator, TypeVar, BOUND_VAR, OBJECT_VAR
) 
from nodes import FuncDef, TypeInfo, NameExpr, LDEF
import nodes
from noderepr import FuncRepr, FuncArgsRepr, CallExprRepr
from lex import Token
from nodes import function_type
from sametypes import is_same_type
from parse import none


Callable prepend_arg_type(Callable t, Typ arg_type):
    """Prepend an argument with the given type to a callable type."""
    return Callable([arg_type] + t.arg_types,
                    [nodes.ARG_POS] + t.arg_kinds,
                    <str> [None] + t.arg_names,
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


Callable replace_ret_type(Callable t, Typ ret_type):
    """Return a copy of a callable type with a different return type."""
    return Callable(t.arg_types,
                    t.arg_kinds,
                    t.arg_names,
                    ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


Callable dynamic_sig(Callable sig):
    """Translate callable type to type erased (dynamically-typed) callable type
    with the same number of arguments.
    """
    return Callable(<Typ> [Any()] * len(sig.arg_types),
                    sig.arg_kinds,
                    sig.arg_names,
                    Any(),
                    sig.is_type_obj())


Typ translate_type_vars_to_wrapper_vars(Typ typ):
    """Translate any instance type variables in a type into wrapper tvars.
    
    (Wrapper tvars are type variables that refer to values stored in a generic
    class wrapper).
    """
    return typ.accept(TranslateTypeVarsToWrapperVarsVisitor())


class TranslateTypeVarsToWrapperVarsVisitor(TypeTranslator):
    """Visitor that implements TranslateTypeVarsToWrapperVarsVisitor."""
    Typ visit_type_var(self, TypeVar t):
        if t.id > 0:
            return TypeVar(t.name, t.id, True, t.line, t.repr)
        else:
            return t


Typ translate_type_vars_to_bound_vars(Typ typ):
    return typ.accept(TranslateTypeVarsToBoundVarsVisitor())


class TranslateTypeVarsToBoundVarsVisitor(TypeTranslator):
    Typ visit_type_var(self, TypeVar t):
        if t.id > 0:
            return TypeVar(t.name, t.id, BOUND_VAR, t.line, t.repr)
        else:
            return t


Typ translate_type_vars_to_wrapped_object_vars(Typ typ):
    return typ.accept(TranslateTypeVarsToWrappedObjectVarsVisitor())


class TranslateTypeVarsToWrappedObjectVarsVisitor(TypeTranslator):
    Typ visit_type_var(self, TypeVar t):
        if t.id > 0:
            return TypeVar(t.name, t.id, OBJECT_VAR, t.line, t.repr)
        else:
            return t


Typ translate_function_type_vars_to_dynamic(Typ typ):
    """Translate any function type variables in a type into type 'any'."""
    return typ.accept(TranslateFunctionTypeVarsToDynamicVisitor())


class TranslateFunctionTypeVarsToDynamicVisitor(TypeTranslator):
    """Visitor that implements TranslateTypeVarsToWrapperVarsVisitor."""
    Typ visit_type_var(self, TypeVar t):
        if t.id < 0:
            return Any()
        else:
            return t


bool is_generic(FuncDef fdef):
    """Is a function a method of a generic type?

    (Note that this may return False even if the function itself is generic.)
    """
    return fdef.info is not None and fdef.info.type_vars != []


bool is_simple_override(FuncDef fdef, TypeInfo info):
    """Is function an override with the same type precision as the original?
    
    Compare to the original method in the superclass of info.
    """
    # If this is not an override, this can't be a simple override either.
    # Generic inheritance is not currently supported, since we need to map
    # type variables between types; in the future this restriction can be
    # lifted.
    if info.base is None or info.base.type_vars != []:
        return False
    orig = info.base.get_method(fdef.name())
    return is_same_type(function_type(fdef), function_type(orig))


str tvar_slot_name(int n, any is_alt=False):
    """Return the name of the member that holds the runtime value of the given
    type variable slot.
    """
    if is_alt != BOUND_VAR:
        if n == 0:
            return '__tv'
        else:
            return '__tv{}'.format(n + 1)
    else:
        # Greatest lower bound
        if n == 0:
            return '__btv'
        else:
            return '__btv{}'.format(n + 1)


str tvar_arg_name(int n, any is_alt=False):
    """Return the name of the implicit function/constructor argument that
    contains the runtime value of a type variable. n is 1, 2, ... for instance
    type variables and -1, -2, ... for function type variables.
    """
    if is_alt != BOUND_VAR:
        if n > 0:
            # Equivalent to slot name.
            return tvar_slot_name(n - 1)
        elif n == -1:
            return '__ftv'
        else:
            return '__ftv{}'.format(-n)
    else:
        if n > 0:
            # Equivalent to slot name.
            return tvar_slot_name(n - 1, BOUND_VAR)
        elif n == -1:
            return '__bftv' # FIX do we need this?
        else:
            return '__bftv{}'.format(-n) # FIX do we need this?


str dynamic_suffix(bool is_pretty):
    """Return the suffix of the dynamic wrapper of a method or class."""
    if is_pretty:
        return '*'
    else:
        return '___dyn'


NameExpr self_expr():
    n = NameExpr('self')
    n.kind = LDEF
    return n
