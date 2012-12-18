from mtypes import Typ, TypeTranslator, TypeVar, RuntimeTypeVar
from nodes import NameExpr, TypeInfo
from transutil import tvar_arg_name
from maptypevar import get_tvar_access_expression


Typ translate_runtime_type_vars_locally(Typ typ):
    """Replace type variable references in a type with runtime type variable
    references that refer to a runtime local variable (tv*).
    """
    return typ.accept(TranslateRuntimeTypeVarsLocallyVisitor())


class TranslateRuntimeTypeVarsLocallyVisitor(TypeTranslator):
    """Reuse most of the implementation by inheriting TypeTranslator."""
    Typ visit_type_var(self, TypeVar t):
        # FIX function type variables
        return RuntimeTypeVar(NameExpr(tvar_arg_name(t.id)))


Typ translate_runtime_type_vars_in_context(Typ typ, TypeInfo context, any is_java):
    """Replace type variable types within a type with runtime type variable
    references in the context of the given type.
    
    For example, assume class A<T, S> ... and class B<U> is A<X, Y<U>> ...:
    
      TranslateRuntimeTypeVarsInContext(C<U`1>, <B>) ==
        C<RuntimeTypeVar(<self.__tv2.args[0]>)>  (<...> uses node repr.)
        """
    return typ.accept(ContextualRuntimeTypeVarTranslator(context, is_java))


class ContextualRuntimeTypeVarTranslator(TypeTranslator):
    """Reuse most of the implementation by inheriting TypeTranslator."""
    def __init__(self, context, is_java):
        self.context = context
        self.is_java = is_java
    
    Typ visit_type_var(self, TypeVar t):
        if t.id < 0:
            # Generic function type variable; always stored in a local variable.
            return RuntimeTypeVar(NameExpr(tvar_arg_name(t.id)))
        else:
            # Instance type variables are stored in the instance.
            return get_tvar_access_expression(self.context, t.id, t.is_wrapper_var, self.is_java)
