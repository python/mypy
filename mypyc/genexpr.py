"""Transform mypy expression ASTs to mypyc IR (Intermediate Representation).

The top-level AST transformation logic is implemented in mypyc.genops.
"""

from typing import List, Optional, Union

from mypy.nodes import (
    Expression, NameExpr, MemberExpr, SuperExpr, CallExpr, UnaryExpr, OpExpr, IndexExpr,
    ConditionalExpr, ComparisonExpr, IntExpr, FloatExpr, ComplexExpr, StrExpr,
    BytesExpr, EllipsisExpr, ListExpr, TupleExpr, DictExpr, SetExpr, ListComprehension,
    SetComprehension, DictionaryComprehension, SliceExpr, GeneratorExpr, CastExpr, StarExpr,
    Var, RefExpr, MypyFile, TypeInfo, TypeApplication, LDEF, ARG_POS
)

from mypyc.ops import (
    Value, TupleGet, TupleSet, PrimitiveOp, BasicBlock, RTuple, OpDescription, Assign,
    object_rprimitive, is_none_rprimitive, FUNC_CLASSMETHOD, FUNC_STATICMETHOD
)
from mypyc.ops_primitive import name_ref_ops
from mypyc.ops_misc import new_slice_op, iter_op, ellipsis_op, type_op
from mypyc.ops_list import new_list_op, list_append_op, list_extend_op
from mypyc.ops_tuple import list_tuple_op
from mypyc.ops_dict import new_dict_op, dict_set_item_op
from mypyc.ops_set import new_set_op, set_add_op, set_update_op
from mypyc.specialize import specializers
from mypyc.genops import IRBuilder


class BuildExpressionIR:
    def __init__(self, builder: IRBuilder) -> None:
        self.builder = builder

    # Name and attribute references

    def visit_name_expr(self, expr: NameExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            return self.builder.add(PrimitiveOp([], desc, expr.line))

        if isinstance(expr.node, Var) and expr.node.is_final:
            value = self.builder.emit_load_final(
                expr.node,
                fullname,
                expr.name,
                self.builder.is_native_ref_expr(expr),
                self.builder.types[expr],
                expr.line,
            )
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.builder.imports:
            return self.builder.load_module(expr.node.fullname)

        # If the expression is locally defined, then read the result from the corresponding
        # assignment target and return it. Otherwise if the expression is a global, load it from
        # the globals dictionary.
        # Except for imports, that currently always happens in the global namespace.
        if expr.kind == LDEF and not (isinstance(expr.node, Var)
                                      and expr.node.is_suppressed_import):
            # Try to detect and error when we hit the irritating mypy bug
            # where a local variable is cast to None. (#5423)
            if (isinstance(expr.node, Var) and is_none_rprimitive(self.builder.node_type(expr))
                    and expr.node.is_inferred):
                self.builder.error(
                    "Local variable '{}' has inferred type None; add an annotation".format(
                        expr.node.name),
                    expr.node.line)

            # TODO: Behavior currently only defined for Var and FuncDef node types.
            return self.builder.read(self.builder.get_assignment_target(expr), expr.line)

        return self.builder.load_global(expr)

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        # First check if this is maybe a final attribute.
        final = self.builder.get_final_ref(expr)
        if final is not None:
            fullname, final_var, native = final
            value = self.builder.emit_load_final(final_var, fullname, final_var.name, native,
                                         self.builder.types[expr], expr.line)
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.builder.imports:
            return self.builder.load_module(expr.node.fullname)

        obj = self.builder.accept(expr.expr)
        return self.builder.builder.get_attr(
            obj, expr.name, self.builder.node_type(expr), expr.line
        )

    def visit_super_expr(self, o: SuperExpr) -> Value:
        # self.warning('can not optimize super() expression', o.line)
        sup_val = self.builder.load_module_attr_by_fullname('builtins.super', o.line)
        if o.call.args:
            args = [self.builder.accept(arg) for arg in o.call.args]
        else:
            assert o.info is not None
            typ = self.builder.load_native_type_object(o.info.fullname)
            ir = self.builder.mapper.type_to_ir[o.info]
            iter_env = iter(self.builder.environment.indexes)
            vself = next(iter_env)  # grab first argument
            if self.builder.fn_info.is_generator:
                # grab sixth argument (see comment in translate_super_method_call)
                self_targ = list(self.builder.environment.symtable.values())[6]
                vself = self.builder.read(self_targ, self.builder.fn_info.fitem.line)
            elif not ir.is_ext_class:
                vself = next(iter_env)  # second argument is self if non_extension class
            args = [typ, vself]
        res = self.builder.py_call(sup_val, args, o.line)
        return self.builder.py_get_attr(res, o.name, o.line)

    # Calls

    def visit_call_expr(self, expr: CallExpr) -> Value:
        if isinstance(expr.analyzed, CastExpr):
            return self.translate_cast_expr(expr.analyzed)

        callee = expr.callee
        if isinstance(callee, IndexExpr) and isinstance(callee.analyzed, TypeApplication):
            callee = callee.analyzed.expr  # Unwrap type application

        if isinstance(callee, MemberExpr):
            return self.translate_method_call(expr, callee)
        elif isinstance(callee, SuperExpr):
            return self.translate_super_method_call(expr, callee)
        else:
            return self.translate_call(expr, callee)

    def translate_call(self, expr: CallExpr, callee: Expression) -> Value:
        # The common case of calls is refexprs
        if isinstance(callee, RefExpr):
            return self.translate_refexpr_call(expr, callee)

        function = self.builder.accept(callee)
        args = [self.builder.accept(arg) for arg in expr.args]
        return self.builder.py_call(function, args, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def translate_refexpr_call(self, expr: CallExpr, callee: RefExpr) -> Value:
        """Translate a non-method call."""

        # TODO: Allow special cases to have default args or named args. Currently they don't since
        # they check that everything in arg_kinds is ARG_POS.

        # If there is a specializer for this function, try calling it.
        if callee.fullname and (callee.fullname, None) in specializers:
            val = specializers[callee.fullname, None](self.builder, expr, callee)
            if val is not None:
                return val

        # Gen the argument values
        arg_values = [self.builder.accept(arg) for arg in expr.args]

        return self.builder.call_refexpr_with_args(expr, callee, arg_values)

    def translate_method_call(self, expr: CallExpr, callee: MemberExpr) -> Value:
        """Generate IR for an arbitrary call of form e.m(...).

        This can also deal with calls to module-level functions.
        """
        if self.builder.is_native_ref_expr(callee):
            # Call to module-level native function or such
            return self.translate_call(expr, callee)
        elif (
            isinstance(callee.expr, RefExpr)
            and isinstance(callee.expr.node, TypeInfo)
            and callee.expr.node in self.builder.mapper.type_to_ir
            and self.builder.mapper.type_to_ir[callee.expr.node].has_method(callee.name)
        ):
            # Call a method via the *class*
            assert isinstance(callee.expr.node, TypeInfo)
            ir = self.builder.mapper.type_to_ir[callee.expr.node]
            decl = ir.method_decl(callee.name)
            args = []
            arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]
            # Add the class argument for class methods in extension classes
            if decl.kind == FUNC_CLASSMETHOD and ir.is_ext_class:
                args.append(self.builder.load_native_type_object(callee.expr.node.fullname))
                arg_kinds.insert(0, ARG_POS)
                arg_names.insert(0, None)
            args += [self.builder.accept(arg) for arg in expr.args]

            if ir.is_ext_class:
                return self.builder.builder.call(decl, args, arg_kinds, arg_names, expr.line)
            else:
                obj = self.builder.accept(callee.expr)
                return self.builder.gen_method_call(obj,
                                            callee.name,
                                            args,
                                            self.builder.node_type(expr),
                                            expr.line,
                                            expr.arg_kinds,
                                            expr.arg_names)

        elif self.builder.is_module_member_expr(callee):
            # Fall back to a PyCall for non-native module calls
            function = self.builder.accept(callee)
            args = [self.builder.accept(arg) for arg in expr.args]
            return self.builder.py_call(function, args, expr.line,
                                arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)
        else:
            receiver_typ = self.builder.node_type(callee.expr)

            # If there is a specializer for this method name/type, try calling it.
            if (callee.name, receiver_typ) in specializers:
                val = specializers[callee.name, receiver_typ](self.builder, expr, callee)
                if val is not None:
                    return val

            obj = self.builder.accept(callee.expr)
            args = [self.builder.accept(arg) for arg in expr.args]
            return self.builder.gen_method_call(obj,
                                        callee.name,
                                        args,
                                        self.builder.node_type(expr),
                                        expr.line,
                                        expr.arg_kinds,
                                        expr.arg_names)

    def translate_super_method_call(self, expr: CallExpr, callee: SuperExpr) -> Value:
        if callee.info is None or callee.call.args:
            return self.translate_call(expr, callee)
        ir = self.builder.mapper.type_to_ir[callee.info]
        # Search for the method in the mro, skipping ourselves.
        for base in ir.mro[1:]:
            if callee.name in base.method_decls:
                break
        else:
            return self.translate_call(expr, callee)

        decl = base.method_decl(callee.name)
        arg_values = [self.builder.accept(arg) for arg in expr.args]
        arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]

        if decl.kind != FUNC_STATICMETHOD:
            vself = next(iter(self.builder.environment.indexes))  # grab first argument
            if decl.kind == FUNC_CLASSMETHOD:
                vself = self.builder.primitive_op(type_op, [vself], expr.line)
            elif self.builder.fn_info.is_generator:
                # For generator classes, the self target is the 6th value
                # in the symbol table (which is an ordered dict). This is sort
                # of ugly, but we can't search by name since the 'self' parameter
                # could be named anything, and it doesn't get added to the
                # environment indexes.
                self_targ = list(self.builder.environment.symtable.values())[6]
                vself = self.builder.read(self_targ, self.builder.fn_info.fitem.line)
            arg_values.insert(0, vself)
            arg_kinds.insert(0, ARG_POS)
            arg_names.insert(0, None)

        return self.builder.builder.call(decl, arg_values, arg_kinds, arg_names, expr.line)

    def translate_cast_expr(self, expr: CastExpr) -> Value:
        src = self.builder.accept(expr.expr)
        target_type = self.builder.type_to_rtype(expr.type)
        return self.builder.coerce(src, target_type, expr.line)

    # Operators

    def visit_unary_expr(self, expr: UnaryExpr) -> Value:
        return self.builder.unary_op(self.builder.accept(expr.expr), expr.op, expr.line)

    def visit_op_expr(self, expr: OpExpr) -> Value:
        if expr.op in ('and', 'or'):
            return self.builder.shortcircuit_expr(expr)
        return self.builder.binary_op(
            self.builder.accept(expr.left), self.builder.accept(expr.right), expr.op, expr.line
        )

    def visit_index_expr(self, expr: IndexExpr) -> Value:
        base = self.builder.accept(expr.base)

        if isinstance(base.type, RTuple) and isinstance(expr.index, IntExpr):
            return self.builder.add(TupleGet(base, expr.index.value, expr.line))

        index_reg = self.builder.accept(expr.index)
        return self.builder.gen_method_call(
            base, '__getitem__', [index_reg], self.builder.node_type(expr), expr.line)

    def visit_conditional_expr(self, expr: ConditionalExpr) -> Value:
        if_body, else_body, next = BasicBlock(), BasicBlock(), BasicBlock()

        self.builder.process_conditional(expr.cond, if_body, else_body)
        expr_type = self.builder.node_type(expr)
        # Having actual Phi nodes would be really nice here!
        target = self.builder.alloc_temp(expr_type)

        self.builder.activate_block(if_body)
        true_value = self.builder.accept(expr.if_expr)
        true_value = self.builder.coerce(true_value, expr_type, expr.line)
        self.builder.add(Assign(target, true_value))
        self.builder.goto(next)

        self.builder.activate_block(else_body)
        false_value = self.builder.accept(expr.else_expr)
        false_value = self.builder.coerce(false_value, expr_type, expr.line)
        self.builder.add(Assign(target, false_value))
        self.builder.goto(next)

        self.builder.activate_block(next)

        return target

    def visit_comparison_expr(self, e: ComparisonExpr) -> Value:
        # TODO: Don't produce an expression when used in conditional context

        # All of the trickiness here is due to support for chained conditionals
        # (`e1 < e2 > e3`, etc). `e1 < e2 > e3` is approximately equivalent to
        # `e1 < e2 and e2 > e3` except that `e2` is only evaluated once.
        expr_type = self.builder.node_type(e)

        # go(i, prev) generates code for `ei opi e{i+1} op{i+1} ... en`,
        # assuming that prev contains the value of `ei`.
        def go(i: int, prev: Value) -> Value:
            if i == len(e.operators) - 1:
                return self.visit_basic_comparison(
                    e.operators[i], prev, self.builder.accept(e.operands[i + 1]), e.line)

            next = self.builder.accept(e.operands[i + 1])
            return self.builder.builder.shortcircuit_helper(
                'and', expr_type,
                lambda: self.visit_basic_comparison(
                    e.operators[i], prev, next, e.line),
                lambda: go(i + 1, next),
                e.line)

        return go(0, self.builder.accept(e.operands[0]))

    def visit_basic_comparison(self, op: str, left: Value, right: Value, line: int) -> Value:
        negate = False
        if op == 'is not':
            op, negate = 'is', True
        elif op == 'not in':
            op, negate = 'in', True

        target = self.builder.binary_op(left, right, op, line)

        if negate:
            target = self.builder.unary_op(target, 'not', line)
        return target

    # Literals

    def visit_int_expr(self, expr: IntExpr) -> Value:
        return self.builder.builder.load_static_int(expr.value)

    def visit_float_expr(self, expr: FloatExpr) -> Value:
        return self.builder.builder.load_static_float(expr.value)

    def visit_complex_expr(self, expr: ComplexExpr) -> Value:
        return self.builder.builder.load_static_complex(expr.value)

    def visit_str_expr(self, expr: StrExpr) -> Value:
        return self.builder.load_static_unicode(expr.value)

    def visit_bytes_expr(self, expr: BytesExpr) -> Value:
        value = bytes(expr.value, 'utf8').decode('unicode-escape').encode('raw-unicode-escape')
        return self.builder.builder.load_static_bytes(value)

    def visit_ellipsis(self, o: EllipsisExpr) -> Value:
        return self.builder.primitive_op(ellipsis_op, [], o.line)

    # Display expressions

    def visit_list_expr(self, expr: ListExpr) -> Value:
        return self._visit_list_display(expr.items, expr.line)

    def _visit_list_display(self, items: List[Expression], line: int) -> Value:
        return self._visit_display(
            items,
            new_list_op,
            list_append_op,
            list_extend_op,
            line
        )

    def visit_tuple_expr(self, expr: TupleExpr) -> Value:
        if any(isinstance(item, StarExpr) for item in expr.items):
            # create a tuple of unknown length
            return self._visit_tuple_display(expr)

        # create a tuple of fixed length (RTuple)
        tuple_type = self.builder.node_type(expr)
        # When handling NamedTuple et. al we might not have proper type info,
        # so make some up if we need it.
        types = (tuple_type.types if isinstance(tuple_type, RTuple)
                 else [object_rprimitive] * len(expr.items))

        items = []
        for item_expr, item_type in zip(expr.items, types):
            reg = self.builder.accept(item_expr)
            items.append(self.builder.coerce(reg, item_type, item_expr.line))
        return self.builder.add(TupleSet(items, expr.line))

    def _visit_tuple_display(self, expr: TupleExpr) -> Value:
        """Create a list, then turn it into a tuple."""
        val_as_list = self._visit_list_display(expr.items, expr.line)
        return self.builder.primitive_op(list_tuple_op, [val_as_list], expr.line)

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        """First accepts all keys and values, then makes a dict out of them."""
        key_value_pairs = []
        for key_expr, value_expr in expr.items:
            key = self.builder.accept(key_expr) if key_expr is not None else None
            value = self.builder.accept(value_expr)
            key_value_pairs.append((key, value))

        return self.builder.builder.make_dict(key_value_pairs, expr.line)

    def visit_set_expr(self, expr: SetExpr) -> Value:
        return self._visit_display(
            expr.items,
            new_set_op,
            set_add_op,
            set_update_op,
            expr.line
        )

    def _visit_display(self,
                       items: List[Expression],
                       constructor_op: OpDescription,
                       append_op: OpDescription,
                       extend_op: OpDescription,
                       line: int
                       ) -> Value:
        accepted_items = []
        for item in items:
            if isinstance(item, StarExpr):
                accepted_items.append((True, self.builder.accept(item.expr)))
            else:
                accepted_items.append((False, self.builder.accept(item)))

        result = None  # type: Union[Value, None]
        initial_items = []
        for starred, value in accepted_items:
            if result is None and not starred and constructor_op.is_var_arg:
                initial_items.append(value)
                continue

            if result is None:
                result = self.builder.primitive_op(constructor_op, initial_items, line)

            self.builder.primitive_op(extend_op if starred else append_op, [result, value], line)

        if result is None:
            result = self.builder.primitive_op(constructor_op, initial_items, line)

        return result

    # Comprehensions

    def visit_list_comprehension(self, o: ListComprehension) -> Value:
        return self.builder.translate_list_comprehension(o.generator)

    def visit_set_comprehension(self, o: SetComprehension) -> Value:
        gen = o.generator
        set_ops = self.builder.primitive_op(new_set_op, [], o.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.builder.accept(gen.left_expr)
            self.builder.primitive_op(set_add_op, [set_ops, e], o.line)

        self.builder.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return set_ops

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> Value:
        d = self.builder.primitive_op(new_dict_op, [], o.line)
        loop_params = list(zip(o.indices, o.sequences, o.condlists))

        def gen_inner_stmts() -> None:
            k = self.builder.accept(o.key)
            v = self.builder.accept(o.value)
            self.builder.primitive_op(dict_set_item_op, [d, k, v], o.line)

        self.builder.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return d

    # Misc

    def visit_slice_expr(self, expr: SliceExpr) -> Value:
        def get_arg(arg: Optional[Expression]) -> Value:
            if arg is None:
                return self.builder.none_object()
            else:
                return self.builder.accept(arg)

        args = [get_arg(expr.begin_index),
                get_arg(expr.end_index),
                get_arg(expr.stride)]
        return self.builder.primitive_op(new_slice_op, args, expr.line)

    def visit_generator_expr(self, o: GeneratorExpr) -> Value:
        self.builder.warning('Treating generator comprehension as list', o.line)
        return self.builder.primitive_op(
            iter_op, [self.builder.translate_list_comprehension(o)], o.line
        )
