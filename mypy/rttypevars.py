"""Translation of type variables to runtime type variable expressions.

Source-level type variables are mapped to references to type variable slots
in instancse or local variables that contain the runtime values of type
variables.
"""

from mypy.types import Type, TypeTranslator, TypeVar, RuntimeTypeVar
from mypy.nodes import NameExpr, TypeInfo
from mypy.transutil import tvar_arg_name
from mypy.maptypevar import get_tvar_access_expression
from typing import Any


def translate_runtime_type_vars_locally(typ: Type) -> Type:
    """Replace type variable references in a type with runtime type variables.

    The type variable references refer to runtime local variables (__tv* etc.),
    i.e. this assumes a generic class constructor context.
    """
    return typ.accept(TranslateRuntimeTypeVarsLocallyVisitor())


class TranslateRuntimeTypeVarsLocallyVisitor(TypeTranslator):
    """Reuse most of the implementation by inheriting TypeTranslator."""
    def visit_type_var(self, t: TypeVar) -> Type:
        # FIX function type variables
        return RuntimeTypeVar(NameExpr(tvar_arg_name(t.id)))


def translate_runtime_type_vars_in_context(typ: Type, context: TypeInfo,
                                           is_java: Any) -> Type:
    """Replace type variable types within a type with runtime type variables.

    Perform the translation in the context of the given type.
    
    For example, assume class A<T, S> ... and class B<U>(A<X, Y<U>>) ...:
    
      TranslateRuntimeTypeVarsInContext(C<U`1>, <B>) ==
        C<RuntimeTypeVar(<self.__tv2.args[0]>)>  (<...> uses node repr.)
    """
    return typ.accept(ContextualRuntimeTypeVarTranslator(context, is_java))


class ContextualRuntimeTypeVarTranslator(TypeTranslator):
    """Reuse most of the implementation by inheriting TypeTranslator."""
    def __init__(self, context, is_java):
        self.context = context
        self.is_java = is_java
    
    def visit_type_var(self, t: TypeVar) -> Type:
        if t.id < 0:
            # Generic function type variable; always in a local variable.
            return RuntimeTypeVar(NameExpr(tvar_arg_name(t.id)))
        else:
            # Instance type variables are stored in the instance.
            return get_tvar_access_expression(self.context, t.id,
                                              t.is_wrapper_var, self.is_java)
