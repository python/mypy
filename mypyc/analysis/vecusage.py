"""Analysis to decide whether a module needs the vec capsule."""

from mypyc.ir.func_ir import FuncIR
from mypyc.ir.module_ir import ModuleIR
from mypyc.ir.rtypes import RStruct, RTuple, RType, RUnion, RVec


def needs_vec_capsule(module: ModuleIR) -> bool:
    for f in module.functions:
        if func_needs_vec(f):
            return True
    for cl in module.classes:
        for base in cl.mro:
            for f in base.methods.values():
                if func_needs_vec(f):
                    return True
            for t in base.attributes.values():
                if uses_vec_type(t):
                    return True
    return False


def func_needs_vec(func: FuncIR) -> bool:
    for arg in func.arg_regs:
        if uses_vec_type(arg.type):
            return True
    if uses_vec_type(func.decl.sig.ret_type):
        return True
    for block in func.blocks:
        for op in block.ops:
            if uses_vec_type(op.type) or any(uses_vec_type(s.type) for s in op.sources()):
                return True
    return False


def uses_vec_type(typ: RType) -> bool:
    if isinstance(typ, RVec):
        return True
    if isinstance(typ, RUnion) and any(uses_vec_type(t) for t in typ.items):
        return True
    if isinstance(typ, (RTuple, RStruct)) and any(uses_vec_type(t) for t in typ.types):
        return True
    return False
