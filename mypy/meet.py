from mypy.join import is_similar_callables, combine_similar_callables
from mypy.types import (
    Type, Any, TypeVisitor, UnboundType, Void, ErrorType, NoneTyp, TypeVar,
    Instance, Callable, TupleType, ErasedType, BasicTypes
)
from mypy.sametypes import is_same_type
from mypy.subtypes import is_subtype


Type meet_types(Type s, Type t, BasicTypes basic):
    if isinstance(s, Any) or isinstance(s, ErasedType):
        return s
    
    return t.accept(TypeMeetVisitor(s, basic))


class TypeMeetVisitor(TypeVisitor<Type>):
    void __init__(self, Type s, BasicTypes basic):
        self.s = s
        self.basic = basic
    
    Type visit_unbound_type(self, UnboundType t):
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        elif isinstance(self.s, NoneTyp):
            return self.s
        else:
            return Any()
    
    Type visit_error_type(self, ErrorType t):
        return t
    
    Type visit_any(self, Any t):
        return t
    
    Type visit_void(self, Void t):
        if isinstance(self.s, Void):
            return t
        else:
            return ErrorType()
    
    Type visit_none_type(self, NoneTyp t):
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            return t
        else:
            return ErrorType()

    Type visit_erased_type(self, ErasedType t):
        return self.s
    
    Type visit_type_var(self, TypeVar t):
        if isinstance(self.s, TypeVar) and ((TypeVar)self.s).id == t.id:
            return self.s
        else:
            return self.default(self.s)
    
    Type visit_instance(self, Instance t):
        if isinstance(self.s, Instance):
            si = (Instance)self.s
            if t.type == si.type:
                if is_subtype(t, self.s):
                    # Combine type arguments. We could have used join below
                    # equivalently.
                    Type[] args = []
                    for i in range(len(t.args)):
                        args.append(self.meet(t.args[i], si.args[i]))
                    return Instance(t.type, args)
                else:
                    return NoneTyp()
            else:
                if is_subtype(t, self.s):
                    return t
                elif is_subtype(self.s, t):
                    # See also above comment.
                    return self.s
                else:
                    return NoneTyp()
        else:
            return self.default(self.s)
    
    Type visit_callable(self, Callable t):
        if isinstance(self.s, Callable) and is_similar_callables(
                                                        t, (Callable)self.s):
            return combine_similar_callables(t, (Callable)self.s, self.basic)
        else:
            return self.default(self.s)
    
    Type visit_tuple_type(self, TupleType t):
        if isinstance(self.s, TupleType) and (((TupleType)self.s).length() ==
                                              t.length()):
            Type[] items = []
            for i in range(t.length()):
                items.append(self.meet(t.items[i],
                                       ((TupleType)self.s).items[i]))
            return TupleType(items)
        else:
            return self.default(self.s)
    
    def visit_intersection(self, t):
        # Only support very rudimentary meets between intersection types.
        if is_same_type(self.s, t):
            return self.s
        else:
            return self.default(self.s)
    
    def meet(self, s, t):
        return meet_types(s, t, self.basic)
    
    def default(self, typ):
        if isinstance(typ, UnboundType):
            return Any()
        elif isinstance(typ, Void) or isinstance(typ, ErrorType):
            return ErrorType()
        else:
            return NoneTyp()
