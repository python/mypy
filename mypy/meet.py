from mypy.join import is_similar_callables, combine_similar_callables
from mypy.types import (
    Type, AnyType, TypeVisitor, UnboundType, Void, ErrorType, NoneTyp, TypeVar,
    Instance, Callable, TupleType, ErasedType, BasicTypes, TypeList
)
from mypy.sametypes import is_same_type
from mypy.subtypes import is_subtype
from typing import cast, List


def meet_types(s: Type, t: Type, basic: BasicTypes) -> Type:
    if isinstance(s, AnyType) or isinstance(s, ErasedType):
        return s
    
    return t.accept(TypeMeetVisitor(s, basic))


class TypeMeetVisitor(TypeVisitor[Type]):
    def __init__(self, s: Type, basic: BasicTypes) -> None:
        self.s = s
        self.basic = basic
    
    def visit_unbound_type(self, t: UnboundType) -> Type:
        if isinstance(self.s, Void) or isinstance(self.s, ErrorType):
            return ErrorType()
        elif isinstance(self.s, NoneTyp):
            return self.s
        else:
            return AnyType()
    
    def visit_error_type(self, t: ErrorType) -> Type:
        return t
    
    def visit_type_list(self, t: TypeList) -> Type:
        assert False, 'Not supported'
    
    def visit_any(self, t: AnyType) -> Type:
        return t
    
    def visit_void(self, t: Void) -> Type:
        if isinstance(self.s, Void):
            return t
        else:
            return ErrorType()
    
    def visit_none_type(self, t: NoneTyp) -> Type:
        if not isinstance(self.s, Void) and not isinstance(self.s, ErrorType):
            return t
        else:
            return ErrorType()

    def visit_erased_type(self, t: ErasedType) -> Type:
        return self.s
    
    def visit_type_var(self, t: TypeVar) -> Type:
        if isinstance(self.s, TypeVar) and (cast(TypeVar, self.s)).id == t.id:
            return self.s
        else:
            return self.default(self.s)
    
    def visit_instance(self, t: Instance) -> Type:
        if isinstance(self.s, Instance):
            si = cast(Instance, self.s)
            if t.type == si.type:
                if is_subtype(t, self.s):
                    # Combine type arguments. We could have used join below
                    # equivalently.
                    args = [] # type: List[Type]
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
    
    def visit_callable(self, t: Callable) -> Type:
        if isinstance(self.s, Callable) and is_similar_callables(
                                                        t, cast(Callable, self.s)):
            return combine_similar_callables(t, cast(Callable, self.s), self.basic)
        else:
            return self.default(self.s)
    
    def visit_tuple_type(self, t: TupleType) -> Type:
        if isinstance(self.s, TupleType) and ((cast(TupleType, self.s)).length() ==
                                              t.length()):
            items = [] # type: List[Type]
            for i in range(t.length()):
                items.append(self.meet(t.items[i],
                                       (cast(TupleType, self.s)).items[i]))
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
            return AnyType()
        elif isinstance(typ, Void) or isinstance(typ, ErrorType):
            return ErrorType()
        else:
            return NoneTyp()
