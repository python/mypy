from typing import cast, Any, List

from mypy.types import (
    Callable, Type, AnyType, TypeTranslator, TypeVar, BOUND_VAR, OBJECT_VAR,
    replace_self_type
) 
from mypy.nodes import FuncDef, TypeInfo, NameExpr, LDEF
from mypy import nodes
from mypy.noderepr import FuncRepr, FuncArgsRepr, CallExprRepr
from mypy.lex import Token
from mypy.nodes import function_type
from mypy.sametypes import is_same_type
from mypy.parse import none


def prepend_arg_type(t: Callable, arg_type: Type) -> Callable:
    """Prepend an argument with the given type to a callable type."""
    return Callable([arg_type] + t.arg_types,
                    [nodes.ARG_POS] + t.arg_kinds,
                    List[str]([None]) + t.arg_names,
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


def add_arg_type_after_self(t: Callable, arg_type: Type) -> Callable:
    """Add an argument with the given type to a callable type after 'self'."""
    return Callable([t.arg_types[0], arg_type] + t.arg_types[1:],
                    [t.arg_kinds[0], nodes.ARG_POS] + t.arg_kinds[1:],
                    [t.arg_names[0], None] + t.arg_names[1:],
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)


def replace_ret_type(t: Callable, ret_type: Type) -> Callable:
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


def dynamic_sig(sig: Callable) -> Callable:
    """Translate callable type to type erased (dynamically-typed) callable.

    Preserve the number and kinds of arguments.
    """
    return Callable( [AnyType()] * len(sig.arg_types),
                    sig.arg_kinds,
                    sig.arg_names,
                    AnyType(),
                    sig.is_type_obj())


def translate_type_vars_to_wrapper_vars(typ: Type) -> Type:
    """Translate any instance type variables in a type into wrapper tvars.
    
    (Wrapper tvars are type variables that refer to values stored in a generic
    class wrapper).
    """
    return typ.accept(TranslateTypeVarsToWrapperVarsVisitor())


class TranslateTypeVarsToWrapperVarsVisitor(TypeTranslator):
    """Visitor that implements TranslateTypeVarsToWrapperVarsVisitor."""
    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id > 0:
            return TypeVar(t.name, t.id, t.values, True, t.line, t.repr)
        else:
            return t


def translate_type_vars_to_bound_vars(typ: Type) -> Type:
    return typ.accept(TranslateTypeVarsToBoundVarsVisitor())


class TranslateTypeVarsToBoundVarsVisitor(TypeTranslator):
    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id > 0:
            return TypeVar(t.name, t.id, t.values, BOUND_VAR, t.line, t.repr)
        else:
            return t


def translate_type_vars_to_wrapped_object_vars(typ: Type) -> Type:
    return typ.accept(TranslateTypeVarsToWrappedObjectVarsVisitor())


class TranslateTypeVarsToWrappedObjectVarsVisitor(TypeTranslator):
    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id > 0:
            return TypeVar(t.name, t.id, t.values, OBJECT_VAR, t.line, t.repr)
        else:
            return t


def translate_function_type_vars_to_dynamic(typ: Type) -> Type:
    """Translate any function type variables in a type into type 'Any'."""
    return typ.accept(TranslateFunctionTypeVarsToDynamicVisitor())


class TranslateFunctionTypeVarsToDynamicVisitor(TypeTranslator):
    """Visitor that implements TranslateTypeVarsToWrapperVarsVisitor."""
    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id < 0:
            return AnyType()
        else:
            return t


def is_generic(fdef: FuncDef) -> bool:
    """Is a function a method of a generic type?

    (Note that this may return False even if the function itself is generic.)
    """
    return fdef.info is not None and fdef.info.type_vars != []


def is_simple_override(fdef: FuncDef, info: TypeInfo) -> bool:
    """Is function an override with the same type precision as the original?
    
    Compare to the original method in the superclass of info.
    """
    # If this is not an override, this can't be a simple override either.
    # Generic inheritance is not currently supported, since we need to map
    # type variables between types; in the future this restriction can be
    # lifted.
    if len(info.mro) <= 1:
        return False
    base = info.mro[1]
    if base.type_vars != []:
        return False
    orig = base.get_method(fdef.name())
    # Ignore the first argument (self) when determining type sameness.
    # TODO overloads
    newtype = cast(Callable, function_type(fdef))
    newtype = replace_self_type(newtype, AnyType())
    origtype = cast(Callable, function_type(orig))
    origtype = replace_self_type(origtype, AnyType())
    return is_same_type(newtype, origtype)


def tvar_slot_name(n: int, is_alt: Any = False) -> str:
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


def tvar_arg_name(n: int, is_alt: Any = False) -> str:
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


def dynamic_suffix(is_pretty: bool) -> str:
    """Return the suffix of the dynamic wrapper of a method or class."""
    if is_pretty:
        return '*'
    else:
        return '___dyn'


def self_expr() -> NameExpr:
    n = NameExpr('self')
    n.kind = LDEF
    return n
