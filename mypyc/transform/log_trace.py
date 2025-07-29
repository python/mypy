"""This optional pass adds logging of various executed operations.

Some subset of the executed operations are logged to the mypyc_trace.txt file.

This is useful for performance analysis. For example, it's possible
to identify how frequently various primitive functions are called,
and in which code locations they are called.
"""

from __future__ import annotations

from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import Call, CallC, CString, LoadLiteral, LoadStatic, Op, PrimitiveOp, Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.options import CompilerOptions
from mypyc.primitives.misc_ops import log_trace_event
from mypyc.transform.ir_transform import IRTransform


def insert_event_trace_logging(fn: FuncIR, options: CompilerOptions) -> None:
    builder = LowLevelIRBuilder(None, options)
    transform = LogTraceEventTransform(builder, fn.decl.fullname)
    transform.transform_blocks(fn.blocks)
    fn.blocks = builder.blocks


def get_load_global_name(op: CallC) -> str | None:
    name = op.function_name
    if name == "CPyDict_GetItem":
        arg = op.args[0]
        if (
            isinstance(arg, LoadStatic)
            and arg.namespace == "static"
            and arg.identifier == "globals"
            and isinstance(op.args[1], LoadLiteral)
        ):
            return str(op.args[1].value)
    return None


class LogTraceEventTransform(IRTransform):
    def __init__(self, builder: LowLevelIRBuilder, fullname: str) -> None:
        super().__init__(builder)
        self.fullname = fullname.encode("utf-8")

    def visit_call(self, op: Call) -> Value:
        # TODO: Use different op name when constructing an instance
        return self.log(op, "call", op.fn.fullname)

    def visit_primitive_op(self, op: PrimitiveOp) -> Value:
        return self.log(op, "primitive_op", op.desc.name)

    def visit_call_c(self, op: CallC) -> Value:
        if global_name := get_load_global_name(op):
            return self.log(op, "globals_dict_get_item", global_name)

        func_name = op.function_name
        if func_name == "PyObject_Vectorcall" and isinstance(op.args[0], CallC):
            if global_name := get_load_global_name(op.args[0]):
                return self.log(op, "python_call_global", global_name)
        elif func_name == "CPyObject_GetAttr" and isinstance(op.args[1], LoadLiteral):
            return self.log(op, "python_get_attr", str(op.args[1].value))
        elif func_name == "PyObject_VectorcallMethod" and isinstance(op.args[0], LoadLiteral):
            return self.log(op, "python_call_method", str(op.args[0].value))

        return self.log(op, "call_c", func_name)

    def log(self, op: Op, name: str, details: str) -> Value:
        if op.line >= 0:
            line_str = str(op.line)
        else:
            line_str = ""
        self.builder.primitive_op(
            log_trace_event,
            [
                CString(self.fullname),
                CString(line_str.encode("ascii")),
                CString(name.encode("utf-8")),
                CString(details.encode("utf-8")),
            ],
            op.line,
        )
        return self.add(op)
