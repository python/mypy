from mypy.mtypes import (
    Type, TypeVisitor, UnboundType, ErrorType, Any, Void, NoneTyp, Instance,
    TypeVar, Callable, TupleType, Overloaded, ErasedType, TypeTranslator,
    BasicTypes
)


Type erase_type(Type typ, BasicTypes basic):
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


class EraseTypeVisitor(TypeVisitor<Type>):
    void __init__(self, BasicTypes basic):
        self.basic = basic
    
    Type visit_unbound_type(self, UnboundType t):
        return t
    
    Type visit_error_type(self, ErrorType t):
        return t
    
    Type visit_any(self, Any t):
        return t
    
    Type visit_void(self, Void t):
        return t
    
    Type visit_none_type(self, NoneTyp t):
        return t
    
    Type visit_erased_type(self, ErasedType t):
        # Should not get here.
        raise RuntimeError()
    
    Type visit_instance(self, Instance t):
        return Instance(t.type, <Type> [Any()] * len(t.args), t.line, t.repr)
    
    Type visit_type_var(self, TypeVar t):
        return Any()
    
    Type visit_callable(self, Callable t):
        # We must preserve the type object flag for overload resolution to
        # work.
        return Callable([], [], [], Void(), t.is_type_obj())

    Type visit_overloaded(self, Overloaded t):
        return t.items()[0].accept(self)
    
    Type visit_tuple_type(self, TupleType t):
        return self.basic.tuple


Type erase_generic_types(Type t):
    """Remove generic type arguments and type variables from a type.

    Replace all types A<...> with simply A, and all type variables
    with 'any'.
    """
    if t:
        return t.accept(GenericTypeEraser())
    else:
        return None


class GenericTypeEraser(TypeTranslator):
    """Implementation of type erasure"""
    # FIX: What about generic function types?
    
    Type visit_type_var(self, TypeVar t):
        return Any()
    
    Type visit_instance(self, Instance t):
        return Instance(t.type, [], t.line)


Type erase_typevars(Type t):
    """Replace all type variables in a type with any."""
    return t.accept(TypeVarEraser())


class TypeVarEraser(TypeTranslator):
    """Implementation of type erasure"""
    
    Type visit_type_var(self, TypeVar t):
        return Any()
