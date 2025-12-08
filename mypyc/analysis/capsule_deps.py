from __future__ import annotations

from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import CallC, PrimitiveOp


def find_implicit_capsule_dependencies(fn: FuncIR) -> set[str] | None:
    """Find implicit dependencies on capsules that need to be imported.

    Using primitives or types defined in librt submodules such as "librt.base64"
    requires a capsule import.

    Note that a module can depend on a librt module even if it doesn't explicitly
    import it, for example via re-exported names or via return types of functions
    defined in other modules.
    """
    deps: set[str] | None = None
    for block in fn.blocks:
        for op in block.ops:
            # TODO: Also determine implicit type object dependencies (e.g. cast targets)
            if isinstance(op, CallC) and op.capsule is not None:
                if deps is None:
                    deps = set()
                deps.add(op.capsule)
            else:
                assert not isinstance(op, PrimitiveOp), "Lowered IR is expected"
    return deps
