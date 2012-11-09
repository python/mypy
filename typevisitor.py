

# Visitor class for types (Typ subclasses). The parameter T is the return
# type of the visit methods.
class TypeVisitor<T>:
    T visit_unbound_type(self, UnboundType t):
        pass
    
    T visit_error_type(self, ErrorType t):
        pass
    
    T visit_any(self, Any t):
        pass
    
    T visit_void(self, Void t):
        pass
    
    T visit_none_type(self, NoneType t):
        pass
    
    T visit_type_var(self, TypeVar t):
        pass
    
    T visit_instance(self, Instance t):
        pass
    
    T visit_callable(self, Callable t):
        pass
    
    T visit_overloaded(self, Overloaded t):
        pass
    
    T visit_tuple_type(self, TupleType t):
        pass
    
    T visit_runtime_type_var(self, RuntimeTypeVar t):
        pass
