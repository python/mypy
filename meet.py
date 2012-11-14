from checker import BasicTypes
from join import is_similar_callables, combine_similar_callables
from mtypes import (
    Typ, Any, TypeVisitor, UnboundType, Void, ErrorType, NoneTyp, TypeVar,
    Instance, Callable, TupleType
)
from sametypes import is_same_type
from subtypes import is_subtype


Typ meet_types(Typ s, Typ t, BasicTypes basic):
    if isinstance(s, Any):
        return s
    
    return t.accept(TypeMeetVisitor(s, basic))


class TypeMeetVisitor(TypeVisitor<Typ>):
    Typ s
    BasicTypes basic
    
    void __init__(self, Typ s, BasicTypes basic):
        self.s = s
        self.basic = basic
    
    Typ visit_unbound_type(self, UnboundType t):
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        elif isinstance(self.s, NoneTyp):
            return self.s
        else:
            return Any()
    
    Typ visit_error_type(self, ErrorType t):
        return t
    
    Typ visit_any(self, Any t):
        return t
    
    Typ visit_void(self, Void t):
        if isinstance(self.s, Void):
            return t
        else:
            return ErrorType()
    
    Typ visit_none_type(self, NoneTyp t):
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            return t
        else:
            return ErrorType()
    
    Typ visit_type_var(self, TypeVar t):
        if isinstance(self.s, TypeVar) and ((TypeVar)self.s).id == t.id:
            return self.s
        else:
            return self.default(self.s)
    
    Typ visit_instance(self, Instance t):
        if isinstance(self.s, Instance):
            si = (Instance)self.s
            if t.typ == si.typ:
                if is_subtype(t, self.s):
                    # Combine type arguments. We could have used join below
                    # equivalently.
                    list<Typ> args = []
                    for i in range(len(t.args)):
                        args.append(self.meet(t.args[i], si.args[i]))
                    return Instance(t.typ, args)
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
    
    Typ visit_callable(self, Callable t):
        if isinstance(self.s, Callable) and is_similar_callables(t, (Callable)self.s):
            return combine_similar_callables(t, (Callable)self.s, self.basic)
        else:
            return self.default(self.s)
    
    Typ visit_tuple_type(self, TupleType t):
        if isinstance(self.s, TupleType) and (((TupleType)self.s).length() ==
                                              t.length()):
            list<Typ> items = []
            for i in range(t.length()):
                items.append(self.meet(t.items[i], ((TupleType)self.s).items[i]))
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
