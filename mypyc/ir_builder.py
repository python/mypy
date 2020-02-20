"""A "low-level" IR builder class.

LowLevelIRBuilder provides core abstractions we use for constructing
IR as well as a number of higher-level ones (accessing attributes,
calling functions and methods, and coercing between types, for
example). The core principle of the low-level IR builder is that all
of its facilities operate solely on the IR level and not the AST
level---it has *no knowledge* of mypy types or expressions.
"""

from typing import (
    Callable, List, Tuple, Optional, Union, Sequence, cast
)

from mypy.nodes import ARG_POS, ARG_NAMED, ARG_STAR, ARG_STAR2, op_methods
from mypy.types import AnyType, TypeOfAny
from mypy.checkexpr import map_actuals_to_formals

from mypyc.ops import (
    BasicBlock, Environment, Op, LoadInt, RType, Value, Register,
    Assign, Branch, Goto, Call, Box, Unbox, Cast, ClassIR, RInstance, GetAttr,
    LoadStatic, MethodCall, int_rprimitive, float_rprimitive, bool_rprimitive, list_rprimitive,
    str_rprimitive, is_none_rprimitive, object_rprimitive,
    PrimitiveOp, OpDescription, RegisterOp,
    FuncSignature, NAMESPACE_TYPE, NAMESPACE_MODULE,
    LoadErrorValue, FuncDecl, RUnion, optional_value_type, all_concrete_classes
)
from mypyc.common import (
    FAST_ISINSTANCE_MAX_SUBCLASSES, MAX_LITERAL_SHORT_INT,
)
from mypyc.ops_primitive import binary_ops, unary_ops, method_ops
from mypyc.ops_list import (
    list_extend_op, list_len_op, new_list_op
)
from mypyc.ops_tuple import list_tuple_op, new_tuple_op
from mypyc.ops_dict import (
    new_dict_op, dict_update_in_display_op,
)
from mypyc.ops_misc import (
    none_op, none_object_op, false_op,
    py_getattr_op, py_call_op, py_call_with_kwargs_op, py_method_call_op,
    fast_isinstance_op, bool_op, type_is_op,
)
from mypyc.rt_subtype import is_runtime_subtype
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type
from mypyc.genopsmapper import Mapper


DictEntry = Tuple[Optional[Value], Value]


class LowLevelIRBuilder:
    def __init__(
        self,
        current_module: str,
        mapper: Mapper,
    ) -> None:
        self.current_module = current_module
        self.mapper = mapper
        self.environment = Environment()
        self.blocks = []  # type: List[BasicBlock]
        # Stack of except handler entry blocks
        self.error_handlers = [None]  # type: List[Optional[BasicBlock]]

    def add(self, op: Op) -> Value:
        assert not self.blocks[-1].terminated, "Can't add to finished block"

        self.blocks[-1].ops.append(op)
        if isinstance(op, RegisterOp):
            self.environment.add_op(op)
        return op

    def goto(self, target: BasicBlock) -> None:
        if not self.blocks[-1].terminated:
            self.add(Goto(target))

    def activate_block(self, block: BasicBlock) -> None:
        if self.blocks:
            assert self.blocks[-1].terminated

        block.error_handler = self.error_handlers[-1]
        self.blocks.append(block)

    def goto_and_activate(self, block: BasicBlock) -> None:
        self.goto(block)
        self.activate_block(block)

    def push_error_handler(self, handler: Optional[BasicBlock]) -> None:
        self.error_handlers.append(handler)

    def pop_error_handler(self) -> Optional[BasicBlock]:
        return self.error_handlers.pop()

    ##

    def get_native_type(self, cls: ClassIR) -> Value:
        fullname = '%s.%s' % (cls.module_name, cls.name)
        return self.load_native_type_object(fullname)

    def primitive_op(self, desc: OpDescription, args: List[Value], line: int) -> Value:
        assert desc.result_type is not None
        coerced = []
        for i, arg in enumerate(args):
            formal_type = self.op_arg_type(desc, i)
            arg = self.coerce(arg, formal_type, line)
            coerced.append(arg)
        target = self.add(PrimitiveOp(coerced, desc, line))
        return target

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def op_arg_type(self, desc: OpDescription, n: int) -> RType:
        if n >= len(desc.arg_types):
            assert desc.is_var_arg
            return desc.arg_types[-1]
        return desc.arg_types[n]

    def box(self, src: Value) -> Value:
        if src.type.is_unboxed:
            return self.add(Box(src))
        else:
            return src

    def unbox_or_cast(self, src: Value, target_type: RType, line: int) -> Value:
        if target_type.is_unboxed:
            return self.add(Unbox(src, target_type, line))
        else:
            return self.add(Cast(src, target_type, line))

    def coerce(self, src: Value, target_type: RType, line: int, force: bool = False) -> Value:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

        If force is true, always generate an op (even if it is just an assignment) so
        that the result will have exactly target_type as the type.

        Returns the register with the converted value (may be same as src).
        """
        if src.type.is_unboxed and not target_type.is_unboxed:
            return self.box(src)
        if ((src.type.is_unboxed and target_type.is_unboxed)
                and not is_runtime_subtype(src.type, target_type)):
            # To go from one unboxed type to another, we go through a boxed
            # in-between value, for simplicity.
            tmp = self.box(src)
            return self.unbox_or_cast(tmp, target_type, line)
        if ((not src.type.is_unboxed and target_type.is_unboxed)
                or not is_subtype(src.type, target_type)):
            return self.unbox_or_cast(src, target_type, line)
        elif force:
            tmp = self.alloc_temp(target_type)
            self.add(Assign(tmp, src))
            return tmp
        return src

    def none(self) -> Value:
        return self.add(PrimitiveOp([], none_op, line=-1))

    def none_object(self) -> Value:
        return self.add(PrimitiveOp([], none_object_op, line=-1))

    def get_attr(self, obj: Value, attr: str, result_type: RType, line: int) -> Value:
        if (isinstance(obj.type, RInstance) and obj.type.class_ir.is_ext_class
                and obj.type.class_ir.has_attr(attr)):
            return self.add(GetAttr(obj, attr, line))
        elif isinstance(obj.type, RUnion):
            return self.union_get_attr(obj, obj.type, attr, result_type, line)
        else:
            return self.py_get_attr(obj, attr, line)

    def union_get_attr(self,
                       obj: Value,
                       rtype: RUnion,
                       attr: str,
                       result_type: RType,
                       line: int) -> Value:
        def get_item_attr(value: Value) -> Value:
            return self.get_attr(value, attr, result_type, line)

        return self.decompose_union_helper(obj, rtype, result_type, get_item_attr, line)

    def decompose_union_helper(self,
                               obj: Value,
                               rtype: RUnion,
                               result_type: RType,
                               process_item: Callable[[Value], Value],
                               line: int) -> Value:
        """Generate isinstance() + specialized operations for union items.

        Say, for Union[A, B] generate ops resembling this (pseudocode):

            if isinstance(obj, A):
                result = <result of process_item(cast(A, obj)>
            else:
                result = <result of process_item(cast(B, obj)>

        Args:
            obj: value with a union type
            rtype: the union type
            result_type: result of the operation
            process_item: callback to generate op for a single union item (arg is coerced
                to union item type)
            line: line number
        """
        # TODO: Optimize cases where a single operation can handle multiple union items
        #     (say a method is implemented in a common base class)
        fast_items = []
        rest_items = []
        for item in rtype.items:
            if isinstance(item, RInstance):
                fast_items.append(item)
            else:
                # For everything but RInstance we fall back to C API
                rest_items.append(item)
        exit_block = BasicBlock()
        result = self.alloc_temp(result_type)
        for i, item in enumerate(fast_items):
            more_types = i < len(fast_items) - 1 or rest_items
            if more_types:
                # We are not at the final item so we need one more branch
                op = self.isinstance_native(obj, item.class_ir, line)
                true_block, false_block = BasicBlock(), BasicBlock()
                self.add_bool_branch(op, true_block, false_block)
                self.activate_block(true_block)
            coerced = self.coerce(obj, item, line)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
            if more_types:
                self.activate_block(false_block)
        if rest_items:
            # For everything else we use generic operation. Use force=True to drop the
            # union type.
            coerced = self.coerce(obj, object_rprimitive, line, force=True)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
        self.activate_block(exit_block)
        return result

    def isinstance_helper(self, obj: Value, class_irs: List[ClassIR], line: int) -> Value:
        """Fast path for isinstance() that checks against a list of native classes."""
        if not class_irs:
            return self.primitive_op(false_op, [], line)
        ret = self.isinstance_native(obj, class_irs[0], line)
        for class_ir in class_irs[1:]:
            def other() -> Value:
                return self.isinstance_native(obj, class_ir, line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def isinstance_native(self, obj: Value, class_ir: ClassIR, line: int) -> Value:
        """Fast isinstance() check for a native class.

        If there three or less concrete (non-trait) classes among the class and all
        its children, use even faster type comparison checks `type(obj) is typ`.
        """
        concrete = all_concrete_classes(class_ir)
        if concrete is None or len(concrete) > FAST_ISINSTANCE_MAX_SUBCLASSES + 1:
            return self.primitive_op(fast_isinstance_op,
                                     [obj, self.get_native_type(class_ir)],
                                     line)
        if not concrete:
            # There can't be any concrete instance that matches this.
            return self.primitive_op(false_op, [], line)
        type_obj = self.get_native_type(concrete[0])
        ret = self.primitive_op(type_is_op, [obj, type_obj], line)
        for c in concrete[1:]:
            def other() -> Value:
                return self.primitive_op(type_is_op, [obj, self.get_native_type(c)], line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def py_get_attr(self, obj: Value, attr: str, line: int) -> Value:
        key = self.load_static_unicode(attr)
        return self.add(PrimitiveOp([obj, key], py_getattr_op, line))

    def py_call(self,
                function: Value,
                arg_values: List[Value],
                line: int,
                arg_kinds: Optional[List[int]] = None,
                arg_names: Optional[Sequence[Optional[str]]] = None) -> Value:
        """Use py_call_op or py_call_with_kwargs_op for function call."""
        # If all arguments are positional, we can use py_call_op.
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            return self.primitive_op(py_call_op, [function] + arg_values, line)

        # Otherwise fallback to py_call_with_kwargs_op.
        assert arg_names is not None

        pos_arg_values = []
        kw_arg_key_value_pairs = []  # type: List[DictEntry]
        star_arg_values = []
        for value, kind, name in zip(arg_values, arg_kinds, arg_names):
            if kind == ARG_POS:
                pos_arg_values.append(value)
            elif kind == ARG_NAMED:
                assert name is not None
                key = self.load_static_unicode(name)
                kw_arg_key_value_pairs.append((key, value))
            elif kind == ARG_STAR:
                star_arg_values.append(value)
            elif kind == ARG_STAR2:
                # NOTE: mypy currently only supports a single ** arg, but python supports multiple.
                # This code supports multiple primarily to make the logic easier to follow.
                kw_arg_key_value_pairs.append((None, value))
            else:
                assert False, ("Argument kind should not be possible:", kind)

        if len(star_arg_values) == 0:
            # We can directly construct a tuple if there are no star args.
            pos_args_tuple = self.primitive_op(new_tuple_op, pos_arg_values, line)
        else:
            # Otherwise we construct a list and call extend it with the star args, since tuples
            # don't have an extend method.
            pos_args_list = self.primitive_op(new_list_op, pos_arg_values, line)
            for star_arg_value in star_arg_values:
                self.primitive_op(list_extend_op, [pos_args_list, star_arg_value], line)
            pos_args_tuple = self.primitive_op(list_tuple_op, [pos_args_list], line)

        kw_args_dict = self.make_dict(kw_arg_key_value_pairs, line)

        return self.primitive_op(
            py_call_with_kwargs_op, [function, pos_args_tuple, kw_args_dict], line)

    def py_method_call(self,
                       obj: Value,
                       method_name: str,
                       arg_values: List[Value],
                       line: int,
                       arg_kinds: Optional[List[int]],
                       arg_names: Optional[Sequence[Optional[str]]]) -> Value:
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            method_name_reg = self.load_static_unicode(method_name)
            return self.primitive_op(py_method_call_op, [obj, method_name_reg] + arg_values, line)
        else:
            method = self.py_get_attr(obj, method_name, line)
            return self.py_call(method, arg_values, line, arg_kinds=arg_kinds, arg_names=arg_names)

    def call(self, decl: FuncDecl, args: Sequence[Value],
             arg_kinds: List[int],
             arg_names: Sequence[Optional[str]],
             line: int) -> Value:
        # Normalize args to positionals.
        args = self.native_args_to_positional(
            args, arg_kinds, arg_names, decl.sig, line)
        return self.add(Call(decl, args, line))

    def native_args_to_positional(self,
                                  args: Sequence[Value],
                                  arg_kinds: List[int],
                                  arg_names: Sequence[Optional[str]],
                                  sig: FuncSignature,
                                  line: int) -> List[Value]:
        """Prepare arguments for a native call.

        Given args/kinds/names and a target signature for a native call, map
        keyword arguments to their appropriate place in the argument list,
        fill in error values for unspecified default arguments,
        package arguments that will go into *args/**kwargs into a tuple/dict,
        and coerce arguments to the appropriate type.
        """

        sig_arg_kinds = [arg.kind for arg in sig.args]
        sig_arg_names = [arg.name for arg in sig.args]
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  sig_arg_kinds,
                                                  sig_arg_names,
                                                  lambda n: AnyType(TypeOfAny.special_form))

        # Flatten out the arguments, loading error values for default
        # arguments, constructing tuples/dicts for star args, and
        # coercing everything to the expected type.
        output_args = []
        for lst, arg in zip(formal_to_actual, sig.args):
            output_arg = None
            if arg.kind == ARG_STAR:
                output_arg = self.primitive_op(new_tuple_op, [args[i] for i in lst], line)
            elif arg.kind == ARG_STAR2:
                dict_entries = [(self.load_static_unicode(cast(str, arg_names[i])), args[i])
                                for i in lst]
                output_arg = self.make_dict(dict_entries, line)
            elif not lst:
                output_arg = self.add(LoadErrorValue(arg.type, is_borrowed=True))
            else:
                output_arg = args[lst[0]]
            output_args.append(self.coerce(output_arg, arg.type, line))

        return output_args

    def make_dict(self, key_value_pairs: Sequence[DictEntry], line: int) -> Value:
        result = None  # type: Union[Value, None]
        initial_items = []  # type: List[Value]
        for key, value in key_value_pairs:
            if key is not None:
                # key:value
                if result is None:
                    initial_items.extend((key, value))
                    continue

                self.translate_special_method_call(
                    result,
                    '__setitem__',
                    [key, value],
                    result_type=None,
                    line=line)
            else:
                # **value
                if result is None:
                    result = self.primitive_op(new_dict_op, initial_items, line)

                self.primitive_op(
                    dict_update_in_display_op,
                    [result, value],
                    line=line
                )

        if result is None:
            result = self.primitive_op(new_dict_op, initial_items, line)

        return result

    # Loading stuff
    def literal_static_name(self, value: Union[int, float, complex, str, bytes]) -> str:
        return self.mapper.literal_static_name(self.current_module, value)

    def load_static_int(self, value: int) -> Value:
        """Loads a static integer Python 'int' object into a register."""
        if abs(value) > MAX_LITERAL_SHORT_INT:
            static_symbol = self.literal_static_name(value)
            return self.add(LoadStatic(int_rprimitive, static_symbol, ann=value))
        else:
            return self.add(LoadInt(value))

    def load_static_float(self, value: float) -> Value:
        """Loads a static float value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(float_rprimitive, static_symbol, ann=value))

    def load_static_bytes(self, value: bytes) -> Value:
        """Loads a static bytes value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_complex(self, value: complex) -> Value:
        """Loads a static complex value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_unicode(self, value: str) -> Value:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(str_rprimitive, static_symbol, ann=value))

    def load_module(self, name: str) -> Value:
        return self.add(LoadStatic(object_rprimitive, name, namespace=NAMESPACE_MODULE))

    def load_native_type_object(self, fullname: str) -> Value:
        module, name = fullname.rsplit('.', 1)
        return self.add(LoadStatic(object_rprimitive, name, module, NAMESPACE_TYPE))

    def matching_primitive_op(self,
                              candidates: List[OpDescription],
                              args: List[Value],
                              line: int,
                              result_type: Optional[RType] = None) -> Optional[Value]:
        # Find the highest-priority primitive op that matches.
        matching = None  # type: Optional[OpDescription]
        for desc in candidates:
            if len(desc.arg_types) != len(args):
                continue
            if all(is_subtype(actual.type, formal)
                   for actual, formal in zip(args, desc.arg_types)):
                if matching:
                    assert matching.priority != desc.priority, 'Ambiguous:\n1) %s\n2) %s' % (
                        matching, desc)
                    if desc.priority > matching.priority:
                        matching = desc
                else:
                    matching = desc
        if matching:
            target = self.primitive_op(matching, args, line)
            if result_type and not is_runtime_subtype(target.type, result_type):
                if is_none_rprimitive(result_type):
                    # Special case None return. The actual result may actually be a bool
                    # and so we can't just coerce it.
                    target = self.none()
                else:
                    target = self.coerce(target, result_type, line)
            return target
        return None

    def binary_op(self,
                  lreg: Value,
                  rreg: Value,
                  expr_op: str,
                  line: int) -> Value:
        # Special case == and != when we can resolve the method call statically.
        value = None
        if expr_op in ('==', '!='):
            value = self.translate_eq_cmp(lreg, rreg, expr_op, line)
        if value is not None:
            return value

        ops = binary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg, rreg], line)
        assert target, 'Unsupported binary operation: %s' % expr_op
        return target

    def unary_op(self,
                 lreg: Value,
                 expr_op: str,
                 line: int) -> Value:
        ops = unary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg], line)
        assert target, 'Unsupported unary operation: %s' % expr_op
        return target

    def shortcircuit_helper(self, op: str,
                            expr_type: RType,
                            left: Callable[[], Value],
                            right: Callable[[], Value], line: int) -> Value:
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)
        # left_body takes the value of the left side, right_body the right
        left_body, right_body, next = BasicBlock(), BasicBlock(), BasicBlock()
        # true_body is taken if the left is true, false_body if it is false.
        # For 'and' the value is the right side if the left is true, and for 'or'
        # it is the right side if the left is false.
        true_body, false_body = (
            (right_body, left_body) if op == 'and' else (left_body, right_body))

        left_value = left()
        self.add_bool_branch(left_value, true_body, false_body)

        self.activate_block(left_body)
        left_coerced = self.coerce(left_value, expr_type, line)
        self.add(Assign(target, left_coerced))
        self.goto(next)

        self.activate_block(right_body)
        right_value = right()
        right_coerced = self.coerce(right_value, expr_type, line)
        self.add(Assign(target, right_coerced))
        self.goto(next)

        self.activate_block(next)
        return target

    def add_bool_branch(self, value: Value, true: BasicBlock, false: BasicBlock) -> None:
        if is_runtime_subtype(value.type, int_rprimitive):
            zero = self.add(LoadInt(0))
            value = self.binary_op(value, zero, '!=', value.line)
        elif is_same_type(value.type, list_rprimitive):
            length = self.primitive_op(list_len_op, [value], value.line)
            zero = self.add(LoadInt(0))
            value = self.binary_op(length, zero, '!=', value.line)
        elif (isinstance(value.type, RInstance) and value.type.class_ir.is_ext_class
                and value.type.class_ir.has_method('__bool__')):
            # Directly call the __bool__ method on classes that have it.
            value = self.gen_method_call(value, '__bool__', [], bool_rprimitive, value.line)
        else:
            value_type = optional_value_type(value.type)
            if value_type is not None:
                is_none = self.binary_op(value, self.none_object(), 'is not', value.line)
                branch = Branch(is_none, true, false, Branch.BOOL_EXPR)
                self.add(branch)
                always_truthy = False
                if isinstance(value_type, RInstance):
                    # check whether X.__bool__ is always just the default (object.__bool__)
                    if (not value_type.class_ir.has_method('__bool__')
                            and value_type.class_ir.is_method_final('__bool__')):
                        always_truthy = True

                if not always_truthy:
                    # Optional[X] where X may be falsey and requires a check
                    branch.true = BasicBlock()
                    self.activate_block(branch.true)
                    # unbox_or_cast instead of coerce because we want the
                    # type to change even if it is a subtype.
                    remaining = self.unbox_or_cast(value, value_type, value.line)
                    self.add_bool_branch(remaining, true, false)
                return
            elif not is_same_type(value.type, bool_rprimitive):
                value = self.primitive_op(bool_op, [value], value.line)
        self.add(Branch(value, true, false, Branch.BOOL_EXPR))

    def translate_special_method_call(self,
                                      base_reg: Value,
                                      name: str,
                                      args: List[Value],
                                      result_type: Optional[RType],
                                      line: int) -> Optional[Value]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.

        Return None if no translation found; otherwise return the target register.
        """
        ops = method_ops.get(name, [])
        return self.matching_primitive_op(ops, [base_reg] + args, line, result_type=result_type)

    def translate_eq_cmp(self,
                         lreg: Value,
                         rreg: Value,
                         expr_op: str,
                         line: int) -> Optional[Value]:
        ltype = lreg.type
        rtype = rreg.type
        if not (isinstance(ltype, RInstance) and ltype == rtype):
            return None

        class_ir = ltype.class_ir
        # Check whether any subclasses of the operand redefines __eq__
        # or it might be redefined in a Python parent class or by
        # dataclasses
        cmp_varies_at_runtime = (
            not class_ir.is_method_final('__eq__')
            or not class_ir.is_method_final('__ne__')
            or class_ir.inherits_python
            or class_ir.is_augmented
        )

        if cmp_varies_at_runtime:
            # We might need to call left.__eq__(right) or right.__eq__(left)
            # depending on which is the more specific type.
            return None

        if not class_ir.has_method('__eq__'):
            # There's no __eq__ defined, so just use object identity.
            identity_ref_op = 'is' if expr_op == '==' else 'is not'
            return self.binary_op(lreg, rreg, identity_ref_op, line)

        return self.gen_method_call(
            lreg,
            op_methods[expr_op],
            [rreg],
            ltype,
            line
        )

    def gen_method_call(self,
                        base: Value,
                        name: str,
                        arg_values: List[Value],
                        result_type: Optional[RType],
                        line: int,
                        arg_kinds: Optional[List[int]] = None,
                        arg_names: Optional[List[Optional[str]]] = None) -> Value:
        # If arg_kinds contains values other than arg_pos and arg_named, then fallback to
        # Python method call.
        if (arg_kinds is not None
                and not all(kind in (ARG_POS, ARG_NAMED) for kind in arg_kinds)):
            return self.py_method_call(base, name, arg_values, base.line, arg_kinds, arg_names)

        # If the base type is one of ours, do a MethodCall
        if (isinstance(base.type, RInstance) and base.type.class_ir.is_ext_class
                and not base.type.class_ir.builtin_base):
            if base.type.class_ir.has_method(name):
                decl = base.type.class_ir.method_decl(name)
                if arg_kinds is None:
                    assert arg_names is None, "arg_kinds not present but arg_names is"
                    arg_kinds = [ARG_POS for _ in arg_values]
                    arg_names = [None for _ in arg_values]
                else:
                    assert arg_names is not None, "arg_kinds present but arg_names is not"

                # Normalize args to positionals.
                assert decl.bound_sig
                arg_values = self.native_args_to_positional(
                    arg_values, arg_kinds, arg_names, decl.bound_sig, line)
                return self.add(MethodCall(base, name, arg_values, line))
            elif base.type.class_ir.has_attr(name):
                function = self.add(GetAttr(base, name, line))
                return self.py_call(function, arg_values, line,
                                    arg_kinds=arg_kinds, arg_names=arg_names)

        elif isinstance(base.type, RUnion):
            return self.union_method_call(base, base.type, name, arg_values, result_type, line,
                                          arg_kinds, arg_names)

        # Try to do a special-cased method call
        if not arg_kinds or arg_kinds == [ARG_POS] * len(arg_values):
            target = self.translate_special_method_call(base, name, arg_values, result_type, line)
            if target:
                return target

        # Fall back to Python method call
        return self.py_method_call(base, name, arg_values, line, arg_kinds, arg_names)

    def union_method_call(self,
                          base: Value,
                          obj_type: RUnion,
                          name: str,
                          arg_values: List[Value],
                          return_rtype: Optional[RType],
                          line: int,
                          arg_kinds: Optional[List[int]],
                          arg_names: Optional[List[Optional[str]]]) -> Value:
        # Union method call needs a return_rtype for the type of the output register.
        # If we don't have one, use object_rprimitive.
        return_rtype = return_rtype or object_rprimitive

        def call_union_item(value: Value) -> Value:
            return self.gen_method_call(value, name, arg_values, return_rtype, line,
                                        arg_kinds, arg_names)

        return self.decompose_union_helper(base, obj_type, return_rtype, call_union_item, line)
