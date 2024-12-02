from __future__ import annotations

from mypyc.ir.ops import GetElementPtr, LoadMem, Value, LoadLiteral, Integer
from mypyc.ir.rtypes import PyVarObject, c_pyssize_t_rprimitive
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.lower.registry import lower_primitive_op


