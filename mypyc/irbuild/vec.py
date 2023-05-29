"""Generate IR for vecs.vec operations"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple, Union, cast

from mypyc.common import PLATFORM_SIZE
from mypyc.ir.ops import (
    ERR_FALSE,
    ERR_MAGIC,
    Assign,
    BasicBlock,
    Branch,
    CallC,
    ComparisonOp,
    GetElementPtr,
    Integer,
    IntOp,
    KeepAlive,
    LoadAddress,
    RaiseStandardError,
    Register,
    Unreachable,
    Value,
)
from mypyc.ir.rtypes import (
    RInstance,
    RPrimitive,
    RType,
    RUnion,
    RTuple,
    RVec,
    bool_rprimitive,
    c_int_rprimitive,
    c_pyssize_t_rprimitive,
    int32_rprimitive,
    int64_rprimitive,
    is_c_py_ssize_t_rprimitive,
    is_int32_rprimitive,
    is_int64_rprimitive,
    is_none_rprimitive,
    object_pointer_rprimitive,
    object_rprimitive,
    optional_value_type,
    pointer_rprimitive,
    vec_depth,
    is_short_int_rprimitive, is_int_rprimitive,
)
from mypyc.primitives.registry import builtin_names

if TYPE_CHECKING:
    from mypyc.irbuild.ll_builder import LowLevelIRBuilder


def as_platform_int(builder: LowLevelIRBuilder, v: Value, line: int) -> Value:
    rtype = v.type
    if is_c_py_ssize_t_rprimitive(rtype):
        return v
    if isinstance(v, Integer):
        if is_short_int_rprimitive(rtype) or is_int_rprimitive(rtype):
            return Integer(v.value // 2, c_pyssize_t_rprimitive)
        return Integer(v.value, c_pyssize_t_rprimitive)
    if isinstance(rtype, RPrimitive):
        if PLATFORM_SIZE == 8 and is_int64_rprimitive(rtype):
            return v
        if PLATFORM_SIZE == 4 and is_int32_rprimitive(rtype):
            return v
    return builder.coerce(v, c_pyssize_t_rprimitive, line)


def vec_create(
    builder: "LowLevelIRBuilder", vtype: RVec, length: Union[int, Value], line: int
) -> Value:
    if isinstance(length, int):
        length = Integer(length, c_pyssize_t_rprimitive)
    length = as_platform_int(builder, length, line)

    item_type = vtype.item_type
    if is_int64_rprimitive(item_type):
        call = CallC(
            "VecI64Api.alloc", [length], vtype, False, False, error_kind=ERR_MAGIC, line=line
        )
        return builder.add(call)

    typeobj, optionals, depth = vec_item_type_info(builder, item_type, line)
    if typeobj is not None:
        if optionals == 0 and depth == 0:
            typeval = Register(pointer_rprimitive)
            builder.add(Assign(typeval, typeobj))
            call = CallC(
                "VecTApi.alloc",
                [length, typeval],
                vtype,
                False,
                False,
                error_kind=ERR_MAGIC,
                line=line,
            )
            return builder.add(call)
        else:
            call = CallC(
                "VecTExtApi.alloc",
                [
                    length,
                    typeobj,
                    Integer(optionals, int32_rprimitive),
                    Integer(depth, int32_rprimitive),
                ],
                vtype,
                False,
                False,
                error_kind=ERR_MAGIC,
                line=line,
            )
            return builder.add(call)

    assert False, "unsupported: %s" % vtype


def vec_create_initialized(
    builder: "LowLevelIRBuilder", vtype: RVec, length: Union[int, Value], init: Value, line: int
) -> Value:
    """Create vec with items initialized to the given value."""
    if isinstance(length, int):
        length = Integer(length, c_pyssize_t_rprimitive)
    length = as_platform_int(builder, length, line)

    item_type = vtype.item_type
    init = builder.coerce(init, item_type, line)
    vec = vec_create(builder, vtype, length, line)

    items_start = vec_items(builder, vec)
    step = step_size(item_type)
    items_end = builder.int_add(items_start, builder.int_mul(length, step))

    for_loop = builder.begin_for(items_start, items_end, step, signed=False)
    builder.set_mem(for_loop.index, item_type, init)
    for_loop.finish()

    builder.keep_alive([vec])
    return vec


def vec_create_from_values(
    builder: "LowLevelIRBuilder", vtype: RVec, values: List[Value], line: int
) -> Value:
    vec = vec_create(builder, vtype, len(values), line)
    ptr = vec_items(builder, vec)
    item_type = vtype.item_type
    step = step_size(item_type)
    for value in values:
        builder.set_mem(ptr, item_type, value)
        ptr = builder.int_add(ptr, step)
    builder.keep_alive([vec])
    return vec


def step_size(item_type: RType) -> int:
    if isinstance(item_type, RPrimitive):
        return item_type.size
    else:
        return PLATFORM_SIZE


def vec_item_type_info(
    builder: "LowLevelIRBuilder", typ: RType, line: int
) -> Tuple[Optional[Value], int, int]:
    if isinstance(typ, RPrimitive) and typ.is_refcounted:
        typ, src = builtin_names[typ.name]
        return builder.load_address(src, typ), 0, 0
    elif isinstance(typ, RInstance):
        return builder.load_native_type_object(typ.name), 0, 0
    elif isinstance(typ, RUnion):
        non_opt = optional_value_type(typ)
        if non_opt is not None:
            typeval, optionals, depth = vec_item_type_info(builder, non_opt, line)
            if typeval is not None:
                return typeval, (optionals << 1) | 1, depth
    elif isinstance(typ, RVec):
        if is_int64_rprimitive(typ.item_type):
            addr = builder.load_address("VecI64Api.type", pointer_rprimitive)
            load = builder.load_mem(addr, object_rprimitive)
            return load, 0, 0
        typeval, optionals, depth = vec_item_type_info(builder, typ.item_type, line)
        if typeval is not None:
            return typeval, optionals, depth + 1
    return None, 0, 0


def vec_len(builder: "LowLevelIRBuilder", val: Value) -> Value:
    # TODO: what about 32-bit archs?
    # TODO: merge vec_len and vec_len_native
    return vec_len_native(builder, val)


def vec_len_native(builder: "LowLevelIRBuilder", val: Value) -> Value:
    return builder.get_element(val, "len")


def vec_items(builder: "LowLevelIRBuilder", vecobj: Value) -> Value:
    vtype = cast(RVec, vecobj.type)
    buf = builder.get_element(vecobj, "buf")
    return builder.add(GetElementPtr(buf, vtype.buf_type, "items"))


def vec_item_ptr(builder: "LowLevelIRBuilder", vecobj: Value, index: Value) -> Value:
    items_addr = vec_items(builder, vecobj)
    delta = builder.int_mul(index, 8)
    return builder.int_add(items_addr, delta)


def vec_check_index(builder: "LowLevelIRBuilder", lenv: Value, index: Value, line: int) -> None:
    ok, fail = BasicBlock(), BasicBlock()
    is_less = builder.comparison_op(index, lenv, ComparisonOp.ULT, line)
    builder.add_bool_branch(is_less, ok, fail)
    builder.activate_block(fail)
    # TODO: Include index in exception
    builder.add(RaiseStandardError(RaiseStandardError.INDEX_ERROR, None, line))
    builder.add(Unreachable())
    builder.activate_block(ok)


def vec_get_item(builder: "LowLevelIRBuilder", base: Value, index: Value, line: int) -> Value:
    """Generate inlined vec __getitem__ call.

    We inline this, since it's simple but performance-critical.
    """
    assert isinstance(base.type, RVec)
    vtype = base.type
    # TODO: Support more item types
    # TODO: Support more index types
    len_val = vec_len_native(builder, base)
    vec_check_index(builder, len_val, index, line)
    item_addr = vec_item_ptr(builder, base, index)
    result = builder.load_mem(item_addr, vtype.item_type)
    builder.keep_alive([base])
    return result


def vec_get_item_unsafe(
    builder: "LowLevelIRBuilder", base: Value, index: Value, line: int
) -> Value:
    """Get vec item, assuming index is non-negative and within bounds."""
    assert isinstance(base.type, RVec)
    index = as_platform_int(builder, index, line)
    vtype = base.type
    item_addr = vec_item_ptr(builder, base, index)
    result = builder.load_mem(item_addr, vtype.item_type)
    builder.keep_alive([base])
    return result


def vec_set_item(
    builder: "LowLevelIRBuilder", base: Value, index: Value, item: Value, line: int
) -> None:
    assert isinstance(base.type, RVec)
    vtype = base.type
    len_val = vec_len_native(builder, base)
    vec_check_index(builder, len_val, index, line)
    item_addr = vec_item_ptr(builder, base, index)
    item_type = vtype.item_type
    item = builder.coerce(item, item_type, line)
    if item_type.is_refcounted:
        # Read an unborrowed reference to cause a decref to be
        # generated for the old item.
        old_item = builder.load_mem(item_addr, item_type)
        old_item.is_borrowed = False
    builder.set_mem(item_addr, item_type, item)
    builder.keep_alive([base])


def vec_append(builder: "LowLevelIRBuilder", vec: Value, item: Value, line: int) -> Value:
    vec_type = vec.type
    assert isinstance(vec_type, RVec)
    item_type = vec_type.item_type
    item = builder.coerce(item, item_type, line)
    if is_int64_rprimitive(item_type):
        name = "VecI64Api.append"
    elif vec_depth(vec_type) == 0 and not isinstance(item_type, RUnion):
        name = "VecTApi.append"
    else:
        name = "VecTExtApi.append"
    call = CallC(
        name,
        [vec, item],
        vec_type,
        steals=[True, False],
        is_borrowed=False,
        error_kind=ERR_MAGIC,
        line=line,
    )
    return builder.add(call)


def vec_pop(builder: "LowLevelIRBuilder", base: Value, index: Value, line: int) -> Value:
    assert isinstance(base.type, RVec)
    vec_type = base.type
    item_type = vec_type.item_type
    index = as_platform_int(builder, index, line)

    if is_int64_rprimitive(item_type):
        name = "VecI64Api.pop"
    elif vec_depth(vec_type) == 0 and not isinstance(item_type, RUnion):
        name = "VecTApi.pop"
    else:
        name = "VecTExtApi.pop"
    call = CallC(
        name,
        [base, index],
        RTuple([vec_type, item_type]),
        steals=[False, False],
        is_borrowed=False,
        error_kind=ERR_MAGIC,
        line=line,
    )
    return builder.add(call)


def vec_remove(builder: "LowLevelIRBuilder", vec: Value, item: Value, line: int) -> Value:
    assert isinstance(vec.type, RVec)
    vec_type = vec.type
    item_type = vec_type.item_type
    item = builder.coerce(item, item_type, line)

    if is_int64_rprimitive(item_type):
        name = "VecI64Api.remove"
    elif vec_depth(vec_type) == 0 and not isinstance(item_type, RUnion):
        name = "VecTApi.remove"
    else:
        name = "VecTExtApi.remove"
    call = CallC(
        name,
        [vec, item],
        vec_type,
        steals=[False, False],
        is_borrowed=False,
        error_kind=ERR_FALSE,
        line=line,
    )
    return builder.add(call)


def vec_contains(builder: "LowLevelIRBuilder", vec: Value, target: Value, line: int) -> Value:
    assert isinstance(vec.type, RVec)
    vec_type = vec.type
    item_type = vec_type.item_type
    target = builder.coerce(target, item_type, line)

    step = step_size(item_type)
    len_val = vec_len_native(builder, vec)
    items_start = vec_items(builder, vec)
    items_end = builder.int_add(items_start, builder.int_mul(len_val, step))

    true, end = BasicBlock(), BasicBlock()

    for_loop = builder.begin_for(items_start, items_end, step, signed=False)
    item = builder.load_mem(for_loop.index, item_type)
    comp = builder.binary_op(item, target, "==", line)
    false = BasicBlock()
    builder.add(Branch(comp, true, false, Branch.BOOL))
    builder.activate_block(false)
    for_loop.finish()

    builder.keep_alive([vec])

    res = Register(bool_rprimitive)
    builder.assign(res, Integer(0, bool_rprimitive))
    builder.goto(end)
    builder.activate_block(true)
    builder.assign(res, Integer(1, bool_rprimitive))
    builder.goto_and_activate(end)
    return res


def vec_slice(
    builder: "LowLevelIRBuilder", vec: Value, begin: Value, end: Value, line: int
) -> Value:
    assert isinstance(vec.type, RVec)
    vec_type = vec.type
    item_type = vec_type.item_type
    begin = builder.coerce(begin, int64_rprimitive, line)
    end = builder.coerce(end, int64_rprimitive, line)
    if is_int64_rprimitive(item_type):
        name = "VecI64Api.slice"
    elif vec_depth(vec_type) == 0 and not isinstance(item_type, RUnion):
        name = "VecTApi.slice"
    else:
        name = "VecTExtApi.slice"
    call = CallC(
        name,
        [vec, begin, end],
        vec_type,
        steals=[False, False, False],
        is_borrowed=False,
        error_kind=ERR_MAGIC,
        line=line,
    )
    return builder.add(call)
