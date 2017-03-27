from typing import Union, List

from mypy.nodes import TypeInfo

from mypy.erasetype import erase_typevars
from mypy.sametypes import is_same_type
from mypy.types import Instance, TypeVarType, TupleType, Type


def fill_typevars(typ: TypeInfo) -> Union[Instance, TupleType]:
    """For a non-generic type, return instance type representing the type.
    For a generic G type with parameters T1, .., Tn, return G[T1, ..., Tn].
    """
    tv = []  # type: List[Type]
    for i in range(len(typ.type_vars)):
        tv.append(TypeVarType(typ.defn.type_vars[i]))
    inst = Instance(typ, tv)
    if typ.tuple_type is None:
        return inst
    return typ.tuple_type.copy_modified(fallback=inst)


def has_no_typevars(typ: Type) -> bool:
    return is_same_type(typ, erase_typevars(typ))
