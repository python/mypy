from mypyc.ir.rtypes import (
    RArray,
    RInstance,
    RPrimitive,
    RStruct,
    RTuple,
    RType,
    RTypeVar,
    RUnion,
    RVec,
    RVoid,
)


def expand_rtype(typ: RType, type_args: list[RType]) -> RType:
    if isinstance(typ, (RPrimitive, RInstance, RVoid)):
        # Atomic types can't contain type variables
        return typ
    elif isinstance(typ, RTypeVar):
        return type_args[typ.id]
    elif isinstance(typ, RVec):
        return RVec(expand_rtype(typ.item_type, type_args))
    elif isinstance(typ, RUnion):
        return RUnion([expand_rtype(item, type_args) for item in typ.items])
    elif isinstance(typ, RTuple):
        return RTuple([expand_rtype(item, type_args) for item in typ.types])
    elif isinstance(typ, RStruct):
        assert False, "Generic RStruct type not supported"
    elif isinstance(typ, RArray):
        assert False, "Generic RArray type not supported"
    else:
        assert False, r"Unexpected type {typ!r}"
