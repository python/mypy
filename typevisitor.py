import mtypes


# Visitor class for types (Typ subclasses). The parameter T is the return
# type of the visit methods.
class TypeVisitor<T>:
    T visit_unbound_type(self, mtypes.UnboundType t):
        pass
    
    T visit_error_type(self, mtypes.ErrorType t):
        pass
    
    T visit_any(self, mtypes.Any t):
        pass
    
    T visit_void(self, mtypes.Void t):
        pass
    
    T visit_none_type(self, mtypes.NoneTyp t):
        pass
    
    T visit_type_var(self, mtypes.TypeVar t):
        pass
    
    T visit_instance(self, mtypes.Instance t):
        pass
    
    T visit_callable(self, mtypes.Callable t):
        pass
    
    T visit_overloaded(self, mtypes.Overloaded t):
        pass
    
    T visit_tuple_type(self, mtypes.TupleType t):
        pass
    
    T visit_runtime_type_var(self, mtypes.RuntimeTypeVar t):
        pass
