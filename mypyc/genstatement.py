from typing import Optional, List, Tuple, Sequence, Callable

from mypy.nodes import (
    Block, ExpressionStmt, ReturnStmt, AssignmentStmt, OperatorAssignmentStmt, IfStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, RaiseStmt, TryStmt, WithStmt, AssertStmt, DelStmt,
    Expression, StrExpr, TempNode, Lvalue
)

from mypyc.ops import (
    Assign, Unreachable, AssignmentTarget, AssignmentTargetRegister, AssignmentTargetIndex,
    AssignmentTargetAttr, AssignmentTargetTuple, PrimitiveOp, RaiseStandardError, LoadErrorValue,
    BasicBlock, TupleGet, Value, Register, Branch, exc_rtuple, NO_TRACEBACK_LINE_NO
)
from mypyc.ops_misc import true_op, false_op, type_op, py_delattr_op
from mypyc.ops_exc import (
    raise_exception_op, reraise_exception_op, error_catch_op, exc_matches_op, restore_exc_info_op,
    get_exc_value_op, keep_propagating_op, get_exc_info_op
)
from mypyc.nonlocalcontrol import (
    ExceptNonlocalControl, FinallyNonlocalControl, TryFinallyNonlocalControl
)
from mypyc.genops import IRBuilder

GenFunc = Callable[[], None]


class BuildStatementIR:
    def __init__(self, builder: IRBuilder) -> None:
        self.builder = builder

    def visit_block(self, block: Block) -> None:
        if not block.is_unreachable:
            for stmt in block.body:
                self.builder.accept(stmt)
        # Raise a RuntimeError if we hit a non-empty unreachable block.
        # Don't complain about empty unreachable blocks, since mypy inserts
        # those after `if MYPY`.
        elif block.body:
            self.builder.add(RaiseStandardError(RaiseStandardError.RUNTIME_ERROR,
                                        'Reached allegedly unreachable code!',
                                        block.line))
            self.builder.add(Unreachable())

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> None:
        if isinstance(stmt.expr, StrExpr):
            # Docstring. Ignore
            return
        # ExpressionStmts do not need to be coerced like other Expressions.
        stmt.expr.accept(self.builder.visitor)

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        if stmt.expr:
            retval = self.builder.accept(stmt.expr)
        else:
            retval = self.builder.builder.none()
        retval = self.builder.coerce(retval, self.builder.ret_types[-1], stmt.line)
        self.builder.nonlocal_control[-1].gen_return(self.builder, retval, stmt.line)

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        assert len(stmt.lvalues) >= 1
        self.builder.disallow_class_assignments(stmt.lvalues, stmt.line)
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.builder.get_assignment_target(lvalue, stmt.line)
            return

        line = stmt.rvalue.line
        rvalue_reg = self.builder.accept(stmt.rvalue)
        if self.builder.non_function_scope() and stmt.is_final_def:
            self.builder.init_final_static(lvalue, rvalue_reg)
        for lvalue in stmt.lvalues:
            target = self.builder.get_assignment_target(lvalue)
            self.builder.assign(target, rvalue_reg, line)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> None:
        """Operator assignment statement such as x += 1"""
        self.builder.disallow_class_assignments([stmt.lvalue], stmt.line)
        target = self.builder.get_assignment_target(stmt.lvalue)
        target_value = self.builder.read(target, stmt.line)
        rreg = self.builder.accept(stmt.rvalue)
        # the Python parser strips the '=' from operator assignment statements, so re-add it
        op = stmt.op + '='
        res = self.builder.binary_op(target_value, rreg, op, stmt.line)
        # usually operator assignments are done in-place
        # but when target doesn't support that we need to manually assign
        self.builder.assign(target, res, res.line)

    def visit_if_stmt(self, stmt: IfStmt) -> None:
        if_body, next = BasicBlock(), BasicBlock()
        else_body = BasicBlock() if stmt.else_body else next

        # If statements are normalized
        assert len(stmt.expr) == 1

        self.builder.process_conditional(stmt.expr[0], if_body, else_body)
        self.builder.activate_block(if_body)
        self.builder.accept(stmt.body[0])
        self.builder.goto(next)
        if stmt.else_body:
            self.builder.activate_block(else_body)
            self.builder.accept(stmt.else_body)
            self.builder.goto(next)
        self.builder.activate_block(next)

    def visit_while_stmt(self, s: WhileStmt) -> None:
        body, next, top, else_block = BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock()
        normal_loop_exit = else_block if s.else_body is not None else next

        self.builder.push_loop_stack(top, next)

        # Split block so that we get a handle to the top of the loop.
        self.builder.goto_and_activate(top)
        self.builder.process_conditional(s.expr, body, normal_loop_exit)

        self.builder.activate_block(body)
        self.builder.accept(s.body)
        # Add branch to the top at the end of the body.
        self.builder.goto(top)

        self.builder.pop_loop_stack()

        if s.else_body is not None:
            self.builder.activate_block(else_block)
            self.builder.accept(s.else_body)
            self.builder.goto(next)

        self.builder.activate_block(next)

    def visit_for_stmt(self, s: ForStmt) -> None:
        def body() -> None:
            self.builder.accept(s.body)

        def else_block() -> None:
            assert s.else_body is not None
            self.builder.accept(s.else_body)

        self.builder.for_loop_helper(s.index, s.expr, body,
                             else_block if s.else_body else None, s.line)

    def visit_break_stmt(self, node: BreakStmt) -> None:
        self.builder.nonlocal_control[-1].gen_break(self.builder, node.line)

    def visit_continue_stmt(self, node: ContinueStmt) -> None:
        self.builder.nonlocal_control[-1].gen_continue(self.builder, node.line)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        if s.expr is None:
            self.builder.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.builder.add(Unreachable())
            return

        exc = self.builder.accept(s.expr)
        self.builder.primitive_op(raise_exception_op, [exc], s.line)
        self.builder.add(Unreachable())

    def visit_try_except(self,
                         body: GenFunc,
                         handlers: Sequence[
                             Tuple[Optional[Expression], Optional[Expression], GenFunc]],
                         else_body: Optional[GenFunc],
                         line: int) -> None:
        """Generalized try/except/else handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        assert handlers, "try needs except"

        except_entry, exit_block, cleanup_block = BasicBlock(), BasicBlock(), BasicBlock()
        double_except_block = BasicBlock()
        # If there is an else block, jump there after the try, otherwise just leave
        else_block = BasicBlock() if else_body else exit_block

        # Compile the try block with an error handler
        self.builder.builder.push_error_handler(except_entry)
        self.builder.goto_and_activate(BasicBlock())
        body()
        self.builder.goto(else_block)
        self.builder.builder.pop_error_handler()

        # The error handler catches the error and then checks it
        # against the except clauses. We compile the error handler
        # itself with an error handler so that it can properly restore
        # the *old* exc_info if an exception occurs.
        # The exception chaining will be done automatically when the
        # exception is raised, based on the exception in exc_info.
        self.builder.builder.push_error_handler(double_except_block)
        self.builder.activate_block(except_entry)
        old_exc = self.builder.maybe_spill(self.builder.primitive_op(error_catch_op, [], line))
        # Compile the except blocks with the nonlocal control flow overridden to clear exc_info
        self.builder.nonlocal_control.append(
            ExceptNonlocalControl(self.builder.nonlocal_control[-1], old_exc))

        # Process the bodies
        for type, var, handler_body in handlers:
            next_block = None
            if type:
                next_block, body_block = BasicBlock(), BasicBlock()
                matches = self.builder.primitive_op(
                    exc_matches_op, [self.builder.accept(type)], type.line
                )
                self.builder.add(Branch(matches, body_block, next_block, Branch.BOOL_EXPR))
                self.builder.activate_block(body_block)
            if var:
                target = self.builder.get_assignment_target(var)
                self.builder.assign(
                    target,
                    self.builder.primitive_op(get_exc_value_op, [], var.line),
                    var.line
                )
            handler_body()
            self.builder.goto(cleanup_block)
            if next_block:
                self.builder.activate_block(next_block)

        # Reraise the exception if needed
        if next_block:
            self.builder.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.builder.add(Unreachable())

        self.builder.nonlocal_control.pop()
        self.builder.builder.pop_error_handler()

        # Cleanup for if we leave except through normal control flow:
        # restore the saved exc_info information and continue propagating
        # the exception if it exists.
        self.builder.activate_block(cleanup_block)
        self.builder.primitive_op(restore_exc_info_op, [self.builder.read(old_exc)], line)
        self.builder.goto(exit_block)

        # Cleanup for if we leave except through a raised exception:
        # restore the saved exc_info information and continue propagating
        # the exception.
        self.builder.activate_block(double_except_block)
        self.builder.primitive_op(restore_exc_info_op, [self.builder.read(old_exc)], line)
        self.builder.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.builder.add(Unreachable())

        # If present, compile the else body in the obvious way
        if else_body:
            self.builder.activate_block(else_block)
            else_body()
            self.builder.goto(exit_block)

        self.builder.activate_block(exit_block)

    def visit_try_except_stmt(self, t: TryStmt) -> None:
        def body() -> None:
            self.builder.accept(t.body)

        # Work around scoping woes
        def make_handler(body: Block) -> GenFunc:
            return lambda: self.builder.accept(body)

        handlers = [(type, var, make_handler(body)) for type, var, body in
                    zip(t.types, t.vars, t.handlers)]
        else_body = (lambda: self.builder.accept(t.else_body)) if t.else_body else None
        self.visit_try_except(body, handlers, else_body, t.line)

    def try_finally_try(self, err_handler: BasicBlock, return_entry: BasicBlock,
                        main_entry: BasicBlock, try_body: GenFunc) -> Optional[Register]:
        # Compile the try block with an error handler
        control = TryFinallyNonlocalControl(return_entry)
        self.builder.builder.push_error_handler(err_handler)

        self.builder.nonlocal_control.append(control)
        self.builder.goto_and_activate(BasicBlock())
        try_body()
        self.builder.goto(main_entry)
        self.builder.nonlocal_control.pop()
        self.builder.builder.pop_error_handler()

        return control.ret_reg

    def try_finally_entry_blocks(self,
                                 err_handler: BasicBlock, return_entry: BasicBlock,
                                 main_entry: BasicBlock, finally_block: BasicBlock,
                                 ret_reg: Optional[Register]) -> Value:
        old_exc = self.builder.alloc_temp(exc_rtuple)

        # Entry block for non-exceptional flow
        self.builder.activate_block(main_entry)
        if ret_reg:
            self.builder.add(
                Assign(
                    ret_reg,
                    self.builder.add(LoadErrorValue(self.builder.ret_types[-1]))
                )
            )
        self.builder.goto(return_entry)

        self.builder.activate_block(return_entry)
        self.builder.add(Assign(old_exc, self.builder.add(LoadErrorValue(exc_rtuple))))
        self.builder.goto(finally_block)

        # Entry block for errors
        self.builder.activate_block(err_handler)
        if ret_reg:
            self.builder.add(
                Assign(
                    ret_reg,
                    self.builder.add(LoadErrorValue(self.builder.ret_types[-1]))
                )
            )
        self.builder.add(Assign(old_exc, self.builder.primitive_op(error_catch_op, [], -1)))
        self.builder.goto(finally_block)

        return old_exc

    def try_finally_body(
            self, finally_block: BasicBlock, finally_body: GenFunc,
            ret_reg: Optional[Value], old_exc: Value) -> Tuple[BasicBlock,
                                                               'FinallyNonlocalControl']:
        cleanup_block = BasicBlock()
        # Compile the finally block with the nonlocal control flow overridden to restore exc_info
        self.builder.builder.push_error_handler(cleanup_block)
        finally_control = FinallyNonlocalControl(
            self.builder.nonlocal_control[-1], ret_reg, old_exc)
        self.builder.nonlocal_control.append(finally_control)
        self.builder.activate_block(finally_block)
        finally_body()
        self.builder.nonlocal_control.pop()

        return cleanup_block, finally_control

    def try_finally_resolve_control(self, cleanup_block: BasicBlock,
                                    finally_control: FinallyNonlocalControl,
                                    old_exc: Value, ret_reg: Optional[Value]) -> BasicBlock:
        """Resolve the control flow out of a finally block.

        This means returning if there was a return, propagating
        exceptions, break/continue (soon), or just continuing on.
        """
        reraise, rest = BasicBlock(), BasicBlock()
        self.builder.add(Branch(old_exc, rest, reraise, Branch.IS_ERROR))

        # Reraise the exception if there was one
        self.builder.activate_block(reraise)
        self.builder.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
        self.builder.add(Unreachable())
        self.builder.builder.pop_error_handler()

        # If there was a return, keep returning
        if ret_reg:
            self.builder.activate_block(rest)
            return_block, rest = BasicBlock(), BasicBlock()
            self.builder.add(Branch(ret_reg, rest, return_block, Branch.IS_ERROR))

            self.builder.activate_block(return_block)
            self.builder.nonlocal_control[-1].gen_return(self.builder, ret_reg, -1)

        # TODO: handle break/continue
        self.builder.activate_block(rest)
        out_block = BasicBlock()
        self.builder.goto(out_block)

        # If there was an exception, restore again
        self.builder.activate_block(cleanup_block)
        finally_control.gen_cleanup(self.builder, -1)
        self.builder.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.builder.add(Unreachable())

        return out_block

    def visit_try_finally_stmt(self, try_body: GenFunc, finally_body: GenFunc) -> None:
        """Generalized try/finally handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        # Finally is a big pain, because there are so many ways that
        # exits can occur. We emit 10+ basic blocks for every finally!

        err_handler, main_entry, return_entry, finally_block = (
            BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock())

        # Compile the body of the try
        ret_reg = self.try_finally_try(
            err_handler, return_entry, main_entry, try_body)

        # Set up the entry blocks for the finally statement
        old_exc = self.try_finally_entry_blocks(
            err_handler, return_entry, main_entry, finally_block, ret_reg)

        # Compile the body of the finally
        cleanup_block, finally_control = self.try_finally_body(
            finally_block, finally_body, ret_reg, old_exc)

        # Resolve the control flow out of the finally block
        out_block = self.try_finally_resolve_control(
            cleanup_block, finally_control, old_exc, ret_reg)

        self.builder.activate_block(out_block)

    def visit_try_stmt(self, t: TryStmt) -> None:
        # Our compilation strategy for try/except/else/finally is to
        # treat try/except/else and try/finally as separate language
        # constructs that we compile separately. When we have a
        # try/except/else/finally, we treat the try/except/else as the
        # body of a try/finally block.
        if t.finally_body:
            def visit_try_body() -> None:
                if t.handlers:
                    self.visit_try_except_stmt(t)
                else:
                    self.builder.accept(t.body)
            body = t.finally_body

            self.visit_try_finally_stmt(visit_try_body, lambda: self.builder.accept(body))
        else:
            self.visit_try_except_stmt(t)

    def get_sys_exc_info(self) -> List[Value]:
        exc_info = self.builder.primitive_op(get_exc_info_op, [], -1)
        return [self.builder.add(TupleGet(exc_info, i, -1)) for i in range(3)]

    def visit_with(self, expr: Expression, target: Optional[Lvalue],
                   body: GenFunc, line: int) -> None:

        # This is basically a straight transcription of the Python code in PEP 343.
        # I don't actually understand why a bunch of it is the way it is.
        # We could probably optimize the case where the manager is compiled by us,
        # but that is not our common case at all, so.
        mgr_v = self.builder.accept(expr)
        typ = self.builder.primitive_op(type_op, [mgr_v], line)
        exit_ = self.builder.maybe_spill(self.builder.py_get_attr(typ, '__exit__', line))
        value = self.builder.py_call(
            self.builder.py_get_attr(typ, '__enter__', line), [mgr_v], line
        )
        mgr = self.builder.maybe_spill(mgr_v)
        exc = self.builder.maybe_spill_assignable(self.builder.primitive_op(true_op, [], -1))

        def try_body() -> None:
            if target:
                self.builder.assign(self.builder.get_assignment_target(target), value, line)
            body()

        def except_body() -> None:
            self.builder.assign(exc, self.builder.primitive_op(false_op, [], -1), line)
            out_block, reraise_block = BasicBlock(), BasicBlock()
            self.builder.add_bool_branch(
                self.builder.py_call(self.builder.read(exit_),
                                     [self.builder.read(mgr)] + self.get_sys_exc_info(), line),
                out_block,
                reraise_block
            )
            self.builder.activate_block(reraise_block)
            self.builder.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.builder.add(Unreachable())
            self.builder.activate_block(out_block)

        def finally_body() -> None:
            out_block, exit_block = BasicBlock(), BasicBlock()
            self.builder.add(
                Branch(self.builder.read(exc), exit_block, out_block, Branch.BOOL_EXPR)
            )
            self.builder.activate_block(exit_block)
            none = self.builder.none_object()
            self.builder.py_call(
                self.builder.read(exit_), [self.builder.read(mgr), none, none, none], line
            )
            self.builder.goto_and_activate(out_block)

        self.visit_try_finally_stmt(
            lambda: self.visit_try_except(try_body, [(None, None, except_body)], None, line),
            finally_body)

    def visit_with_stmt(self, o: WithStmt) -> None:
        # Generate separate logic for each expr in it, left to right
        def generate(i: int) -> None:
            if i >= len(o.expr):
                self.builder.accept(o.body)
            else:
                self.visit_with(o.expr[i], o.target[i], lambda: generate(i + 1), o.line)

        generate(0)

    def visit_assert_stmt(self, a: AssertStmt) -> None:
        if self.builder.options.strip_asserts:
            return
        cond = self.builder.accept(a.expr)
        ok_block, error_block = BasicBlock(), BasicBlock()
        self.builder.add_bool_branch(cond, ok_block, error_block)
        self.builder.activate_block(error_block)
        if a.msg is None:
            # Special case (for simpler generated code)
            self.builder.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, None, a.line))
        elif isinstance(a.msg, StrExpr):
            # Another special case
            self.builder.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, a.msg.value,
                                        a.line))
        else:
            # The general case -- explicitly construct an exception instance
            message = self.builder.accept(a.msg)
            exc_type = self.builder.load_module_attr_by_fullname('builtins.AssertionError', a.line)
            exc = self.builder.py_call(exc_type, [message], a.line)
            self.builder.primitive_op(raise_exception_op, [exc], a.line)
        self.builder.add(Unreachable())
        self.builder.activate_block(ok_block)

    def visit_del_stmt(self, o: DelStmt) -> None:
        self.visit_del_item(self.builder.get_assignment_target(o.expr), o.line)

    def visit_del_item(self, target: AssignmentTarget, line: int) -> None:
        if isinstance(target, AssignmentTargetIndex):
            self.builder.gen_method_call(
                target.base,
                '__delitem__',
                [target.index],
                result_type=None,
                line=line
            )
        elif isinstance(target, AssignmentTargetAttr):
            key = self.builder.load_static_unicode(target.attr)
            self.builder.add(PrimitiveOp([target.obj, key], py_delattr_op, line))
        elif isinstance(target, AssignmentTargetRegister):
            # Delete a local by assigning an error value to it, which will
            # prompt the insertion of uninit checks.
            self.builder.add(Assign(target.register,
                            self.builder.add(LoadErrorValue(target.type, undefines=True))))
        elif isinstance(target, AssignmentTargetTuple):
            for subtarget in target.items:
                self.visit_del_item(subtarget, line)
