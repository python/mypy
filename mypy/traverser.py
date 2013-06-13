from mypy.visitor import NodeVisitor
from mypy.nodes import (
    Block, MypyFile, VarDef, FuncItem, CallExpr, TypeDef, Decorator, FuncDef,
    ExpressionStmt, AssignmentStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, ReturnStmt, AssertStmt, YieldStmt, DelStmt, IfStmt, RaiseStmt,
    TryStmt, WithStmt, ParenExpr, MemberExpr, OpExpr, SliceExpr, CastExpr,
    UnaryExpr, ListExpr, TupleExpr, DictExpr, SetExpr, IndexExpr,
    GeneratorExpr, ListComprehension, ConditionalExpr, TypeApplication,
    FuncExpr, OverloadedFuncDef
)


class TraverserVisitor<T>(NodeVisitor<T>):
    """A parse tree visitor that traverses the parse tree during visiting.

    It does not peform any actions outside the travelsal. Subclasses
    should override visit methods to perform actions during
    travelsal. Calling the superclass method allows reusing the
    travelsal implementation.
    """

    # Visit methods
    
    T visit_mypy_file(self, MypyFile o):
        for d in o.defs:
            d.accept(self)

    T visit_block(self, Block block):
        for s in block.body:
            s.accept(self)
    
    T visit_func(self, FuncItem o):
        for i in o.init:
            if i is not None:
                i.accept(self)
        for v in o.args:
            self.visit_var(v)
        o.body.accept(self)
    
    T visit_func_def(self, FuncDef o):
        self.visit_func(o)

    T visit_overloaded_func_def(self, OverloadedFuncDef o):
        for item in o.items:
            item.accept(self)
    
    T visit_type_def(self, TypeDef o):
        o.defs.accept(self)
    
    T visit_decorator(self, Decorator o):
        o.func.accept(self)
        o.var.accept(self)
        for decorator in o.decorators:
            decorator.accept(self)
    
    T visit_var_def(self, VarDef o):
        if o.init is not None:
            o.init.accept(self)
        for v in o.items:
            self.visit_var(v)
    
    T visit_expression_stmt(self, ExpressionStmt o):
        o.expr.accept(self)
    
    T visit_assignment_stmt(self, AssignmentStmt o):
        o.rvalue.accept(self)
        for l in o.lvalues:
            l.accept(self)
    
    T visit_operator_assignment_stmt(self, OperatorAssignmentStmt o):
        o.rvalue.accept(self)
        o.lvalue.accept(self)
    
    T visit_while_stmt(self, WhileStmt o):
        o.expr.accept(self)
        o.body.accept(self)
        if o.else_body:
            o.else_body.accept(self)
    
    T visit_for_stmt(self, ForStmt o):
        for ind in o.index:
            ind.accept(self)
        o.expr.accept(self)
        o.body.accept(self)
        if o.else_body:
            o.else_body.accept(self)
    
    T visit_return_stmt(self, ReturnStmt o):
        if o.expr is not None:
            o.expr.accept(self)
    
    T visit_assert_stmt(self, AssertStmt o):
        if o.expr is not None:
            o.expr.accept(self)
    
    T visit_yield_stmt(self, YieldStmt o):
        if o.expr is not None:
            o.expr.accept(self)
    
    T visit_del_stmt(self, DelStmt o):
        if o.expr is not None:
            o.expr.accept(self)
    
    T visit_if_stmt(self, IfStmt o):
        for e in o.expr:
            e.accept(self)
        for b in o.body:
            b.accept(self)
        if o.else_body:
            o.else_body.accept(self)
    
    T visit_raise_stmt(self, RaiseStmt o):
        if o.expr is not None:
            o.expr.accept(self)
        if o.from_expr is not None:
            o.from_expr.accept(self)
    
    T visit_try_stmt(self, TryStmt o):
        o.body.accept(self)
        for i in range(len(o.types)):
            o.types[i].accept(self)
            o.handlers[i].accept(self)
        if o.else_body is not None:
            o.else_body.accept(self)
        if o.finally_body is not None:
            o.finally_body.accept(self)
    
    T visit_with_stmt(self, WithStmt o):
        for i in range(len(o.expr)):
            o.expr[i].accept(self)
            if o.name[i] is not None:
                o.name[i].accept(self)
        o.body.accept(self)
    
    T visit_paren_expr(self, ParenExpr o):
        o.expr.accept(self)
    
    T visit_member_expr(self, MemberExpr o):
        o.expr.accept(self)
    
    T visit_call_expr(self, CallExpr o):
        for a in o.args:
            a.accept(self)
        o.callee.accept(self)
    
    T visit_op_expr(self, OpExpr o):
        o.left.accept(self)
        o.right.accept(self)
    
    T visit_slice_expr(self, SliceExpr o):
        if o.begin_index is not None:
            o.begin_index.accept(self)
        if o.end_index is not None:
            o.end_index.accept(self)
        if o.stride is not None:
            o.stride.accept(self)
    
    T visit_cast_expr(self, CastExpr o):
        o.expr.accept(self)
    
    T visit_unary_expr(self, UnaryExpr o):
        o.expr.accept(self)
    
    T visit_list_expr(self, ListExpr o):
        for item in o.items:
            item.accept(self)
    
    T visit_tuple_expr(self, TupleExpr o):
        for item in o.items:
            item.accept(self)
    
    T visit_dict_expr(self, DictExpr o):
        for k, v in o.items:
            k.accept(self)
            v.accept(self)
    
    T visit_set_expr(self, SetExpr o):
        for item in o.items:
            item.accept(self)
    
    T visit_index_expr(self, IndexExpr o):
        o.base.accept(self)
        o.index.accept(self)
    
    T visit_generator_expr(self, GeneratorExpr o):
        o.left_expr.accept(self)
        o.right_expr.accept(self)
        if o.condition is not None:
            o.condition.accept(self)
        for index in o.index:
            index.accept(self)
    
    T visit_list_comprehension(self, ListComprehension o):
        o.generator.accept(self)
    
    T visit_conditional_expr(self, ConditionalExpr o):
        o.cond.accept(self)
        o.if_expr.accept(self)
        o.else_expr.accept(self)
    
    T visit_type_application(self, TypeApplication o):
        o.expr.accept(self)
    
    T visit_func_expr(self, FuncExpr o):
        self.visit_func(o)
