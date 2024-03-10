from __future__ import annotations

from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.ir.ops import Value, Integer, SetMem, IntOp
from mypyc.ir.rtypes import object_rprimitive, pointer_rprimitive, c_pyssize_t_rprimitive
from mypyc.common import PLATFORM_SIZE
from mypyc.lower.registry import lower_primitive_op


@lower_primitive_op("buf_init_item")
def buf_init_item(builder: LowLevelIRBuilder, args: list[Value], line: int) -> Value:
    base = args[0]
    index_value = args[1]
    value = args[2]
    assert isinstance(index_value, Integer)
    index = index_value.numeric_value()
    if index == 0:
        ptr = base
    else:
        ptr = builder.add(IntOp(
            pointer_rprimitive, base,
            Integer(index * PLATFORM_SIZE, c_pyssize_t_rprimitive), IntOp.ADD, line))
    return builder.add(SetMem(object_rprimitive, ptr, value, line))
