"""Transform mypy AST functions to IR (and related things).

This also deals with generators, async functions and nested functions.
"""

from typing import Optional, List, Tuple, Union

from mypy.nodes import (
    ClassDef, FuncDef, OverloadedFuncDef, Decorator, Var, YieldFromExpr, AwaitExpr, YieldExpr,
    FuncItem, SymbolNode, LambdaExpr, ARG_OPT
)
from mypy.types import CallableType, get_proper_type

from mypyc.ir.ops import (
    BasicBlock, Value,  Return, Call, SetAttr, LoadInt, Unreachable, RaiseStandardError,
    Environment, GetAttr, Branch, AssignmentTarget, TupleGet, Goto,
    AssignmentTargetRegister, AssignmentTargetAttr, LoadStatic, InitStatic
)
from mypyc.ir.rtypes import object_rprimitive, int_rprimitive, RInstance
from mypyc.ir.func_ir import (
    FuncIR, FuncSignature, RuntimeArg, FuncDecl, FUNC_CLASSMETHOD, FUNC_STATICMETHOD, FUNC_NORMAL
)
from mypyc.ir.class_ir import ClassIR, NonExtClassInfo
from mypyc.primitives.misc_ops import (
    check_stop_op, yield_from_except_op, next_raw_op, iter_op, coro_op, send_op, py_setattr_op,
    method_new_op
)
from mypyc.primitives.exc_ops import raise_exception_with_tb_op
from mypyc.primitives.dict_ops import dict_set_item_op
from mypyc.common import (
    SELF_NAME, ENV_ATTR_NAME, NEXT_LABEL_ATTR_NAME, LAMBDA_NAME, decorator_helper_name
)
from mypyc.sametype import is_same_method_signature
from mypyc.irbuild.util import concrete_arg_kind, is_constant, add_self_to_env
from mypyc.irbuild.context import FuncInfo, GeneratorClass, ImplicitClass
from mypyc.irbuild.statement import transform_try_except
from mypyc.irbuild.builder import IRBuilder


# Top-level transform functions


def transform_func_def(builder: IRBuilder, fdef: FuncDef) -> None:
    func_ir, func_reg = gen_func_item(builder, fdef, fdef.name, builder.mapper.fdef_to_sig(fdef))

    # If the function that was visited was a nested function, then either look it up in our
    # current environment or define it if it was not already defined.
    if func_reg:
        builder.assign(get_func_target(builder, fdef), func_reg, fdef.line)
    builder.functions.append(func_ir)


def transform_overloaded_func_def(builder: IRBuilder, o: OverloadedFuncDef) -> None:
    # Handle regular overload case
    assert o.impl
    builder.accept(o.impl)


def transform_decorator(builder: IRBuilder, dec: Decorator) -> None:
    func_ir, func_reg = gen_func_item(
        builder,
        dec.func,
        dec.func.name,
        builder.mapper.fdef_to_sig(dec.func)
    )

    if dec.func in builder.nested_fitems:
        assert func_reg is not None
        decorated_func = load_decorated_func(builder, dec.func, func_reg)
        builder.assign(get_func_target(builder, dec.func), decorated_func, dec.func.line)
        func_reg = decorated_func
    else:
        # Obtain the the function name in order to construct the name of the helper function.
        name = dec.func.fullname.split('.')[-1]
        helper_name = decorator_helper_name(name)

        # Load the callable object representing the non-decorated function, and decorate it.
        orig_func = builder.load_global_str(helper_name, dec.line)
        decorated_func = load_decorated_func(builder, dec.func, orig_func)

        # Set the callable object representing the decorated function as a global.
        builder.primitive_op(dict_set_item_op,
                          [builder.load_globals_dict(),
                           builder.load_static_unicode(dec.func.name), decorated_func],
                          decorated_func.line)

    builder.functions.append(func_ir)


def transform_method(builder: IRBuilder,
                     cdef: ClassDef,
                     non_ext: Optional[NonExtClassInfo],
                     fdef: FuncDef) -> None:
    if non_ext:
        handle_non_ext_method(builder, non_ext, cdef, fdef)
    else:
        handle_ext_method(builder, cdef, fdef)


def transform_lambda_expr(builder: IRBuilder, expr: LambdaExpr) -> Value:
    typ = get_proper_type(builder.types[expr])
    assert isinstance(typ, CallableType)

    runtime_args = []
    for arg, arg_type in zip(expr.arguments, typ.arg_types):
        arg.variable.type = arg_type
        runtime_args.append(
            RuntimeArg(arg.variable.name, builder.type_to_rtype(arg_type), arg.kind))
    ret_type = builder.type_to_rtype(typ.ret_type)

    fsig = FuncSignature(runtime_args, ret_type)

    fname = '{}{}'.format(LAMBDA_NAME, builder.lambda_counter)
    builder.lambda_counter += 1
    func_ir, func_reg = gen_func_item(builder, expr, fname, fsig)
    assert func_reg is not None

    builder.functions.append(func_ir)
    return func_reg


def transform_yield_expr(builder: IRBuilder, expr: YieldExpr) -> Value:
    if expr.expr:
        retval = builder.accept(expr.expr)
    else:
        retval = builder.builder.none()
    return emit_yield(builder, retval, expr.line)


def transform_yield_from_expr(builder: IRBuilder, o: YieldFromExpr) -> Value:
    return handle_yield_from_and_await(builder, o)


def transform_await_expr(builder: IRBuilder, o: AwaitExpr) -> Value:
    return handle_yield_from_and_await(builder, o)


# Internal functions


def gen_func_item(builder: IRBuilder,
                  fitem: FuncItem,
                  name: str,
                  sig: FuncSignature,
                  cdef: Optional[ClassDef] = None,
                  ) -> Tuple[FuncIR, Optional[Value]]:
    # TODO: do something about abstract methods.

    """Generates and returns the FuncIR for a given FuncDef.

    If the given FuncItem is a nested function, then we generate a callable class representing
    the function and use that instead of the actual function. if the given FuncItem contains a
    nested function, then we generate an environment class so that inner nested functions can
    access the environment of the given FuncDef.

    Consider the following nested function.
    def a() -> None:
        def b() -> None:
            def c() -> None:
                return None
            return None
        return None

    The classes generated would look something like the following.

                has pointer to        +-------+
        +-------------------------->  | a_env |
        |                             +-------+
        |                                 ^
        |                                 | has pointer to
    +-------+     associated with     +-------+
    | b_obj |   ------------------->  | b_env |
    +-------+                         +-------+
                                          ^
                                          |
    +-------+         has pointer to      |
    | c_obj |   --------------------------+
    +-------+
    """

    func_reg = None  # type: Optional[Value]

    # We treat lambdas as always being nested because we always generate
    # a class for lambdas, no matter where they are. (It would probably also
    # work to special case toplevel lambdas and generate a non-class function.)
    is_nested = fitem in builder.nested_fitems or isinstance(fitem, LambdaExpr)
    contains_nested = fitem in builder.encapsulating_funcs.keys()
    is_decorated = fitem in builder.fdefs_to_decorators
    in_non_ext = False
    class_name = None
    if cdef:
        ir = builder.mapper.type_to_ir[cdef.info]
        in_non_ext = not ir.is_ext_class
        class_name = cdef.name

    builder.enter(FuncInfo(fitem, name, class_name, gen_func_ns(builder, ),
                        is_nested, contains_nested, is_decorated, in_non_ext))

    # Functions that contain nested functions need an environment class to store variables that
    # are free in their nested functions. Generator functions need an environment class to
    # store a variable denoting the next instruction to be executed when the __next__ function
    # is called, along with all the variables inside the function itself.
    if builder.fn_info.contains_nested or builder.fn_info.is_generator:
        setup_env_class(builder, )

    if builder.fn_info.is_nested or builder.fn_info.in_non_ext:
        setup_callable_class(builder, )

    if builder.fn_info.is_generator:
        # Do a first-pass and generate a function that just returns a generator object.
        gen_generator_func(builder, )
        blocks, env, ret_type, fn_info = builder.leave()
        func_ir, func_reg = gen_func_ir(builder, blocks, sig, env, fn_info, cdef)

        # Re-enter the FuncItem and visit the body of the function this time.
        builder.enter(fn_info)
        setup_env_for_generator_class(builder, )
        load_outer_envs(builder, builder.fn_info.generator_class)
        if builder.fn_info.is_nested and isinstance(fitem, FuncDef):
            setup_func_for_recursive_call(builder, fitem, builder.fn_info.generator_class)
        create_switch_for_generator_class(builder, )
        add_raise_exception_blocks_to_generator_class(builder, fitem.line)
    else:
        load_env_registers(builder, )
        gen_arg_defaults(builder, )

    if builder.fn_info.contains_nested and not builder.fn_info.is_generator:
        finalize_env_class(builder, )

    builder.ret_types[-1] = sig.ret_type

    # Add all variables and functions that are declared/defined within this
    # function and are referenced in functions nested within this one to this
    # function's environment class so the nested functions can reference
    # them even if they are declared after the nested function's definition.
    # Note that this is done before visiting the body of this function.

    env_for_func = builder.fn_info  # type: Union[FuncInfo, ImplicitClass]
    if builder.fn_info.is_generator:
        env_for_func = builder.fn_info.generator_class
    elif builder.fn_info.is_nested or builder.fn_info.in_non_ext:
        env_for_func = builder.fn_info.callable_class

    if builder.fn_info.fitem in builder.free_variables:
        # Sort the variables to keep things deterministic
        for var in sorted(builder.free_variables[builder.fn_info.fitem],
                          key=lambda x: x.name):
            if isinstance(var, Var):
                rtype = builder.type_to_rtype(var.type)
                builder.add_var_to_env_class(var, rtype, env_for_func, reassign=False)

    if builder.fn_info.fitem in builder.encapsulating_funcs:
        for nested_fn in builder.encapsulating_funcs[builder.fn_info.fitem]:
            if isinstance(nested_fn, FuncDef):
                # The return type is 'object' instead of an RInstance of the
                # callable class because differently defined functions with
                # the same name and signature across conditional blocks
                # will generate different callable classes, so the callable
                # class that gets instantiated must be generic.
                builder.add_var_to_env_class(
                    nested_fn, object_rprimitive, env_for_func, reassign=False
                )

    builder.accept(fitem.body)
    builder.maybe_add_implicit_return()

    if builder.fn_info.is_generator:
        populate_switch_for_generator_class(builder, )

    blocks, env, ret_type, fn_info = builder.leave()

    if fn_info.is_generator:
        helper_fn_decl = add_helper_to_generator_class(builder, blocks, sig, env, fn_info)
        add_next_to_generator_class(builder, fn_info, helper_fn_decl, sig)
        add_send_to_generator_class(builder, fn_info, helper_fn_decl, sig)
        add_iter_to_generator_class(builder, fn_info)
        add_throw_to_generator_class(builder, fn_info, helper_fn_decl, sig)
        add_close_to_generator_class(builder, fn_info)
        if fitem.is_coroutine:
            add_await_to_generator_class(builder, fn_info)

    else:
        func_ir, func_reg = gen_func_ir(builder, blocks, sig, env, fn_info, cdef)

    calculate_arg_defaults(builder, fn_info, env, func_reg)

    return (func_ir, func_reg)


def gen_func_ir(builder: IRBuilder,
                blocks: List[BasicBlock],
                sig: FuncSignature,
                env: Environment,
                fn_info: FuncInfo,
                cdef: Optional[ClassDef]) -> Tuple[FuncIR, Optional[Value]]:
    """Generates the FuncIR for a function given the blocks, environment, and function info of
    a particular function and returns it. If the function is nested, also returns the register
    containing the instance of the corresponding callable class.
    """
    func_reg = None  # type: Optional[Value]
    if fn_info.is_nested or fn_info.in_non_ext:
        func_ir = add_call_to_callable_class(builder, blocks, sig, env, fn_info)
        add_get_to_callable_class(builder, fn_info)
        func_reg = instantiate_callable_class(builder, fn_info)
    else:
        assert isinstance(fn_info.fitem, FuncDef)
        func_decl = builder.mapper.func_to_decl[fn_info.fitem]
        if fn_info.is_decorated:
            class_name = None if cdef is None else cdef.name
            func_decl = FuncDecl(fn_info.name, class_name, builder.module_name, sig,
                                 func_decl.kind,
                                 func_decl.is_prop_getter, func_decl.is_prop_setter)
            func_ir = FuncIR(func_decl, blocks, env, fn_info.fitem.line,
                             traceback_name=fn_info.fitem.name)
        else:
            func_ir = FuncIR(func_decl, blocks, env,
                             fn_info.fitem.line, traceback_name=fn_info.fitem.name)
    return (func_ir, func_reg)


def handle_ext_method(builder: IRBuilder, cdef: ClassDef, fdef: FuncDef) -> None:
    # Perform the function of visit_method for methods inside extension classes.
    name = fdef.name
    class_ir = builder.mapper.type_to_ir[cdef.info]
    func_ir, func_reg = gen_func_item(builder, fdef, name, builder.mapper.fdef_to_sig(fdef), cdef)
    builder.functions.append(func_ir)

    if is_decorated(builder, fdef):
        # Obtain the the function name in order to construct the name of the helper function.
        _, _, name = fdef.fullname.rpartition('.')
        helper_name = decorator_helper_name(name)
        # Read the PyTypeObject representing the class, get the callable object
        # representing the non-decorated method
        typ = builder.load_native_type_object(cdef.fullname)
        orig_func = builder.py_get_attr(typ, helper_name, fdef.line)

        # Decorate the non-decorated method
        decorated_func = load_decorated_func(builder, fdef, orig_func)

        # Set the callable object representing the decorated method as an attribute of the
        # extension class.
        builder.primitive_op(py_setattr_op,
                          [
                              typ,
                              builder.load_static_unicode(name),
                              decorated_func
                          ],
                          fdef.line)

    if fdef.is_property:
        # If there is a property setter, it will be processed after the getter,
        # We populate the optional setter field with none for now.
        assert name not in class_ir.properties
        class_ir.properties[name] = (func_ir, None)

    elif fdef in builder.prop_setters:
        # The respective property getter must have been processed already
        assert name in class_ir.properties
        getter_ir, _ = class_ir.properties[name]
        class_ir.properties[name] = (getter_ir, func_ir)

    class_ir.methods[func_ir.decl.name] = func_ir

    # If this overrides a parent class method with a different type, we need
    # to generate a glue method to mediate between them.
    for base in class_ir.mro[1:]:
        if (name in base.method_decls and name != '__init__'
                and not is_same_method_signature(class_ir.method_decls[name].sig,
                                                 base.method_decls[name].sig)):

            # TODO: Support contravariant subtyping in the input argument for
            # property setters. Need to make a special glue method for handling this,
            # similar to gen_glue_property.

            f = gen_glue(builder, base.method_decls[name].sig, func_ir, class_ir, base, fdef)
            class_ir.glue_methods[(base, name)] = f
            builder.functions.append(f)

    # If the class allows interpreted children, create glue
    # methods that dispatch via the Python API. These will go in a
    # "shadow vtable" that will be assigned to interpreted
    # children.
    if class_ir.allow_interpreted_subclasses:
        f = gen_glue(builder, func_ir.sig, func_ir, class_ir, class_ir, fdef, do_py_ops=True)
        class_ir.glue_methods[(class_ir, name)] = f
        builder.functions.append(f)


def handle_non_ext_method(
        builder: IRBuilder, non_ext: NonExtClassInfo, cdef: ClassDef, fdef: FuncDef) -> None:
    # Perform the function of visit_method for methods inside non-extension classes.
    name = fdef.name
    func_ir, func_reg = gen_func_item(builder, fdef, name, builder.mapper.fdef_to_sig(fdef), cdef)
    assert func_reg is not None
    builder.functions.append(func_ir)

    if is_decorated(builder, fdef):
        # The undecorated method is a generated callable class
        orig_func = func_reg
        func_reg = load_decorated_func(builder, fdef, orig_func)

    # TODO: Support property setters in non-extension classes
    if fdef.is_property:
        prop = builder.load_module_attr_by_fullname('builtins.property', fdef.line)
        func_reg = builder.py_call(prop, [func_reg], fdef.line)

    elif builder.mapper.func_to_decl[fdef].kind == FUNC_CLASSMETHOD:
        cls_meth = builder.load_module_attr_by_fullname('builtins.classmethod', fdef.line)
        func_reg = builder.py_call(cls_meth, [func_reg], fdef.line)

    elif builder.mapper.func_to_decl[fdef].kind == FUNC_STATICMETHOD:
        stat_meth = builder.load_module_attr_by_fullname(
            'builtins.staticmethod', fdef.line
        )
        func_reg = builder.py_call(stat_meth, [func_reg], fdef.line)

    builder.add_to_non_ext_dict(non_ext, name, func_reg, fdef.line)


def gen_arg_defaults(builder: IRBuilder) -> None:
    """Generate blocks for arguments that have default values.

    If the passed value is an error value, then assign the default
    value to the argument.
    """
    fitem = builder.fn_info.fitem
    for arg in fitem.arguments:
        if arg.initializer:
            target = builder.environment.lookup(arg.variable)

            def get_default() -> Value:
                assert arg.initializer is not None

                # If it is constant, don't bother storing it
                if is_constant(arg.initializer):
                    return builder.accept(arg.initializer)

                # Because gen_arg_defaults runs before calculate_arg_defaults, we
                # add the static/attribute to final_names/the class here.
                elif not builder.fn_info.is_nested:
                    name = fitem.fullname + '.' + arg.variable.name
                    builder.final_names.append((name, target.type))
                    return builder.add(LoadStatic(target.type, name, builder.module_name))
                else:
                    name = arg.variable.name
                    builder.fn_info.callable_class.ir.attributes[name] = target.type
                    return builder.add(
                        GetAttr(builder.fn_info.callable_class.self_reg, name, arg.line))
            assert isinstance(target, AssignmentTargetRegister)
            builder.assign_if_null(target, get_default, arg.initializer.line)


def calculate_arg_defaults(builder: IRBuilder,
                           fn_info: FuncInfo,
                           env: Environment,
                           func_reg: Optional[Value]) -> None:
    """Calculate default argument values and store them.

    They are stored in statics for top level functions and in
    the function objects for nested functions (while constants are
    still stored computed on demand).
    """
    fitem = fn_info.fitem
    for arg in fitem.arguments:
        # Constant values don't get stored but just recomputed
        if arg.initializer and not is_constant(arg.initializer):
            value = builder.coerce(
                builder.accept(arg.initializer),
                env.lookup(arg.variable).type,
                arg.line
            )
            if not fn_info.is_nested:
                name = fitem.fullname + '.' + arg.variable.name
                builder.add(InitStatic(value, name, builder.module_name))
            else:
                assert func_reg is not None
                builder.add(SetAttr(func_reg, arg.variable.name, value, arg.line))


def gen_generator_func(builder: IRBuilder) -> None:
    setup_generator_class(builder, )
    load_env_registers(builder, )
    gen_arg_defaults(builder, )
    finalize_env_class(builder, )
    builder.add(Return(instantiate_generator_class(builder, )))


def instantiate_generator_class(builder: IRBuilder) -> Value:
    fitem = builder.fn_info.fitem
    generator_reg = builder.add(Call(builder.fn_info.generator_class.ir.ctor, [], fitem.line))

    # Get the current environment register. If the current function is nested, then the
    # generator class gets instantiated from the callable class' '__call__' method, and hence
    # we use the callable class' environment register. Otherwise, we use the original
    # function's environment register.
    if builder.fn_info.is_nested:
        curr_env_reg = builder.fn_info.callable_class.curr_env_reg
    else:
        curr_env_reg = builder.fn_info.curr_env_reg

    # Set the generator class' environment attribute to point at the environment class
    # defined in the current scope.
    builder.add(SetAttr(generator_reg, ENV_ATTR_NAME, curr_env_reg, fitem.line))

    # Set the generator class' environment class' NEXT_LABEL_ATTR_NAME attribute to 0.
    zero_reg = builder.add(LoadInt(0))
    builder.add(SetAttr(curr_env_reg, NEXT_LABEL_ATTR_NAME, zero_reg, fitem.line))
    return generator_reg


def setup_generator_class(builder: IRBuilder) -> ClassIR:
    name = '{}_gen'.format(builder.fn_info.namespaced_name())

    generator_class_ir = ClassIR(name, builder.module_name, is_generated=True)
    generator_class_ir.attributes[ENV_ATTR_NAME] = RInstance(builder.fn_info.env_class)
    generator_class_ir.mro = [generator_class_ir]

    builder.classes.append(generator_class_ir)
    builder.fn_info.generator_class = GeneratorClass(generator_class_ir)
    return generator_class_ir


def create_switch_for_generator_class(builder: IRBuilder) -> None:
    builder.add(Goto(builder.fn_info.generator_class.switch_block))
    block = BasicBlock()
    builder.fn_info.generator_class.continuation_blocks.append(block)
    builder.activate_block(block)


def populate_switch_for_generator_class(builder: IRBuilder) -> None:
    cls = builder.fn_info.generator_class
    line = builder.fn_info.fitem.line

    builder.activate_block(cls.switch_block)
    for label, true_block in enumerate(cls.continuation_blocks):
        false_block = BasicBlock()
        comparison = builder.binary_op(
            cls.next_label_reg, builder.add(LoadInt(label)), '==', line
        )
        builder.add_bool_branch(comparison, true_block, false_block)
        builder.activate_block(false_block)

    builder.add(RaiseStandardError(RaiseStandardError.STOP_ITERATION, None, line))
    builder.add(Unreachable())


def add_raise_exception_blocks_to_generator_class(builder: IRBuilder, line: int) -> None:
    """
    Generates blocks to check if error flags are set while calling the helper method for
    generator functions, and raises an exception if those flags are set.
    """
    cls = builder.fn_info.generator_class
    assert cls.exc_regs is not None
    exc_type, exc_val, exc_tb = cls.exc_regs

    # Check to see if an exception was raised.
    error_block = BasicBlock()
    ok_block = BasicBlock()
    comparison = builder.binary_op(exc_type, builder.none_object(), 'is not', line)
    builder.add_bool_branch(comparison, error_block, ok_block)

    builder.activate_block(error_block)
    builder.primitive_op(raise_exception_with_tb_op, [exc_type, exc_val, exc_tb], line)
    builder.add(Unreachable())
    builder.goto_and_activate(ok_block)


def add_helper_to_generator_class(builder: IRBuilder,
                                  blocks: List[BasicBlock],
                                  sig: FuncSignature,
                                  env: Environment,
                                  fn_info: FuncInfo) -> FuncDecl:
    """Generates a helper method for a generator class, called by '__next__' and 'throw'."""
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                         RuntimeArg('type', object_rprimitive),
                         RuntimeArg('value', object_rprimitive),
                         RuntimeArg('traceback', object_rprimitive),
                         RuntimeArg('arg', object_rprimitive)
                         ), sig.ret_type)
    helper_fn_decl = FuncDecl('__mypyc_generator_helper__', fn_info.generator_class.ir.name,
                              builder.module_name, sig)
    helper_fn_ir = FuncIR(helper_fn_decl, blocks, env,
                          fn_info.fitem.line, traceback_name=fn_info.fitem.name)
    fn_info.generator_class.ir.methods['__mypyc_generator_helper__'] = helper_fn_ir
    builder.functions.append(helper_fn_ir)
    return helper_fn_decl


def add_iter_to_generator_class(builder: IRBuilder, fn_info: FuncInfo) -> None:
    """Generates the '__iter__' method for a generator class."""
    builder.enter(fn_info)
    self_target = add_self_to_env(builder.environment, fn_info.generator_class.ir)
    builder.add(Return(builder.read(self_target, fn_info.fitem.line)))
    blocks, env, _, fn_info = builder.leave()

    # Next, add the actual function as a method of the generator class.
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
    iter_fn_decl = FuncDecl('__iter__', fn_info.generator_class.ir.name, builder.module_name, sig)
    iter_fn_ir = FuncIR(iter_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['__iter__'] = iter_fn_ir
    builder.functions.append(iter_fn_ir)


def add_next_to_generator_class(builder: IRBuilder,
                                fn_info: FuncInfo,
                                fn_decl: FuncDecl,
                                sig: FuncSignature) -> None:
    """Generates the '__next__' method for a generator class."""
    builder.enter(fn_info)
    self_reg = builder.read(add_self_to_env(builder.environment, fn_info.generator_class.ir))
    none_reg = builder.none_object()

    # Call the helper function with error flags set to Py_None, and return that result.
    result = builder.add(Call(fn_decl, [self_reg, none_reg, none_reg, none_reg, none_reg],
                           fn_info.fitem.line))
    builder.add(Return(result))
    blocks, env, _, fn_info = builder.leave()

    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), sig.ret_type)
    next_fn_decl = FuncDecl('__next__', fn_info.generator_class.ir.name, builder.module_name, sig)
    next_fn_ir = FuncIR(next_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['__next__'] = next_fn_ir
    builder.functions.append(next_fn_ir)


def add_send_to_generator_class(builder: IRBuilder,
                                fn_info: FuncInfo,
                                fn_decl: FuncDecl,
                                sig: FuncSignature) -> None:
    """Generates the 'send' method for a generator class."""
    # FIXME: this is basically the same as add_next...
    builder.enter(fn_info)
    self_reg = builder.read(add_self_to_env(builder.environment, fn_info.generator_class.ir))
    arg = builder.environment.add_local_reg(Var('arg'), object_rprimitive, True)
    none_reg = builder.none_object()

    # Call the helper function with error flags set to Py_None, and return that result.
    result = builder.add(Call(fn_decl, [self_reg, none_reg, none_reg, none_reg, builder.read(arg)],
                           fn_info.fitem.line))
    builder.add(Return(result))
    blocks, env, _, fn_info = builder.leave()

    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                         RuntimeArg('arg', object_rprimitive),), sig.ret_type)
    next_fn_decl = FuncDecl('send', fn_info.generator_class.ir.name, builder.module_name, sig)
    next_fn_ir = FuncIR(next_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['send'] = next_fn_ir
    builder.functions.append(next_fn_ir)


def add_throw_to_generator_class(builder: IRBuilder,
                                 fn_info: FuncInfo,
                                 fn_decl: FuncDecl,
                                 sig: FuncSignature) -> None:
    """Generates the 'throw' method for a generator class."""
    builder.enter(fn_info)
    self_reg = builder.read(add_self_to_env(builder.environment, fn_info.generator_class.ir))

    # Add the type, value, and traceback variables to the environment.
    typ = builder.environment.add_local_reg(Var('type'), object_rprimitive, True)
    val = builder.environment.add_local_reg(Var('value'), object_rprimitive, True)
    tb = builder.environment.add_local_reg(Var('traceback'), object_rprimitive, True)

    # Because the value and traceback arguments are optional and hence can be NULL if not
    # passed in, we have to assign them Py_None if they are not passed in.
    none_reg = builder.none_object()
    builder.assign_if_null(val, lambda: none_reg, builder.fn_info.fitem.line)
    builder.assign_if_null(tb, lambda: none_reg, builder.fn_info.fitem.line)

    # Call the helper function using the arguments passed in, and return that result.
    result = builder.add(
        Call(
            fn_decl,
            [self_reg, builder.read(typ), builder.read(val), builder.read(tb), none_reg],
            fn_info.fitem.line
        )
    )
    builder.add(Return(result))
    blocks, env, _, fn_info = builder.leave()

    # Create the FuncSignature for the throw function. NOte that the value and traceback fields
    # are optional, and are assigned to if they are not passed in inside the body of the throw
    # function.
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                         RuntimeArg('type', object_rprimitive),
                         RuntimeArg('value', object_rprimitive, ARG_OPT),
                         RuntimeArg('traceback', object_rprimitive, ARG_OPT)),
                        sig.ret_type)

    throw_fn_decl = FuncDecl('throw', fn_info.generator_class.ir.name, builder.module_name, sig)
    throw_fn_ir = FuncIR(throw_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['throw'] = throw_fn_ir
    builder.functions.append(throw_fn_ir)


def add_close_to_generator_class(builder: IRBuilder, fn_info: FuncInfo) -> None:
    """Generates the '__close__' method for a generator class."""
    # TODO: Currently this method just triggers a runtime error,
    # we should fill this out eventually.
    builder.enter(fn_info)
    add_self_to_env(builder.environment, fn_info.generator_class.ir)
    builder.add(RaiseStandardError(RaiseStandardError.RUNTIME_ERROR,
                                'close method on generator classes uimplemented',
                                fn_info.fitem.line))
    builder.add(Unreachable())
    blocks, env, _, fn_info = builder.leave()

    # Next, add the actual function as a method of the generator class.
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
    close_fn_decl = FuncDecl('close', fn_info.generator_class.ir.name, builder.module_name, sig)
    close_fn_ir = FuncIR(close_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['close'] = close_fn_ir
    builder.functions.append(close_fn_ir)


def add_await_to_generator_class(builder: IRBuilder, fn_info: FuncInfo) -> None:
    """Generates the '__await__' method for a generator class."""
    builder.enter(fn_info)
    self_target = add_self_to_env(builder.environment, fn_info.generator_class.ir)
    builder.add(Return(builder.read(self_target, fn_info.fitem.line)))
    blocks, env, _, fn_info = builder.leave()

    # Next, add the actual function as a method of the generator class.
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
    await_fn_decl = FuncDecl('__await__', fn_info.generator_class.ir.name,
                             builder.module_name, sig)
    await_fn_ir = FuncIR(await_fn_decl, blocks, env)
    fn_info.generator_class.ir.methods['__await__'] = await_fn_ir
    builder.functions.append(await_fn_ir)


def setup_env_for_generator_class(builder: IRBuilder) -> None:
    """Populates the environment for a generator class."""
    fitem = builder.fn_info.fitem
    cls = builder.fn_info.generator_class
    self_target = add_self_to_env(builder.environment, cls.ir)

    # Add the type, value, and traceback variables to the environment.
    exc_type = builder.environment.add_local(Var('type'), object_rprimitive, is_arg=True)
    exc_val = builder.environment.add_local(Var('value'), object_rprimitive, is_arg=True)
    exc_tb = builder.environment.add_local(Var('traceback'), object_rprimitive, is_arg=True)
    # TODO: Use the right type here instead of object?
    exc_arg = builder.environment.add_local(Var('arg'), object_rprimitive, is_arg=True)

    cls.exc_regs = (exc_type, exc_val, exc_tb)
    cls.send_arg_reg = exc_arg

    cls.self_reg = builder.read(self_target, fitem.line)
    cls.curr_env_reg = load_outer_env(builder, cls.self_reg, builder.environment)

    # Define a variable representing the label to go to the next time the '__next__' function
    # of the generator is called, and add it as an attribute to the environment class.
    cls.next_label_target = builder.add_var_to_env_class(
        Var(NEXT_LABEL_ATTR_NAME),
        int_rprimitive,
        cls,
        reassign=False
    )

    # Add arguments from the original generator function to the generator class' environment.
    add_args_to_env(builder, local=False, base=cls, reassign=False)

    # Set the next label register for the generator class.
    cls.next_label_reg = builder.read(cls.next_label_target, fitem.line)


def setup_func_for_recursive_call(builder: IRBuilder, fdef: FuncDef, base: ImplicitClass) -> None:
    """
    Adds the instance of the callable class representing the given FuncDef to a register in the
    environment so that the function can be called recursively. Note that this needs to be done
    only for nested functions.
    """
    # First, set the attribute of the environment class so that GetAttr can be called on it.
    prev_env = builder.fn_infos[-2].env_class
    prev_env.attributes[fdef.name] = builder.type_to_rtype(fdef.type)

    if isinstance(base, GeneratorClass):
        # If we are dealing with a generator class, then we need to first get the register
        # holding the current environment class, and load the previous environment class from
        # there.
        prev_env_reg = builder.add(GetAttr(base.curr_env_reg, ENV_ATTR_NAME, -1))
    else:
        prev_env_reg = base.prev_env_reg

    # Obtain the instance of the callable class representing the FuncDef, and add it to the
    # current environment.
    val = builder.add(GetAttr(prev_env_reg, fdef.name, -1))
    target = builder.environment.add_local_reg(fdef, object_rprimitive)
    builder.assign(target, val, -1)


def gen_func_ns(builder: IRBuilder) -> str:
    """Generates a namespace for a nested function using its outer function names."""
    return '_'.join(info.name + ('' if not info.class_name else '_' + info.class_name)
                    for info in builder.fn_infos
                    if info.name and info.name != '<top level>')


def emit_yield(builder: IRBuilder, val: Value, line: int) -> Value:
    retval = builder.coerce(val, builder.ret_types[-1], line)

    cls = builder.fn_info.generator_class
    # Create a new block for the instructions immediately following the yield expression, and
    # set the next label so that the next time '__next__' is called on the generator object,
    # the function continues at the new block.
    next_block = BasicBlock()
    next_label = len(cls.continuation_blocks)
    cls.continuation_blocks.append(next_block)
    builder.assign(cls.next_label_target, builder.add(LoadInt(next_label)), line)
    builder.add(Return(retval))
    builder.activate_block(next_block)

    add_raise_exception_blocks_to_generator_class(builder, line)

    assert cls.send_arg_reg is not None
    return cls.send_arg_reg


def handle_yield_from_and_await(builder: IRBuilder, o: Union[YieldFromExpr, AwaitExpr]) -> Value:
    # This is basically an implementation of the code in PEP 380.

    # TODO: do we want to use the right types here?
    result = builder.alloc_temp(object_rprimitive)
    to_yield_reg = builder.alloc_temp(object_rprimitive)
    received_reg = builder.alloc_temp(object_rprimitive)

    if isinstance(o, YieldFromExpr):
        iter_val = builder.primitive_op(iter_op, [builder.accept(o.expr)], o.line)
    else:
        iter_val = builder.primitive_op(coro_op, [builder.accept(o.expr)], o.line)

    iter_reg = builder.maybe_spill_assignable(iter_val)

    stop_block, main_block, done_block = BasicBlock(), BasicBlock(), BasicBlock()
    _y_init = builder.primitive_op(next_raw_op, [builder.read(iter_reg)], o.line)
    builder.add(Branch(_y_init, stop_block, main_block, Branch.IS_ERROR))

    # Try extracting a return value from a StopIteration and return it.
    # If it wasn't, this reraises the exception.
    builder.activate_block(stop_block)
    builder.assign(result, builder.primitive_op(check_stop_op, [], o.line), o.line)
    builder.goto(done_block)

    builder.activate_block(main_block)
    builder.assign(to_yield_reg, _y_init, o.line)

    # OK Now the main loop!
    loop_block = BasicBlock()
    builder.goto_and_activate(loop_block)

    def try_body() -> None:
        builder.assign(
            received_reg, emit_yield(builder, builder.read(to_yield_reg), o.line), o.line
        )

    def except_body() -> None:
        # The body of the except is all implemented in a C function to
        # reduce how much code we need to generate. It returns a value
        # indicating whether to break or yield (or raise an exception).
        res = builder.primitive_op(yield_from_except_op, [builder.read(iter_reg)], o.line)
        to_stop = builder.add(TupleGet(res, 0, o.line))
        val = builder.add(TupleGet(res, 1, o.line))

        ok, stop = BasicBlock(), BasicBlock()
        builder.add(Branch(to_stop, stop, ok, Branch.BOOL_EXPR))

        # The exception got swallowed. Continue, yielding the returned value
        builder.activate_block(ok)
        builder.assign(to_yield_reg, val, o.line)
        builder.nonlocal_control[-1].gen_continue(builder, o.line)

        # The exception was a StopIteration. Stop iterating.
        builder.activate_block(stop)
        builder.assign(result, val, o.line)
        builder.nonlocal_control[-1].gen_break(builder, o.line)

    def else_body() -> None:
        # Do a next() or a .send(). It will return NULL on exception
        # but it won't automatically propagate.
        _y = builder.primitive_op(
            send_op, [builder.read(iter_reg), builder.read(received_reg)], o.line
        )
        ok, stop = BasicBlock(), BasicBlock()
        builder.add(Branch(_y, stop, ok, Branch.IS_ERROR))

        # Everything's fine. Yield it.
        builder.activate_block(ok)
        builder.assign(to_yield_reg, _y, o.line)
        builder.nonlocal_control[-1].gen_continue(builder, o.line)

        # Try extracting a return value from a StopIteration and return it.
        # If it wasn't, this rereaises the exception.
        builder.activate_block(stop)
        builder.assign(result, builder.primitive_op(check_stop_op, [], o.line), o.line)
        builder.nonlocal_control[-1].gen_break(builder, o.line)

    builder.push_loop_stack(loop_block, done_block)
    transform_try_except(
        builder, try_body, [(None, None, except_body)], else_body, o.line
    )
    builder.pop_loop_stack()

    builder.goto_and_activate(done_block)
    return builder.read(result)


def load_decorated_func(builder: IRBuilder, fdef: FuncDef, orig_func_reg: Value) -> Value:
    """
    Given a decorated FuncDef and the register containing an instance of the callable class
    representing that FuncDef, applies the corresponding decorator functions on that decorated
    FuncDef and returns a register containing an instance of the callable class representing
    the decorated function.
    """
    if not is_decorated(builder, fdef):
        # If there are no decorators associated with the function, then just return the
        # original function.
        return orig_func_reg

    decorators = builder.fdefs_to_decorators[fdef]
    func_reg = orig_func_reg
    for d in reversed(decorators):
        decorator = d.accept(builder.visitor)
        assert isinstance(decorator, Value)
        func_reg = builder.py_call(decorator, [func_reg], func_reg.line)
    return func_reg


def is_decorated(builder: IRBuilder, fdef: FuncDef) -> bool:
    return fdef in builder.fdefs_to_decorators


def gen_glue(builder: IRBuilder, sig: FuncSignature, target: FuncIR,
             cls: ClassIR, base: ClassIR, fdef: FuncItem,
             *,
             do_py_ops: bool = False
             ) -> FuncIR:
    """Generate glue methods that mediate between different method types in subclasses.

    Works on both properties and methods. See gen_glue_methods below for more details.

    If do_py_ops is True, then the glue methods should use generic
    C API operations instead of direct calls, to enable generating
    "shadow" glue methods that work with interpreted subclasses.
    """
    if fdef.is_property:
        return gen_glue_property(builder, sig, target, cls, base, fdef.line, do_py_ops)
    else:
        return gen_glue_method(builder, sig, target, cls, base, fdef.line, do_py_ops)


def gen_glue_method(builder: IRBuilder, sig: FuncSignature, target: FuncIR,
                    cls: ClassIR, base: ClassIR, line: int,
                    do_pycall: bool,
                    ) -> FuncIR:
    """Generate glue methods that mediate between different method types in subclasses.

    For example, if we have:

    class A:
        def f(builder: IRBuilder, x: int) -> object: ...

    then it is totally permissible to have a subclass

    class B(A):
        def f(builder: IRBuilder, x: object) -> int: ...

    since '(object) -> int' is a subtype of '(int) -> object' by the usual
    contra/co-variant function subtyping rules.

    The trickiness here is that int and object have different
    runtime representations in mypyc, so A.f and B.f have
    different signatures at the native C level. To deal with this,
    we need to generate glue methods that mediate between the
    different versions by coercing the arguments and return
    values.

    If do_pycall is True, then make the call using the C API
    instead of a native call.
    """
    builder.enter()
    builder.ret_types[-1] = sig.ret_type

    rt_args = list(sig.args)
    if target.decl.kind == FUNC_NORMAL:
        rt_args[0] = RuntimeArg(sig.args[0].name, RInstance(cls))

    # The environment operates on Vars, so we make some up
    fake_vars = [(Var(arg.name), arg.type) for arg in rt_args]
    args = [builder.read(builder.environment.add_local_reg(var, type, is_arg=True), line)
            for var, type in fake_vars]
    arg_names = [arg.name for arg in rt_args]
    arg_kinds = [concrete_arg_kind(arg.kind) for arg in rt_args]

    if do_pycall:
        retval = builder.builder.py_method_call(
            args[0], target.name, args[1:], line, arg_kinds[1:], arg_names[1:])
    else:
        retval = builder.builder.call(target.decl, args, arg_kinds, arg_names, line)
    retval = builder.coerce(retval, sig.ret_type, line)
    builder.add(Return(retval))

    blocks, env, ret_type, _ = builder.leave()
    return FuncIR(
        FuncDecl(target.name + '__' + base.name + '_glue',
                 cls.name, builder.module_name,
                 FuncSignature(rt_args, ret_type),
                 target.decl.kind),
        blocks, env)


def gen_glue_property(builder: IRBuilder,
                      sig: FuncSignature,
                      target: FuncIR,
                      cls: ClassIR,
                      base: ClassIR,
                      line: int,
                      do_pygetattr: bool) -> FuncIR:
    """Generate glue methods for properties that mediate between different subclass types.

    Similarly to methods, properties of derived types can be covariantly subtyped. Thus,
    properties also require glue. However, this only requires the return type to change.
    Further, instead of a method call, an attribute get is performed.

    If do_pygetattr is True, then get the attribute using the C
    API instead of a native call.
    """
    builder.enter()

    rt_arg = RuntimeArg(SELF_NAME, RInstance(cls))
    arg = builder.read(add_self_to_env(builder.environment, cls), line)
    builder.ret_types[-1] = sig.ret_type
    if do_pygetattr:
        retval = builder.py_get_attr(arg, target.name, line)
    else:
        retval = builder.add(GetAttr(arg, target.name, line))
    retbox = builder.coerce(retval, sig.ret_type, line)
    builder.add(Return(retbox))

    blocks, env, return_type, _ = builder.leave()
    return FuncIR(
        FuncDecl(target.name + '__' + base.name + '_glue',
                 cls.name, builder.module_name, FuncSignature([rt_arg], return_type)),
        blocks, env)


def setup_callable_class(builder: IRBuilder) -> None:
    """Generates a callable class representing a nested function or a function within a
    non-extension class and sets up the 'self' variable for that class.

    This takes the most recently visited function and returns a ClassIR to represent that
    function. Each callable class contains an environment attribute with points to another
    ClassIR representing the environment class where some of its variables can be accessed.
    Note that its '__call__' method is not yet implemented, and is implemented in the
    add_call_to_callable_class function.

    Returns a newly constructed ClassIR representing the callable class for the nested
    function.
    """

    # Check to see that the name has not already been taken. If so, rename the class. We allow
    # multiple uses of the same function name because this is valid in if-else blocks. Example:
    #     if True:
    #         def foo():          ---->    foo_obj()
    #             return True
    #     else:
    #         def foo():          ---->    foo_obj_0()
    #             return False
    name = base_name = '{}_obj'.format(builder.fn_info.namespaced_name())
    count = 0
    while name in builder.callable_class_names:
        name = base_name + '_' + str(count)
        count += 1
    builder.callable_class_names.add(name)

    # Define the actual callable class ClassIR, and set its environment to point at the
    # previously defined environment class.
    callable_class_ir = ClassIR(name, builder.module_name, is_generated=True)

    # The functools @wraps decorator attempts to call setattr on nested functions, so
    # we create a dict for these nested functions.
    # https://github.com/python/cpython/blob/3.7/Lib/functools.py#L58
    if builder.fn_info.is_nested:
        callable_class_ir.has_dict = True

    # If the enclosing class doesn't contain nested (which will happen if
    # this is a toplevel lambda), don't set up an environment.
    if builder.fn_infos[-2].contains_nested:
        callable_class_ir.attributes[ENV_ATTR_NAME] = RInstance(
            builder.fn_infos[-2].env_class
        )
    callable_class_ir.mro = [callable_class_ir]
    builder.fn_info.callable_class = ImplicitClass(callable_class_ir)
    builder.classes.append(callable_class_ir)

    # Add a 'self' variable to the callable class' environment, and store that variable in a
    # register to be accessed later.
    self_target = add_self_to_env(builder.environment, callable_class_ir)
    builder.fn_info.callable_class.self_reg = builder.read(self_target, builder.fn_info.fitem.line)


def add_call_to_callable_class(builder: IRBuilder,
                               blocks: List[BasicBlock],
                               sig: FuncSignature,
                               env: Environment,
                               fn_info: FuncInfo) -> FuncIR:
    """Generates a '__call__' method for a callable class representing a nested function.

    This takes the blocks, signature, and environment associated with a function definition and
    uses those to build the '__call__' method of a given callable class, used to represent that
    function. Note that a 'self' parameter is added to its list of arguments, as the nested
    function becomes a class method.
    """
    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),) + sig.args, sig.ret_type)
    call_fn_decl = FuncDecl('__call__', fn_info.callable_class.ir.name, builder.module_name, sig)
    call_fn_ir = FuncIR(call_fn_decl, blocks, env,
                        fn_info.fitem.line, traceback_name=fn_info.fitem.name)
    fn_info.callable_class.ir.methods['__call__'] = call_fn_ir
    return call_fn_ir


def add_get_to_callable_class(builder: IRBuilder, fn_info: FuncInfo) -> None:
    """Generates the '__get__' method for a callable class."""
    line = fn_info.fitem.line
    builder.enter(fn_info)

    vself = builder.read(
        builder.environment.add_local_reg(Var(SELF_NAME), object_rprimitive, True)
    )
    instance = builder.environment.add_local_reg(Var('instance'), object_rprimitive, True)
    builder.environment.add_local_reg(Var('owner'), object_rprimitive, True)

    # If accessed through the class, just return the callable
    # object. If accessed through an object, create a new bound
    # instance method object.
    instance_block, class_block = BasicBlock(), BasicBlock()
    comparison = builder.binary_op(
        builder.read(instance), builder.none_object(), 'is', line
    )
    builder.add_bool_branch(comparison, class_block, instance_block)

    builder.activate_block(class_block)
    builder.add(Return(vself))

    builder.activate_block(instance_block)
    builder.add(Return(builder.primitive_op(method_new_op, [vself, builder.read(instance)], line)))

    blocks, env, _, fn_info = builder.leave()

    sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                         RuntimeArg('instance', object_rprimitive),
                         RuntimeArg('owner', object_rprimitive)),
                        object_rprimitive)
    get_fn_decl = FuncDecl('__get__', fn_info.callable_class.ir.name, builder.module_name, sig)
    get_fn_ir = FuncIR(get_fn_decl, blocks, env)
    fn_info.callable_class.ir.methods['__get__'] = get_fn_ir
    builder.functions.append(get_fn_ir)


def instantiate_callable_class(builder: IRBuilder, fn_info: FuncInfo) -> Value:
    """
    Assigns a callable class to a register named after the given function definition. Note
    that fn_info refers to the function being assigned, whereas builder.fn_info refers to the
    function encapsulating the function being turned into a callable class.
    """
    fitem = fn_info.fitem
    func_reg = builder.add(Call(fn_info.callable_class.ir.ctor, [], fitem.line))

    # Set the callable class' environment attribute to point at the environment class
    # defined in the callable class' immediate outer scope. Note that there are three possible
    # environment class registers we may use. If the encapsulating function is:
    # - a generator function, then the callable class is instantiated from the generator class'
    #   __next__' function, and hence the generator class' environment register is used.
    # - a nested function, then the callable class is instantiated from the current callable
    #   class' '__call__' function, and hence the callable class' environment register is used.
    # - neither, then we use the environment register of the original function.
    curr_env_reg = None
    if builder.fn_info.is_generator:
        curr_env_reg = builder.fn_info.generator_class.curr_env_reg
    elif builder.fn_info.is_nested:
        curr_env_reg = builder.fn_info.callable_class.curr_env_reg
    elif builder.fn_info.contains_nested:
        curr_env_reg = builder.fn_info.curr_env_reg
    if curr_env_reg:
        builder.add(SetAttr(func_reg, ENV_ATTR_NAME, curr_env_reg, fitem.line))
    return func_reg


def setup_env_class(builder: IRBuilder) -> ClassIR:
    """Generates a class representing a function environment.

    Note that the variables in the function environment are not actually populated here. This
    is because when the environment class is generated, the function environment has not yet
    been visited. This behavior is allowed so that when the compiler visits nested functions,
    it can use the returned ClassIR instance to figure out free variables it needs to access.
    The remaining attributes of the environment class are populated when the environment
    registers are loaded.

    Returns a ClassIR representing an environment for a function containing a nested function.
    """
    env_class = ClassIR('{}_env'.format(builder.fn_info.namespaced_name()),
                        builder.module_name, is_generated=True)
    env_class.attributes[SELF_NAME] = RInstance(env_class)
    if builder.fn_info.is_nested:
        # If the function is nested, its environment class must contain an environment
        # attribute pointing to its encapsulating functions' environment class.
        env_class.attributes[ENV_ATTR_NAME] = RInstance(builder.fn_infos[-2].env_class)
    env_class.mro = [env_class]
    builder.fn_info.env_class = env_class
    builder.classes.append(env_class)
    return env_class


def finalize_env_class(builder: IRBuilder) -> None:
    """Generates, instantiates, and sets up the environment of an environment class."""

    instantiate_env_class(builder, )

    # Iterate through the function arguments and replace local definitions (using registers)
    # that were previously added to the environment with references to the function's
    # environment class.
    if builder.fn_info.is_nested:
        add_args_to_env(builder, local=False, base=builder.fn_info.callable_class)
    else:
        add_args_to_env(builder, local=False, base=builder.fn_info)


def instantiate_env_class(builder: IRBuilder) -> Value:
    """Assigns an environment class to a register named after the given function definition."""
    curr_env_reg = builder.add(
        Call(builder.fn_info.env_class.ctor, [], builder.fn_info.fitem.line)
    )

    if builder.fn_info.is_nested:
        builder.fn_info.callable_class._curr_env_reg = curr_env_reg
        builder.add(SetAttr(curr_env_reg,
                         ENV_ATTR_NAME,
                         builder.fn_info.callable_class.prev_env_reg,
                         builder.fn_info.fitem.line))
    else:
        builder.fn_info._curr_env_reg = curr_env_reg

    return curr_env_reg


def load_env_registers(builder: IRBuilder) -> None:
    """Loads the registers for the current FuncItem being visited.

    Adds the arguments of the FuncItem to the environment. If the FuncItem is nested inside of
    another function, then this also loads all of the outer environments of the FuncItem into
    registers so that they can be used when accessing free variables.
    """
    add_args_to_env(builder, local=True)

    fn_info = builder.fn_info
    fitem = fn_info.fitem
    if fn_info.is_nested:
        load_outer_envs(builder, fn_info.callable_class)
        # If this is a FuncDef, then make sure to load the FuncDef into its own environment
        # class so that the function can be called recursively.
        if isinstance(fitem, FuncDef):
            setup_func_for_recursive_call(builder, fitem, fn_info.callable_class)


def load_outer_env(builder: IRBuilder, base: Value, outer_env: Environment) -> Value:
    """Loads the environment class for a given base into a register.

    Additionally, iterates through all of the SymbolNode and AssignmentTarget instances of the
    environment at the given index's symtable, and adds those instances to the environment of
    the current environment. This is done so that the current environment can access outer
    environment variables without having to reload all of the environment registers.

    Returns the register where the environment class was loaded.
    """
    env = builder.add(GetAttr(base, ENV_ATTR_NAME, builder.fn_info.fitem.line))
    assert isinstance(env.type, RInstance), '{} must be of type RInstance'.format(env)

    for symbol, target in outer_env.symtable.items():
        env.type.class_ir.attributes[symbol.name] = target.type
        symbol_target = AssignmentTargetAttr(env, symbol.name)
        builder.environment.add_target(symbol, symbol_target)

    return env


def load_outer_envs(builder: IRBuilder, base: ImplicitClass) -> None:
    index = len(builder.builders) - 2

    # Load the first outer environment. This one is special because it gets saved in the
    # FuncInfo instance's prev_env_reg field.
    if index > 1:
        # outer_env = builder.fn_infos[index].environment
        outer_env = builder.builders[index].environment
        if isinstance(base, GeneratorClass):
            base.prev_env_reg = load_outer_env(builder, base.curr_env_reg, outer_env)
        else:
            base.prev_env_reg = load_outer_env(builder, base.self_reg, outer_env)
        env_reg = base.prev_env_reg
        index -= 1

    # Load the remaining outer environments into registers.
    while index > 1:
        # outer_env = builder.fn_infos[index].environment
        outer_env = builder.builders[index].environment
        env_reg = load_outer_env(builder, env_reg, outer_env)
        index -= 1


def add_args_to_env(builder: IRBuilder,
                    local: bool = True,
                    base: Optional[Union[FuncInfo, ImplicitClass]] = None,
                    reassign: bool = True) -> None:
    fn_info = builder.fn_info
    if local:
        for arg in fn_info.fitem.arguments:
            rtype = builder.type_to_rtype(arg.variable.type)
            builder.environment.add_local_reg(arg.variable, rtype, is_arg=True)
    else:
        for arg in fn_info.fitem.arguments:
            if is_free_variable(builder, arg.variable) or fn_info.is_generator:
                rtype = builder.type_to_rtype(arg.variable.type)
                assert base is not None, 'base cannot be None for adding nonlocal args'
                builder.add_var_to_env_class(arg.variable, rtype, base, reassign=reassign)


def is_free_variable(builder: IRBuilder, symbol: SymbolNode) -> bool:
    fitem = builder.fn_info.fitem
    return (
        fitem in builder.free_variables
        and symbol in builder.free_variables[fitem]
    )


def get_func_target(builder: IRBuilder, fdef: FuncDef) -> AssignmentTarget:
    """
    Given a FuncDef, return the target associated the instance of its callable class. If the
    function was not already defined somewhere, then define it and add it to the current
    environment.
    """
    if fdef.original_def:
        # Get the target associated with the previously defined FuncDef.
        return builder.environment.lookup(fdef.original_def)

    if builder.fn_info.is_generator or builder.fn_info.contains_nested:
        return builder.environment.lookup(fdef)

    return builder.environment.add_local_reg(fdef, object_rprimitive)
