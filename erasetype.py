from mtypes import (
    Typ, TypeVisitor, UnboundType, ErrorType, Any, Void, NoneTyp, Instance,
    TypeVar, Callable, TupleType
)
from checker import BasicTypes


# Erase any type variables from a type. Also replace complex types (tuple,
# function) with the corresponding concrete types.
#
# Examples:
#   A -> A
#   B<X> -> B<any>
#   tuple<A, B> -> tuple
#   func<...> -> function
Typ erase_type(Typ typ, BasicTypes basic):
    return typ.accept(EraseTypeVisitor(basic))


class EraseTypeVisitor(TypeVisitor<Typ>):
    BasicTypes basic
    
    void __init__(self, BasicTypes basic):
        self.basic = basic
    
    Typ visit_unbound_type(self, UnboundType t):
        return t
    
    Typ visit_error_type(self, ErrorType t):
        return t
    
    Typ visit_any(self, Any t):
        return t
    
    Typ visit_void(self, Void t):
        return t
    
    Typ visit_none_type(self, NoneTyp t):
        return t
    
    Typ visit_instance(self, Instance t):
        return Instance(t.typ, <Typ> [Any()] * len(t.args), t.line, t.repr)
    
    Typ visit_type_var(self, TypeVar t):
        return Any()
    
    Typ visit_callable(self, Callable t):
        return self.basic.function
    
    Typ visit_tuple_type(self, TupleType t):
        return self.basic.tuple
