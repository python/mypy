"""Generic node traverser visitor"""

from mypy.visitor import AbstractNodeVisitor
from mypy.nodes import (
    Block, MypyFile, FuncItem, CallExpr, ClassDef, Decorator, FuncDef,
    ExpressionStmt, AssignmentStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, ReturnStmt, AssertStmt, DelStmt, IfStmt, RaiseStmt,
    TryStmt, WithStmt, MemberExpr, OpExpr, SliceExpr, CastExpr, RevealTypeExpr,
    UnaryExpr, ListExpr, TupleExpr, DictExpr, SetExpr, IndexExpr,
    GeneratorExpr, ListComprehension, ConditionalExpr, TypeApplication,
    LambdaExpr, ComparisonExpr, OverloadedFuncDef, YieldFromExpr,
    YieldExpr, StarExpr, BackquoteExpr, AwaitExpr,
    TempNode, PromoteExpr, NewTypeExpr, TypedDictExpr, EnumCallExpr, NamedTupleExpr,
    TypeAliasExpr, TypeVarExpr, DictionaryComprehension, SetComprehension, SuperExpr,
    NameExpr, EllipsisExpr, ComplexExpr, FloatExpr, UnicodeExpr, BytesExpr, StrExpr,
    IntExpr, ExecStmt, PrintStmt, PassStmt, ContinueStmt, BreakStmt, NonlocalDecl,
    GlobalDecl, ImportAll, Var, ImportFrom, Import,
)


class TraverserVisitor(AbstractNodeVisitor[None]):
    """A parse tree visitor that traverses the parse tree during visiting.

    It does not peform any actions outside the traversal. Subclasses
    should override visit methods to perform actions during
    traversal. Calling the superclass method allows reusing the
    traversal implementation.
    """

    # Visit methods

    def visit_mypy_file(self, o: MypyFile) -> None:
        for d in o.defs:
            d.accept(self)

    def visit_block(self, block: Block) -> None:
        for s in block.body:
            s.accept(self)

    def visit_func(self, o: FuncItem) -> None:
        for arg in o.arguments:
            init = arg.initialization_statement
            if init is not None:
                init.accept(self)

        for arg in o.arguments:
            self.visit_var(arg.variable)

        o.body.accept(self)

    def visit_func_def(self, o: FuncDef) -> None:
        self.visit_func(o)

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> None:
        for item in o.items:
            item.accept(self)
        if o.impl:
            o.impl.accept(self)

    def visit_class_def(self, o: ClassDef) -> None:
        for d in o.decorators:
            d.accept(self)
        for base in o.base_type_exprs:
            base.accept(self)
        o.defs.accept(self)

    def visit_decorator(self, o: Decorator) -> None:
        o.func.accept(self)
        o.var.accept(self)
        for decorator in o.decorators:
            decorator.accept(self)

    def visit_expression_stmt(self, o: ExpressionStmt) -> None:
        o.expr.accept(self)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        o.rvalue.accept(self)
        for l in o.lvalues:
            l.accept(self)

    def visit_operator_assignment_stmt(self, o: OperatorAssignmentStmt) -> None:
        o.rvalue.accept(self)
        o.lvalue.accept(self)

    def visit_while_stmt(self, o: WhileStmt) -> None:
        o.expr.accept(self)
        o.body.accept(self)
        if o.else_body:
            o.else_body.accept(self)

    def visit_for_stmt(self, o: ForStmt) -> None:
        o.index.accept(self)
        o.expr.accept(self)
        o.body.accept(self)
        if o.else_body:
            o.else_body.accept(self)

    def visit_return_stmt(self, o: ReturnStmt) -> None:
        if o.expr is not None:
            o.expr.accept(self)

    def visit_assert_stmt(self, o: AssertStmt) -> None:
        if o.expr is not None:
            o.expr.accept(self)
        if o.msg is not None:
            o.msg.accept(self)

    def visit_del_stmt(self, o: DelStmt) -> None:
        if o.expr is not None:
            o.expr.accept(self)

    def visit_if_stmt(self, o: IfStmt) -> None:
        for e in o.expr:
            e.accept(self)
        for b in o.body:
            b.accept(self)
        if o.else_body:
            o.else_body.accept(self)

    def visit_raise_stmt(self, o: RaiseStmt) -> None:
        if o.expr is not None:
            o.expr.accept(self)
        if o.from_expr is not None:
            o.from_expr.accept(self)

    def visit_try_stmt(self, o: TryStmt) -> None:
        o.body.accept(self)
        for i in range(len(o.types)):
            if o.types[i]:
                o.types[i].accept(self)
            o.handlers[i].accept(self)
        if o.else_body is not None:
            o.else_body.accept(self)
        if o.finally_body is not None:
            o.finally_body.accept(self)

    def visit_with_stmt(self, o: WithStmt) -> None:
        for i in range(len(o.expr)):
            o.expr[i].accept(self)
            if o.target[i] is not None:
                o.target[i].accept(self)
        o.body.accept(self)

    def visit_member_expr(self, o: MemberExpr) -> None:
        o.expr.accept(self)

    def visit_yield_from_expr(self, o: YieldFromExpr) -> None:
        o.expr.accept(self)

    def visit_yield_expr(self, o: YieldExpr) -> None:
        if o.expr:
            o.expr.accept(self)

    def visit_call_expr(self, o: CallExpr) -> None:
        for a in o.args:
            a.accept(self)
        o.callee.accept(self)
        if o.analyzed:
            o.analyzed.accept(self)

    def visit_op_expr(self, o: OpExpr) -> None:
        o.left.accept(self)
        o.right.accept(self)

    def visit_comparison_expr(self, o: ComparisonExpr) -> None:
        for operand in o.operands:
            operand.accept(self)

    def visit_slice_expr(self, o: SliceExpr) -> None:
        if o.begin_index is not None:
            o.begin_index.accept(self)
        if o.end_index is not None:
            o.end_index.accept(self)
        if o.stride is not None:
            o.stride.accept(self)

    def visit_cast_expr(self, o: CastExpr) -> None:
        o.expr.accept(self)

    def visit_reveal_type_expr(self, o: RevealTypeExpr) -> None:
        o.expr.accept(self)

    def visit_unary_expr(self, o: UnaryExpr) -> None:
        o.expr.accept(self)

    def visit_list_expr(self, o: ListExpr) -> None:
        for item in o.items:
            item.accept(self)

    def visit_tuple_expr(self, o: TupleExpr) -> None:
        for item in o.items:
            item.accept(self)

    def visit_dict_expr(self, o: DictExpr) -> None:
        for k, v in o.items:
            if k is not None:
                k.accept(self)
            v.accept(self)

    def visit_set_expr(self, o: SetExpr) -> None:
        for item in o.items:
            item.accept(self)

    def visit_index_expr(self, o: IndexExpr) -> None:
        o.base.accept(self)
        o.index.accept(self)
        if o.analyzed:
            o.analyzed.accept(self)

    def visit_generator_expr(self, o: GeneratorExpr) -> None:
        for index, sequence, conditions in zip(o.indices, o.sequences,
                                               o.condlists):
            sequence.accept(self)
            index.accept(self)
            for cond in conditions:
                cond.accept(self)
        o.left_expr.accept(self)

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> None:
        for index, sequence, conditions in zip(o.indices, o.sequences,
                                               o.condlists):
            sequence.accept(self)
            index.accept(self)
            for cond in conditions:
                cond.accept(self)
        o.key.accept(self)
        o.value.accept(self)

    def visit_list_comprehension(self, o: ListComprehension) -> None:
        o.generator.accept(self)

    def visit_set_comprehension(self, o: SetComprehension) -> None:
        o.generator.accept(self)

    def visit_conditional_expr(self, o: ConditionalExpr) -> None:
        o.cond.accept(self)
        o.if_expr.accept(self)
        o.else_expr.accept(self)

    def visit_type_application(self, o: TypeApplication) -> None:
        o.expr.accept(self)

    def visit_lambda_expr(self, o: LambdaExpr) -> None:
        self.visit_func(o)

    def visit_star_expr(self, o: StarExpr) -> None:
        o.expr.accept(self)

    def visit_backquote_expr(self, o: BackquoteExpr) -> None:
        o.expr.accept(self)

    def visit_await_expr(self, o: AwaitExpr) -> None:
        o.expr.accept(self)

    def visit_import(self, o: Import) -> None:
        for a in o.assignments:
            a.accept(self)

    def visit_import_from(self, o: ImportFrom) -> None:
        for a in o.assignments:
            a.accept(self)

    def visit_print_stmt(self, o: PrintStmt) -> None:
        for arg in o.args:
            arg.accept(self)

    def visit_exec_stmt(self, o: ExecStmt) -> None:
        o.expr.accept(self)

    def visit_import_all(self, o: ImportAll) -> None:
        pass

    def visit_global_decl(self, o: GlobalDecl) -> None:
        pass

    def visit_nonlocal_decl(self, o: NonlocalDecl) -> None:
        pass

    def visit_var(self, o: Var) -> None:
        pass

    def visit_break_stmt(self, o: BreakStmt) -> None:
        pass

    def visit_continue_stmt(self, o: ContinueStmt) -> None:
        pass

    def visit_pass_stmt(self, o: PassStmt) -> None:
        pass

    def visit_int_expr(self, o: IntExpr) -> None:
        pass

    def visit_str_expr(self, o: StrExpr) -> None:
        pass

    def visit_bytes_expr(self, o: BytesExpr) -> None:
        pass

    def visit_unicode_expr(self, o: UnicodeExpr) -> None:
        pass

    def visit_float_expr(self, o: FloatExpr) -> None:
        pass

    def visit_complex_expr(self, o: ComplexExpr) -> None:
        pass

    def visit_ellipsis(self, o: EllipsisExpr) -> None:
        pass

    def visit_name_expr(self, o: NameExpr) -> None:
        pass

    def visit_super_expr(self, o: SuperExpr) -> None:
        pass

    def visit_type_var_expr(self, o: TypeVarExpr) -> None:
        pass

    def visit_type_alias_expr(self, o: TypeAliasExpr) -> None:
        pass

    def visit_namedtuple_expr(self, o: NamedTupleExpr) -> None:
        pass

    def visit_enum_call_expr(self, o: EnumCallExpr) -> None:
        pass

    def visit_typeddict_expr(self, o: TypedDictExpr) -> None:
        pass

    def visit_newtype_expr(self, o: NewTypeExpr) -> None:
        pass

    def visit__promote_expr(self, o: PromoteExpr) -> None:
        pass

    def visit_temp_node(self, o: TempNode) -> None:
        pass
