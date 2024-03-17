from __future__ import annotations

from mypyc.ir.ops import Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.lower.registry import lower_binary_op


@lower_binary_op("int_eq")
def lower_int_eq(builder: LowLevelIRBuilder, args: list[Value], line: int) -> Value:
    return builder.compare_tagged(args[0], args[1], "==", line)


@lower_binary_op("int_ne")
def lower_int_ne(builder: LowLevelIRBuilder, args: list[Value], line: int) -> Value:
    return builder.compare_tagged(args[0], args[1], "!=", line)
