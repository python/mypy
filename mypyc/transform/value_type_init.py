"""Transformation for changing the initialization method of a value type.

This transformation changes the type of the self parameter of the __init__ method
of a value type to be a reference to the value type. This is necessary because
the __init__ method of a value type is called with the purpose of initializing
the attributes on the storage but the self parameter being passed by value
won't make the changes on the target object.
"""

from mypyc.ir.func_ir import FuncIR
from mypyc.ir.rtypes import RInstance, RInstanceValue
from mypyc.options import CompilerOptions


def patch_value_type_init_methods(ir: FuncIR, options: CompilerOptions) -> None:
    if ir.name != "__init__" or not ir.args or not ir.blocks:
        return

    if not isinstance(ir.args[0].type, RInstanceValue):
        return

    self_rtype: RInstanceValue = ir.args[0].type
    cl = self_rtype.class_ir

    # ensure we are processing the __init__ method of a value type
    if not cl.is_value_type or cl.get_method("__init__") is not ir:
        return

    # patch the type of the self parameter to be a reference to the value type
    ref_type = RInstance(cl)
    # the refcounted flag is set to False because we only need to initialize the
    # attributes of the value type, but it is not expected to be refcounted
    ref_type.is_refcounted = False
    ir.args[0].type = ref_type
    ir.arg_regs[0].type = ref_type
