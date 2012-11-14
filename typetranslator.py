

# Identity type transformation. Subclass this and override some methods to
# implement a non-trivial transformation.
class TypeTranslator(TypeVisitor<Typ>):
    Typ visit_unbound_type(self, UnboundType t):
        return t
    
    Typ visit_error_type(self, ErrorType t):
        return t
    
    Typ visit_any(self, Any t):
        return t
    
    Typ visit_void(self, Void t):
        return t
    
    Typ visit_none_type(self, NoneType t):
        return t
    
    Typ visit_instance(self, Instance t):
        return Instance(t.typ, self.translate_types(t.args), t.line, t.repr)
    
    Typ visit_type_var(self, TypeVar t):
        return t
    
    Typ visit_callable(self, Callable t):
        return Callable(self.translate_types(t.arg_types), t.min_args, t.is_var_arg, t.ret_type.accept(self), t.is_type_obj, t.name, t.variables, self.translate_bound_vars(t.bound_vars), t.line, t.repr)
    
    Typ visit_tuple_type(self, TupleType t):
        return TupleType(self.translate_types(t.items), t.line, t.repr)
    
    list<Typ> translate_types(self, list<Typ> types):
        list<Typ> a = []
        for t in types:
            a.append(t.accept(self))
        return a
    
    list<tuple<int, Typ>> translate_bound_vars(self, list<tuple<int, Typ>> types):
        list<tuple<int, Typ>> a = []
        for id, t in types:
            a.append((id, t.accept(self)))
        return a
