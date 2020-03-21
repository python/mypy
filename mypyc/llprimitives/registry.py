from typing import Dict, List, Optional

from mypyc.ir.ops import (
  LLOpDescription, IREmitCallback, StealsDescription, short_name
)
from mypyc.ir.rtypes import RType
# LLPrimitive ops for built-in methods (key is method name such as 'builtins.list.append')
ll_method_ops = {}  # type: Dict[str, List[LLOpDescription]]


def method_op(name: str,
              arg_types: List[RType],
              result_type: Optional[RType],
              error_kind: int,
              ir_emit: IREmitCallback,
              steals: StealsDescription = False,
              is_borrowed: bool = False,
              priority: int = 1) -> LLOpDescription:
    ops = ll_method_ops.setdefault(name, [])
    assert len(arg_types) > 0
    args = ', '.join('{args[%d]}' % i
                     for i in range(1, len(arg_types)))
    type_name = short_name(arg_types[0].name)
    if name == '__getitem__':
        format_str = '{dest} = {args[0]}[{args[1]}] :: %s' % type_name
    else:
        format_str = '{dest} = {args[0]}.%s(%s) :: %s' % (name, args, type_name)
    desc = LLOpDescription(name, arg_types, result_type, False, error_kind, format_str, ir_emit,
                         steals, is_borrowed, priority)
    ops.append(desc)
    return desc


import mypyc.llprimitives.list_ops  # noqa
