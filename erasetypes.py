from lex import Token
from nodes import Annotation
from mtypes import Typ, TypeTranslator, TypeVar, Any, Instance
from typerepr import CommonTypeRepr


Token none = Token('')


# Remove generic type arguments and type variables from an annotation.
void erase_annotation(Annotation a):
    if a is not None:
        a.typ = erase_generic_types(a.typ)


# Remove generic type arguments and type variables from a type. Replace all
# types A<...> with simply A, and all type variables with "dynamic".
Typ erase_generic_types(Typ t):
    if t is not None:
        return t.accept(GenericTypeEraser())
    else:
        return None


# Implementation of type erasure
class GenericTypeEraser(TypeTranslator):
    # FIX: What about generic function types?
    
    Typ visit_type_var(self, TypeVar t):
        return Any()
    
    Typ visit_instance(self, Instance t):
        # IDEA: Retain all whitespace in the representation.
        repr = CommonTypeRepr(t.repr.components, none, [], none)
        return Instance(t.typ, [], t.line, repr)
