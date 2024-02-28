from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import PrimitiveOp, Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.lower.registry import lowering_registry
from mypyc.transform.ir_transform import IRTransform


def lower_ir(ir: FuncIR, module: str) -> None:
    errors = Errors()
    # mapper??
    builder = LowLevelIRBuilder(module, errors, mapper, options)
    visitor = LoweringVisitor(builder)
    visitor.transform_blocks(ir.blocks)
    ir.blocks = builder.blocks


class LoweringVisitor(IRTransform):
    def visit_primitive_op(self, op: PrimitiveOp) -> Value:
        lower_fn = lowering_registry[op.desc.name]
        return lower_fn(self.builder, op.args, op.line)
