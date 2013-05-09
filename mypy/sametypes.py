from mypy.types import (
    Type, UnboundType, ErrorType, Any, NoneTyp, Void, TupleType, Callable,
    TypeVar, Instance, TypeVisitor, ErasedType, TypeList
)


bool is_same_type(Type left, Type right):
    """Is 'left' the same type as 'right'?"""
    if isinstance(right, UnboundType):
        # Make unbound types same as anything else to reduce the number of
        # generated spurious error messages.
        return True
    else:
        return left.accept(SameTypeVisitor(right))


bool is_same_types(Type[] a1, Type[] a2):
    if len(a1) != len(a2):
        return False
    for i in range(len(a1)):
        if not is_same_type(a1[i], a2[i]):
            return False
    return True


class SameTypeVisitor(TypeVisitor<bool>):
    """Visitor for checking whether two types are the 'same' type."""
    void __init__(self, Type right):
        self.right = right
    
    # visit_x(left) means: is left (which is an instance of X) the same type as
    # right?
    
    bool visit_unbound_type(self, UnboundType left):
        return True
    
    bool visit_error_type(self, ErrorType left):
        return False
    
    bool visit_type_list(self, TypeList t):
        assert False, 'Not supported'
    
    bool visit_any(self, Any left):
        return isinstance(self.right, Any)
    
    bool visit_void(self, Void left):
        return isinstance(self.right, Void)
    
    bool visit_none_type(self, NoneTyp left):
        return isinstance(self.right, NoneTyp)
    
    bool visit_erased_type(self, ErasedType left):
        # Should not get here.
        raise RuntimeError()
    
    bool visit_instance(self, Instance left):
        return (isinstance(self.right, Instance) and
                left.type == ((Instance)self.right).type and
                is_same_types(left.args, ((Instance)self.right).args))
    
    bool visit_type_var(self, TypeVar left):
        return (isinstance(self.right, TypeVar) and
                left.id == ((TypeVar)self.right).id and
                left.is_wrapper_var == ((TypeVar)self.right).is_wrapper_var)
    
    bool visit_callable(self, Callable left):
        # FIX generics
        if isinstance(self.right, Callable):
            cright = (Callable)self.right
            return (is_same_type(left.ret_type, cright.ret_type) and
                    is_same_types(left.arg_types, cright.arg_types)  and
                    left.arg_names == cright.arg_names and
                    left.arg_kinds == cright.arg_kinds and
                    left.is_type_obj() == cright.is_type_obj())
        else:
            return False
    
    bool visit_tuple_type(self, TupleType left):
        if isinstance(self.right, TupleType):
            return is_same_types(left.items, ((TupleType)self.right).items)
        else:
            return False
