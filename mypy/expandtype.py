from mypy.types import (
    Type, Instance, Callable, TypeVisitor, UnboundType, ErrorType, AnyType, Void,
    NoneTyp, TypeVar, Overloaded, TupleType, ErasedType, TypeList
)


Type expand_type(Type typ, dict<int, Type> map):
    """Expand any type variable references in a type with the actual values of
    type variables in an instance.
    """
    return typ.accept(ExpandTypeVisitor(map))


Type expand_type_by_instance(Type typ, Instance instance):
    """Expand type variables in type using type variable values in an
    instance."""
    if instance.args == []:
        return typ
    else:
        dict<int, Type> variables = {}
        for i in range(len(instance.args)):
            variables[i + 1] = instance.args[i]
        typ = expand_type(typ, variables)
        if isinstance(typ, Callable):
            list<tuple<int, Type>> bounds = []
            for j in range(len(instance.args)):
                bounds.append((j + 1, instance.args[j]))
            typ = update_callable_implicit_bounds((Callable)typ, bounds)
        else:
            pass
        return typ


class ExpandTypeVisitor(TypeVisitor<Type>):
    dict<int, Type> variables  # Lower bounds
    
    void __init__(self, dict<int, Type> variables):
        self.variables = variables
    
    Type visit_unbound_type(self, UnboundType t):
        return t
    
    Type visit_error_type(self, ErrorType t):
        return t
    
    Type visit_type_list(self, TypeList t):
        assert False, 'Not supported'
    
    Type visit_any(self, AnyType t):
        return t
    
    Type visit_void(self, Void t):
        return t
    
    Type visit_none_type(self, NoneTyp t):
        return t
    
    Type visit_erased_type(self, ErasedType t):
        # Should not get here.
        raise RuntimeError()
    
    Type visit_instance(self, Instance t):
        args = self.expand_types(t.args)
        return Instance(t.type, args, t.line, t.repr)
    
    Type visit_type_var(self, TypeVar t):
        repl = self.variables.get(t.id, t)
        if isinstance(repl, Instance):
            inst = (Instance)repl
            # Return copy of instance with type erasure flag on.
            return Instance(inst.type, inst.args, inst.line, inst.repr, True)
        else:
            return repl
    
    Type visit_callable(self, Callable t):
        return Callable(self.expand_types(t.arg_types),
                        t.arg_kinds,
                        t.arg_names,
                        t.ret_type.accept(self),
                        t.is_type_obj(),
                        t.name,
                        t.variables,
                        self.expand_bound_vars(t.bound_vars), t.line, t.repr)
    
    Type visit_overloaded(self, Overloaded t):
        Callable[] items = []
        for item in t.items():
            items.append((Callable)item.accept(self))
        return Overloaded(items)
    
    Type visit_tuple_type(self, TupleType t):
        return TupleType(self.expand_types(t.items), t.line, t.repr)
    
    Type[] expand_types(self, Type[] types):
        Type[] a = []
        for t in types:
            a.append(t.accept(self))
        return a
    
    list<tuple<int, Type>> expand_bound_vars(self, list<tuple<int, Type>> types):
        list<tuple<int, Type>> a = []
        for id, t in types:
            a.append((id, t.accept(self)))
        return a


Callable update_callable_implicit_bounds(Callable t,
                                         list<tuple<int, Type>> arg_types):
    # FIX what if there are existing bounds?
    return Callable(t.arg_types,
                    t.arg_kinds,
                    t.arg_names,
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    arg_types, t.line, t.repr)


tuple<Type[], Type> expand_caller_var_args(Type[] arg_types,
                                             int fixed_argc):
    """Expand the caller argument types in a varargs call. Fixedargc
    is the maximum number of fixed arguments that the target function
    accepts.
    
    Return (fixed argument types, type of the rest of the arguments). Return
    (None, None) if the last (vararg) argument had an invalid type. If the
    vararg argument was not an array (nor dynamic), the last item in the
    returned tuple is None.
    """
    if isinstance(arg_types[-1], TupleType):
        return arg_types[:-1] + ((TupleType)arg_types[-1]).items, None
    else:
        Type item_type
        if isinstance(arg_types[-1], AnyType):
            item_type = AnyType()
        elif isinstance(arg_types[-1], Instance) and (
                ((Instance)arg_types[-1]).type.fullname() == 'builtins.list'):
            # List.
            item_type = ((Instance)arg_types[-1]).args[0]
        else:
            return None, None
        
        if len(arg_types) > fixed_argc:
            return arg_types[:-1], item_type
        else:
            return (arg_types[:-1] +
                    [item_type] * (fixed_argc - len(arg_types) + 1), item_type)
