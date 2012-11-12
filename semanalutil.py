from types import Instance, Typ, TypeVar
from nodes import TypeInfo


# Type for reporting parsing context in error messages.
interface Context:
    
    @property
    int line():
        pass


# For a non-generic type, return instance type representing the type.
# For a generic G type with parameters T1, .., Tn, return G<T1, ..., Tn>.
Instance self_type(TypeInfo typ):
    list<Typ> tv = []
    for i in range(len(typ.type_vars)):
        tv.append(TypeVar(typ.type_vars[i], i + 1))
    return Instance(typ, tv)
