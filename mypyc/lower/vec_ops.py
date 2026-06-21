from __future__ import annotations

from mypyc.ir.ops import Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.irbuild.vec import vec_get_item_lower
from mypyc.lower.registry import lower_primitive_op


@lower_primitive_op("vec_get_item")
def vec_get_item(builder: LowLevelIRBuilder, args: list[Value], line: int) -> Value:
    base, index = args
    return vec_get_item_lower(builder, base, index, line, can_borrow=False)


@lower_primitive_op("vec_get_item_borrow")
def vec_get_item_borrow(builder: LowLevelIRBuilder, args: list[Value], line: int) -> Value:
    base, index = args
    return vec_get_item_lower(builder, base, index, line, can_borrow=True)
