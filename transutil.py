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


# Prepend an argument with the given type to a callable type.
Callable prepend_arg_type(Callable t, Typ arg_type):
    return Callable([arg_type] + t.arg_types,
                    [nodes.ARG_POS] + t.arg_kinds,
                    <str> [None] + t.arg_names,
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


# Return a copy of a callable type with a different return type.
Callable replace_ret_type(Callable t, Typ ret_type):
    return Callable(t.arg_types,
                    t.arg_kinds,
                    t.arg_names,
                    ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


# Translate callable type to type erased (dynamically-typed) callable type
# with the same number of arguments.
Callable dynamic_sig(Callable sig):
    return Callable(<Typ> [Any()] * len(sig.arg_types),
                    sig.arg_kinds,
                    sig.arg_names,
                    Any(),
                    sig.is_type_obj())


# Prepend an argument with the given name to a representation of a function.
# Or if frepr == None, return None.
FuncRepr prepend_arg_repr(FuncRepr frepr, str name):
    if frepr is None:
        return None
    ar = frepr.args
    # We may need to add a comma as well.
    commas = [Token('')]
    if len(ar.arg_names) > 0:
        commas = [Token(', ')] + ar.commas
    args = FuncArgsRepr(ar.lseparator, ar.rseparator, [Token(name)] + ar.arg_names, commas, [Token('')] + ar.assigns, ar.asterisk)
    r = frepr
    return FuncRepr(r.def_tok, r.name, args)


# If fdef has a representation, return a copy of the representation with the
# given name substituted for the original name. Otherwise, return nil.
FuncRepr func_repr_with_name(FuncDef fdef, str name):
    r = fdef.repr
    if r is None:
        return r
    else:
        return FuncRepr(r.def_tok, Token(name, r.name.pre), r.args)


# Prepend an argument to the representation of a call expression with the
# given number of arguments.
CallExprRepr prepend_call_arg_repr(CallExprRepr r, int argc):
    # Actually only add a comma token (if there are any original arguments)
    # since the representations of the argument expressions are stored with
    # the relevant expression nodes.
    Token[] commas = []
    if argc > 0:
        commas = [Token(', ')] + r.commas
    return CallExprRepr(r.lparen, commas, r.star, r.star2,
                        [[none]] + r.keywords, r.rparen)


# Translate any instance type variables in a type into wrapper type variables
# (i.e. into type variables that refer to values stored in a generic class
# wrapper).
Typ translate_type_vars_to_wrapper_vars(Typ typ):
    return typ.accept(TranslateTypeVarsToWrapperVarsVisitor())


# Visitor that implements TranslateTypeVarsToWrapperVarsVisitor.
class TranslateTypeVarsToWrapperVarsVisitor(TypeTranslator):
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


# Translate any function type variables in a type into type "dynamic".
Typ translate_function_type_vars_to_dynamic(Typ typ):
    return typ.accept(TranslateFunctionTypeVarsToDynamicVisitor())


# Visitor that implements TranslateTypeVarsToWrapperVarsVisitor.
class TranslateFunctionTypeVarsToDynamicVisitor(TypeTranslator):
    Typ visit_type_var(self, TypeVar t):
        if t.id < 0:
            return Any()
        else:
            return t


# Is a function a method of a generic type? (Note that this may return False
# even if the function itself is generic.)
bool is_generic(FuncDef fdef):
    return fdef.info is not None and fdef.info.type_vars != []


# Is the function an override with the same type precision as the original
# method in the superclass of "info"?
bool is_simple_override(FuncDef fdef, TypeInfo info):
    # If this is not an override, this can't be a simple override either.
    # Generic inheritance is not currently supported, since we need to map
    # type variables between types; in the future this restriction can be
    # lifted.
    if info.base is None or info.base.type_vars != []:
        return False
    orig = info.base.get_method(fdef.name())
    return is_same_type(function_type(fdef), function_type(orig))


# Return the name of the member that holds the runtime value of the given
# type variable slot.
str tvar_slot_name(int n, any is_alt=False):
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


# Return the name of the implicit function/constructor argument that contains
# the runtime value of a type variable. n is 1, 2, ... for instance type
# variables and -1, -2, ... for function type variables.
str tvar_arg_name(int n, any is_alt=False):
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


# Return the suffix of the dynamic wrapper of a method, getter or class.
str dynamic_suffix(bool is_pretty):
    if is_pretty:
        return '*'
    else:
        return '___dyn'


NameExpr self_expr():
    n = NameExpr('self')
    n.kind = LDEF
    return n
