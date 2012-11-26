from mtypes import (
    Typ, TypeVisitor, UnboundType, ErrorType, Any, Void, NoneTyp, Instance,
    TypeVar, Callable, TupleType, Overloaded
)
import checker


Typ erase_type(Typ typ, checker.BasicTypes basic):
    """Erase any type variables from a type.

    Also replace tuple types with the corresponding concrete types. Replace
    callable types with empty callable types.
    
    Examples:
      A -> A
      B<X> -> B<any>
      tuple<A, B> -> tuple
      func<...> -> func<void>
      """
    return typ.accept(EraseTypeVisitor(basic))


class EraseTypeVisitor(TypeVisitor<Typ>):
    void __init__(self, checker.BasicTypes basic):
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
        # We must preserve the type object flag for overload resolution to
        # work.
        return Callable([], 0, False, Void(), t.is_type_obj())

    Typ visit_overloaded(self, Overloaded t):
        return t.items()[0].accept(self)
    
    Typ visit_tuple_type(self, TupleType t):
        return self.basic.tuple
