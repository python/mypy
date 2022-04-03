"""Special casing for the handling of the functools.singledispatch decorator

mypyc's support for singledispatch is optimizes calls to singledispatch mainly by replacing
non-native calls to implementations with native calls.

The approach that we take, which is similar to the standard library implementation of
singledispatch, we maintain a `registry` dict that maps the dispatch type (the type used as the
first argument) to the registered implementation for that dispatch type.

Then, whenever someone calls that singledispatch function, we call functools._find_impl to
determine which of those implementations should be stored, cache that in the `dispatch_cache`
attribute, and then call the correct implementation.

The key optimization here is that, instead of storing the registered implementation in the registry
as a non-native callable like the standard library, we store integer IDs in the registry for every
compiled function. Then, whenever one of those implementations is called, we look up the integer in
a table of function pointers that we generate at compile time, and call the correct function
without going through the Python API.

In the case that we don't or can't apply that optimization (either because the function is compiled
in a separate SCC, it was registered at runtime, or the function just wasn't compiled) we fall back
to what is essentially the standard library implementation. We add a runtime function to register
the functions into our registry dict (see CPySingledispatch_RegisterFunction in misc_ops.c for the
implementation), and then call the function using the Python API when we need to use it.
"""

from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Tuple
from mypy.nodes import ArgKind, FuncDef, TypeInfo
from mypyc.ir.func_ir import FuncDecl, FuncIR, FuncSignature
from mypyc.ir.ops import (
    BasicBlock, Integer, LoadAddress, LoadLiteral, Register, Return, SetAttr, Unbox, Unreachable,
    Value,
)
from mypyc.ir.rtypes import bool_rprimitive, dict_rprimitive, int_rprimitive, object_rprimitive
from mypyc.irbuild.builder import IRBuilder
from mypyc.irbuild.callable_class import (
    add_call_to_callable_class, add_get_to_callable_class, instantiate_callable_class,
    setup_callable_class,
)
from mypyc.irbuild.context import FuncInfo
# avoid importing the functions themselves to avoid a circular import
from mypyc.irbuild import function
from mypyc.primitives.dict_ops import dict_set_item_op, dict_new_op, dict_get_method_with_none
from mypyc.primitives.misc_ops import register_function
from mypyc.primitives.generic_ops import py_setattr_op
from mypyc.primitives.registry import builtin_names


def generate_singledispatch_dispatch_function(
    builder: IRBuilder,
    main_singledispatch_function_name: str,
    fitem: FuncDef,
) -> None:
    line = fitem.line
    current_func_decl = builder.mapper.func_to_decl[fitem]
    arg_info = function.get_args(builder, current_func_decl.sig.args, line)

    dispatch_func_obj = builder.self()

    arg_type = builder.builder.get_type_of_obj(arg_info.args[0], line)
    dispatch_cache = builder.builder.get_attr(
        dispatch_func_obj, 'dispatch_cache', dict_rprimitive, line
    )
    call_find_impl, use_cache, call_func = BasicBlock(), BasicBlock(), BasicBlock()
    get_result = builder.call_c(dict_get_method_with_none, [dispatch_cache, arg_type], line)
    is_not_none = builder.translate_is_op(get_result, builder.none_object(), 'is not', line)
    impl_to_use = Register(object_rprimitive)
    builder.add_bool_branch(is_not_none, use_cache, call_find_impl)

    builder.activate_block(use_cache)
    builder.assign(impl_to_use, get_result, line)
    builder.goto(call_func)

    builder.activate_block(call_find_impl)
    find_impl = builder.load_module_attr_by_fullname('functools._find_impl', line)
    registry = load_singledispatch_registry(builder, dispatch_func_obj, line)
    uncached_impl = builder.py_call(find_impl, [arg_type, registry], line)
    builder.call_c(dict_set_item_op, [dispatch_cache, arg_type, uncached_impl], line)
    builder.assign(impl_to_use, uncached_impl, line)
    builder.goto(call_func)

    builder.activate_block(call_func)
    gen_calls_to_correct_impl(builder, impl_to_use, arg_info, fitem, line)


def gen_calls_to_correct_impl(
    builder: IRBuilder,
    impl_to_use: Value,
    arg_info: function.ArgInfo,
    fitem: FuncDef,
    line: int,
) -> None:
    current_func_decl = builder.mapper.func_to_decl[fitem]

    def gen_native_func_call_and_return(fdef: FuncDef) -> None:
        func_decl = builder.mapper.func_to_decl[fdef]
        ret_val = builder.builder.call(
            func_decl, arg_info.args, arg_info.arg_kinds, arg_info.arg_names, line
        )
        coerced = builder.coerce(ret_val, current_func_decl.sig.ret_type, line)
        builder.add(Return(coerced))

    typ, src = builtin_names['builtins.int']
    int_type_obj = builder.add(LoadAddress(typ, src, line))
    is_int = builder.builder.type_is_op(impl_to_use, int_type_obj, line)

    native_call, non_native_call = BasicBlock(), BasicBlock()
    builder.add_bool_branch(is_int, native_call, non_native_call)
    builder.activate_block(native_call)

    passed_id = builder.add(Unbox(impl_to_use, int_rprimitive, line))

    native_ids = get_native_impl_ids(builder, fitem)
    for impl, i in native_ids.items():
        call_impl, next_impl = BasicBlock(), BasicBlock()

        current_id = builder.load_int(i)
        builder.builder.compare_tagged_condition(
            passed_id,
            current_id,
            '==',
            call_impl,
            next_impl,
            line,
        )

        # Call the registered implementation
        builder.activate_block(call_impl)

        gen_native_func_call_and_return(impl)
        builder.activate_block(next_impl)

    # We've already handled all the possible integer IDs, so we should never get here
    builder.add(Unreachable())

    builder.activate_block(non_native_call)
    ret_val = builder.py_call(
        impl_to_use, arg_info.args, line, arg_info.arg_kinds, arg_info.arg_names
    )
    coerced = builder.coerce(ret_val, current_func_decl.sig.ret_type, line)
    builder.add(Return(coerced))


def gen_dispatch_func_ir(
    builder: IRBuilder,
    fitem: FuncDef,
    main_func_name: str,
    dispatch_name: str,
    sig: FuncSignature,
) -> Tuple[FuncIR, Value]:
    """Create a dispatch function (a function that checks the first argument type and dispatches
    to the correct implementation)
    """
    builder.enter(FuncInfo(fitem, dispatch_name))
    setup_callable_class(builder)
    builder.fn_info.callable_class.ir.attributes['registry'] = dict_rprimitive
    builder.fn_info.callable_class.ir.attributes['dispatch_cache'] = dict_rprimitive
    builder.fn_info.callable_class.ir.has_dict = True
    builder.fn_info.callable_class.ir.needs_getseters = True
    generate_singledispatch_callable_class_ctor(builder)

    generate_singledispatch_dispatch_function(builder, main_func_name, fitem)
    args, _, blocks, _, fn_info = builder.leave()
    dispatch_callable_class = add_call_to_callable_class(builder, args, blocks, sig, fn_info)
    builder.functions.append(dispatch_callable_class)
    add_get_to_callable_class(builder, fn_info)
    add_register_method_to_callable_class(builder, fn_info)
    func_reg = instantiate_callable_class(builder, fn_info)
    dispatch_func_ir = generate_dispatch_glue_native_function(
        builder, fitem, dispatch_callable_class.decl, dispatch_name
    )

    return dispatch_func_ir, func_reg


def generate_dispatch_glue_native_function(
    builder: IRBuilder,
    fitem: FuncDef,
    callable_class_decl: FuncDecl,
    dispatch_name: str,
) -> FuncIR:
    line = fitem.line
    builder.enter()
    # We store the callable class in the globals dict for this function
    callable_class = builder.load_global_str(dispatch_name, line)
    decl = builder.mapper.func_to_decl[fitem]
    arg_info = function.get_args(builder, decl.sig.args, line)
    args = [callable_class] + arg_info.args
    arg_kinds = [ArgKind.ARG_POS] + arg_info.arg_kinds
    arg_names = arg_info.arg_names
    arg_names.insert(0, 'self')
    ret_val = builder.builder.call(callable_class_decl, args, arg_kinds, arg_names, line)
    builder.add(Return(ret_val))
    arg_regs, _, blocks, _, fn_info = builder.leave()
    return FuncIR(decl, arg_regs, blocks)


def generate_singledispatch_callable_class_ctor(builder: IRBuilder) -> None:
    """Create an __init__ that sets registry and dispatch_cache to empty dicts"""
    line = -1
    class_ir = builder.fn_info.callable_class.ir
    with builder.enter_method(class_ir, '__init__', bool_rprimitive):
        empty_dict = builder.call_c(dict_new_op, [], line)
        builder.add(SetAttr(builder.self(), 'registry', empty_dict, line))
        cache_dict = builder.call_c(dict_new_op, [], line)
        dispatch_cache_str = builder.load_str('dispatch_cache')
        # use the py_setattr_op instead of SetAttr so that it also gets added to our __dict__
        builder.call_c(py_setattr_op, [builder.self(), dispatch_cache_str, cache_dict], line)
        # the generated C code seems to expect that __init__ returns a char, so just return 1
        builder.add(Return(Integer(1, bool_rprimitive, line), line))


def add_register_method_to_callable_class(builder: IRBuilder, fn_info: FuncInfo) -> None:
    line = -1
    with builder.enter_method(fn_info.callable_class.ir, 'register', object_rprimitive):
        cls_arg = builder.add_argument('cls', object_rprimitive)
        func_arg = builder.add_argument('func', object_rprimitive, ArgKind.ARG_OPT)
        ret_val = builder.call_c(register_function, [builder.self(), cls_arg, func_arg], line)
        builder.add(Return(ret_val, line))


def load_singledispatch_registry(builder: IRBuilder, dispatch_func_obj: Value, line: int) -> Value:
    return builder.builder.get_attr(dispatch_func_obj, 'registry', dict_rprimitive, line)


def maybe_insert_into_registry_dict(builder: IRBuilder, fitem: FuncDef) -> None:
    line = fitem.line
    is_singledispatch_main_func = fitem in builder.singledispatch_impls
    # dict of singledispatch_func to list of register_types (fitem is the function to register)
    to_register: DefaultDict[FuncDef, List[TypeInfo]] = defaultdict(list)
    for main_func, impls in builder.singledispatch_impls.items():
        for dispatch_type, impl in impls:
            if fitem == impl:
                to_register[main_func].append(dispatch_type)

    if not to_register and not is_singledispatch_main_func:
        return

    if is_singledispatch_main_func:
        main_func_name = singledispatch_main_func_name(fitem.name)
        main_func_obj = load_func(builder, main_func_name, fitem.fullname, line)

        loaded_object_type = builder.load_module_attr_by_fullname('builtins.object', line)
        registry_dict = builder.builder.make_dict([(loaded_object_type, main_func_obj)], line)

        dispatch_func_obj = builder.load_global_str(fitem.name, line)
        builder.call_c(
            py_setattr_op, [dispatch_func_obj, builder.load_str('registry'), registry_dict], line
        )

    for singledispatch_func, types in to_register.items():
        # TODO: avoid recomputing the native IDs for all the functions every time we find a new
        # function
        native_ids = get_native_impl_ids(builder, singledispatch_func)
        if fitem not in native_ids:
            to_insert = load_func(builder, fitem.name, fitem.fullname, line)
        else:
            current_id = native_ids[fitem]
            load_literal = LoadLiteral(current_id, object_rprimitive)
            to_insert = builder.add(load_literal)
        # TODO: avoid reloading the registry here if we just created it
        dispatch_func_obj = load_func(
            builder, singledispatch_func.name, singledispatch_func.fullname, line
        )
        registry = load_singledispatch_registry(builder, dispatch_func_obj, line)
        for typ in types:
            loaded_type = function.load_type(builder, typ, line)
            builder.call_c(dict_set_item_op, [registry, loaded_type, to_insert], line)
        dispatch_cache = builder.builder.get_attr(
            dispatch_func_obj, 'dispatch_cache', dict_rprimitive, line
        )
        builder.gen_method_call(dispatch_cache, 'clear', [], None, line)


def get_native_impl_ids(builder: IRBuilder, singledispatch_func: FuncDef) -> Dict[FuncDef, int]:
    """Return a dict of registered implementation to native implementation ID for all
    implementations
    """
    impls = builder.singledispatch_impls[singledispatch_func]
    return {
        impl: i for i, (typ, impl) in enumerate(impls) if not function.is_decorated(builder, impl)
    }


def singledispatch_main_func_name(orig_name: str) -> str:
    return '__mypyc_singledispatch_main_function_{}__'.format(orig_name)


def load_func(builder: IRBuilder, func_name: str, fullname: Optional[str], line: int) -> Value:
    if fullname is not None and not fullname.startswith(builder.current_module):
        # we're calling a function in a different module

        # We can't use load_module_attr_by_fullname here because we need to load the function using
        # func_name, not the name specified by fullname (which can be different for underscore
        # function)
        module = fullname.rsplit('.')[0]
        loaded_module = builder.load_module(module)

        func = builder.py_get_attr(loaded_module, func_name, line)
    else:
        func = builder.load_global_str(func_name, line)
    return func
