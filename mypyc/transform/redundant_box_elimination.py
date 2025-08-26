from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import (
    Assign,
    AssignMulti,
    Box,
    Call,
    CallC,
    ComparisonOp,
    DecRef,
    IncRef,
    KeepAlive,
    Op,
    Return,
    Unbox,
    Value,
)
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.options import CompilerOptions
from mypyc.transform.ir_transform import IRTransform


def do_box_unbox_elimination(fn: FuncIR, options: CompilerOptions) -> None:
    builder = LowLevelIRBuilder(None, options)
    use_map = build_use_map(fn)
    transform = BoxUnboxEliminationTransform(builder, use_map)
    transform.transform_blocks(fn.blocks)
    fn.blocks = builder.blocks


def build_use_map(fn: FuncIR) -> Dict[Value, list[Op]]:
    # Map each Value to a list of ops that use it
    use_map: Dict[Value, list[Op]] = {}
    for block in fn.blocks:
        for op in block.ops:
            for src in op.sources():
                use_map.setdefault(src, []).append(op)
    return use_map


_unsupported = (Box, Unbox, IncRef, DecRef, KeepAlive)
# I'm not actually sure that these won't work but they aren't guaranteed to at this time

_supported_ops = (Assign, AssignMulti, Call, CallC, ComparisonOp, Return)


class BoxUnboxEliminationTransform(IRTransform):
    def __init__(self, builder: LowLevelIRBuilder, use_map: dict[Value, list[Op]]):
        super().__init__(builder)
        self.use_map = use_map

    def visit_box(self, op: Box) -> Value | None:
        users = self.use_map.get(op, [])
        if len(users) == 0:
            return None
        # Check for Unbox->Box
        if (
            isinstance(op.src, Unbox)
            and op.type == op.src.src.type
            and all(isinstance(user, _supported_ops) for user in users)
        ):
            unbox = op.src
            for user in users:
                user.set_sources([unbox.src if src is op else src for src in user.sources()])
            return None
        return self.add(op)

    def visit_unbox(self, op: Unbox) -> Value | None:
        users = self.use_map.get(op, [])
        if len(users) == 0:
            return None
        # Check for Box->Unbox
        if (
            isinstance(op.src, Box)
            and op.type == op.src.src.type
            and all(isinstance(user, _supported_ops) for user in users)
        ):
            box = op.src
            for user in users:
                user.set_sources([box.src if src is op else src for src in user.sources()])
            return None
        return self.add(op)

    def visit_op(self, op: Op) -> Value | None:
        return self.add(op)
