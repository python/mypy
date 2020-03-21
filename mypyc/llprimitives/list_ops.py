"""List llprimitive ops."""

from typing import List

from mypyc.ir.ops import (
  Op, Value, CFunctionCall, IREmitCallback,
  ERR_MAGIC,
)
from mypyc.ir.rtypes import (
    int_rprimitive, list_rprimitive, object_rprimitive,
)
from mypyc.llprimitives.registry import method_op


def list_getitem_helper(function_name: str) -> IREmitCallback:
    def list_getitem_callback(builder: 'LowLevelIRBuilder',
                              args: List[Value],
                              ret_typ: Value) -> List[Op]:
        return [CFunctionCall(function_name, args, ret_typ)]
    return list_getitem_callback


# Version with no int bounds check for when it is known to be short
list_get_item_op = method_op(
    name='__getitem__',
    arg_types=[list_rprimitive, int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    ir_emit=list_getitem_helper('CPyList_GetItem'),
    priority=2)
